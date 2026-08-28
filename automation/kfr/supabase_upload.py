"""Upload immutable KFR Partner API JSON snapshots to Supabase."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

from kfr_api import SOURCE_TO_API_NAME, load_payload, validate_payload
from kfr_partner_api_download import previous_business_day


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value.rstrip("/")


class SupabaseRest:
    def __init__(self, url: str, service_role_key: str) -> None:
        self.base_url = f"{url.rstrip('/')}/rest/v1"
        self.headers = {"apikey": service_role_key, "Content-Type": "application/json"}
        if service_role_key.count(".") == 2:
            self.headers["Authorization"] = f"Bearer {service_role_key}"

    def request(self, method: str, path: str, body: Any | None = None, prefer: str | None = None) -> Any:
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(f"{self.base_url}/{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Supabase HTTP {exc.code}: {detail[:1000]}") from exc
        return json.loads(payload) if payload else None


def validate_business_date(source_key: str, rows: list[dict[str, Any]], business_date: date) -> None:
    if not rows:
        raise RuntimeError(f"{source_key}: API response is empty for {business_date}")
    date_field = "trade_day" if source_key != "fund_holdings" else None
    if not date_field:
        return
    expected = business_date.isoformat()
    found = sorted({_normalized_date_value(row.get(date_field)) for row in rows})
    dated = [value for value in found if value]
    if set(dated) != {expected}:
        raise RuntimeError(f"{source_key}: expected {date_field}={expected}, found={found}")


def _normalized_date_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() == "none":
        return ""
    return text[:10]


def upload_payload(client: SupabaseRest, source_key: str, path: Path, business_date: date) -> tuple[int, int, bool]:
    api_payload = load_payload(path)
    rows = validate_payload(source_key, api_payload)
    validate_business_date(source_key, rows, business_date)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    metadata = {key: value for key, value in api_payload.items() if key != "content"}

    query = urllib.parse.urlencode({
        "source_key": f"eq.{source_key}", "business_date": f"eq.{business_date.isoformat()}",
        "select": "id,row_count,sha256", "order": "downloaded_at.desc",
    })
    existing = client.request("GET", f"kfr_source_snapshots?{query}") or []
    duplicate = next((item for item in existing if item["sha256"] == digest), None)
    if duplicate:
        return int(duplicate["id"]), int(duplicate["row_count"]), False

    snapshot = client.request("POST", "kfr_source_snapshots", {
        "source_key": source_key, "business_date": business_date.isoformat(), "file_name": path.name,
        "sha256": digest, "sheet_names": ["content"], "row_count": len(rows),
        "source_format": "kfr_partner_api_json", "response_metadata": metadata,
    }, prefer="return=representation")[0]
    snapshot_id = int(snapshot["id"])
    try:
        payload = [
            {"snapshot_id": snapshot_id, "sheet_name": "content", "row_no": index, "payload": row}
            for index, row in enumerate(rows, start=1)
        ]
        for start in range(0, len(payload), 500):
            client.request("POST", "kfr_source_rows", payload[start : start + 500], prefer="return=minimal")
        for old_snapshot in existing:
            client.request("DELETE", f"kfr_source_snapshots?id=eq.{int(old_snapshot['id'])}")
    except Exception:
        client.request("DELETE", f"kfr_source_snapshots?id=eq.{snapshot_id}")
        raise
    return snapshot_id, len(rows), True


def existing_snapshot_is_valid(
    client: SupabaseRest, source_key: str, business_date: date
) -> tuple[bool, str]:
    query = urllib.parse.urlencode({
        "source_key": f"eq.{source_key}",
        "business_date": f"eq.{business_date.isoformat()}",
        "source_format": "eq.kfr_partner_api_json",
        "select": "id,row_count",
        "order": "downloaded_at.desc",
        "limit": "1",
    })
    snapshots = client.request("GET", f"kfr_source_snapshots?{query}") or []
    if not snapshots:
        return False, "snapshot missing"
    snapshot = snapshots[0]
    expected_count = int(snapshot.get("row_count") or 0)
    if expected_count <= 0:
        return False, f"invalid row_count={expected_count}"

    row_query = urllib.parse.urlencode({
        "snapshot_id": f"eq.{int(snapshot['id'])}",
        "select": "row_no,payload",
        "order": "row_no.desc",
        "limit": "1",
    })
    stored_rows = client.request("GET", f"kfr_source_rows?{row_query}") or []
    if not stored_rows:
        return False, "stored rows missing"
    last_row = stored_rows[0]
    if int(last_row.get("row_no") or 0) != expected_count:
        return False, f"stored rows end at {last_row.get('row_no')}, expected {expected_count}"
    payload = last_row.get("payload")
    if not isinstance(payload, dict):
        return False, "stored payload is not an object"
    validate_payload(source_key, {"content": [payload], "total_elements": 1})
    validate_business_date(source_key, [payload], business_date)
    return True, f"snapshot={snapshot['id']}, rows={expected_count}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default=".")
    parser.add_argument("--business-date", default=previous_business_day().isoformat())
    parser.add_argument(
        "--check-existing",
        action="store_true",
        help="Exit successfully only when all four API snapshots already exist and are valid",
    )
    parser.add_argument(
        "--allow-no-data",
        action="store_true",
        help="Exit successfully when a no-data marker exists for the target KFR date",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir).expanduser().resolve()
    business_date = date.fromisoformat(args.business_date)
    client = SupabaseRest(required_env("SUPABASE_URL"), required_env("SUPABASE_SERVICE_ROLE_KEY"))
    if args.check_existing:
        invalid = 0
        for source_key in SOURCE_TO_API_NAME:
            try:
                valid, detail = existing_snapshot_is_valid(client, source_key, business_date)
            except Exception as exc:
                valid, detail = False, str(exc)
            print(f"{source_key}: {'valid' if valid else 'invalid'}: {detail}")
            invalid += int(not valid)
        if invalid:
            raise SystemExit(1)
        return

    marker = input_dir / f"no_data_{business_date.isoformat()}.json"
    if marker.is_file():
        message = f"KFR has no business data for {business_date}; upload skipped"
        if args.allow_no_data:
            print(message)
            return
        raise RuntimeError(message)
    for source_key, api_name in SOURCE_TO_API_NAME.items():
        path = input_dir / f"{api_name}_{business_date.isoformat()}.json"
        if not path.is_file():
            raise FileNotFoundError(f"Missing KFR API JSON: {path}")
        snapshot_id, row_count, created = upload_payload(client, source_key, path, business_date)
        print(f"{source_key}: snapshot={snapshot_id}, rows={row_count}, {'uploaded' if created else 'already exists'}")


if __name__ == "__main__":
    main()

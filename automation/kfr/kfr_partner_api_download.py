"""Download all Hana Bank partner API datasets for one trade date."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from kfr_api import SOURCE_TO_API_NAME, validate_payload


BASE_URL = "https://apiservice.kfr.co.kr"
ENDPOINTS = {
    "prices": "/v1/hbank/funds/prices",
    "holdings": "/v1/hbank/funds/holdings",
    "trades": "/v1/hbank/funds/trades",
    "mezzanine-portfolio": "/v1/hbank/funds/mezzanine-portfolio",
}
KST = ZoneInfo("Asia/Seoul")


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def request_json(request: urllib.request.Request, timeout: float = 60.0) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw_detail = exc.read()
        detail = raw_detail.decode("utf-8", errors="replace")
        if "�" in detail:
            detail = raw_detail.decode("cp949", errors="replace")
        raise RuntimeError(f"KFR HTTP {exc.code}: {detail[:1000]}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("KFR response is not a JSON object")
    return payload


def issue_token(app_key_id: str, app_key_secret: str) -> str:
    body = json.dumps(
        {"app_key_id": app_key_id, "app_key_secret": app_key_secret}
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL}/v1/auth/token",
        data=body,
        method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    payload = request_json(request)
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Token response did not contain access_token")
    return token


def fetch_dataset(endpoint: str, token: str, trade_day: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({"tradeDay": trade_day})
    request = urllib.request.Request(
        f"{BASE_URL}{endpoint}?{query}",
        method="GET",
        headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
    )
    return request_json(request)


def previous_business_day(today: date | None = None) -> date:
    current = today or datetime.now(KST).date()
    current -= timedelta(days=1)
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current


def credentials(env_file: Path | None) -> tuple[str, str]:
    values = dict(os.environ)
    if env_file:
        values.update(load_env(env_file))
    app_key_id = values.get("KFR_APP_KEY_ID", "").strip()
    app_key_secret = values.get("KFR_APP_KEY_SECRET", "").strip()
    if not app_key_id or not app_key_secret:
        raise RuntimeError("KFR_APP_KEY_ID and KFR_APP_KEY_SECRET are required")
    return app_key_id, app_key_secret


def write_dataset(
    output_dir: Path,
    name: str,
    trade_day: str,
    payload: dict[str, Any],
    *,
    write_csv: bool = False,
) -> tuple[Path, Path | None, int]:
    source_key = next(key for key, api_name in SOURCE_TO_API_NAME.items() if api_name == name)
    content = validate_payload(source_key, payload)

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{name}_{trade_day}"
    json_path = output_dir / f"{stem}.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    csv_path = None
    if write_csv:
        csv_path = output_dir / f"{stem}.csv"
        columns: list[str] = []
        for row in content:
            for column in row:
                if column not in columns:
                    columns.append(column)
        with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
            if columns:
                writer.writeheader()
                writer.writerows(content)
    return json_path, csv_path, len(content)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=previous_business_day().isoformat(), help="Trade date in YYYY-MM-DD format")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--write-csv", action="store_true", help="Also create human-review CSV files")
    args = parser.parse_args()

    date.fromisoformat(args.date)
    app_key_id, app_key_secret = credentials(args.env_file)
    token = issue_token(app_key_id, app_key_secret)
    print("token issued")
    failures = 0
    payloads: dict[str, dict[str, Any]] = {}
    for name, endpoint in ENDPOINTS.items():
        try:
            payloads[name] = fetch_dataset(endpoint, token, args.date)
            validate_payload(next(key for key, api_name in SOURCE_TO_API_NAME.items() if api_name == name), payloads[name])
        except Exception as exc:
            failures += 1
            print(f"{name}: failed: {exc}", file=sys.stderr)
    if failures:
        return 1

    no_data = False
    for name in ("prices", "trades", "mezzanine-portfolio"):
        rows = payloads[name]["content"]
        trade_days = {str(row.get("trade_day") or "")[:10] for row in rows}
        if not rows or trade_days != {args.date}:
            no_data = True
            break
    args.output_dir.mkdir(parents=True, exist_ok=True)
    marker = args.output_dir / f"no_data_{args.date}.json"
    if no_data:
        marker.write_text(
            json.dumps({"trade_day": args.date, "status": "no_business_data"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"no KFR business data for {args.date}; upload skipped")
        return 0
    if marker.exists():
        marker.unlink()
    for name, payload in payloads.items():
        json_path, csv_path, count = write_dataset(
            args.output_dir, name, args.date, payload, write_csv=args.write_csv
        )
        csv_note = f" csv={csv_path.name}" if csv_path else ""
        print(f"{name}: rows={count} json={json_path.name}{csv_note}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)

"""Publish Global Strategy dashboard market data to Supabase.

The deployed dashboard cannot call the user's local Kiwoom API directly.
Instead, browser users write refresh requests to Supabase and this local
receiver processes those requests on the user's PC.

Runtime behavior:
1. Korean listed securities refresh every 20 seconds.
2. US/global/full refreshes run only when a pending DB request exists.
3. The shared snapshot is still written to global/market_data for the
   existing dashboard hydration path.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from global_dashboard_server import KiwoomClient, is_ks_security, normalize_security  # noqa: E402


DEFAULT_SUPABASE_URL = "https://esqakvzvchcunhzjlyry.supabase.co"
GLOBAL_DOMAIN = "global"
MARKET_FILE_KEY = "market_data"
MARKET_FILE_LABEL = "Market data"
REQUEST_TABLE = "global_market_refresh_requests"
QUOTE_TABLE = "global_market_quotes"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} environment variable is required.")
    return value


class SupabaseRest:
    def __init__(self, url: str, secret_key: str) -> None:
        self.url = url.rstrip("/")
        self.base_url = f"{self.url}/rest/v1"
        self.headers = {
            "apikey": secret_key,
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json",
        }

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: Any | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 60.0,
    ) -> bytes:
        payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/{path}",
            data=payload,
            method=method,
            headers={**self.headers, **(headers or {})},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as res:
                return res.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Supabase HTTP {exc.code}: {detail[:1000]}") from exc

    def get_all(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode(params, safe=".,()")
        out: list[dict[str, Any]] = []
        for start in range(0, 1_000_000, 1000):
            page = self.request(
                f"{table}?{query}",
                headers={"Range": f"{start}-{start + 999}"},
            )
            rows = json.loads(page or b"[]")
            out.extend(rows)
            if len(rows) < 1000:
                return out
        raise RuntimeError(f"{table} pagination limit exceeded.")

    def upsert_rows(self, table: str, rows: list[dict[str, Any]], conflict: str) -> None:
        if not rows:
            return
        endpoint = f"{table}?on_conflict={urllib.parse.quote(conflict)}"
        for start in range(0, len(rows), 500):
            self.request(
                endpoint,
                method="POST",
                body=rows[start : start + 500],
                headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            )

    def update_rows(self, table: str, filters: dict[str, str], payload: dict[str, Any]) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode(filters, safe=".,()")
        raw = self.request(
            f"{table}?{query}",
            method="PATCH",
            body=payload,
            headers={"Prefer": "return=representation"},
        )
        return json.loads(raw or b"[]")


def suffix_from_listing(listing: str) -> str:
    text = str(listing or "").upper()
    if any(token in text for token in ("한국", "국내", "KOREA", "KR", "KS", "KOSPI", "KOSDAQ")):
        return "KS Equity"
    if any(token in text for token in ("미국", "US", "USA", "NYSE", "NASDAQ", "AMEX")):
        return "US Equity"
    return ""


def candidate_security(value: Any, listing: str = "") -> str:
    text = normalize_security(str(value or ""))
    if not text:
        return ""
    upper = text.upper()
    if upper.endswith(" US EQUITY") or upper.endswith(" KS EQUITY"):
        return text
    suffix = suffix_from_listing(listing)
    if suffix:
        return f"{text.split()[0].upper()} {suffix}"
    return text.split()[0].upper()


def normalize_security_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    securities: list[str] = []
    for value in values:
        security = candidate_security(value)
        if security:
            securities.append(security)
    return list(dict.fromkeys(securities))


def collect_securities(client: SupabaseRest) -> tuple[list[str], str | None]:
    etf_rows = client.get_all(
        "manual_file_rows",
        {
            "select": "payload,created_by",
            "domain": f"eq.{GLOBAL_DOMAIN}",
            "file_key": "eq.etf_db",
            "order": "row_no.asc",
        },
    )
    emp_rows = client.get_all(
        "manual_file_rows",
        {
            "select": "payload,created_by",
            "domain": f"eq.{GLOBAL_DOMAIN}",
            "file_key": "eq.emp_portfolios",
            "order": "row_no.asc",
        },
    )
    market_rows = client.get_all(
        "manual_file_rows",
        {
            "select": "payload,created_by",
            "domain": f"eq.{GLOBAL_DOMAIN}",
            "file_key": f"eq.{MARKET_FILE_KEY}",
            "order": "row_no.asc",
            "limit": "1",
        },
    )
    created_by = next(
        (
            row.get("created_by")
            for row in [*market_rows, *etf_rows, *emp_rows]
            if row.get("created_by")
        ),
        None,
    )

    securities: list[str] = []
    for row in etf_rows:
        payload = row.get("payload") or {}
        listing = str(payload.get("listing") or "")
        for key in ("ticker", "security", "name"):
            security = candidate_security(payload.get(key), listing)
            if security:
                securities.append(security)
                break
    for row in emp_rows:
        payload = row.get("payload") or {}
        security = candidate_security(payload.get("security") or payload.get("ticker") or payload.get("name"))
        if security:
            securities.append(security)

    return list(dict.fromkeys(securities)), created_by


def load_market_snapshot(client: SupabaseRest) -> tuple[dict[str, Any], str | None]:
    rows = client.get_all(
        "manual_file_rows",
        {
            "select": "payload,created_by",
            "domain": f"eq.{GLOBAL_DOMAIN}",
            "file_key": f"eq.{MARKET_FILE_KEY}",
            "order": "row_no.asc",
            "limit": "1",
        },
    )
    if not rows:
        return {"securities": {}, "errors": {}, "fx": 1, "source": "kiwoom-supabase-receiver"}, None
    return rows[0].get("payload") or {}, rows[0].get("created_by")


def merge_market_snapshot(existing: dict[str, Any], incoming: dict[str, Any], *, label: str) -> dict[str, Any]:
    merged = dict(existing or {})
    merged["securities"] = {
        **((existing or {}).get("securities") or {}),
        **(incoming.get("securities") or {}),
    }
    merged["errors"] = {
        **((existing or {}).get("errors") or {}),
        **(incoming.get("errors") or {}),
    }
    if incoming.get("fx"):
        merged["fx"] = incoming["fx"]
    merged["asOf"] = incoming.get("asOf") or existing.get("asOf") or ""
    merged["publishedAt"] = utc_now()
    merged["source"] = "kiwoom-supabase-receiver"
    merged["lastRefreshType"] = label
    merged["universeCount"] = len(merged.get("securities") or {})
    return merged


def publish_market_snapshot(client: SupabaseRest, market: dict[str, Any], created_by: str | None) -> None:
    record: dict[str, Any] = {
        "domain": GLOBAL_DOMAIN,
        "file_key": MARKET_FILE_KEY,
        "file_label": MARKET_FILE_LABEL,
        "sheet_name": "Data",
        "row_no": 1,
        "payload": market,
        "updated_at": utc_now(),
    }
    if created_by:
        record["created_by"] = created_by
    client.upsert_rows("manual_file_rows", [record], "domain,file_key,sheet_name,row_no")


def publish_quotes(client: SupabaseRest, market: dict[str, Any]) -> None:
    securities = market.get("securities") or {}
    errors = market.get("errors") or {}
    rows: list[dict[str, Any]] = []
    now = utc_now()
    for security, payload in securities.items():
        rows.append({
            "security": security,
            "payload": payload,
            "fx": market.get("fx"),
            "source": market.get("source") or "kiwoom",
            "as_of": market.get("asOf"),
            "updated_at": now,
            "error": None,
        })
    for security, error in errors.items():
        if security in securities:
            continue
        rows.append({
            "security": security,
            "payload": {},
            "fx": market.get("fx"),
            "source": market.get("source") or "kiwoom",
            "as_of": market.get("asOf"),
            "updated_at": now,
            "error": str(error),
        })
    client.upsert_rows(QUOTE_TABLE, rows, "security")


def fetch_and_publish(
    supabase: SupabaseRest,
    kiwoom: KiwoomClient,
    securities: list[str],
    *,
    refresh_type: str,
    created_by: str | None = None,
) -> dict[str, Any]:
    securities = list(dict.fromkeys([candidate_security(item) for item in securities if candidate_security(item)]))
    if not securities:
        raise RuntimeError("No securities to refresh.")
    incoming = kiwoom.fetch_reference(securities)
    incoming["source"] = "kiwoom-supabase-receiver"
    incoming["requestedCount"] = len(securities)
    existing, existing_created_by = load_market_snapshot(supabase)
    market = merge_market_snapshot(existing, incoming, label=refresh_type)
    publish_quotes(supabase, incoming)
    publish_market_snapshot(supabase, market, created_by or existing_created_by)
    return incoming


def claim_pending_request(client: SupabaseRest) -> dict[str, Any] | None:
    rows = client.get_all(
        REQUEST_TABLE,
        {
            "select": "*",
            "status": "eq.pending",
            "order": "priority.desc,requested_at.asc",
            "limit": "1",
        },
    )
    if not rows:
        return None
    request = rows[0]
    claimed = client.update_rows(
        REQUEST_TABLE,
        {"id": f"eq.{request['id']}", "status": "eq.pending"},
        {"status": "processing", "started_at": utc_now(), "error": None},
    )
    return claimed[0] if claimed else None


def complete_request(
    client: SupabaseRest,
    request_id: str,
    *,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    client.update_rows(
        REQUEST_TABLE,
        {"id": f"eq.{request_id}"},
        {
            "status": status,
            "completed_at": utc_now(),
            "result": result or {},
            "error": error,
        },
    )


def process_one_request(supabase: SupabaseRest, kiwoom: KiwoomClient, *, limit: int | None = None) -> bool:
    request = claim_pending_request(supabase)
    if not request:
        return False
    request_id = request["id"]
    refresh_type = str(request.get("request_type") or "batch")
    try:
        securities = normalize_security_list(request.get("securities"))
        created_by = request.get("requested_by")
        if refresh_type == "full" and not securities:
            securities, created_by = collect_securities(supabase)
        if limit:
            securities = securities[:limit]
        incoming = fetch_and_publish(
            supabase,
            kiwoom,
            securities,
            refresh_type=refresh_type,
            created_by=created_by,
        )
        result = {
            "requestedCount": len(securities),
            "successCount": len(incoming.get("securities") or {}),
            "failedCount": len(incoming.get("errors") or {}),
            "asOf": incoming.get("asOf"),
        }
        complete_request(supabase, request_id, status="done", result=result)
        print(f"request {request_id} done: {result}")
    except Exception as exc:
        complete_request(supabase, request_id, status="failed", error=str(exc))
        print(f"request {request_id} failed: {exc}")
    return True


def refresh_domestic_once(
    supabase: SupabaseRest,
    kiwoom: KiwoomClient,
    *,
    limit: int | None = None,
) -> dict[str, Any] | None:
    securities, created_by = collect_securities(supabase)
    domestic = [security for security in securities if is_ks_security(security)]
    if limit:
        domestic = domestic[:limit]
    if not domestic:
        print("domestic refresh skipped: no KS securities")
        return None
    incoming = fetch_and_publish(
        supabase,
        kiwoom,
        domestic,
        refresh_type="domestic_auto",
        created_by=created_by,
    )
    print(
        f"{incoming.get('asOf')} domestic refresh: "
        f"requested={len(domestic)}, success={len(incoming.get('securities') or {})}, "
        f"failed={len(incoming.get('errors') or {})}"
    )
    return incoming


def main() -> None:
    parser = argparse.ArgumentParser(description="Global dashboard Kiwoom Supabase receiver")
    parser.add_argument("--cycle-seconds", type=float, default=20.0, help="Alias for --domestic-cycle-seconds.")
    parser.add_argument("--domestic-cycle-seconds", type=float, default=None)
    parser.add_argument("--request-poll-seconds", type=float, default=2.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    domestic_cycle = args.domestic_cycle_seconds or args.cycle_seconds
    supabase = SupabaseRest(
        os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL),
        required_env("SUPABASE_SERVICE_ROLE_KEY"),
    )
    kiwoom = KiwoomClient()

    print("Global dashboard Kiwoom receiver started")
    print(f"domestic refresh: every {domestic_cycle:g}s")
    print(f"request polling : every {args.request_poll_seconds:g}s")

    last_domestic = 0.0
    while True:
        now = time.monotonic()
        if args.once or now - last_domestic >= domestic_cycle:
            try:
                refresh_domestic_once(supabase, kiwoom, limit=args.limit)
            except Exception as exc:
                print(f"domestic refresh failed: {exc}")
            last_domestic = time.monotonic()

        try:
            while process_one_request(supabase, kiwoom, limit=args.limit):
                if args.once:
                    break
        except Exception as exc:
            print(f"request polling failed: {exc}")

        if args.once:
            break

        time.sleep(max(0.5, args.request_poll_seconds))


if __name__ == "__main__":
    main()

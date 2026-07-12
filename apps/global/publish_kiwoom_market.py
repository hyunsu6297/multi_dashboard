"""Continuously publish Global Strategy dashboard market data to Supabase.

This is the shared-price worker for the deployed global dashboard:

1. Read ETF DB / EMP portfolio tickers from Supabase manual_file_rows.
2. Fetch prices with Kiwoom REST API.
3. Store one shared market snapshot in global/market_data.

The browser only reads that snapshot, so other users do not need to run a
local Kiwoom receiver.
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

from global_dashboard_server import KiwoomClient, normalize_security  # noqa: E402


DEFAULT_SUPABASE_URL = "https://esqakvzvchcunhzjlyry.supabase.co"
GLOBAL_DOMAIN = "global"
MARKET_FILE_KEY = "market_data"
MARKET_FILE_LABEL = "시세 데이터"


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} 환경변수가 필요합니다.")
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
        raise RuntimeError(f"{table} 페이지네이션 한도를 초과했습니다.")

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
        for key in ("ticker", "name"):
            security = candidate_security(payload.get(key), listing)
            if security:
                securities.append(security)
                break
    for row in emp_rows:
        payload = row.get("payload") or {}
        security = candidate_security(payload.get("security") or payload.get("ticker") or payload.get("name"))
        if security:
            securities.append(security)

    unique = list(dict.fromkeys(securities))
    return unique, created_by


def publish_market_snapshot(client: SupabaseRest, market: dict[str, Any], created_by: str | None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    record: dict[str, Any] = {
        "domain": GLOBAL_DOMAIN,
        "file_key": MARKET_FILE_KEY,
        "file_label": MARKET_FILE_LABEL,
        "sheet_name": "Data",
        "row_no": 1,
        "payload": market,
        "updated_at": now,
    }
    if created_by:
        record["created_by"] = created_by
    client.upsert_rows("manual_file_rows", [record], "domain,file_key,sheet_name,row_no")


def run_once(supabase: SupabaseRest, kiwoom: KiwoomClient, *, limit: int | None = None) -> dict[str, Any]:
    securities, created_by = collect_securities(supabase)
    if limit:
        securities = securities[:limit]
    if not securities:
        raise RuntimeError("Supabase ETF DB/EMP상세에서 조회할 종목을 찾지 못했습니다.")
    market = kiwoom.fetch_reference(securities)
    market["source"] = "kiwoom-supabase-receiver"
    market["universeCount"] = len(securities)
    market["publishedAt"] = datetime.now(timezone.utc).isoformat()
    publish_market_snapshot(supabase, market, created_by)
    return market


def main() -> None:
    parser = argparse.ArgumentParser(description="글로벌전략 대시보드 키움 시세를 Supabase에 게시합니다.")
    parser.add_argument("--cycle-seconds", type=float, default=20.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    supabase = SupabaseRest(
        os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL),
        required_env("SUPABASE_SERVICE_ROLE_KEY"),
    )
    kiwoom = KiwoomClient()

    while True:
        started = time.monotonic()
        try:
            market = run_once(supabase, kiwoom, limit=args.limit)
            success = len(market.get("securities", {}))
            failed = len(market.get("errors", {}))
            print(
                f"{market.get('asOf')} published: "
                f"universe={market.get('universeCount', 0)}, success={success}, failed={failed}, fx={market.get('fx')}"
            )
            if failed:
                sample = list((market.get("errors") or {}).items())[:3]
                for security, error in sample:
                    print(f"  - {security}: {error}")
        except Exception as exc:
            print(f"publish failed: {exc}")
        if args.once:
            break
        sleep_for = max(0.0, args.cycle_seconds - (time.monotonic() - started))
        print(f"next refresh in {sleep_for:.2f}s")
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()

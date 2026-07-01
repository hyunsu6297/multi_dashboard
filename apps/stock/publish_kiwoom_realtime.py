"""Refresh Kiwoom quotes locally and publish the live stock dashboard to Supabase."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_fund_dashboard import build_dashboard
from fetch_kiwoom_quotes import (
    BASE_DIR,
    DEFAULT_BATCH_SIZE,
    DEFAULT_CYCLE_SECONDS,
    DEFAULT_HOST,
    OUTPUT,
    collect_codes,
    collect_mezzanine_codes,
    load_credentials,
    request_token,
    run_refresh,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))
from scripts.restore_dashboard_inputs import SupabaseRest, restore_manual  # noqa: E402


DEFAULT_SUPABASE_URL = "https://esqakvzvchcunhzjlyry.supabase.co"
STORAGE_BUCKET = "dashboard-live"
STORAGE_PATH = "stock/index.html"


def required_secret() -> str:
    value = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SECRET_KEY")
        or ""
    ).strip()
    if not value:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required")
    return value


class SupabasePublisher:
    def __init__(self, url: str, secret_key: str) -> None:
        self.url = url.rstrip("/")
        self.headers = {
            "apikey": secret_key,
            "Authorization": f"Bearer {secret_key}",
        }

    def request(
        self,
        url: str,
        *,
        method: str,
        body: bytes | None = None,
        content_type: str,
        headers: dict[str, str] | None = None,
    ) -> bytes:
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                **self.headers,
                "Content-Type": content_type,
                **(headers or {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Supabase HTTP {exc.code}: {detail[:1000]}") from exc

    def manual_version(self) -> str:
        query = urllib.parse.urlencode({
            "select": "updated_at",
            "domain": "in.(stock,bond)",
            "order": "updated_at.desc",
            "limit": "1",
        }, safe=".,()")
        payload = self.request(
            f"{self.url}/rest/v1/manual_file_rows?{query}",
            method="GET",
            content_type="application/json",
        )
        rows = json.loads(payload or b"[]")
        return str(rows[0]["updated_at"]) if rows else ""

    def upsert_rows(self, table: str, rows: list[dict[str, Any]], conflict: str) -> None:
        endpoint = f"{self.url}/rest/v1/{table}?on_conflict={urllib.parse.quote(conflict)}"
        for start in range(0, len(rows), 250):
            batch = rows[start : start + 250]
            self.request(
                endpoint,
                method="POST",
                body=json.dumps(batch, ensure_ascii=False).encode("utf-8"),
                content_type="application/json",
                headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            )

    def upload_dashboard(self, html_path: Path) -> None:
        object_path = urllib.parse.quote(STORAGE_PATH, safe="/")
        self.request(
            f"{self.url}/storage/v1/object/{STORAGE_BUCKET}/{object_path}",
            method="POST",
            body=html_path.read_bytes(),
            content_type="text/html",
            headers={"x-upsert": "true", "cache-control": "no-cache"},
        )


def quote_rows(quotes: dict[str, Any], collected_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code, item in quotes.get("stocks", {}).items():
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "code": str(code),
                "name": str(item.get("name") or ""),
                "price": item.get("price"),
                "change_rate": item.get("change_rate"),
                "industry": str(item.get("industry") or ""),
                "market": str(item.get("market") or ""),
                "kiwoom_rest_code": item.get("kiwoom_rest_code"),
                "proxy_code": item.get("proxy_code"),
                "error": item.get("error"),
                "payload": item,
                "collected_at": collected_at,
                "updated_at": collected_at,
            }
        )
    return rows


def publish_cycle(
    publisher: SupabasePublisher,
    args: argparse.Namespace,
    token: str,
    codes: dict[str, str],
) -> None:
    quotes = run_refresh(args, token, codes)
    rows = quote_rows(quotes, datetime.now(timezone.utc).isoformat())
    available = sum(1 for row in rows if row["price"] not in (None, 0, 0.0))
    if not rows or available == 0:
        raise RuntimeError("No usable Kiwoom quotes were returned; previous live dashboard was retained")

    manual_version = publisher.manual_version()
    if manual_version != getattr(args, "manual_version", None):
        restore_client = SupabaseRest(publisher.url, required_secret())
        restore_manual(
            restore_client,
            REPOSITORY_ROOT / "apps" / "stock",
            REPOSITORY_ROOT / "apps" / "bond",
        )
        args.manual_version = manual_version
    html_path = build_dashboard()
    publisher.upsert_rows("kiwoom_realtime_quotes", rows, "code")
    publisher.upload_dashboard(html_path)
    publisher.upsert_rows(
        "dashboard_live_versions",
        [
            {
                "dashboard_key": "stock",
                "storage_bucket": STORAGE_BUCKET,
                "storage_path": STORAGE_PATH,
                "version": uuid.uuid4().hex,
                "quote_count": len(rows),
                "available_count": available,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
        "dashboard_key",
    )
    print(f"published to Supabase: quotes={len(rows)}, available={available}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish Kiwoom live quotes to Supabase.")
    parser.add_argument("--host", default=os.getenv("KIWOOM_HOST", DEFAULT_HOST))
    parser.add_argument("--cycle-seconds", type=float, default=DEFAULT_CYCLE_SECONDS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--code", default=None)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    args.build_dashboard = False

    appkey, secretkey = load_credentials()
    if not appkey or not secretkey:
        raise SystemExit("KIWOOM_APPKEY and KIWOOM_SECRETKEY are required")
    token = request_token(args.host, appkey, secretkey, args.timeout)
    stock_codes = collect_codes()
    mezzanine_codes = collect_mezzanine_codes()
    codes = {**stock_codes, **mezzanine_codes}
    if not codes:
        raise SystemExit("No quote codes found")
    print(
        "quote universe: "
        f"stock={len(stock_codes)}, mezzanine_underlyings={len(mezzanine_codes)}, merged={len(codes)}"
    )

    publisher = SupabasePublisher(
        os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL),
        required_secret(),
    )

    while True:
        started = time.monotonic()
        try:
            publish_cycle(publisher, args, token, codes)
        except Exception as exc:
            print(f"publish cycle failed: {exc}")
        if args.once:
            break
        sleep_for = max(0.0, args.cycle_seconds - (time.monotonic() - started))
        print(f"next refresh in {sleep_for:.2f}s")
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()



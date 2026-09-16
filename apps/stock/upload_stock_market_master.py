"""Upload the cached Kiwoom KOSPI/KOSDAQ membership map to Supabase."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = BASE_DIR.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from publish_kiwoom_realtime import (  # noqa: E402
    DEFAULT_SUPABASE_URL,
    SupabasePublisher,
    required_secret,
)


def normalize_code(value: object) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return digits[-6:].zfill(6) if digits else ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a stable stock market membership master.")
    parser.add_argument("--input", type=Path, default=BASE_DIR / "kiwoom_quotes.json")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    master = payload.get("market_master", {})
    if not isinstance(master, dict) or not master:
        raise RuntimeError("The Kiwoom quote cache does not contain market_master data.")

    updated_at = datetime.now(timezone.utc).isoformat()
    rows_by_code: dict[str, dict[str, str]] = {}
    for raw_code, item in master.items():
        if not isinstance(item, dict):
            continue
        code = normalize_code(raw_code)
        market = str(item.get("market") or "").strip()
        if len(code) != 6 or market not in {"코스피", "코스닥"}:
            continue
        rows_by_code[code] = {
            "code": code,
            "market": market,
            "source": "kiwoom",
            "updated_at": updated_at,
        }
    rows = list(rows_by_code.values())
    if len(rows) < 1000:
        raise RuntimeError(f"Market master has too few valid rows: {len(rows)}")

    publisher = SupabasePublisher(DEFAULT_SUPABASE_URL, required_secret())
    publisher.upsert_rows("stock_market_master", rows, "code")
    counts = {market: sum(1 for row in rows if row["market"] == market) for market in ("코스피", "코스닥")}
    print(f"uploaded={len(rows)}, counts={counts}")


if __name__ == "__main__":
    main()

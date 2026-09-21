"""Backfill missing daily fund-price snapshots from retained KFR history."""

from __future__ import annotations

import argparse
import gzip
import json
import tempfile
from collections import defaultdict
from datetime import date
from pathlib import Path

from kfr_api import api_shape_rows, validate_payload
from supabase_upload import (
    SupabaseRest,
    existing_snapshot_is_valid,
    required_env,
    upload_payload,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = REPO_ROOT / "data" / "kfr" / "prices_legacy_history.json.gz"


def load_rows(path: Path) -> list[dict]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as file:
            payload = json.load(file)
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("content") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise RuntimeError(f"KFR history has no content rows: {path}")
    return api_shape_rows("fund_prices", rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="First date to backfill (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="Last date to backfill (YYYY-MM-DD)")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if end < start:
        raise ValueError("--end must be on or after --start")

    rows_by_date: dict[date, list[dict]] = defaultdict(list)
    for row in load_rows(args.input.expanduser().resolve()):
        trade_day = str(row.get("trade_day") or "").strip()[:10]
        try:
            business_date = date.fromisoformat(trade_day)
        except ValueError:
            continue
        if start <= business_date <= end:
            rows_by_date[business_date].append(row)

    if not rows_by_date:
        raise RuntimeError(f"No fund-price rows found from {start} through {end}")
    print(
        f"prepared dates={len(rows_by_date)}, rows={sum(len(rows) for rows in rows_by_date.values())}, "
        f"range={min(rows_by_date)}..{max(rows_by_date)}"
    )
    if args.dry_run:
        return

    client = SupabaseRest(required_env("SUPABASE_URL"), required_env("SUPABASE_SERVICE_ROLE_KEY"))
    with tempfile.TemporaryDirectory(prefix="kfr-fund-price-backfill-") as directory:
        output_dir = Path(directory)
        for business_date in sorted(rows_by_date):
            valid, detail = existing_snapshot_is_valid(client, "fund_prices", business_date)
            if valid:
                print(f"{business_date}: already valid ({detail})")
                continue
            rows = rows_by_date[business_date]
            payload = {"content": rows, "total_elements": len(rows)}
            validate_payload("fund_prices", payload)
            path = output_dir / f"prices_{business_date.isoformat()}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            snapshot_id, row_count, created = upload_payload(
                client, "fund_prices", path, business_date
            )
            state = "uploaded" if created else "already exists"
            print(f"{business_date}: snapshot={snapshot_id}, rows={row_count}, {state}")


if __name__ == "__main__":
    main()

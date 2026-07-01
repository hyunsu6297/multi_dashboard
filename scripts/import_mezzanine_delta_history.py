"""One-time import of historical mezzanine NAV files into Supabase."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


def normalize_code(value: object) -> str:
    return str(value or "").strip()


def build_records(input_dir: Path) -> list[dict]:
    observations = []
    for path in sorted(input_dir.glob("메자닌 기준가(*).xlsx")):
        frame = pd.read_excel(path, sheet_name="Data", header=1).dropna(how="all")
        for _, row in frame.iterrows():
            security_code = normalize_code(row.get("상품코드"))
            if not security_code or pd.isna(row.get("기준가")) or pd.isna(row.get("거래일")):
                continue
            observations.append({
                "business_date": pd.Timestamp(row["거래일"]).date().isoformat(),
                "security_code": security_code,
                "security_name": normalize_code(row.get("종목명")),
                "fund_name": normalize_code(row.get("펀드명")),
                "nav": float(row["기준가"]),
                "underlying_change_rate": None,
            })
    observations.sort(key=lambda item: (item["security_code"], item["fund_name"], item["business_date"]))
    previous: dict[tuple[str, str], float] = {}
    records = []
    for item in observations:
        key = (item["security_code"], item["fund_name"])
        prior_nav = previous.get(key)
        nav_return = item["nav"] / prior_nav - 1.0 if prior_nav else None
        daily_delta = None
        records.append({
            **item,
            "nav_return": nav_return,
            "daily_delta": daily_delta,
            "is_valid": daily_delta is not None and 0 <= daily_delta <= 1,
            "source": "historical_xlsx",
        })
        previous[key] = item["nav"]
    return records


def upload(records: list[dict]) -> None:
    url = required_env("SUPABASE_URL").rstrip("/")
    key = required_env("SUPABASE_SERVICE_ROLE_KEY")
    headers = {"apikey": key, "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"}
    if key.count(".") == 2:
        headers["Authorization"] = f"Bearer {key}"
    endpoint = f"{url}/rest/v1/mezzanine_delta_history?on_conflict=business_date,security_code,fund_name"
    for start in range(0, len(records), 500):
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(records[start : start + 500], ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60):
                pass
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Supabase HTTP {exc.code}: {detail[:1000]}") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="메자닌 추가자료")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--export-json-dir")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    records = build_records(Path(args.input_dir))
    valid = sum(record["is_valid"] for record in records)
    print(f"prepared={len(records)}, valid_delta={valid}")
    if args.export_json_dir:
        output_dir = Path(args.export_json_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        for start in range(0, len(records), args.batch_size):
            (output_dir / f"batch_{start // args.batch_size:04d}.json").write_text(
                json.dumps(records[start : start + args.batch_size], ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
        print(f"exported_batches={len(list(output_dir.glob('batch_*.json')))}")
        return
    if not args.dry_run:
        upload(records)
        print("uploaded")


if __name__ == "__main__":
    main()

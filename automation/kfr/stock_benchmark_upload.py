"""Download Samsung KODEX benchmark holdings and store dated snapshots in Supabase."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

from kfr_partner_api_download import previous_business_day
from supabase_upload import SupabaseRest, required_env


BENCHMARKS = {
    "코스피": {"fund_id": "2ETF52", "scale": 1.0, "label": "KODEX 코스피"},
    "코스닥": {"fund_id": "2ETF54", "scale": 0.5, "label": "KODEX 코스닥150 x 50%"},
}


def clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def normalize_code(value: object) -> str:
    text = clean_text(value).replace(".0", "")
    text = re.sub(r"^A", "", text, flags=re.IGNORECASE)
    digits = re.sub(r"\D", "", text)
    return digits.zfill(6) if digits else ""


def parse_workbook(content: bytes, scale: float) -> tuple[str, dict[str, dict[str, Any]]]:
    if not content.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
        raise RuntimeError("삼성자산운용 응답이 XLS 파일이 아닙니다.")
    frame = pd.read_excel(BytesIO(content), header=2, engine="xlrd", dtype={"종목코드": str})
    if "종목코드" not in frame or "비중(%)" not in frame:
        raise RuntimeError("삼성자산운용 BM 파일의 컬럼 형식이 예상과 다릅니다.")
    name_column = next((name for name in ("종목명", "종목") if name in frame), None)
    rows: dict[str, dict[str, Any]] = {}
    for _, row in frame.iterrows():
        code = normalize_code(row.get("종목코드"))
        weight = pd.to_numeric(row.get("비중(%)"), errors="coerce")
        if not re.fullmatch(r"\d{6}", code) or pd.isna(weight):
            continue
        value = float(weight)
        if abs(value) > 1:
            value /= 100
        rows[code] = {
            "name": clean_text(row.get(name_column)) if name_column else "",
            "weight": value * scale,
        }
    if len(rows) < 100:
        raise RuntimeError(f"삼성자산운용 BM 구성종목이 너무 적습니다: {len(rows)}건")
    raw = pd.read_excel(BytesIO(content), header=None, nrows=2, engine="xlrd")
    source_date = clean_text(raw.iloc[1, 0]) if len(raw.index) > 1 else ""
    return source_date.replace("/", "-"), rows


def download(market: str, config: dict[str, Any], business_date: date) -> dict[str, Any]:
    compact_date = business_date.strftime("%Y%m%d")
    url = f"https://www.samsungfund.com/excel_pdf.do?fId={config['fund_id']}&gijunYMD={compact_date}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        content = response.read()
    source_date, rows = parse_workbook(content, float(config["scale"]))
    normalized_source_date = source_date[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", source_date) else ""
    if normalized_source_date and normalized_source_date != business_date.isoformat():
        raise RuntimeError(
            f"{market}: 요청일 {business_date.isoformat()}과 파일 기준일 {normalized_source_date}이 다릅니다."
        )
    return {
        "market": market,
        "business_date": business_date.isoformat(),
        "source_date": normalized_source_date or business_date.isoformat(),
        "label": str(config["label"]),
        "source_url": url,
        "scale": float(config["scale"]),
        "row_count": len(rows),
        "sha256": hashlib.sha256(content).hexdigest(),
        "weights": rows,
    }


def cache_payload(snapshots: list[dict[str, Any]], business_date: date) -> dict[str, Any]:
    return {
        "requestedDate": business_date.isoformat(),
        "generatedAt": pd.Timestamp.now(tz="Asia/Seoul").isoformat(),
        "weights": {
            item["market"]: {code: row["weight"] for code, row in item["weights"].items()}
            for item in snapshots
        },
        "sources": {
            item["market"]: {
                "label": item["label"],
                "date": item["source_date"],
                "url": item["source_url"],
                "count": item["row_count"],
                "scale": item["scale"],
            }
            for item in snapshots
        },
        "errors": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--business-date", default=previous_business_day().isoformat())
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    business_date = date.fromisoformat(args.business_date)
    snapshots = [download(market, config, business_date) for market, config in BENCHMARKS.items()]
    client = SupabaseRest(required_env("SUPABASE_URL"), required_env("SUPABASE_SERVICE_ROLE_KEY"))
    for snapshot in snapshots:
        payload = dict(snapshot)
        payload["weights"] = snapshot["weights"]
        client.request(
            "POST",
            "stock_benchmark_snapshots?on_conflict=market,business_date",
            payload,
            prefer="resolution=merge-duplicates,return=minimal",
        )
        print(
            f"{snapshot['market']}: date={snapshot['business_date']}, "
            f"rows={snapshot['row_count']}, uploaded"
        )

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(cache_payload(snapshots, business_date), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"cache: {output}")


if __name__ == "__main__":
    main()

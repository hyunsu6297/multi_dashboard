"""Shared KFR Partner API schema validation and JSON loading helpers.

KFR rows are stored in Supabase exactly as returned by the API (snake_case).
Dashboard builders call this module to translate those rows to the legacy Korean
column names expected by the existing calculation code.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


SOURCE_TO_API_NAME = {
    "fund_prices": "prices",
    "fund_holdings": "holdings",
    "fund_trades": "trades",
    "mezzanine_price": "mezzanine-portfolio",
}
API_NAME_TO_SOURCE = {value: key for key, value in SOURCE_TO_API_NAME.items()}

API_FIELDS = {
    "fund_prices": [
        "trade_day", "cm_seq", "composite_name", "fund_ksd_code", "invest_day",
        "fund_k_name", "ret", "price", "prev_price", "share_rate", "cul_ret",
        "kospi", "kosdaq", "sp500", "nasdaq", "kobi30", "kobi120", "econo_idx",
    ],
    "fund_holdings": [
        "buy_day", "composite_name", "fund_ksd_code", "fund_kr_code", "fund_k_name",
        "asset_b_class_k_name", "asset_s_class_k_name", "item_code", "item_k_name",
        "qty", "price", "eval_amt", "invest_amt", "credit_grade", "duration", "ytm",
        "coup_rate", "issue_day", "due_day", "nav_amt", "class_name", "flag", "share_ratio",
    ],
    "fund_trades": [
        "trade_day", "fund_ksd_code", "fund_kr_code", "fund_kr_full_name",
        "asset_b_class_k_name", "asset_s_class_k_name", "item_code", "item_k_name",
        "trade_type", "trade_qty", "trade_price", "settle_amt", "issue_day", "due_day",
        "mac_duration", "trade_ret",
    ],
    "mezzanine_price": [
        "trade_day", "fund_ksd_code", "fund_k_name", "composite_type_name", "class_name",
        "item_code", "item_k_name", "price", "qty", "price_change_rate", "eval_amt",
        "asset_b_class",
    ],
}

LEGACY_COLUMN_MAP = {
    "fund_prices": {
        "trade_day": "기준일", "cm_seq": "구성순번", "composite_name": "유형",
        "fund_ksd_code": "예탁원펀드코드", "invest_day": "투자일", "fund_k_name": "펀드명",
        "ret": "일수익률", "price": "기준가", "prev_price": "전일기준가",
        "share_rate": "결산분배율", "cul_ret": "누적수익률", "kospi": "KOSPI",
        "kosdaq": "KOSDAQ", "sp500": "S&P500", "nasdaq": "NASDAQ",
        "kobi30": "KOBI30", "kobi120": "KOBI120", "econo_idx": "기준금리",
    },
    "fund_holdings": {
        "buy_day": "보유일", "composite_name": "유형", "fund_ksd_code": "예탁원코드",
        "fund_kr_code": "협회펀드코드", "fund_k_name": "펀드명",
        "asset_b_class_k_name": "자산군", "asset_s_class_k_name": "시장구분",
        "item_code": "종목코드", "item_k_name": "종목명", "qty": "수량",
        "price": "평가가격", "eval_amt": "평가금", "invest_amt": "취득가액",
        "credit_grade": "신용등급", "duration": "듀레이션", "ytm": "YTM",
        "coup_rate": "이표율", "issue_day": "발행일", "due_day": "만기일",
        "nav_amt": "순자산", "class_name": "섹터", "flag": "포지션",
        "share_ratio": "지분율",
    },
    "fund_trades": {
        "trade_day": "기준일", "fund_ksd_code": "예탁원펀드코드",
        "fund_kr_code": "협회펀드코드", "fund_kr_full_name": "펀드명",
        "asset_b_class_k_name": "자산구분", "asset_s_class_k_name": "시장구분",
        "item_code": "종목코드", "item_k_name": "종목명", "trade_type": "거래구분",
        "trade_qty": "매매수량", "trade_price": "매매가격", "settle_amt": "결제금액",
        "issue_day": "채권발행일", "due_day": "채권만기일",
        "mac_duration": "듀레이션", "trade_ret": "매매금리",
    },
    "mezzanine_price": {
        "trade_day": "거래일", "fund_ksd_code": "예탁원펀드코드", "fund_k_name": "펀드명",
        "composite_type_name": "유형코드(대)", "class_name": "유형코드(소)",
        "item_code": "상품코드", "item_k_name": "종목명", "price": "기준가",
        "qty": "수량", "price_change_rate": "등락율", "eval_amt": "평가금액",
        "asset_b_class": "자산대분류코드",
    },
}


def source_key(value: str) -> str:
    key = API_NAME_TO_SOURCE.get(value, value)
    if key not in SOURCE_TO_API_NAME:
        raise KeyError(f"Unknown KFR dataset: {value}")
    return key


def validate_payload(dataset: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    key = source_key(dataset)
    content = payload.get("content")
    if not isinstance(content, list) or any(not isinstance(row, dict) for row in content):
        raise RuntimeError(f"{key}: content must be a list of objects")
    total = payload.get("total_elements")
    if isinstance(total, int) and total != len(content):
        raise RuntimeError(f"{key}: total_elements={total}, content={len(content)}")
    for index, row in enumerate(content, start=1):
        missing = [field for field in API_FIELDS[key] if field not in row]
        if missing:
            raise RuntimeError(
                f"{key}: row {index} missing API fields: {', '.join(missing)}"
            )
    return content


def normalize_rows(dataset: str, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    key = source_key(dataset)
    mapping = LEGACY_COLUMN_MAP[key]
    normalized: list[dict[str, Any]] = []
    for raw in rows:
        row = {mapping[name]: raw.get(name) for name in API_FIELDS[key]}
        for name, value in row.items():
            if isinstance(value, str):
                row[name] = value.strip()
        normalized.append(row)
    return normalized


def api_shape_rows(dataset: str, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return API-shaped rows, converting retained legacy Excel snapshots when needed."""
    key = source_key(dataset)
    output: list[dict[str, Any]] = []
    for row in rows:
        if any(field in row for field in API_FIELDS[key]):
            output.append({field: row.get(field) for field in API_FIELDS[key]})
            continue
        mapping = LEGACY_COLUMN_MAP[key]
        output.append({field: row.get(mapping[field]) for field in API_FIELDS[key]})
    return output


def frame_from_rows(dataset: str, rows: Iterable[dict[str, Any]]) -> pd.DataFrame:
    key = source_key(dataset)
    columns = [LEGACY_COLUMN_MAP[key][field] for field in API_FIELDS[key]]
    return pd.DataFrame(normalize_rows(key, rows), columns=columns)


def load_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"KFR JSON is not an object: {path}")
    return payload


def load_manifest(data_dir: Path) -> dict[str, Any]:
    path = data_dir / "index.json"
    if not path.is_file():
        datasets: dict[str, list[dict[str, Any]]] = {}
        for key, api_name in SOURCE_TO_API_NAME.items():
            entries = []
            for candidate in data_dir.glob(f"{api_name}_*.json"):
                match = re.search(r"(\d{4}-\d{2}-\d{2})$", candidate.stem)
                if match:
                    entries.append({"business_date": match.group(1), "file": candidate.name})
            datasets[key] = sorted(entries, key=lambda entry: entry["business_date"])
        if any(datasets.values()):
            return {"generated_at": "", "datasets": datasets}
        raise FileNotFoundError(f"KFR JSON manifest is missing and no API files were found: {data_dir}")
    payload = load_payload(path)
    if not isinstance(payload.get("datasets"), dict):
        raise RuntimeError(f"Invalid KFR JSON manifest: {path}")
    return payload


def available_dates(data_dir: Path, dataset: str) -> list[str]:
    key = source_key(dataset)
    entries = load_manifest(data_dir)["datasets"].get(key, [])
    return sorted({str(entry.get("business_date", "")) for entry in entries if entry.get("business_date")})


def load_frame(
    data_dir: Path,
    dataset: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    latest_only: bool = False,
) -> pd.DataFrame:
    key = source_key(dataset)
    entries = list(load_manifest(data_dir)["datasets"].get(key, []))
    if start_date:
        entries = [entry for entry in entries if str(entry.get("business_date", "")) >= start_date]
    if end_date:
        entries = [entry for entry in entries if str(entry.get("business_date", "")) <= end_date]
    entries.sort(key=lambda entry: (str(entry.get("business_date", "")), str(entry.get("downloaded_at", ""))))
    if latest_only and entries:
        entries = [entries[-1]]

    frames: list[pd.DataFrame] = []
    for entry in entries:
        path = data_dir / str(entry["file"])
        payload = load_payload(path)
        rows = validate_payload(key, payload)
        frame = frame_from_rows(key, rows)
        frame["스냅샷일"] = str(entry.get("business_date", ""))
        frame["원천파일"] = path.name
        frames.append(frame)
    if not frames:
        return frame_from_rows(key, [])
    return pd.concat(frames, ignore_index=True)

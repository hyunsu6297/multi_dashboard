# -*- coding: utf-8 -*-
from __future__ import annotations

import html
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parents[1]
KFR_MODULE_DIR = REPO_ROOT / "automation" / "kfr"
if str(KFR_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(KFR_MODULE_DIR))
from kfr_api import available_dates as available_kfr_dates  # noqa: E402
from kfr_api import load_frame as load_kfr_frame  # noqa: E402
from kfr_api import normalize_rows as normalize_kfr_rows  # noqa: E402

KFR_DATA_DIR = Path(os.getenv("KFR_JSON_DIR", str(REPO_ROOT / "data" / "kfr")))


def pick_input(default_name: str, *patterns: str) -> Path:
    for pattern in patterns:
        matches = sorted(
            (path for path in BASE_DIR.glob(pattern) if not path.name.startswith("~$")),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if matches:
            return matches[0]
    return BASE_DIR / default_name


INPUTS = {
    "fund_info": BASE_DIR / "펀드 정보.xlsx",
    "direct_stocks": BASE_DIR / "주식보유현황.xlsx",
    "industry": BASE_DIR / "업종.xlsx",
}
QUOTE_CANDIDATES = [
    BASE_DIR / "kiwoom_quotes.json",
    BASE_DIR / "kiwoom_realtime_quotes.json",
    BASE_DIR / "realtime_quotes.json",
    BASE_DIR / "change_rates.json",
]
OUTPUT = BASE_DIR / "fund_dashboard.html"
DATA_DIR = BASE_DIR / "data"
FUND_MASTER_VERSION_FILE = BASE_DIR / "stock_fund_master_versions.json"
DEFAULT_SUPABASE_URL = "https://esqakvzvchcunhzjlyry.supabase.co"


def esc(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return html.escape(str(value), quote=True)


def clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip().replace(",", "")
    if text.endswith(".0"):
        text = text[:-2]
    return text


def normalize_code(value: object) -> str:
    text = clean_text(value)
    if not text or text.lower() == "nan":
        return ""
    if len(text) >= 9 and text.startswith("KR7") and text[3:9].isdigit():
        return text[3:9]
    return text.zfill(6) if text.isdigit() else text


def load_fund_master_versions() -> dict[str, object]:
    if not FUND_MASTER_VERSION_FILE.exists():
        return {}
    try:
        payload = json.loads(FUND_MASTER_VERSION_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    versions = payload.get("versions") if isinstance(payload, dict) else payload
    if not isinstance(versions, list) or not versions:
        return {}
    versions = [version for version in versions if isinstance(version, dict)]
    if not versions:
        return {}
    latest_key = payload.get("latestEffectiveDate") if isinstance(payload, dict) else ""
    latest = next((version for version in versions if str(version.get("effectiveDate", "")) == str(latest_key)), None)
    if latest is None:
        latest = sorted(versions, key=lambda version: str(version.get("effectiveDate", "")))[-1]
    rows = latest.get("rows", [])
    if not isinstance(rows, list):
        return {}
    by_code: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = normalize_code(row.get("펀드코드"))
        if not code:
            continue
        by_code[code] = {
            "name": clean_text(row.get("펀드명(약식)") or row.get("펀드명") or ""),
            "type": clean_text(row.get("유형") or "기타") or "기타",
            "status": clean_text(row.get("상태") or "활성") or "활성",
        }
    return {"effective_date": str(latest.get("effectiveDate", "")), "by_code": by_code}


def apply_fund_master(funds: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    master = load_fund_master_versions()
    by_code = master.get("by_code")
    if not isinstance(by_code, dict) or not by_code:
        return funds, master
    order = {code: index for index, code in enumerate(by_code)}
    funds = funds.copy()
    funds["_master_order"] = funds["펀드코드"].map(lambda code: order.get(code, 9999))
    funds["_master_status"] = funds["펀드코드"].map(lambda code: by_code.get(code, {}).get("status", "활성"))
    funds = funds[funds["_master_status"].ne("비활성")].copy()
    funds["펀드명"] = funds.apply(lambda row: by_code.get(row["펀드코드"], {}).get("name") or row["펀드명"], axis=1)
    funds["유형"] = funds.apply(lambda row: by_code.get(row["펀드코드"], {}).get("type") or row["유형"], axis=1)
    return funds.sort_values("_master_order").drop(columns=["_master_order", "_master_status"], errors="ignore"), master


class SupabaseRest:
    def __init__(self, url: str, key: str) -> None:
        self.base_url = f"{url.rstrip('/')}/rest/v1"
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    def get(self, path: str) -> list[dict[str, object]]:
        request = urllib.request.Request(f"{self.base_url}/{path}", headers=self.headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Supabase HTTP {exc.code}: {detail[:1000]}") from exc
        return json.loads(payload or b"[]")


def supabase_client() -> SupabaseRest:
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY") or "").strip()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY 환경변수가 필요합니다.")
    return SupabaseRest(os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL), key)


def fetch_kfr_snapshots(
    client: SupabaseRest,
    source_key: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    latest_only: bool = False,
) -> list[dict[str, object]]:
    filters = {
        "select": "id,business_date,row_count,file_name,downloaded_at",
        "source_key": f"eq.{source_key}",
        "order": "business_date.desc,downloaded_at.desc" if latest_only else "business_date.asc,downloaded_at.asc",
        "source_format": "eq.kfr_partner_api_json",
    }
    if start_date:
        filters["business_date"] = f"gte.{start_date}"
    if end_date:
        filters["business_date"] = f"lte.{end_date}"
    if latest_only:
        filters["limit"] = "1"
    query = urllib.parse.urlencode(filters, safe=".,()")
    snapshots = client.get(f"kfr_source_snapshots?{query}")
    if not latest_only:
        deduped: dict[str, dict[str, object]] = {}
        for snapshot in snapshots:
            deduped[str(snapshot["business_date"])] = snapshot
        snapshots = [deduped[key] for key in sorted(deduped)]
    return snapshots


def fetch_kfr_rows(
    client: SupabaseRest,
    source_key: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    latest_only: bool = False,
) -> pd.DataFrame:
    snapshots = fetch_kfr_snapshots(
        client,
        source_key,
        start_date=start_date,
        end_date=end_date,
        latest_only=latest_only,
    )
    rows: list[dict[str, object]] = []
    for snapshot in snapshots:
        snapshot_id = int(snapshot["id"])
        business_date = str(snapshot["business_date"])
        offset = 0
        while True:
            query = urllib.parse.urlencode(
                {
                    "select": "snapshot_id,sheet_name,row_no,payload",
                    "snapshot_id": f"eq.{snapshot_id}",
                    "order": "row_no.asc",
                    "limit": "1000",
                    "offset": str(offset),
                },
                safe=".,()",
            )
            batch = client.get(f"kfr_source_rows?{query}")
            if not batch:
                break
            for item in batch:
                payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
                normalized = normalize_kfr_rows(source_key, [payload])[0]
                rows.append({**normalized, "스냅샷일": business_date, "원천파일": snapshot.get("file_name", "")})
            if len(batch) < 1000:
                break
            offset += 1000
    return pd.DataFrame(rows)


def fetch_manual_file_rows(client: SupabaseRest, domain: str, file_key: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    offset = 0
    while True:
        query = urllib.parse.urlencode(
            {
                "select": "sheet_name,row_no,payload",
                "domain": f"eq.{domain}",
                "file_key": f"eq.{file_key}",
                "order": "row_no.asc",
                "limit": "1000",
                "offset": str(offset),
            },
            safe=".,()",
        )
        batch = client.get(f"manual_file_rows?{query}")
        if not batch:
            break
        for item in batch:
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            rows.append(dict(payload))
        if len(batch) < 1000:
            break
        offset += 1000
    return pd.DataFrame(rows)


def is_effective_sheet_name(value: object) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value or "").strip()))


def normalize_date_label(value: object) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return ""
    return parsed.strftime("%Y-%m-%d")


def choose_effective_sheet(sheet_names: list[str], as_of_date: str | None) -> str | None:
    dated = sorted(name for name in sheet_names if is_effective_sheet_name(name))
    if dated:
        target = normalize_date_label(as_of_date) if as_of_date else ""
        if target:
            eligible = [name for name in dated if name <= target]
            return eligible[-1] if eligible else dated[0]
        return dated[-1]
    if "Sheet1" in sheet_names:
        return "Sheet1"
    return sorted(sheet_names)[0] if sheet_names else None


def fetch_stock_fund_info_rows(client: SupabaseRest, as_of_date: str | None = None) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    offset = 0
    while True:
        query = urllib.parse.urlencode(
            {
                "select": "sheet_name,row_no,payload",
                "domain": "eq.stock",
                "file_key": "eq.fund_info",
                "order": "sheet_name.asc,row_no.asc",
                "limit": "1000",
                "offset": str(offset),
            },
            safe=".,()",
        )
        batch = client.get(f"manual_file_rows?{query}")
        if not batch:
            break
        records.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000

    grouped: dict[str, list[dict[str, object]]] = {}
    for item in records:
        sheet_name = str(item.get("sheet_name") or "Sheet1")
        grouped.setdefault(sheet_name, []).append(item)

    chosen = choose_effective_sheet(list(grouped), as_of_date)
    if not chosen:
        return pd.DataFrame()

    chosen_rows = sorted(grouped.get(chosen, []), key=lambda row: int(row.get("row_no") or 0))
    rows: list[dict[str, object]] = []
    for item in chosen_rows:
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        rows.append(dict(payload))
    df = pd.DataFrame(rows)
    df.attrs["fund_master_sheet_name"] = chosen
    return df


def read_fund_info_from_excel() -> pd.DataFrame:
    return (
        pd.read_excel(INPUTS["fund_info"], header=3)
        .dropna(axis=1, how="all")
        .dropna(how="all")
    )[["펀드코드", "펀드명", "지분율", "유형", "평가액"]].copy()


def parse_float(value: object, default: float | None = 0.0) -> float | None:
    text = clean_text(value).replace("+", "")
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def fmt_money(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    value = float(value)
    sign = "-" if value < 0 else ""
    return f"{sign}{abs(value) / 100_000_000:,.2f}억"


def fmt_money_1(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    value = float(value)
    sign = "-" if value < 0 else ""
    return f"{sign}{abs(value) / 100_000_000:,.1f}억"


def fmt_million(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    value = float(value)
    sign = "-" if value < 0 else ""
    return f"{sign}{abs(value) / 1_000_000:,.0f}"


def fmt_price(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.0f}"


def fmt_pct(value: float | int | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value) * 100:.{digits}f}%"


def fmt_rate_percent(value: float | int | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.{digits}f}%"


def rate_bar(value: float | int | None, limit: float) -> str:
    if value is None or pd.isna(value):
        return "<td>-</td>"
    rate = float(value)
    pct = max(min(rate / limit, 1), -1)
    width = abs(pct) * 50
    if rate >= 0:
        bar = f"<span class='bar-pos' style='left:50%;width:{width:.1f}%'></span>"
    else:
        bar = f"<span class='bar-neg' style='left:{50 - width:.1f}%;width:{width:.1f}%'></span>"
    return f"<td><div class='rate-bar'><span class='bar-zero'></span>{bar}<em>{fmt_rate_percent(rate)}</em></div></td>"


def pnl_cell(value: float | int | None) -> str:
    cls = "profit-cell" if (0 if value is None or pd.isna(value) else value) >= 0 else "loss-cell"
    return f"<td class='{cls}'>{fmt_money(value)}</td>"


def pnl_cell_1(value: float | int | None) -> str:
    cls = "profit-cell" if (0 if value is None or pd.isna(value) else value) >= 0 else "loss-cell"
    return f"<td class='{cls}'>{fmt_money_1(value)}</td>"


def signed_td(value: float | int | None, formatter=fmt_money) -> str:
    cls = "profit-cell" if (0 if value is None or pd.isna(value) else value) >= 0 else "loss-cell"
    return f"<td class='{cls}'>{formatter(value)}</td>"


def signed_pct_td(value: float | int | None, digits: int = 2) -> str:
    cls = "profit-cell" if (0 if value is None or pd.isna(value) else value) >= 0 else "loss-cell"
    return f"<td class='{cls}'>{fmt_pct(value, digits)}</td>"


def hana_color(i: int) -> str:
    palette = ["#008485", "#00a69c", "#003b5c", "#7a5c2e", "#e7663f", "#546a7b", "#0f766e", "#b45309", "#4f46e5", "#be123c"]
    return palette[i % len(palette)]


def read_inputs(
    data_source: str = "excel",
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object], dict[str, pd.DataFrame]]:
    client = supabase_client() if data_source == "supabase" else None
    if client:
        funds = fetch_stock_fund_info_rows(client, end_date)
        if funds.empty:
            raise RuntimeError("Supabase manual_file_rows에 stock/fund_info 데이터가 없습니다.")
        fund_master_sheet = str(funds.attrs.get("fund_master_sheet_name") or "")
        if "펀드명" not in funds.columns and "펀드명(약식)" in funds.columns:
            funds["펀드명"] = funds["펀드명(약식)"]
        for column, default in {
            "펀드코드": "",
            "펀드명": "",
            "지분율": 1,
            "유형": "기타",
            "평가액": 0,
            "상태": "활성",
        }.items():
            if column not in funds.columns:
                funds[column] = default
        funds = funds[funds["상태"].fillna("활성").astype(str).str.strip().ne("비활성")].copy()
        funds = funds[["펀드코드", "펀드명", "지분율", "유형", "평가액"]].copy()
    else:
        funds = read_fund_info_from_excel()
    funds["펀드코드"] = funds["펀드코드"].map(normalize_code)
    funds["펀드명"] = funds["펀드명"].astype(str).str.strip()
    funds["유형"] = funds["유형"].fillna("기타").astype(str).str.strip()
    funds["지분율"] = pd.to_numeric(funds["지분율"], errors="coerce").fillna(1)
    funds.loc[funds["지분율"] > 1, "지분율"] = funds.loc[funds["지분율"] > 1, "지분율"] / 100
    funds["평가액"] = pd.to_numeric(funds["평가액"], errors="coerce")
    funds["평가액원"] = funds["평가액"] * 1_000_000
    funds, fund_master = apply_fund_master(funds)
    if data_source == "supabase":
        fund_master = {
            **(fund_master if isinstance(fund_master, dict) else {}),
            "source": f"supabase:manual_file_rows/stock/fund_info/{fund_master_sheet}",
            "rows": int(len(funds)),
            "effective_date": fund_master_sheet if is_effective_sheet_name(fund_master_sheet) else "",
        }

    source_frames: dict[str, pd.DataFrame] = {}
    if data_source == "supabase":
        assert client is not None
        holdings_ts = fetch_kfr_rows(client, "fund_holdings", start_date=start_date, end_date=end_date)
        trades = fetch_kfr_rows(client, "fund_trades", start_date=start_date, end_date=end_date)
        holdings = fetch_kfr_rows(client, "fund_holdings", start_date=start_date, end_date=end_date, latest_only=True)
        source_frames = {"holdings_ts": holdings_ts, "trades_ts": trades}
    elif data_source == "json":
        holdings_ts = load_kfr_frame(
            KFR_DATA_DIR, "fund_holdings", start_date=start_date, end_date=end_date
        )
        trades = load_kfr_frame(
            KFR_DATA_DIR, "fund_trades", start_date=start_date, end_date=end_date
        )
        holdings = load_kfr_frame(
            KFR_DATA_DIR, "fund_holdings", start_date=start_date, end_date=end_date, latest_only=True
        )
        source_frames = {"holdings_ts": holdings_ts, "trades_ts": trades}
    else:
        raise ValueError(f"지원하지 않는 KFR 데이터 소스입니다: {data_source}")

    for df in (trades, holdings):
        for col in [c for c, dtype in df.dtypes.items() if str(dtype) in {"object", "string"}]:
            df[col] = df[col].astype(str).str.strip()

    for col in ["매매수량", "매매가격", "결제금액", "듀레이션", "매매금리"]:
        if col not in trades:
            trades[col] = pd.NA
        trades[col] = pd.to_numeric(trades[col], errors="coerce")
    for col in ["수량", "평가가격", "평가금", "취득가액", "듀레이션", "YTM", "이표율", "순자산", "지분율"]:
        if col not in holdings:
            holdings[col] = pd.NA
        holdings[col] = pd.to_numeric(holdings[col], errors="coerce")
    if "지분율" not in holdings:
        holdings["지분율"] = 1
    holdings["지분율"] = holdings["지분율"].fillna(1)
    holdings.loc[holdings["지분율"] > 1, "지분율"] = holdings.loc[holdings["지분율"] > 1, "지분율"] / 100

    for col in ["기준일", "협회펀드코드", "종목코드", "펀드명", "종목명", "자산구분", "거래구분"]:
        if col not in trades:
            trades[col] = pd.NA
    for col in ["보유일", "협회펀드코드", "종목코드", "펀드명", "종목명", "자산군", "자산구분", "포지션"]:
        if col not in holdings:
            holdings[col] = pd.NA
    trades["기준일"] = pd.to_datetime(trades["기준일"], errors="coerce")
    holdings["보유일"] = pd.to_datetime(holdings["보유일"], errors="coerce")
    trades["협회펀드코드"] = trades["협회펀드코드"].map(normalize_code)
    holdings["협회펀드코드"] = holdings["협회펀드코드"].map(normalize_code)
    trades["종목코드정규"] = trades["종목코드"].map(normalize_code)
    holdings["종목코드정규"] = holdings["종목코드"].map(normalize_code)
    active_codes = set(funds["펀드코드"])
    if active_codes:
        trades = trades[trades["협회펀드코드"].isin(active_codes)].copy()
        holdings = holdings[holdings["협회펀드코드"].isin(active_codes)].copy()
    return funds, trades, holdings, fund_master, source_frames


def prepare_holdings_frame(
    raw: pd.DataFrame,
    funds: pd.DataFrame,
    industry_large_by_code: dict[str, str],
    industry_mid_by_code: dict[str, str],
    *,
    allow_unknown_funds: bool = False,
) -> pd.DataFrame:
    codes = set(funds["펀드코드"])
    info = funds.set_index("펀드코드")
    holdings = raw.copy()
    for col in ["수량", "평가가격", "평가금", "취득가액", "듀레이션", "YTM", "이표율", "순자산", "지분율"]:
        if col in holdings:
            holdings[col] = pd.to_numeric(holdings[col], errors="coerce")
    holdings["협회펀드코드"] = holdings["협회펀드코드"].map(normalize_code)
    holdings["종목코드정규"] = holdings["종목코드"].map(normalize_code)
    if not allow_unknown_funds:
        holdings = holdings[holdings["협회펀드코드"].isin(codes)].copy()
    holdings["보유펀드명"] = holdings["협회펀드코드"].map(info["펀드명"]).fillna(holdings["펀드명"])
    if "지분율" not in holdings:
        holdings["지분율"] = holdings["협회펀드코드"].map(info["지분율"])
    holdings["지분율"] = holdings["지분율"].fillna(holdings["협회펀드코드"].map(info["지분율"])).fillna(1)
    holdings.loc[holdings["지분율"] > 1, "지분율"] = holdings.loc[holdings["지분율"] > 1, "지분율"] / 100
    holdings["우리평가금"] = holdings["평가금"].fillna(0) * holdings["지분율"]
    holdings["우리순자산"] = holdings["순자산"].fillna(0) * holdings["지분율"]
    holdings["포지션부호"] = holdings.apply(signed_position, axis=1)
    holdings["업종대분류"] = holdings["종목코드정규"].map(industry_large_by_code).fillna("미분류")
    holdings["업종중분류"] = holdings["종목코드정규"].map(industry_mid_by_code).fillna("미분류")
    holdings["업종"] = holdings["업종중분류"]
    return holdings


def prepare_trades_frame(
    raw: pd.DataFrame,
    funds: pd.DataFrame,
    fund_share_by_code: pd.Series,
    fund_investment_by_code: pd.Series,
    industry_large_by_code: dict[str, str],
    industry_mid_by_code: dict[str, str],
    *,
    allow_unknown_funds: bool = False,
) -> pd.DataFrame:
    codes = set(funds["펀드코드"])
    info = funds.set_index("펀드코드")
    trades = raw.copy()
    for col in ["매매수량", "매매가격", "결제금액", "듀레이션", "매매금리"]:
        if col in trades:
            trades[col] = pd.to_numeric(trades[col], errors="coerce")
    trades["기준일"] = pd.to_datetime(trades["기준일"], errors="coerce")
    trades["협회펀드코드"] = trades["협회펀드코드"].map(normalize_code)
    trades["종목코드정규"] = trades["종목코드"].map(normalize_code)
    if not allow_unknown_funds:
        trades = trades[trades["협회펀드코드"].isin(codes)].copy()
    trades["보유펀드명"] = trades["협회펀드코드"].map(info["펀드명"]).fillna(trades["펀드명"])
    trades["지분율"] = trades["협회펀드코드"].map(fund_share_by_code).fillna(trades["협회펀드코드"].map(info["지분율"])).fillna(1)
    trades["펀드투자금"] = trades["협회펀드코드"].map(fund_investment_by_code)
    trades["우리결제금액"] = trades["결제금액"].fillna(0) * trades["지분율"]
    trades["업종대분류"] = trades["종목코드정규"].map(industry_large_by_code).fillna("미분류")
    trades["업종중분류"] = trades["종목코드정규"].map(industry_mid_by_code).fillna("미분류")
    trades["업종"] = trades["업종중분류"]
    return trades


def read_industry_map() -> tuple[dict[str, str], dict[str, str]]:
    if not INPUTS["industry"].exists():
        return {}, {}
    industry = pd.read_excel(INPUTS["industry"]).dropna(how="all")
    if industry.empty:
        return {}, {}
    code_col = "코드" if "코드" in industry.columns else "Code" if "Code" in industry.columns else None
    large_col = "업종(대)" if "업종(대)" in industry.columns else "대분류" if "대분류" in industry.columns else None
    mid_col = "업종(중)" if "업종(중)" in industry.columns else "중분류" if "중분류" in industry.columns else None
    if not code_col:
        return {}, {}
    industry["종목코드정규"] = industry[code_col].map(normalize_code)
    industry = industry[industry["종목코드정규"].ne("")]
    large = industry[large_col].fillna("미분류").astype(str).str.strip() if large_col else pd.Series("미분류", index=industry.index)
    mid = industry[mid_col].fillna("미분류").astype(str).str.strip() if mid_col else large
    industry["업종대분류"] = large.mask(large.eq(""), "미분류")
    industry["업종중분류"] = mid.mask(mid.eq(""), "미분류")
    deduped = industry.drop_duplicates("종목코드정규")
    return (
        deduped.set_index("종목코드정규")["업종대분류"].to_dict(),
        deduped.set_index("종목코드정규")["업종중분류"].to_dict(),
    )


def load_quote_cache() -> tuple[dict[str, dict[str, float | None]], str]:
    quote_path = next((path for path in QUOTE_CANDIDATES if path.exists()), None)
    if not quote_path:
        return {}, "시세 캐시 파일 없음"
    try:
        data = json.loads(quote_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, f"시세 캐시 읽기 실패: {exc}"

    raw_stocks = data.get("stocks", data) if isinstance(data, dict) else {}
    quotes: dict[str, dict[str, float | None]] = {}
    if isinstance(raw_stocks, dict):
        for code, item in raw_stocks.items():
            norm = normalize_code(code)
            if not norm:
                continue
            if isinstance(item, dict):
                price = parse_float(item.get("price", item.get("cur_prc")), None)
                rate = parse_float(item.get("change_rate", item.get("flu_rt")), None)
            else:
                price = None
                rate = parse_float(item, None)
            quotes[norm] = {
                "price": abs(price) if price is not None else None,
                "change_rate": rate,
                "industry": item.get("industry") or item.get("upName") or "",
                "market": item.get("market") or item.get("marketName") or "",
            }
    return quotes, quote_path.name


def quote_for(row: pd.Series, quotes: dict[str, dict[str, float | None]]) -> pd.Series:
    quote = quotes.get(row.get("종목코드정규", ""), {})
    return pd.Series({"현재가": quote.get("price"), "등락율": quote.get("change_rate"), "키움업종": quote.get("industry")})


def is_equity_related(df: pd.DataFrame, asset_col: str) -> pd.Series:
    asset = df[asset_col].fillna("").astype(str)
    market = df["시장구분"].fillna("").astype(str)
    sector = df.get("업종", df.get("섹터", pd.Series("", index=df.index))).fillna("").astype(str)
    return (
        asset.eq("주식")
        | market.str.contains("주식|주가지수|코스닥|거래소상장|개별주식선물|해외파생", regex=True)
        | sector.str.contains("해외주식", regex=True)
    )


def kpi(label: str, value: str, sub: str = "") -> str:
    return f"<div class='kpi'><span>{esc(label)}</span><strong>{esc(value)}</strong><small>{esc(sub)}</small></div>"


def empty(message: str = "표시할 데이터가 없습니다.") -> str:
    return f"<div class='empty'>{esc(message)}</div>"


def pie_svg(rows: list[tuple[object, float]], size: int = 360, max_rows: int = 8) -> str:
    rows = [(str(k) if str(k) != "nan" else "미분류", float(v or 0)) for k, v in rows if pd.notna(v) and float(v or 0) > 0]
    rows = rows[: max_rows - 1] + [("기타 합계", sum(v for _, v in rows[max_rows - 1 :]))] if len(rows) > max_rows else rows
    total = sum(v for _, v in rows)
    if total <= 0:
        return empty()
    import math

    cx = cy = size / 2
    r = size / 2 - 8
    start = 0.0
    paths, legend = [], []
    for i, (label, value) in enumerate(rows):
        angle = value / total * 2 * math.pi
        end = start + angle
        x1, y1 = cx + r * math.cos(start), cy + r * math.sin(start)
        x2, y2 = cx + r * math.cos(end), cy + r * math.sin(end)
        large = 1 if angle > math.pi else 0
        color = hana_color(i)
        tooltip = esc(f"{label}: {fmt_pct(value / total)} / {fmt_money(value)}")
        paths.append(f'<path d="M {cx:.1f} {cy:.1f} L {x1:.1f} {y1:.1f} A {r:.1f} {r:.1f} 0 {large} 1 {x2:.1f} {y2:.1f} Z" fill="{color}"><title>{tooltip}</title></path>')
        mid = start + angle / 2
        lx, ly = cx + (r * 0.62) * math.cos(mid), cy + (r * 0.62) * math.sin(mid)
        if value / total >= 0.055:
            paths.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" class="pie-label">{esc(label[:8])}</text>')
        legend.append(f'<li><span style="background:{color}"></span><b>{esc(label)}</b><em>{fmt_pct(value / total)}</em><small>{fmt_money(value)}</small></li>')
        start = end
    return f"<div class='pie-wrap'><svg viewBox='0 0 {size} {size}' class='pie'>{''.join(paths)}<circle cx='{cx}' cy='{cy}' r='{r * .46:.1f}' fill='#fff'></circle></svg><ul class='legend'>{''.join(legend)}</ul></div>"


def sector_large_pie_svg(rows: list[tuple[object, float]], size: int = 500, max_rows: int = 9) -> str:
    rows = [(str(k) if str(k) != "nan" else "미분류", float(v or 0)) for k, v in rows if pd.notna(v) and float(v or 0) > 0]
    rows = sorted(rows, key=lambda x: x[1], reverse=True)
    rows = rows[: max_rows - 1] + [("기타", sum(v for _, v in rows[max_rows - 1 :]))] if len(rows) > max_rows else rows
    total = sum(v for _, v in rows)
    if total <= 0:
        return empty()
    import math

    cx = cy = size / 2
    r = size / 2 - 18
    start = -math.pi / 2
    parts = [f'<svg viewBox="0 0 {size} {size}" class="sector-pie">']
    legend = []
    callouts = []
    for i, (label, value) in enumerate(rows):
        angle = value / total * 2 * math.pi
        end = start + angle
        x1, y1 = cx + r * math.cos(start), cy + r * math.sin(start)
        x2, y2 = cx + r * math.cos(end), cy + r * math.sin(end)
        large = 1 if angle > math.pi else 0
        color = hana_color(i)
        tooltip = esc(f"{label}: {fmt_pct(value / total, 0)} / {fmt_money(value)}")
        parts.append(f'<path d="M {cx:.1f} {cy:.1f} L {x1:.1f} {y1:.1f} A {r:.1f} {r:.1f} 0 {large} 1 {x2:.1f} {y2:.1f} Z" fill="{color}" stroke="#fff" stroke-width="2"><title>{tooltip}</title></path>')
        mid = start + angle / 2
        pct = value / total
        if pct >= 0.055:
            lx, ly = cx + (r * 0.62) * math.cos(mid), cy + (r * 0.62) * math.sin(mid)
            text = esc(f"{label[:7]}, {fmt_pct(pct, 0)}")
            parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" class="slice-tag">{text}</text>')
        else:
            side = 1 if math.cos(mid) >= 0 else -1
            callouts.append({
                "label": label,
                "pct": pct,
                "side": side,
                "anchor_x": cx + (r * 0.98) * math.cos(mid),
                "anchor_y": cy + (r * 0.98) * math.sin(mid),
                "target_y": cy + (r * 1.02) * math.sin(mid),
            })
        legend.append(f'<li><span style="background:{color}"></span><b>{esc(label)}</b><em>{fmt_pct(pct, 0)}</em><small>{fmt_money(value)}</small></li>')
        start = end
    for side in (-1, 1):
        side_callouts = sorted([item for item in callouts if item["side"] == side], key=lambda item: item["target_y"])
        if not side_callouts:
            continue
        min_y, max_y, gap = 34, size - 34, 22
        for idx, item in enumerate(side_callouts):
            item["label_y"] = min(max(item["target_y"], min_y + idx * gap), max_y)
        for idx in range(1, len(side_callouts)):
            prev = side_callouts[idx - 1]
            item = side_callouts[idx]
            item["label_y"] = max(item["label_y"], prev["label_y"] + gap)
        overflow = side_callouts[-1]["label_y"] - max_y
        if overflow > 0:
            for item in side_callouts:
                item["label_y"] -= overflow
        for idx in range(len(side_callouts) - 2, -1, -1):
            item = side_callouts[idx]
            nxt = side_callouts[idx + 1]
            item["label_y"] = min(item["label_y"], nxt["label_y"] - gap)
        for item in side_callouts:
            text_x = size - 86 if side > 0 else 86
            elbow_x = cx + side * (r + 8)
            anchor = "start" if side > 0 else "end"
            line_end_x = text_x - 46 if side > 0 else text_x + 46
            text = esc(f"{str(item['label'])[:7]}, {fmt_pct(item['pct'], 0)}")
            parts.append(f'<path d="M {item["anchor_x"]:.1f} {item["anchor_y"]:.1f} L {elbow_x:.1f} {item["label_y"]:.1f} L {line_end_x:.1f} {item["label_y"]:.1f}" class="callout"></path>')
            parts.append(f'<text x="{text_x:.1f}" y="{item["label_y"] + 3:.1f}" text-anchor="{anchor}" class="slice-callout">{text}</text>')
    parts.append("</svg>")
    return "".join(parts) + f"<ul class='sector-legend'>{''.join(legend)}</ul>"


def sector_mid_bar_svg(rows: list[tuple[object, float]], all_labels: list[str], width: int = 640, max_rows: int = 18) -> str:
    values = {str(k) if str(k) != "nan" else "미분류": float(v or 0) for k, v in rows if pd.notna(k)}
    if all_labels:
        rows = sorted(((label, values.get(label, 0.0)) for label in all_labels), key=lambda x: x[1], reverse=True)[:max_rows]
    else:
        rows = sorted(values.items(), key=lambda x: x[1], reverse=True)[:max_rows]
    total = sum(values.values())
    if total <= 0:
        total = 1
    left, right, top, bottom = 148, 48, 14, 34
    row_h = 24
    height = top + bottom + row_h * len(rows)
    plot_w = width - left - right
    max_pct = max([v / total for _, v in rows] + [0.01])
    grid_max = max(0.05, (int(max_pct * 20) + 1) / 20)
    parts = [f'<svg viewBox="0 0 {width} {height}" class="sector-bar">']
    for tick in range(0, int(grid_max * 100) + 1, 5):
        x = left + plot_w * (tick / 100) / grid_max
        parts.append(f'<line x1="{x:.1f}" y1="{top - 4}" x2="{x:.1f}" y2="{height - bottom}" class="bar-grid"></line>')
        parts.append(f'<text x="{x:.1f}" y="{height - 8}" text-anchor="middle" class="bar-axis">{tick}%</text>')
    for i, (label, value) in enumerate(rows):
        pct = value / total
        y = top + i * row_h
        w = plot_w * pct / grid_max if pct > 0 else 0
        parts.append(f'<text x="{left - 9}" y="{y + 16}" text-anchor="end" class="bar-label">{esc(label[:13])}</text>')
        if w:
            parts.append(f'<rect x="{left}" y="{y + 6}" width="{w:.1f}" height="11" rx="2" fill="#00483a"></rect>')
        parts.append(f'<text x="{left + w + 7:.1f}" y="{y + 16}" class="bar-value">{fmt_pct(pct, 0)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def diverging_bar_svg(rows: list[tuple[object, float]], width: int = 1120, max_rows: int = 12) -> str:
    rows = [(str(k) if str(k) != "nan" else "미분류", float(v or 0)) for k, v in rows if pd.notna(v) and float(v or 0) != 0]
    rows = sorted(rows, key=lambda x: abs(x[1]), reverse=True)[:max_rows]
    if not rows:
        return empty()
    left, right, top, bottom = 158, 122, 16, 24
    height = 520
    available_h = height - top - bottom
    gap = 10
    bar_h = max(24, min(32, (available_h / max(len(rows), 1)) - gap))
    plot_w = width - left - right
    zero_x = left + plot_w / 2
    scale = (plot_w / 2) / (max(abs(v) for _, v in rows) or 1)
    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart">']
    parts.append(f'<line x1="{zero_x:.1f}" y1="4" x2="{zero_x:.1f}" y2="{height - bottom + 4}" class="zero"></line>')
    for i, (label, value) in enumerate(rows):
        y = top + i * (bar_h + gap)
        w = max(3, abs(value) * scale)
        x = zero_x if value >= 0 else zero_x - w
        fill = "#d92d20" if value >= 0 else "#2563eb"
        parts.append(f'<text x="0" y="{y + 18}" class="axis big-axis">{esc(label[:18])}</text>')
        parts.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="3" fill="{fill}"></rect>')
        tx = x + w + 7 if value >= 0 else x - 7
        anchor = "start" if value >= 0 else "end"
        parts.append(f'<text x="{tx:.1f}" y="{y + 18}" text-anchor="{anchor}" class="value big-axis">{fmt_money(value)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def daily_trade_svg(df: pd.DataFrame, width: int = 1120, height: int = 520) -> str:
    if df.empty:
        return empty("매매 데이터가 없습니다.")
    pivot = df.pivot_table(index="기준일", columns="거래구분", values="우리결제금액", aggfunc="sum", fill_value=0).sort_index()
    dates = list(pivot.index)
    buys = pivot["매수"] if "매수" in pivot else pd.Series(0, index=pivot.index)
    sells = pivot["매도"] if "매도" in pivot else pd.Series(0, index=pivot.index)
    max_v = max((buys + sells).max(), 1)
    left, right, top, bottom = 74, 24, 30, 54
    plot_w, plot_h = width - left - right, height - top - bottom
    bar_w = min(86, plot_w / max(len(dates), 1) * 0.62)
    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart">']
    for tick in range(3):
        y = top + plot_h * tick / 2
        val = max_v * (1 - tick / 2)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" class="gridline"></line>')
        parts.append(f'<text x="2" y="{y + 4:.1f}" class="axis daily-axis">{fmt_money(val)}</text>')
    for i, date in enumerate(dates):
        x = left + (i + 0.5) * plot_w / len(dates) - bar_w / 2
        buy_h = plot_h * buys.loc[date] / max_v
        sell_h = plot_h * sells.loc[date] / max_v
        parts.append(f'<rect x="{x:.1f}" y="{top + plot_h - buy_h:.1f}" width="{bar_w:.1f}" height="{buy_h:.1f}" rx="3" fill="#d92d20"></rect>')
        parts.append(f'<rect x="{x:.1f}" y="{top + plot_h - buy_h - sell_h:.1f}" width="{bar_w:.1f}" height="{sell_h:.1f}" rx="3" fill="#2563eb"></rect>')
        parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{height - 14}" text-anchor="middle" class="axis daily-axis">{date.strftime("%m-%d")}</text>')
    parts.append("</svg>")
    return "".join(parts)


def trade_category_svg(rows: list[tuple[object, float]], all_labels: list[str] | None = None, width: int = 1180, height: int = 390, max_rows: int = 28) -> str:
    values = {str(k) if str(k) != "nan" else "미분류": float(v or 0) for k, v in rows if pd.notna(k)}
    if all_labels:
        rows = sorted(((label, values.get(label, 0.0)) for label in all_labels), key=lambda x: x[1], reverse=True)[:max_rows]
    else:
        rows = sorted(values.items(), key=lambda x: x[1], reverse=True)[:max_rows]
    if not rows:
        return empty("업종별 매매 데이터가 없습니다.")
    left, right, top, bottom = 54, 32, 26, 76
    plot_w, plot_h = width - left - right, height - top - bottom
    max_abs = max(abs(v) for _, v in rows) or 1
    zero_y = top + plot_h / 2
    scale = (plot_h / 2 - 10) / max_abs
    step = plot_w / max(len(rows), 1)
    bar_w = max(12, min(36, step * 0.52))
    tick_count = 4
    parts = [f'<svg viewBox="0 0 {width} {height}" class="trade-category-chart">']
    for i in range(-tick_count, tick_count + 1):
        value = max_abs * i / tick_count
        y = zero_y - value * scale
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" class="gridline"></line>')
        if i != 0:
            parts.append(f'<text x="6" y="{y + 4:.1f}" class="axis trade-axis">{fmt_money(value)}</text>')
    parts.append(f'<line x1="{left}" y1="{zero_y:.1f}" x2="{width - right}" y2="{zero_y:.1f}" class="zero"></line>')
    for i, (label, value) in enumerate(rows):
        cx = left + step * (i + 0.5)
        h = max(1.0, abs(value) * scale) if value else 0.0
        y = zero_y - h if value >= 0 else zero_y
        filter_value = esc(label)
        parts.append(f'<rect x="{cx - bar_w / 2:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="#005344" class="trade-filter-target" data-trade-filter="{filter_value}"></rect>')
        label_text = esc(label[:12])
        label_y = height - 58
        parts.append(f'<text x="{cx:.1f}" y="{label_y}" text-anchor="end" transform="rotate(-42 {cx:.1f} {label_y})" class="trade-label trade-filter-target" data-trade-filter="{filter_value}">{label_text}</text>')
    parts.append("</svg>")
    return "".join(parts)


def trend_svg(series_list: list[dict[str, object]], width: int = 760, height: int = 300) -> str:
    series_list = [item for item in series_list if item.get("points")]
    if not series_list:
        return empty("시계열 데이터가 없습니다.")
    dates = sorted({point[0] for item in series_list for point in item["points"]})
    if not dates:
        return empty("시계열 데이터가 없습니다.")
    values = [float(point[1]) for item in series_list for point in item["points"] if point[1] is not None and pd.notna(point[1])]
    if not values:
        return empty("시계열 데이터가 없습니다.")
    min_v, max_v = min(values), max(values)
    if min_v == max_v:
        pad = abs(max_v) * 0.08 or 1
        min_v -= pad
        max_v += pad
    left, right, top, bottom = 64, 22, 24, 54
    plot_w, plot_h = width - left - right, height - top - bottom
    date_index = {date: i for i, date in enumerate(dates)}

    def x_for(date: pd.Timestamp) -> float:
        if len(dates) == 1:
            return left + plot_w / 2
        return left + plot_w * date_index[date] / (len(dates) - 1)

    def y_for(value: float) -> float:
        return top + plot_h - plot_h * (value - min_v) / (max_v - min_v)

    parts = [f'<svg viewBox="0 0 {width} {height}" class="timeseries-chart">']
    for i in range(5):
        value = min_v + (max_v - min_v) * i / 4
        y = y_for(value)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" class="gridline"></line>')
        parts.append(f'<text x="8" y="{y + 4:.1f}" class="axis ts-axis">{fmt_money(value)}</text>')
    for date in dates:
        x = x_for(date)
        parts.append(f'<text x="{x:.1f}" y="{height - 18}" text-anchor="middle" class="axis ts-date">{date.strftime("%m-%d")}</text>')
    for item in series_list:
        color = item.get("color", "#00483a")
        points = [(pd.Timestamp(date), float(value)) for date, value in item["points"] if pd.notna(value)]
        path = " ".join(f'{"M" if idx == 0 else "L"} {x_for(date):.1f} {y_for(value):.1f}' for idx, (date, value) in enumerate(points))
        if path:
            parts.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>')
            for date, value in points:
                parts.append(f'<circle cx="{x_for(date):.1f}" cy="{y_for(value):.1f}" r="3.2" fill="{color}"></circle>')
    legend = "".join(f'<li><span style="background:{item.get("color", "#00483a")}"></span>{esc(item.get("label", ""))}</li>' for item in series_list)
    parts.append(f'<foreignObject x="{left}" y="0" width="{plot_w}" height="24"><ul xmlns="http://www.w3.org/1999/xhtml" class="ts-legend">{legend}</ul></foreignObject>')
    parts.append("</svg>")
    return "".join(parts)


def stock_exp_weight_combo_svg(daily: pd.DataFrame, width: int = 760, height: int = 330) -> str:
    if daily.empty:
        return empty("시계열 데이터가 없습니다.")
    rows = daily.sort_values("스냅샷일")
    exp_values = [float(v) for v in rows["주식Exp"] if pd.notna(v)]
    weight_values = [float(v) for v in rows["주식비중"] if pd.notna(v)]
    if not exp_values or not weight_values:
        return empty("주식 Exp/비중 데이터가 없습니다.")
    min_exp, max_exp = min(0.0, min(exp_values)), max(exp_values)
    if min_exp == max_exp:
        max_exp = max_exp or 1.0
    min_weight, max_weight = min(0.0, min(weight_values)), max(weight_values)
    if min_weight == max_weight:
        max_weight = max_weight or 0.01
    width = max(width, len(rows) * 34 + 150)
    left, right, top, bottom = 72, 68, 42, 62
    plot_w, plot_h = width - left - right, height - top - bottom
    dates = rows["스냅샷일"].tolist()
    step = plot_w / max(len(dates), 1)
    bar_w = max(18, min(46, step * 0.46))

    def x_for(index: int) -> float:
        return left + step * (index + 0.5)

    def y_exp(value: float) -> float:
        return top + plot_h - plot_h * (value - min_exp) / (max_exp - min_exp)

    def y_weight(value: float) -> float:
        return top + plot_h - plot_h * (value - min_weight) / (max_weight - min_weight)

    parts = [f'<div class="ts-chart-scroll"><svg viewBox="0 0 {width} {height}" class="timeseries-combo-chart" style="width:{width}px;max-width:none">']
    parts.append('<text x="18" y="20" class="ts-axis">주식 Exp(좌)</text>')
    parts.append(f'<text x="{width - 12}" y="20" text-anchor="end" class="ts-axis">주식비중(우)</text>')
    for i in range(5):
        exp_value = min_exp + (max_exp - min_exp) * i / 4
        weight_value = min_weight + (max_weight - min_weight) * i / 4
        y = y_exp(exp_value)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" class="bar-grid"></line>')
        parts.append(f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" class="ts-axis">{fmt_money_1(exp_value)}</text>')
        parts.append(f'<text x="{width - 8}" y="{y_weight(weight_value) + 4:.1f}" text-anchor="end" class="ts-axis">{fmt_pct(weight_value, 1)}</text>')
    parts.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{width - right}" y2="{top + plot_h}" class="zero"></line>')
    line_points = []
    for idx, (_, row) in enumerate(rows.iterrows()):
        x = x_for(idx)
        exp = float(row["주식Exp"]) if pd.notna(row["주식Exp"]) else 0.0
        weight = float(row["주식비중"]) if pd.notna(row["주식비중"]) else 0.0
        y = y_exp(exp)
        h = top + plot_h - y
        parts.append(f'<rect x="{x - bar_w / 2:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{max(1, h):.1f}" rx="3" fill="#008485"></rect>')
        parts.append(f'<text x="{x:.1f}" y="{y + max(14, h / 2):.1f}" text-anchor="middle" class="ts-bar-label">{fmt_money_1(exp)}</text>')
        line_points.append((x, y_weight(weight)))
        parts.append(f'<text x="{x:.1f}" y="{height - 24}" text-anchor="middle" class="ts-date">{row["스냅샷일"]:%m-%d}</text>')
    path = " ".join(f'{"M" if idx == 0 else "L"} {x:.1f} {y:.1f}' for idx, (x, y) in enumerate(line_points))
    if path:
        parts.append(f'<path d="{path}" fill="none" stroke="#12372d" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>')
        for idx, (x, y) in enumerate(line_points):
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#12372d" stroke="#fff" stroke-width="1.5"></circle>')
            weight = float(rows.iloc[idx]["주식비중"]) if pd.notna(rows.iloc[idx]["주식비중"]) else 0.0
            parts.append(f'<text x="{x:.1f}" y="{y - 9:.1f}" text-anchor="middle" class="ts-line-label">{fmt_pct(weight, 1)}</text>')
    parts.append('<foreignObject x="72" y="6" width="420" height="24"><ul xmlns="http://www.w3.org/1999/xhtml" class="ts-legend"><li><span style="background:#008485"></span>주식 Exp</li><li><span style="background:#12372d"></span>주식비중</li></ul></foreignObject>')
    parts.append("</svg></div>")
    return "".join(parts)


def mini_bar(value: float | int | None, limit: float, label: str | None = None) -> str:
    if value is None or pd.isna(value):
        return "<td>-</td>"
    value = float(value)
    width = min(100, abs(value) / limit * 100) if limit else 0
    cls = "profit-cell" if value >= 0 else "loss-cell"
    text = label if label is not None else fmt_money(value)
    return f"<td><div class='mini-bar'><span class='{cls}' style='width:{width:.1f}%'></span><em class='{cls}'>{esc(text)}</em></div></td>"


def table_html(headers: list[str], rows: list[list[str]], css_class: str = "table-wrap") -> str:
    if not rows:
        return empty()
    head = "".join(f"<th data-sort-index='{i}'>{esc(h)}</th>" for i, h in enumerate(headers))
    body = "".join("<tr>" + "".join(cell for cell in row) + "</tr>" for row in rows)
    return f"<div class='{css_class}'><table class='sortable-table'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def holding_table_html(rows: list[list[str]]) -> str:
    if not rows:
        return empty()
    colgroup = """
      <colgroup>
        <col style="width:132px">
        <col style="width:62px">
        <col style="width:66px">
        <col style="width:74px">
        <col style="width:84px">
        <col style="width:58px">
        <col style="width:82px">
        <col style="width:82px">
        <col style="width:76px">
        <col style="width:98px">
        <col style="width:82px">
      </colgroup>
    """
    headers = ["종목명", "편입비", "등락율", "예상PL", "업종", "보유펀드", "평가액", "취득원가", "취득단가", "평가손익(전일기준)", "평단수익률"]
    head = "".join(f"<th data-sort-index='{i}'>{esc(h)}</th>" for i, h in enumerate(headers))
    body = "".join("<tr>" + "".join(cell for cell in row) + "</tr>" for row in rows)
    return f"<div class='table-wrap holding-detail'><table class='sortable-table'>{colgroup}<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def fund_pl_table_html(rows: list[list[str]]) -> str:
    if not rows:
        return empty()
    colgroup = """
      <colgroup>
        <col style="width:78px">
        <col style="width:38px">
        <col style="width:52px">
        <col style="width:58px">
        <col style="width:72px">
        <col style="width:72px">
        <col style="width:62px">
        <col style="width:46px">
        <col style="width:66px">
        <col style="width:46px">
      </colgroup>
    """
    head = """
      <tr>
        <th rowspan="2" data-sort-index="0">펀드명</th>
        <th rowspan="2" data-sort-index="1">종목수</th>
        <th rowspan="2" data-sort-index="2">등락율</th>
        <th rowspan="2" data-sort-index="3">주식PL</th>
        <th rowspan="2" data-sort-index="4">당행 평가액</th>
        <th rowspan="2" data-sort-index="5">펀드 Exp</th>
        <th colspan="2">주식</th>
        <th colspan="2">채권 및 현금</th>
      </tr>
      <tr>
        <th data-sort-index="6">Exp</th>
        <th data-sort-index="7">비중</th>
        <th data-sort-index="8">Exp</th>
        <th data-sort-index="9">비중</th>
      </tr>
    """
    body = "".join("<tr>" + "".join(cell for cell in row) + "</tr>" for row in rows)
    return f"<div class='table-wrap fund-pl'><table class='sortable-table'>{colgroup}<thead>{head}</thead><tbody>{body}</tbody></table></div>"


def signed_position(row: pd.Series) -> float:
    return -1.0 if row.get("포지션") == "매도" else 1.0


def safe_sum(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.sum())


def holding_breakdowns(df: pd.DataFrame, amount_col: str) -> dict[str, str]:
    breakdowns = {}
    for key, rows in df.groupby(["종목코드정규", "종목명", "포지션"], dropna=False):
        total = rows[amount_col].sum()
        lines = []
        for fund, amount in rows.groupby("보유펀드명")[amount_col].sum().sort_values(ascending=False).items():
            lines.append(f"{fund}: {fmt_money(amount)} ({fmt_pct(amount / total if total else 0)})")
        breakdowns["|".join(map(str, key))] = "\n".join(lines)
    return breakdowns


def net_trade_breakdowns(df: pd.DataFrame) -> dict[str, str]:
    breakdowns = {}
    for key, rows in df.groupby(["종목코드정규", "종목명"], dropna=False):
        signed = rows.assign(순매수금액=rows["우리결제금액"] * rows["거래구분"].map({"매수": 1, "매도": -1}).fillna(0))
        by_fund = signed.groupby("보유펀드명")["순매수금액"].sum()
        total_abs = by_fund.abs().sum()
        lines = []
        for fund, amount in by_fund.sort_values(key=lambda s: s.abs(), ascending=False).items():
            if amount:
                lines.append(f"{fund}: {fmt_money(amount)} ({fmt_pct(abs(amount) / total_abs if total_abs else 0)})")
        breakdowns["|".join(map(str, key))] = "\n".join(lines)
    return breakdowns


def holding_table(df: pd.DataFrame, position: str, denominator: float | None = None, limit: int = 20) -> str:
    rows = df[df["포지션"] == position].copy()
    if rows.empty:
        return empty(f"{position} 포지션 보유내역이 없습니다.")
    tips = holding_breakdowns(rows, "우리평가금")
    summary = (
        rows.groupby(["종목코드정규", "종목명", "업종", "포지션"], dropna=False)
        .agg(
            평가금=("우리평가금", "sum"),
            취득원가=("우리취득가액", "sum"),
            평가손익=("평가손익", "sum"),
            시장PL=("시장PL", "sum"),
            PL=("PL", "sum"),
            우리수량=("우리수량", "sum"),
            보유펀드수=("보유펀드명", "nunique"),
        )
        .reset_index()
    )
    summary["편입비"] = summary["평가금"] / denominator if denominator else pd.NA
    if position == "매도":
        summary["편입비"] = -summary["편입비"].abs()
    summary["평단가"] = summary["취득원가"] / summary["우리수량"].replace({0: pd.NA})
    summary["평단수익률"] = summary["평가금"] / summary["취득원가"].replace({0: pd.NA}) - 1
    summary["등락율"] = summary["시장PL"] / summary["평가금"].replace({0: pd.NA})
    summary = summary.sort_values("평가금", ascending=False).head(limit)
    body = []
    for _, row in summary.iterrows():
        key = "|".join(map(str, [row["종목코드정규"], row["종목명"], row["포지션"]]))
        tip = tips.get(key, "")
        body.append([
            f"<td class='name-cell'>{esc(row['종목명'])}</td>",
            f"<td>{fmt_pct(row['편입비'])}</td>",
            rate_bar(row["등락율"] * 100 if pd.notna(row["등락율"]) else None, 5),
            signed_td(row["PL"]),
            f"<td>{esc(row['업종'])}</td>",
            f"<td><button type='button' class='fund-count-button' data-holding-key='{esc(key)}'>{int(row['보유펀드수']):,}</button><span class='sr-search'>{esc(tip)}</span></td>",
            f"<td>{fmt_money(row['평가금'])}</td>",
            f"<td>{fmt_money(row['취득원가'])}</td>",
            f"<td>{fmt_price(row['평단가'])}</td>",
            signed_td(row["평가손익"]),
            signed_pct_td(row["평단수익률"]),
        ])
    return holding_table_html(body)


def holding_detail_records(df: pd.DataFrame, position: str, denominator: float | None = None) -> list[dict[str, object]]:
    rows = df[df["포지션"] == position].copy()
    if rows.empty:
        return []
    summary = (
        rows.groupby(["종목코드정규", "종목명", "업종", "포지션"], dropna=False)
        .agg(
            평가금=("우리평가금", "sum"),
            취득원가=("우리취득가액", "sum"),
            평가손익=("평가손익", "sum"),
            시장PL=("시장PL", "sum"),
            PL=("PL", "sum"),
            우리수량=("우리수량", "sum"),
            보유펀드수=("보유펀드명", "nunique"),
        )
        .reset_index()
    )
    summary["편입비"] = summary["평가금"] / denominator if denominator else pd.NA
    if position == "매도":
        summary["편입비"] = -summary["편입비"].abs()
    summary["평단가"] = summary["취득원가"] / summary["우리수량"].replace({0: pd.NA})
    summary["평단수익률"] = summary["평가금"] / summary["취득원가"].replace({0: pd.NA}) - 1
    summary["등락율"] = summary["시장PL"] / summary["평가금"].replace({0: pd.NA})
    summary = summary.sort_values("평가금", ascending=False)
    records = []
    for _, row in summary.iterrows():
        key = "|".join(map(str, [row["종목코드정규"], row["종목명"], row["포지션"]]))
        detail_rows = rows[
            (rows["종목코드정규"].astype(str) == str(row["종목코드정규"]))
            & (rows["종목명"].astype(str) == str(row["종목명"]))
            & (rows["포지션"].astype(str) == str(row["포지션"]))
        ].copy()
        fund_details = []
        for fund_name, fund_rows in detail_rows.groupby("보유펀드명", dropna=False):
            fund_eval = fund_rows["우리평가금"].sum()
            fund_cost = fund_rows["우리취득가액"].sum()
            fund_qty = fund_rows["우리수량"].sum()
            fund_denominator = fund_rows["펀드투자금"].dropna()
            fund_weight = fund_eval / fund_denominator.iloc[0] if not fund_denominator.empty and fund_denominator.iloc[0] else pd.NA
            if position == "매도" and pd.notna(fund_weight):
                fund_weight = -abs(fund_weight)
            fund_details.append({
                "fund": str(fund_name),
                "weight": float(fund_weight) if pd.notna(fund_weight) else None,
                "cost": float(fund_cost) if pd.notna(fund_cost) else 0.0,
                "eval": float(fund_eval) if pd.notna(fund_eval) else 0.0,
                "profit": float(fund_eval - fund_cost) if pd.notna(fund_eval - fund_cost) else 0.0,
                "avgPrice": float(fund_cost / fund_qty) if fund_qty else None,
                "return": float(fund_eval / fund_cost - 1) if fund_cost else None,
            })
        records.append({
            "key": key,
            "name": str(row["종목명"]),
            "weight": float(row["편입비"]) if pd.notna(row["편입비"]) else None,
            "rate": float(row["등락율"]) if pd.notna(row["등락율"]) else None,
            "pl": float(row["PL"]) if pd.notna(row["PL"]) else 0.0,
            "sector": str(row["업종"]),
            "fundCount": int(row["보유펀드수"]),
            "eval": float(row["평가금"]) if pd.notna(row["평가금"]) else 0.0,
            "cost": float(row["취득원가"]) if pd.notna(row["취득원가"]) else 0.0,
            "avgPrice": float(row["평단가"]) if pd.notna(row["평단가"]) else None,
            "profit": float(row["평가손익"]) if pd.notna(row["평가손익"]) else 0.0,
            "return": float(row["평단수익률"]) if pd.notna(row["평단수익률"]) else None,
            "portfolioWeight": float(row["편입비"]) if pd.notna(row["편입비"]) else None,
            "details": sorted(fund_details, key=lambda item: abs(item["eval"] or 0), reverse=True),
        })
    return records


def top20_holdings_table(df: pd.DataFrame, denominator: float | None = None, limit: int = 20) -> str:
    if df.empty:
        return empty("보유내역 TOP20 데이터가 없습니다.")
    rows = df.copy()
    rows["포지션부호"] = rows.apply(signed_position, axis=1)
    rows["순노출"] = rows["우리평가금"] * rows["포지션부호"]
    summary = (
        rows.groupby(["종목코드정규", "종목명"], dropna=False)
        .agg(
            Exp=("순노출", "sum"),
            Gross=("우리평가금", lambda series: series.abs().sum()),
            시장PL=("시장PL", "sum"),
            PL=("PL", "sum"),
            펀드수=("보유펀드명", "nunique"),
        )
        .reset_index()
    )
    summary["비중"] = summary["Exp"] / denominator if denominator else pd.NA
    summary["등락율"] = summary["시장PL"] / summary["Gross"].replace({0: pd.NA})
    summary = summary.sort_values("Exp", key=lambda series: series.abs(), ascending=False).head(limit)
    body = []
    for _, row in summary.iterrows():
        name = esc(row["종목명"])
        body.append([
            f"<td class='name-cell has-tip' title='{name}'>{name}</td>",
            signed_pct_td(row["비중"]),
            f"<td>{int(row['펀드수']):,}</td>",
            signed_td(row["Exp"]),
            rate_bar(row["등락율"] * 100 if pd.notna(row["등락율"]) else None, 5),
            pnl_cell(row["PL"]),
        ])
    return table_html(["종목명", "비중", "펀드수", "Exp", "등락율", "손익"], body, "table-wrap top20-table")


def trade_table(df: pd.DataFrame, limit: int = 24) -> str:
    rows = df[df["우리결제금액"].abs() >= 50_000_000].copy()
    if rows.empty:
        return empty("주식/주식관련 매매내역이 없습니다.")
    rows = rows.sort_values(["기준일", "우리결제금액"], ascending=[False, False]).head(limit)
    body = []
    for _, row in rows.iterrows():
        side_class = "profit-cell" if row["거래구분"] == "매수" else "loss-cell" if row["거래구분"] == "매도" else ""
        body.append([
            f"<td>{esc(row['기준일'])}</td>",
            f"<td>{esc(row['보유펀드명'])}</td>",
            f"<td class='name-cell'>{esc(row['종목명'])}</td>",
            f"<td>{esc(row['업종'])}</td>",
            f"<td class='{side_class}'>{esc(row['거래구분'])}</td>",
            f"<td class='{side_class}'>{fmt_money(row['우리결제금액'])}</td>",
        ])
    return table_html(["기준일", "펀드명", "종목명", "업종", "구분", "결제금액"], body, "table-wrap tall")


def net_trade_table(df: pd.DataFrame, direction: str, limit: int = 24) -> str:
    if df.empty:
        return empty()
    tips = net_trade_breakdowns(df)
    signed = df.assign(순매수금액=df["우리결제금액"] * df["거래구분"].map({"매수": 1, "매도": -1}).fillna(0))
    summary = (
        signed.groupby(["종목코드정규", "종목명", "업종"], dropna=False)
        .agg(순매수금액=("순매수금액", "sum"), 펀드수=("보유펀드명", "nunique"))
        .reset_index()
    )
    if direction == "buy":
        summary = summary[summary["순매수금액"] > 0].sort_values("순매수금액", ascending=False)
    else:
        summary = summary[summary["순매수금액"] < 0].sort_values("순매수금액")
    summary = summary.head(limit)
    if summary.empty:
        return empty("해당 순매매 종목이 없습니다.")
    body = []
    for _, row in summary.iterrows():
        key = "|".join(map(str, [row["종목코드정규"], row["종목명"]]))
        name = esc(row["종목명"])
        body.append([
            f"<td class='name-cell has-tip' title='{esc(tips.get(key, ''))}'><button type='button' class='trade-filter-link' data-trade-filter='{name}'>{name}</button></td>",
            f"<td>{esc(row['업종'])}</td>",
            f"<td>{int(row['펀드수']):,}</td>",
            signed_td(row["순매수금액"]),
        ])
    return table_html(["종목명", "업종", "펀드", "순매수금액"], body)


def direct_stock_table(df: pd.DataFrame, title: str, panel_class: str = "") -> str:
    if df.empty:
        return empty(f"{title} 데이터가 없습니다.")
    rows = df.sort_values("평가액", ascending=False, na_position="last")
    body = []
    for _, row in rows.iterrows():
        body.append([
            f"<td class='name-cell'>{esc(row['종목명'])}</td>",
            f"<td>{fmt_price(row['보유수량'])}</td>",
            f"<td>{fmt_price(row.get('현재가'))}</td>",
            f"<td>{fmt_money(row.get('평가액'))}</td>",
            rate_bar(row.get("등락율"), 10),
            pnl_cell_1(row.get("PL")),
        ])
    for _ in range(max(0, 8 - len(body))):
        body.append(["<td>&nbsp;</td>", "<td></td>", "<td></td>", "<td></td>", "<td></td>", "<td></td>"])
    total_eval = safe_sum(rows["평가액"])
    total_pl = safe_sum(rows["PL"])
    body.append([
        "<td class='total-label'>합계</td>",
        f"<td>{fmt_price(safe_sum(rows['보유수량']))}</td>",
        "<td></td>",
        f"<td>{fmt_money(total_eval)}</td>",
        "<td></td>",
        pnl_cell_1(total_pl),
    ])
    cls = f"panel {panel_class}".strip()
    return f"<article class='{cls}'><div class='panel-title'><h4>{esc(title)}</h4><span>8행 슬롯 + 합계</span></div>" + table_html(["종목명", "수량", "주가", "평가액", "등락율", "PL"], body, "table-wrap direct") + "</article>"


def fund_pl_table(
    df: pd.DataFrame,
    all_holdings: pd.DataFrame,
    fund_catalog: pd.DataFrame | None = None,
    highlight_fund: str | None = None,
) -> str:
    if (df.empty or "PL" not in df) and (fund_catalog is None or fund_catalog.empty):
        return empty("시세 캐시가 없어 펀드별 PL을 계산할 수 없습니다.")

    if fund_catalog is not None and not fund_catalog.empty:
        summary = (
            fund_catalog[["펀드명"]]
            .rename(columns={"펀드명": "보유펀드명"})
            .dropna(subset=["보유펀드명"])
            .drop_duplicates(subset=["보유펀드명"], keep="first")
            .copy()
        )
        summary["펀드투자금"] = 0.0
        summary["펀드Exp"] = 0.0
        summary["Exposure"] = 0.0
        summary["PL"] = 0.0
        summary["종목수"] = 0
    else:
        summary = pd.DataFrame(columns=["보유펀드명", "펀드투자금", "펀드Exp", "Exposure", "PL", "종목수"])

    if not df.empty and "PL" in df:
        stock_rows = df.copy()
        stock_rows["주식NetExp"] = stock_rows["우리평가금"] * stock_rows.apply(signed_position, axis=1)
        stock_summary = (
            stock_rows.groupby("보유펀드명", dropna=False)
            .agg(Exposure=("주식NetExp", "sum"), PL=("PL", "sum"), 종목수=("종목코드정규", "nunique"))
            .reset_index()
        )
        if summary.empty:
            summary = stock_summary
        else:
            summary = summary.merge(stock_summary, on="보유펀드명", how="outer", suffixes=("", "_stock"))
            for column in ("Exposure", "PL", "종목수"):
                summary[column] = summary[f"{column}_stock"].fillna(summary[column]).fillna(0)
                summary.drop(columns=[f"{column}_stock"], inplace=True)

    if not all_holdings.empty and "우리순자산" in all_holdings:
        investment_by_fund = all_holdings.groupby("보유펀드명", dropna=False)["우리순자산"].sum()
        summary["펀드투자금"] = summary["보유펀드명"].map(investment_by_fund).fillna(summary.get("펀드투자금", 0)).fillna(0)
    if not all_holdings.empty and "우리평가금" in all_holdings:
        fund_exp_by_fund = all_holdings.groupby("보유펀드명", dropna=False)["우리평가금"].sum()
        summary["펀드Exp"] = summary["보유펀드명"].map(fund_exp_by_fund).fillna(summary.get("펀드Exp", 0)).fillna(0)
    summary["펀드투자금"] = summary["펀드투자금"].replace(0, pd.NA).fillna(summary["Exposure"])
    summary["펀드Exp"] = summary["펀드Exp"].replace(0, pd.NA).fillna(summary["Exposure"])
    summary["주식비중"] = summary["Exposure"] / summary["펀드투자금"].replace({0: pd.NA})
    summary["기타Exp"] = summary["펀드Exp"] - summary["Exposure"]
    summary["기타비중"] = summary["기타Exp"] / summary["펀드투자금"].replace({0: pd.NA})
    summary["전체비중"] = summary["주식비중"].fillna(0) + summary["기타비중"].fillna(0)
    summary["펀드투자금대비"] = summary["펀드Exp"] / summary["펀드투자금"].replace({0: pd.NA})
    summary["등락율"] = summary["PL"] / summary["펀드투자금"].replace({0: pd.NA})
    summary = summary.sort_values("등락율", ascending=False, na_position="last")
    body = []
    for _, row in summary.iterrows():
        tr_class = " class='highlight-row'" if highlight_fund and row["보유펀드명"] == highlight_fund else ""
        body.append([
            f"<td{tr_class}>{esc(row['보유펀드명'])}</td>",
            f"<td>{int(row['종목수']):,}</td>",
            rate_bar(row["등락율"] * 100 if pd.notna(row["등락율"]) else None, 5),
            signed_td(row["PL"], fmt_money_1),
            f"<td>{fmt_money_1(row['펀드투자금'])}</td>",
            f"<td>{fmt_money_1(row['펀드Exp'])}</td>",
            f"<td>{fmt_money_1(row['Exposure'])}</td>",
            f"<td>{fmt_pct(row['주식비중'], 1)}</td>",
            f"<td>{fmt_money_1(row['기타Exp'])}</td>",
            f"<td>{fmt_pct(row['기타비중'], 1)}</td>",
        ])
    total_exposure = summary["Exposure"].sum()
    total_pl = summary["PL"].sum()
    total_fund_value = summary["펀드투자금"].sum() if "펀드투자금" in summary else total_exposure
    total_fund_exp = summary["펀드Exp"].sum() if "펀드Exp" in summary else total_exposure
    total_other_exp = summary["기타Exp"].sum() if "기타Exp" in summary else 0
    total_stock_weight = total_exposure / total_fund_value if total_fund_value else pd.NA
    total_other_weight = total_other_exp / total_fund_value if total_fund_value else pd.NA
    total_weight = (0 if pd.isna(total_stock_weight) else total_stock_weight) + (0 if pd.isna(total_other_weight) else total_other_weight)
    total_fund_weight = total_fund_exp / total_fund_value if total_fund_value else pd.NA
    total_rate = total_pl / total_fund_value if total_fund_value else pd.NA
    body.append([
        "<td class='total-label'>합계</td>",
        f"<td>{int(summary['종목수'].sum()):,}</td>",
        rate_bar(total_rate * 100 if pd.notna(total_rate) else None, 5),
        signed_td(total_pl, fmt_money_1),
        f"<td>{fmt_money_1(total_fund_value)}</td>",
        f"<td>{fmt_money_1(total_fund_exp)}</td>",
        f"<td>{fmt_money_1(total_exposure)}</td>",
        f"<td>{fmt_pct(total_stock_weight, 1)}</td>",
        f"<td>{fmt_money_1(total_other_exp)}</td>",
        f"<td>{fmt_pct(total_other_weight, 1)}</td>",
    ])
    return fund_pl_table_html(body)


def json_number(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def quote_sensitive_payload(
    stock_holdings: pd.DataFrame,
    all_holdings: pd.DataFrame,
    investment_stocks: pd.DataFrame,
    product_stocks: pd.DataFrame,
    fund_catalog: pd.DataFrame,
) -> dict[str, object]:
    stock_rows: list[dict[str, object]] = []
    if not stock_holdings.empty:
        for _, row in stock_holdings.iterrows():
            stock_rows.append({
                "fundCode": str(row.get("협회펀드코드") or ""),
                "fund": str(row.get("보유펀드명") or ""),
                "code": normalize_code(row.get("종목코드정규") or row.get("종목코드")),
                "name": str(row.get("종목명") or ""),
                "sector": str(row.get("업종") or ""),
                "sectorLarge": str(row.get("업종대분류") or ""),
                "position": str(row.get("포지션") or ""),
                "sign": float(row.get("포지션부호") or signed_position(row)),
                "eval": json_number(row.get("우리평가금")) or 0.0,
                "cost": json_number(row.get("우리취득가액")) or 0.0,
                "profit": json_number(row.get("평가손익")) or 0.0,
                "qty": json_number(row.get("우리수량")) or 0.0,
                "fundInvestment": json_number(row.get("펀드투자금")),
            })

    fund_bases: list[dict[str, object]] = []
    if not all_holdings.empty:
        grouped = (
            all_holdings.groupby(["협회펀드코드", "보유펀드명"], dropna=False)
            .agg(fundInvestment=("우리순자산", "sum"), fundExp=("우리평가금", "sum"))
            .reset_index()
        )
        for _, row in grouped.iterrows():
            fund_bases.append({
                "fundCode": str(row.get("협회펀드코드") or ""),
                "fund": str(row.get("보유펀드명") or ""),
                "fundInvestment": json_number(row.get("fundInvestment")) or 0.0,
                "fundExp": json_number(row.get("fundExp")) or 0.0,
            })

    def direct_rows(frame: pd.DataFrame, kind: str) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        if frame.empty:
            return rows
        for _, row in frame.iterrows():
            rows.append({
                "kind": kind,
                "code": normalize_code(row.get("종목코드정규") or row.get("종목코드")),
                "name": str(row.get("종목명") or ""),
                "qty": json_number(row.get("보유수량")) or 0.0,
            })
        return rows

    catalog: list[dict[str, object]] = []
    if fund_catalog is not None and not fund_catalog.empty:
        for _, row in fund_catalog.iterrows():
            code = normalize_code(row.get("펀드코드"))
            if not code:
                continue
            catalog.append({
                "fundCode": code,
                "fund": str(row.get("펀드명") or ""),
                "type": str(row.get("유형") or ""),
            })

    return {
        "stockPositions": stock_rows,
        "fundBases": fund_bases,
        "directStocks": direct_rows(investment_stocks, "investment") + direct_rows(product_stocks, "product"),
        "fundCatalog": catalog,
    }


def build_time_series(
    funds: pd.DataFrame,
    industry_large_by_code: dict[str, str],
    industry_mid_by_code: dict[str, str],
    source_frames: dict[str, pd.DataFrame] | None = None,
) -> dict[str, object]:
    holding_frames = []
    source_frames = source_frames or {}
    if "holdings_ts" in source_frames and not source_frames["holdings_ts"].empty:
        for snapshot_date, raw in source_frames["holdings_ts"].groupby("스냅샷일", dropna=False):
            frame = prepare_holdings_frame(
                raw.drop(columns=["스냅샷일", "원천파일"], errors="ignore"),
                funds,
                industry_large_by_code,
                industry_mid_by_code,
            )
            if frame.empty:
                continue
            frame["스냅샷일"] = pd.to_datetime(snapshot_date, errors="coerce")
            frame["원천파일"] = raw["원천파일"].iloc[0] if "원천파일" in raw and not raw.empty else "supabase"
            holding_frames.append(frame)
    if holding_frames:
        ts_holdings = pd.concat(holding_frames, ignore_index=True)
    else:
        ts_holdings = pd.DataFrame()

    if ts_holdings.empty:
        return {"dates": [], "holdings": pd.DataFrame(), "trades": pd.DataFrame()}

    latest_holdings = ts_holdings[ts_holdings["스냅샷일"] == ts_holdings["스냅샷일"].max()].copy()
    fund_share_by_code = latest_holdings.groupby("협회펀드코드", dropna=False)["지분율"].first()
    fund_investment_by_code = latest_holdings.groupby("협회펀드코드", dropna=False)["우리순자산"].sum()

    trade_frames = []
    if "trades_ts" in source_frames and not source_frames["trades_ts"].empty:
        raw = source_frames["trades_ts"]
        frame = prepare_trades_frame(
            raw.drop(columns=["스냅샷일", "원천파일"], errors="ignore"),
            funds,
            fund_share_by_code,
            fund_investment_by_code,
            industry_large_by_code,
            industry_mid_by_code,
        )
        if not frame.empty:
            frame["원천파일"] = "supabase"
            trade_frames.append(frame)
    ts_trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()

    stock_holdings = ts_holdings[is_equity_related(ts_holdings, "자산군")].copy()
    if not stock_holdings.empty:
        stock_holdings["주식NetExp"] = stock_holdings["우리평가금"] * stock_holdings["포지션부호"]
    daily_total = (
        ts_holdings.groupby("스냅샷일", dropna=False)
        .agg(당행평가액=("우리순자산", "sum"), 펀드Exp=("우리평가금", "sum"), 펀드수=("보유펀드명", "nunique"), 원천파일=("원천파일", "first"))
        .reset_index()
    )
    if stock_holdings.empty:
        stock_daily = pd.DataFrame(columns=["스냅샷일", "주식Exp", "주식Gross", "보유종목수"])
    else:
        stock_daily = (
            stock_holdings.groupby("스냅샷일", dropna=False)
            .agg(주식Exp=("주식NetExp", "sum"), 주식Gross=("우리평가금", "sum"), 보유종목수=("종목코드정규", "nunique"))
            .reset_index()
        )
    daily = daily_total.merge(stock_daily, on="스냅샷일", how="left").fillna({"주식Exp": 0.0, "주식Gross": 0.0, "보유종목수": 0})
    daily["기타Exp"] = daily["펀드Exp"] - daily["주식Exp"]
    daily["주식비중"] = daily["주식Exp"] / daily["당행평가액"].replace({0: pd.NA})
    daily = daily.sort_values("스냅샷일")

    fund_daily = pd.DataFrame()
    if not ts_holdings.empty:
        all_fund = (
            ts_holdings.groupby(["스냅샷일", "보유펀드명"], dropna=False)
            .agg(당행평가액=("우리순자산", "sum"), 펀드Exp=("우리평가금", "sum"))
            .reset_index()
        )
        stock_fund = (
            stock_holdings.groupby(["스냅샷일", "보유펀드명"], dropna=False)
            .agg(주식Exp=("주식NetExp", "sum"), 종목수=("종목코드정규", "nunique"))
            .reset_index()
            if not stock_holdings.empty else pd.DataFrame(columns=["스냅샷일", "보유펀드명", "주식Exp", "종목수"])
        )
        fund_daily = all_fund.merge(stock_fund, on=["스냅샷일", "보유펀드명"], how="left").fillna({"주식Exp": 0.0, "종목수": 0})
        fund_daily["주식비중"] = fund_daily["주식Exp"] / fund_daily["당행평가액"].replace({0: pd.NA})

    stock_daily_by_name = pd.DataFrame()
    if not stock_holdings.empty:
        stock_daily_by_name = (
            stock_holdings.groupby(["스냅샷일", "종목코드정규", "종목명"], dropna=False)
            .agg(Exp=("주식NetExp", "sum"), 펀드수=("보유펀드명", "nunique"))
            .reset_index()
        )
        denom = daily.set_index("스냅샷일")["당행평가액"]
        stock_daily_by_name["편입비"] = stock_daily_by_name["스냅샷일"].map(denom)
        stock_daily_by_name["편입비"] = stock_daily_by_name["Exp"] / stock_daily_by_name["편입비"].replace({0: pd.NA})

    stock_trades = pd.DataFrame()
    if not ts_trades.empty:
        stock_trades = ts_trades[is_equity_related(ts_trades, "자산구분") & ts_trades["거래구분"].isin(["매수", "매도"])].copy()
        stock_trades["순매수금액"] = stock_trades["우리결제금액"] * stock_trades["거래구분"].map({"매수": 1, "매도": -1}).fillna(0)

    return {
        "dates": daily["스냅샷일"].tolist(),
        "holdings": ts_holdings,
        "stock_holdings": stock_holdings,
        "trades": stock_trades,
        "daily": daily,
        "fund_daily": fund_daily,
        "stock_daily": stock_daily_by_name,
        "files": {
            "holdings": sorted(set(source_frames.get("holdings_ts", pd.DataFrame()).get("원천파일", pd.Series(dtype=str)).dropna().astype(str))),
            "trades": sorted(set(source_frames.get("trades_ts", pd.DataFrame()).get("원천파일", pd.Series(dtype=str)).dropna().astype(str))),
        },
    }


def time_series_table(headers: list[str], rows: list[list[str]], css_class: str = "table-wrap timeseries-table") -> str:
    return table_html(headers, rows, css_class) if rows else empty("표시할 시계열 데이터가 없습니다.")


def make_time_series_tab(ts: dict[str, object]) -> str:
    daily: pd.DataFrame = ts.get("daily", pd.DataFrame())
    fund_daily: pd.DataFrame = ts.get("fund_daily", pd.DataFrame())
    stock_daily: pd.DataFrame = ts.get("stock_daily", pd.DataFrame())
    trades: pd.DataFrame = ts.get("trades", pd.DataFrame())
    if daily.empty:
        return "<section class='tab-panel' data-panel='timeseries'><div class='section-title'><h3>시계열</h3><span>보유현황 파일을 추가하면 표시됩니다.</span></div>" + empty("시계열 데이터가 없습니다.") + "</section>"

    latest_date = daily["스냅샷일"].max()
    prev_date = daily[daily["스냅샷일"] < latest_date]["스냅샷일"].max()
    latest = daily[daily["스냅샷일"] == latest_date].iloc[0]
    prev = daily[daily["스냅샷일"] == prev_date].iloc[0] if pd.notna(prev_date) else None
    stock_weight_change = (latest["주식비중"] - prev["주식비중"]) if prev is not None and pd.notna(prev["주식비중"]) else pd.NA
    stock_exp_change = (latest["주식Exp"] - prev["주식Exp"]) if prev is not None else pd.NA

    trend = trend_svg([
        {"label": "당행 평가액", "color": "#00483a", "points": list(zip(daily["스냅샷일"], daily["당행평가액"]))},
        {"label": "펀드 Exp", "color": "#008485", "points": list(zip(daily["스냅샷일"], daily["펀드Exp"]))},
        {"label": "주식 Net Exp", "color": "#003b5c", "points": list(zip(daily["스냅샷일"], daily["주식Exp"]))},
        {"label": "채권 및 현금 Exp", "color": "#7a5c2e", "points": list(zip(daily["스냅샷일"], daily["기타Exp"]))},
    ])

    timeline_rows = []
    for _, row in daily.sort_values("스냅샷일", ascending=False).iterrows():
        timeline_rows.append([
            f"<td>{row['스냅샷일']:%Y-%m-%d}</td>",
            f"<td>{fmt_money_1(row['당행평가액'])}</td>",
            f"<td>{fmt_money_1(row['펀드Exp'])}</td>",
            signed_td(row["주식Exp"], fmt_money_1),
            f"<td>{fmt_money_1(row['기타Exp'])}</td>",
            signed_pct_td(row["주식비중"], 1),
            f"<td>{int(row['보유종목수']):,}</td>",
        ])

    fund_rows = []
    if not fund_daily.empty and pd.notna(prev_date):
        latest_fund = fund_daily[fund_daily["스냅샷일"] == latest_date].copy()
        prev_fund = fund_daily[fund_daily["스냅샷일"] == prev_date][["보유펀드명", "주식Exp", "주식비중"]].rename(columns={"주식Exp": "전일주식Exp", "주식비중": "전일주식비중"})
        change = latest_fund.merge(prev_fund, on="보유펀드명", how="left")
        change["주식Exp증감"] = change["주식Exp"] - change["전일주식Exp"].fillna(0)
        change["주식비중증감"] = change["주식비중"] - change["전일주식비중"]
        limit = change["주식Exp증감"].abs().max() or 1
        for _, row in change.sort_values("주식Exp증감", key=lambda s: s.abs(), ascending=False).head(18).iterrows():
            fund_rows.append([
                f"<td class='name-cell'>{esc(row['보유펀드명'])}</td>",
                f"<td>{int(row['종목수']):,}</td>",
                signed_td(row["주식Exp"], fmt_money_1),
                signed_pct_td(row["주식비중"], 1),
                mini_bar(row["주식Exp증감"], limit),
                signed_pct_td(row["주식비중증감"], 1),
            ])

    stock_rows = []
    addition_rows = []
    if not stock_daily.empty and pd.notna(prev_date):
        latest_stock = stock_daily[stock_daily["스냅샷일"] == latest_date].copy()
        prev_stock = stock_daily[stock_daily["스냅샷일"] == prev_date][["종목코드정규", "종목명", "Exp", "편입비"]].rename(columns={"Exp": "전일Exp", "편입비": "전일편입비"})
        change = latest_stock.merge(prev_stock, on=["종목코드정규", "종목명"], how="outer").fillna({"Exp": 0.0, "전일Exp": 0.0, "펀드수": 0})
        change["Exp증감"] = change["Exp"] - change["전일Exp"]
        change["편입비증감"] = change["편입비"] - change["전일편입비"]
        limit = change["Exp증감"].abs().max() or 1
        for _, row in change.sort_values("Exp증감", key=lambda s: s.abs(), ascending=False).head(20).iterrows():
            stock_rows.append([
                f"<td class='name-cell'>{esc(row['종목명'])}</td>",
                signed_td(row["Exp"], fmt_money_1),
                signed_pct_td(row["편입비"], 2),
                f"<td>{int(row.get('펀드수', 0) or 0):,}</td>",
                mini_bar(row["Exp증감"], limit),
                signed_pct_td(row["편입비증감"], 2),
            ])
        additions = change[((change["전일Exp"].abs() < 1) & (change["Exp"].abs() > 1)) | ((change["전일Exp"].abs() > 1) & (change["Exp"].abs() < 1))].copy()
        additions["상태"] = additions.apply(lambda row: "신규" if abs(row["전일Exp"]) < 1 else "이탈", axis=1)
        additions["표시금액"] = additions.apply(lambda row: row["Exp"] if row["상태"] == "신규" else -row["전일Exp"], axis=1)
        for _, row in additions.sort_values("표시금액", key=lambda s: s.abs(), ascending=False).head(18).iterrows():
            cls = "profit-cell" if row["상태"] == "신규" else "loss-cell"
            addition_rows.append([
                f"<td><span class='change-badge {cls}'>{row['상태']}</span></td>",
                f"<td class='name-cell'>{esc(row['종목명'])}</td>",
                signed_td(row["표시금액"], fmt_money_1),
                signed_pct_td(row["편입비"] if row["상태"] == "신규" else row["전일편입비"], 2),
            ])

    sector_trade_rows = []
    if not trades.empty:
        period_trades = trades[(trades["기준일"] >= daily["스냅샷일"].min()) & (trades["기준일"] <= latest_date)].copy()
        sector = period_trades.groupby("업종대분류", dropna=False)["순매수금액"].sum().reset_index()
        limit = sector["순매수금액"].abs().max() or 1
        for _, row in sector.sort_values("순매수금액", key=lambda s: s.abs(), ascending=False).head(16).iterrows():
            sector_trade_rows.append([
                f"<td class='name-cell'>{esc(row['업종대분류'])}</td>",
                mini_bar(row["순매수금액"], limit),
            ])

    return f"""
      <section class="tab-panel" data-panel="timeseries">
        <div class="section-title"><h3>시계열</h3><span>{daily['스냅샷일'].min():%Y-%m-%d} ~ {latest_date:%Y-%m-%d} · 보유 스냅샷 {len(daily):,}개</span></div>
        <div class="kpis compact timeseries-kpis">
          {kpi("최신 기준일", f"{latest_date:%Y-%m-%d}", f"전일 {prev_date:%Y-%m-%d}" if pd.notna(prev_date) else "비교일 없음")}
          {kpi("주식 Net Exp", fmt_money(latest["주식Exp"]), f"전일 대비 {fmt_money(stock_exp_change)}")}
          {kpi("주식비중", fmt_pct(latest["주식비중"], 1), f"전일 대비 {fmt_pct(stock_weight_change, 1)}")}
          {kpi("보유 종목수", f"{int(latest['보유종목수']):,}개", f"펀드 {int(latest['펀드수']):,}개")}
        </div>
        <div class="timeseries-grid">
          <article class="panel ts-trend-panel"><div class="panel-title"><h4>전체 Exp 추이</h4><span>Net 주식 기준</span></div>{trend}</article>
          <article class="panel ts-daily-panel"><div class="panel-title"><h4>일별 요약</h4><span>스냅샷 기준</span></div>{time_series_table(["기준일", "당행 평가액", "펀드 Exp", "주식 Net Exp", "채권 및 현금 Exp", "주식비중", "종목수"], timeline_rows)}</article>
          <article class="panel ts-fund-panel"><div class="panel-title"><h4>펀드별 주식비중 변화</h4><span>최신일 vs 전일</span></div>{time_series_table(["펀드명", "종목수", "주식Exp", "주식비중", "Exp 증감", "비중 증감"], fund_rows)}</article>
          <article class="panel ts-stock-panel"><div class="panel-title"><h4>종목별 보유비중 변화</h4><span>절대 증감 상위</span></div>{time_series_table(["종목명", "Exp", "편입비", "펀드수", "Exp 증감", "비중 증감"], stock_rows)}</article>
          <article class="panel ts-change-panel"><div class="panel-title"><h4>신규/이탈 보유</h4><span>최신일 기준</span></div>{time_series_table(["상태", "종목명", "Exp", "편입비"], addition_rows)}</article>
          <article class="panel ts-sector-panel"><div class="panel-title"><h4>업종별 누적 순매매</h4><span>기간 합산</span></div>{time_series_table(["업종", "누적 순매매"], sector_trade_rows)}</article>
        </div>
      </section>
    """


def make_time_series_tab(ts: dict[str, object], fund_code: str | None = None, fund_label: str = "전체 펀드 통합") -> str:
    holdings: pd.DataFrame = ts.get("holdings", pd.DataFrame()).copy()
    if fund_code and fund_code != "ALL" and not holdings.empty:
        holdings = holdings[holdings["협회펀드코드"] == fund_code].copy()
    if holdings.empty:
        return "<section class='tab-panel' data-panel='timeseries'><div class='section-title'><h3>시계열</h3><span>보유현황 파일을 추가하면 표시됩니다.</span></div>" + empty("시계열 데이터가 없습니다.") + "</section>"

    stock_holdings = holdings[is_equity_related(holdings, "자산군")].copy()
    if not stock_holdings.empty:
        stock_holdings["주식NetExp"] = stock_holdings["우리평가금"] * stock_holdings["포지션부호"]

    daily_total = (
        holdings.groupby("스냅샷일", dropna=False)
        .agg(
            당행평가액=("우리순자산", "sum"),
            펀드Exp=("우리평가금", "sum"),
            펀드수=("보유펀드명", "nunique"),
            원천파일=("원천파일", "first"),
        )
        .reset_index()
    )
    stock_daily = (
        stock_holdings.groupby("스냅샷일", dropna=False)
        .agg(주식Exp=("주식NetExp", "sum"), 보유종목수=("종목코드정규", "nunique"))
        .reset_index()
        if not stock_holdings.empty
        else pd.DataFrame(columns=["스냅샷일", "주식Exp", "보유종목수"])
    )
    daily = daily_total.merge(stock_daily, on="스냅샷일", how="left").fillna({"주식Exp": 0.0, "보유종목수": 0})
    daily["주식비중"] = daily["주식Exp"] / daily["당행평가액"].replace({0: pd.NA})
    daily = daily.sort_values("스냅샷일")

    latest_date = daily["스냅샷일"].max()
    prev_date = daily[daily["스냅샷일"] < latest_date]["스냅샷일"].max()
    latest = daily[daily["스냅샷일"] == latest_date].iloc[0]
    prev = daily[daily["스냅샷일"] == prev_date].iloc[0] if pd.notna(prev_date) else None
    stock_weight_change = (latest["주식비중"] - prev["주식비중"]) if prev is not None and pd.notna(prev["주식비중"]) else pd.NA
    stock_exp_change = (latest["주식Exp"] - prev["주식Exp"]) if prev is not None else pd.NA
    scope_note = "전체 펀드 기준" if not fund_code or fund_code == "ALL" else f"{fund_label} 기준"

    timeline_rows = []
    for _, row in daily.sort_values("스냅샷일", ascending=False).iterrows():
        timeline_rows.append([
            f"<td>{row['스냅샷일']:%Y-%m-%d}</td>",
            f"<td>{fmt_money_1(row['당행평가액'])}</td>",
            f"<td>{fmt_money_1(row['펀드Exp'])}</td>",
            signed_td(row["주식Exp"], fmt_money_1),
            signed_pct_td(row["주식비중"], 1),
            f"<td>{int(row['보유종목수']):,}</td>",
        ])

    stock_chart_rows = []
    if not stock_holdings.empty:
        stock_daily_by_name = (
            stock_holdings.groupby(["스냅샷일", "종목코드정규", "종목명"], dropna=False)
            .agg(Exp=("주식NetExp", "sum"), 펀드수=("보유펀드명", "nunique"))
            .reset_index()
        )
        denom = daily.set_index("스냅샷일")["당행평가액"]
        stock_daily_by_name["편입비"] = stock_daily_by_name["스냅샷일"].map(denom)
        stock_daily_by_name["편입비"] = stock_daily_by_name["Exp"] / stock_daily_by_name["편입비"].replace({0: pd.NA})
        if pd.notna(prev_date):
            latest_stock = stock_daily_by_name[stock_daily_by_name["스냅샷일"] == latest_date].copy()
            prev_stock = stock_daily_by_name[stock_daily_by_name["스냅샷일"] == prev_date][["종목코드정규", "종목명", "Exp", "편입비"]].rename(columns={"Exp": "전일Exp", "편입비": "전일편입비"})
            change = latest_stock.merge(prev_stock, on=["종목코드정규", "종목명"], how="outer").fillna({"Exp": 0.0, "전일Exp": 0.0, "펀드수": 0})
            change["Exp증감"] = change["Exp"] - change["전일Exp"]
            change["비중증감"] = change["편입비"].fillna(0) - change["전일편입비"].fillna(0)
        else:
            change = stock_daily_by_name[stock_daily_by_name["스냅샷일"] == latest_date].copy()
            change["전일Exp"] = 0.0
            change["전일편입비"] = pd.NA
            change["Exp증감"] = change["Exp"]
            change["비중증감"] = change["편입비"]
        histories = {}
        for _, row in stock_daily_by_name.sort_values("스냅샷일").iterrows():
            key = str(row["종목코드정규"]) or str(row["종목명"])
            histories.setdefault(key, []).append({
                "date": row["스냅샷일"].strftime("%Y-%m-%d"),
                "exp": float(row["Exp"]) if pd.notna(row["Exp"]) else 0.0,
                "weight": float(row["편입비"]) if pd.notna(row["편입비"]) else None,
            })
        for _, row in change.sort_values("비중증감", key=lambda s: s.abs(), ascending=False).head(120).iterrows():
            key = str(row["종목코드정규"]) or str(row["종목명"])
            stock_chart_rows.append({
                "key": key,
                "name": str(row["종목명"]),
                "code": str(row["종목코드정규"]),
                "exp": float(row["Exp"]) if pd.notna(row["Exp"]) else 0.0,
                "weight": float(row["편입비"]) if pd.notna(row["편입비"]) else None,
                "deltaExp": float(row["Exp증감"]) if pd.notna(row["Exp증감"]) else 0.0,
                "deltaWeight": float(row["비중증감"]) if pd.notna(row["비중증감"]) else None,
                "fundCount": int(row["펀드수"] or 0),
                "history": histories.get(key, []),
            })
    chart_payload = html.escape(json.dumps(stock_chart_rows, ensure_ascii=False), quote=False)
    daily_payload = html.escape(json.dumps([
        {
            "date": row["스냅샷일"].strftime("%Y-%m-%d"),
            "bankValue": float(row["당행평가액"]) if pd.notna(row["당행평가액"]) else 0.0,
            "fundExp": float(row["펀드Exp"]) if pd.notna(row["펀드Exp"]) else 0.0,
            "stockExp": float(row["주식Exp"]) if pd.notna(row["주식Exp"]) else 0.0,
            "stockWeight": float(row["주식비중"]) if pd.notna(row["주식비중"]) else None,
            "stockCount": int(row["보유종목수"] or 0),
        }
        for _, row in daily.sort_values("스냅샷일").iterrows()
    ], ensure_ascii=False), quote=False)

    return f"""
      <section class="tab-panel" data-panel="timeseries">
        <div class="section-title"><h3>시계열</h3><span>{daily['스냅샷일'].min():%Y-%m-%d} ~ {latest_date:%Y-%m-%d} · {scope_note}</span></div>
        <div class="ts-subtabs">
          <button type="button" class="active" data-ts-subtab="overview">추이/요약</button>
          <button type="button" data-ts-subtab="stock">종목별 보유비중 변화</button>
        </div>
        <div class="ts-range-controls">
          <div class="ts-range-presets">
            <button type="button" class="active" data-ts-months="1">1개월</button>
            <button type="button" data-ts-months="2">2개월</button>
            <button type="button" data-ts-months="3">3개월</button>
            <button type="button" data-ts-months="6">6개월</button>
            <button type="button" data-ts-months="12">1년</button>
          </div>
          <div class="ts-range-dates">
            <input type="date" class="ts-date-input" data-ts-start aria-label="시계열 조회 시작일">
            <span>~</span>
            <input type="date" class="ts-date-input" data-ts-end aria-label="시계열 조회 종료일">
            <button type="button" class="ts-apply-button" data-ts-apply>조회</button>
            <button type="button" class="ts-download-button" data-ts-download>일별 요약 다운로드</button>
          </div>
        </div>
        <div class="kpis compact timeseries-kpis">
          {kpi("최신 기준일", f"{latest_date:%Y-%m-%d}", f"전일 {prev_date:%Y-%m-%d}" if pd.notna(prev_date) else "비교일 없음").replace("<strong>", "<strong data-ts-kpi='date'>", 1)}
          {kpi("주식 Exp", fmt_money(latest["주식Exp"]), f"전일 대비 {fmt_money(stock_exp_change)}").replace("<strong>", "<strong data-ts-kpi='stockExp'>", 1).replace("<small>", "<small data-ts-kpi-note='stockExp'>", 1)}
          {kpi("주식비중", fmt_pct(latest["주식비중"], 1), f"전일 대비 {fmt_pct(stock_weight_change, 1)}").replace("<strong>", "<strong data-ts-kpi='stockWeight'>", 1).replace("<small>", "<small data-ts-kpi-note='stockWeight'>", 1)}
          {kpi("보유 종목수", f"{int(latest['보유종목수']):,}개", f"펀드 {int(latest['펀드수']):,}개").replace("<strong>", "<strong data-ts-kpi='stockCount'>", 1)}
        </div>
        <div class="ts-sub-panel active" data-ts-subpanel="overview">
          <div class="timeseries-grid">
            <article class="panel ts-trend-panel"><div class="panel-title"><h4>주식 Exp / 주식비중 추이</h4><span>Exp 좌축 · 비중 우축</span></div><div class="ts-overview-chart"></div><template class="ts-daily-data">{daily_payload}</template></article>
            <article class="panel ts-daily-panel"><div class="panel-title"><h4>일별 요약</h4><span>날짜 내림차순</span></div><div class="ts-daily-host"></div></article>
          </div>
        </div>
        <div class="ts-sub-panel" data-ts-subpanel="stock">
          <article class="panel ts-stock-panel"><div class="panel-title"><h4>종목별 보유비중 변화</h4><span>기본값 SK하이닉스</span></div><div class="ts-stock-widget"><input class="table-search ts-stock-search" type="search" placeholder="종목명/코드 검색" aria-label="종목별 보유비중 변화 검색"><div class="ts-stock-candidates"></div><div class="ts-stock-chart"></div><div class="ts-stock-daily-host"></div><template class="ts-stock-data">{chart_payload}</template></div></article>
        </div>
      </section>
    """


def prepare_direct_stock_sheet(sheet_name: str, quotes: dict[str, dict[str, float | None]]) -> pd.DataFrame:
    if not INPUTS["direct_stocks"].exists():
        return pd.DataFrame(columns=["종목명", "종목코드정규", "보유수량", "현재가", "평가액", "등락율", "PL"])
    df = pd.read_excel(INPUTS["direct_stocks"], sheet_name=sheet_name).dropna(how="all")
    df["종목명"] = df["종목명"].astype(str).str.strip()
    df["종목코드정규"] = df["종목코드"].map(normalize_code)
    df["보유수량"] = pd.to_numeric(df["보유수량"], errors="coerce").fillna(0)
    quote_values = df.apply(lambda row: quote_for(row, quotes), axis=1)
    df = pd.concat([df, quote_values], axis=1)
    df["평가액"] = df["보유수량"] * df["현재가"]
    df["PL"] = df["평가액"] * df["등락율"] / 100.0
    return df


def make_view(
    label: str,
    all_holdings: pd.DataFrame,
    stock_holdings: pd.DataFrame,
    all_stock_holdings_for_pl: pd.DataFrame,
    all_holdings_for_pl: pd.DataFrame,
    stock_trades: pd.DataFrame,
    fund_catalog: pd.DataFrame,
    global_pl: dict[str, float | None],
    investment_table_html: str,
    product_table_html: str,
    sector_large_labels: list[str],
    sector_mid_labels: list[str],
    time_series_html: str,
) -> str:
    total_fund_amount = all_holdings["우리순자산"].sum() if "우리순자산" in all_holdings else all_holdings["우리평가금"].sum()
    long_amount = stock_holdings.loc[stock_holdings["포지션"] == "매수", "우리평가금"].sum()
    short_amount = stock_holdings.loc[stock_holdings["포지션"] == "매도", "우리평가금"].sum()
    net_exposure = long_amount - short_amount
    investment_exposure = global_pl.get("투자주식Exposure")
    product_exposure = global_pl.get("상품주식Exposure")
    total_exposure = (net_exposure or 0) + (investment_exposure or 0) + (product_exposure or 0)
    buy_amount = stock_trades.loc[stock_trades["거래구분"] == "매수", "우리결제금액"].sum()
    sell_amount = stock_trades.loc[stock_trades["거래구분"] == "매도", "우리결제금액"].sum()
    trade_dates = stock_trades["기준일"].dropna()
    period = "-" if trade_dates.empty else f"{trade_dates.min():%Y-%m-%d} ~ {trade_dates.max():%Y-%m-%d}"
    fund_meta = ""
    count_meta = ""
    if not all_holdings.empty:
        rate = all_holdings["지분율"].dropna()
        count_meta = f"지분율 {fmt_pct(rate.iloc[0])} · 보유 {len(stock_holdings):,}건 · 매매 {len(stock_trades):,}건" if label != "전체 펀드 통합" and not rate.empty else f"펀드 {all_holdings['보유펀드명'].nunique():,}개 · 보유 {len(stock_holdings):,}건 · 매매 {len(stock_trades):,}건"
    sector_large_hold = stock_holdings.groupby("업종대분류")["우리평가금"].sum().sort_values(ascending=False).reset_index()
    sector_mid_hold = stock_holdings.groupby("업종중분류")["우리평가금"].sum().sort_values(ascending=False).reset_index()
    sector_trade_large = (
        stock_trades.assign(순매수금액=stock_trades["우리결제금액"] * stock_trades["거래구분"].map({"매수": 1, "매도": -1}).fillna(0))
        .groupby("업종대분류")["순매수금액"].sum().reset_index()
    )
    sector_trade_mid = (
        stock_trades.assign(순매수금액=stock_trades["우리결제금액"] * stock_trades["거래구분"].map({"매수": 1, "매도": -1}).fillna(0))
        .groupby("업종중분류")["순매수금액"].sum().reset_index()
    )
    sector_large_rank = stock_holdings.groupby("업종대분류")["우리평가금"].sum().to_dict() if not stock_holdings.empty else {}
    sector_large_view_labels = sorted(sector_large_labels, key=lambda label: sector_large_rank.get(label, 0.0), reverse=True)
    sector_mid_rank = stock_holdings.groupby("업종중분류")["우리평가금"].sum().to_dict() if not stock_holdings.empty else {}
    sector_mid_view_labels = sorted(sector_mid_labels, key=lambda label: sector_mid_rank.get(label, 0.0), reverse=True)
    fund_pl_holdings = all_holdings_for_pl if all_holdings_for_pl is not None else all_holdings
    return f"""
      <section class="tab-panel" data-panel="summary">
        <div class="summary-strip">
          <span class="period-data" data-period="{esc(period)}"></span>
          <div class="selected-block"><span class="eyebrow">선택 펀드</span><h2>{esc(label)}</h2><small>{esc(count_meta)}</small></div>
          <div class="metric-groups">
            <div class="metric-group pl-group">
              {kpi("전체 PL", fmt_money(global_pl.get("전체PL")), "합산")}
              {kpi("수익증권 PL", fmt_money(global_pl.get("수익증권PL")), "펀드")}
              {kpi("투자주식 PL", fmt_money(global_pl.get("투자주식PL")), "직접")}
              {kpi("상품주식 PL", fmt_money(global_pl.get("상품주식PL")), "직접")}
            </div>
            <div class="metric-group exposure-group">
              {kpi("전체 Exposure", fmt_money(total_exposure), "합산")}
              {kpi("수익증권 투자금", fmt_money(total_fund_amount), "순자산 x raw 지분율")}
              {kpi("수익증권 Net", fmt_money(net_exposure), f"투자금 대비 {fmt_pct(net_exposure / total_fund_amount if total_fund_amount else pd.NA)}")}
              {kpi("직접주식 Exposure", fmt_money((investment_exposure or 0) + (product_exposure or 0)), "투자+상품")}
            </div>
          </div>
        </div>
        <div class="summary-grid">
          {investment_table_html}
          {product_table_html}
          <article class="panel top20-panel"><div class="panel-title"><h4>보유내역 TOP20</h4><span>종목별 순노출 기준</span></div>{top20_holdings_table(stock_holdings, total_fund_amount)}</article>
          <article class="panel fund-pl-panel"><div class="panel-title"><h4>수익증권</h4><div class="title-actions"><button type="button" class="column-help-button" data-open-column-help>컬럼 설명</button><span>투자금 기준</span></div></div>{fund_pl_table(all_stock_holdings_for_pl, fund_pl_holdings, fund_catalog, None if label == "전체 펀드 통합" else label)}</article>
          <div class="sector-row">
            <article class="panel sector-large-panel"><div class="mini-title"><span class="mini-icon"></span>업종별(대)</div>{sector_large_pie_svg(list(zip(sector_large_hold["업종대분류"], sector_large_hold["우리평가금"])))}</article>
            <article class="panel sector-mid-panel"><div class="mini-title"><span class="mini-icon"></span>업종별(중)</div>{sector_mid_bar_svg(list(zip(sector_mid_hold["업종중분류"], sector_mid_hold["우리평가금"])), sector_mid_view_labels)}</article>
          </div>
        </div>
      </section>
      <section class="tab-panel" data-panel="holdings">
        <div class="section-title"><h3>보유상세</h3><span>평가액/취득원가/편입비는 raw 보유현황 지분율 기준</span></div>
        <div class="detail-grid">
          <article class="panel long-panel searchable-panel"><div class="panel-title holding-title"><div class="title-left"><h4>Long 보유내역 (TOP20)</h4><input class="table-search" data-holding-search="매수" type="search" placeholder="종목/펀드 검색" aria-label="Long 보유내역 검색"></div></div><div class="holding-table-host" data-holding-position="매수">{holding_table(stock_holdings, "매수", total_fund_amount)}</div></article>
          <article class="panel short-panel searchable-panel"><div class="panel-title holding-title"><div class="title-left"><h4>Short 보유내역 (TOP20)</h4><input class="table-search" data-holding-search="매도" type="search" placeholder="종목/펀드 검색" aria-label="Short 보유내역 검색"></div></div><div class="holding-table-host" data-holding-position="매도">{holding_table(stock_holdings, "매도", total_fund_amount)}</div></article>
        </div>
      </section>
      <section class="tab-panel" data-panel="trades">
        <div class="section-title"><h3>매매상세</h3><span>현금성자산 제외, 주식/주식관련 포지션만 표시</span></div>
        <div class="kpis compact">
          {kpi("총 매수", fmt_money(buy_amount), f"{int((stock_trades['거래구분'] == '매수').sum()):,}건")}
          {kpi("총 매도", fmt_money(sell_amount), f"{int((stock_trades['거래구분'] == '매도').sum()):,}건")}
          {kpi("순매수", fmt_money(buy_amount - sell_amount), "전체 기간")}
          {kpi("매매 종목", f"{stock_trades['종목코드정규'].nunique():,}개", f"거래 {len(stock_trades):,}건")}
        </div>
        <div class="trade-grid">
          <article class="panel trade-recent searchable-panel"><div class="panel-title trade-title"><h4>매매내역</h4><input class="table-search" id="tradeSearch" type="search" placeholder="종목/펀드 검색" aria-label="매매내역 검색"><div class="trade-range"><div class="trade-presets"><button type="button" data-trade-preset="1d">1일</button><button type="button" data-trade-preset="1w">1주일</button><button type="button" data-trade-preset="1m">1개월</button><button type="button" data-trade-preset="3m">3개월</button></div><input class="trade-date" id="tradeStart" type="date" aria-label="매매 시작일"><button type="button" class="trade-reset-button" id="tradeFilterReset">초기화</button><input class="trade-date" id="tradeEnd" type="date" aria-label="매매 종료일"><span class="trade-filter-state" id="tradeFilterState">전체</span></div></div><div class="table-wrap"><table id="stockTradeTable"></table></div></article>
          <article class="panel net-buy-panel"><div class="panel-title"><h4>상위 순매수</h4><span>기간 필터 반영</span></div><div id="netBuyHost"></div></article>
          <article class="panel net-sell-panel"><div class="panel-title"><h4>상위 순매도</h4><span>기간 필터 반영</span></div><div id="netSellHost"></div></article>
          <article class="panel trade-sector-panel"><div class="panel-title"><h4>업종별 매매내역(중)</h4><span>기간 필터 반영</span></div><div id="tradeSectorMidHost"></div></article>
          <article class="panel trade-sector-panel"><div class="panel-title"><h4>업종별 매매내역(대)</h4><span>기간 필터 반영</span></div><div id="tradeSectorLargeHost"></div></article>
        </div>
      </section>
      {time_series_html}
    """


def build_dashboard(
    data_source: str = "excel",
    start_date: str | None = None,
    end_date: str | None = None,
    output_path: Path | None = None,
) -> Path:
    funds, trades_raw, holdings_raw, fund_master, source_frames = read_inputs(data_source, start_date, end_date)
    quotes, quote_source = load_quote_cache()
    industry_large_by_code, industry_mid_by_code = read_industry_map()
    codes = set(funds["펀드코드"])
    info = funds.set_index("펀드코드")

    holdings = holdings_raw[holdings_raw["협회펀드코드"].isin(codes)].copy()
    trades = trades_raw[trades_raw["협회펀드코드"].isin(codes)].copy()
    holdings["보유펀드명"] = holdings["협회펀드코드"].map(info["펀드명"]).fillna(holdings["펀드명"])
    holdings["펀드평가액원"] = holdings["협회펀드코드"].map(info["평가액원"])
    holdings["지분율"] = holdings["지분율"].fillna(1)
    holdings.loc[holdings["지분율"] > 1, "지분율"] = holdings.loc[holdings["지분율"] > 1, "지분율"] / 100
    trades["보유펀드명"] = trades["협회펀드코드"].map(info["펀드명"]).fillna(trades["펀드명"])
    trades["지분율"] = trades["협회펀드코드"].map(info["지분율"]).fillna(1)
    trades["펀드평가액원"] = trades["협회펀드코드"].map(info["평가액원"])

    holdings["우리평가금"] = holdings["평가금"].fillna(0) * holdings["지분율"]
    holdings["우리취득가액"] = holdings["취득가액"].fillna(0) * holdings["지분율"]
    holdings["우리순자산"] = holdings["순자산"].fillna(0) * holdings["지분율"]
    holdings["우리수량"] = holdings["수량"].fillna(0) * holdings["지분율"]
    holdings["평가손익"] = holdings["우리평가금"] - holdings["우리취득가액"]
    holdings["평단가"] = holdings["우리취득가액"] / holdings["우리수량"].replace({0: pd.NA})
    holdings["평단수익률"] = holdings["우리평가금"] / holdings["우리취득가액"].replace({0: pd.NA}) - 1
    holdings["펀드투자금"] = holdings.groupby("협회펀드코드", dropna=False)["우리순자산"].transform("sum")
    holdings["편입비"] = holdings["우리평가금"] / holdings["펀드투자금"].replace({0: pd.NA})
    holdings.loc[holdings["포지션"] == "매도", "편입비"] = -holdings.loc[holdings["포지션"] == "매도", "편입비"].abs()
    holding_share_by_fund = holdings.groupby("협회펀드코드", dropna=False)["지분율"].first()
    fund_investment_by_code = holdings.groupby("협회펀드코드", dropna=False)["우리순자산"].sum()
    trades["지분율"] = trades["협회펀드코드"].map(holding_share_by_fund).fillna(trades["지분율"])
    trades["펀드투자금"] = trades["협회펀드코드"].map(fund_investment_by_code)
    trades["우리결제금액"] = trades["결제금액"].fillna(0) * trades["지분율"]
    trades["매매편입비"] = trades["우리결제금액"] / trades["펀드투자금"].replace({0: pd.NA})

    quote_values = holdings.apply(lambda row: quote_for(row, quotes), axis=1)
    holdings = pd.concat([holdings, quote_values], axis=1)
    holdings["업종대분류"] = holdings["종목코드정규"].map(industry_large_by_code).fillna("미분류")
    holdings["업종중분류"] = holdings["종목코드정규"].map(industry_mid_by_code).fillna("미분류")
    holdings["업종"] = holdings["업종중분류"]
    holdings["포지션부호"] = holdings.apply(signed_position, axis=1)
    holdings["시장PL"] = holdings["우리평가금"] * holdings["등락율"] / 100.0
    holdings["PL"] = holdings["우리평가금"] * holdings["포지션부호"] * holdings["등락율"] / 100.0

    trades["업종대분류"] = trades["종목코드정규"].map(industry_large_by_code).fillna("미분류")
    trades["업종중분류"] = trades["종목코드정규"].map(industry_mid_by_code).fillna("미분류")
    trades["업종"] = trades["업종중분류"]

    stock_holdings = holdings[is_equity_related(holdings, "자산군")].copy()
    stock_trades = trades[is_equity_related(trades, "자산구분") & trades["거래구분"].isin(["매수", "매도"])].copy()
    stock_trade_history = stock_trades.copy()
    if not stock_trades.empty and stock_trades["기준일"].notna().any():
        default_trade_end = stock_trades["기준일"].max()
        stock_trades = stock_trades[stock_trades["기준일"] >= default_trade_end - pd.DateOffset(months=1)].copy()
    if stock_trade_history.empty:
        trade_history = []
    else:
        stock_trade_history["평단계산금액"] = stock_trade_history["매매가격"] * stock_trade_history["매매수량"].abs()
        signed_trade_history = stock_trade_history.assign(
            순매수금액=stock_trade_history["우리결제금액"] * stock_trade_history["거래구분"].map({"매수": 1, "매도": -1}).fillna(0),
            순매매수량=stock_trade_history["매매수량"] * stock_trade_history["거래구분"].map({"매수": 1, "매도": -1}).fillna(0),
        )
        trade_history_source = (
            signed_trade_history.groupby(["기준일", "협회펀드코드", "보유펀드명", "종목명"], dropna=False)
            .agg(순매수금액=("순매수금액", "sum"), 순매매수량=("순매매수량", "sum"), 펀드투자금=("펀드투자금", "first"), 업종=("업종", "first"), 업종대분류=("업종대분류", "first"))
            .reset_index()
        )
        trade_history_source = trade_history_source[trade_history_source["순매수금액"].abs() > 0].copy()
        trade_history_source["거래구분"] = trade_history_source["순매수금액"].map(lambda value: "매수" if value > 0 else "매도")
        avg_price_source = (
            signed_trade_history.groupby(["기준일", "협회펀드코드", "보유펀드명", "종목명", "거래구분"], dropna=False)
            .agg(평단계산금액=("평단계산금액", "sum"), 매매수량절대값=("매매수량", lambda series: series.abs().sum()), 결제금액절대값=("우리결제금액", lambda series: series.abs().sum()))
            .reset_index()
        )
        avg_price_source["방향평단가"] = avg_price_source["평단계산금액"] / avg_price_source["매매수량절대값"].replace({0: pd.NA})
        fallback_avg_price = avg_price_source["결제금액절대값"] / avg_price_source["매매수량절대값"].replace({0: pd.NA})
        avg_price_source["방향평단가"] = avg_price_source["방향평단가"].where(avg_price_source["방향평단가"].notna(), fallback_avg_price)
        trade_history_source = trade_history_source.merge(
            avg_price_source[["기준일", "협회펀드코드", "보유펀드명", "종목명", "거래구분", "방향평단가"]],
            on=["기준일", "협회펀드코드", "보유펀드명", "종목명", "거래구분"],
            how="left",
        )
        trade_history_source["매매편입비"] = trade_history_source["순매수금액"].abs() / trade_history_source["펀드투자금"].replace({0: pd.NA})
        trade_history = [
            {
                "date": row["기준일"].strftime("%Y-%m-%d") if pd.notna(row["기준일"]) else "",
                "fundCode": str(row["협회펀드코드"]),
                "fund": str(row["보유펀드명"]),
                "name": str(row["종목명"]),
                "sector": str(row["업종"]),
                "sectorLarge": str(row["업종대분류"]),
                "side": str(row["거래구분"]),
                "amount": abs(float(row["순매수금액"])) if pd.notna(row["순매수금액"]) else 0.0,
                "avgPrice": float(row["방향평단가"]) if pd.notna(row["방향평단가"]) else None,
                "weight": float(row["매매편입비"]) if pd.notna(row["매매편입비"]) else None,
            }
            for _, row in trade_history_source.iterrows()
        ]

    investment_stocks = prepare_direct_stock_sheet("투자주식", quotes)
    product_stocks = prepare_direct_stock_sheet("상품주식", quotes)
    fund_pl = safe_sum(stock_holdings["PL"])
    investment_pl = safe_sum(investment_stocks["PL"])
    product_pl = safe_sum(product_stocks["PL"])
    investment_exposure = safe_sum(investment_stocks["평가액"])
    product_exposure = safe_sum(product_stocks["평가액"])
    total_pl = None if all(v is None for v in [fund_pl, investment_pl, product_pl]) else sum(v or 0 for v in [fund_pl, investment_pl, product_pl])
    global_pl = {
        "전체PL": total_pl,
        "수익증권PL": fund_pl,
        "투자주식PL": investment_pl,
        "상품주식PL": product_pl,
        "투자주식Exposure": investment_exposure,
        "상품주식Exposure": product_exposure,
    }
    investment_table = direct_stock_table(investment_stocks, "투자주식", "investment-panel")
    product_table = direct_stock_table(product_stocks, "상품주식", "product-panel")
    quote_sensitive_data = quote_sensitive_payload(stock_holdings, holdings, investment_stocks, product_stocks, funds)
    sector_mid_labels = (
        stock_holdings.groupby("업종중분류")["우리평가금"].sum().sort_values(ascending=False).index.astype(str).tolist()
    )
    sector_large_labels = (
        stock_holdings.groupby("업종대분류")["우리평가금"].sum().sort_values(ascending=False).index.astype(str).tolist()
    )

    time_series = build_time_series(funds, industry_large_by_code, industry_mid_by_code, source_frames)
    views = {"ALL": make_view("전체 펀드 통합", holdings, stock_holdings, stock_holdings, holdings, stock_trades, funds, global_pl, investment_table, product_table, sector_large_labels, sector_mid_labels, make_time_series_tab(time_series, "ALL", "전체 펀드 통합"))}
    holding_detail_data = {
        "ALL": {
            "매수": holding_detail_records(stock_holdings, "매수", holdings["우리순자산"].sum() if "우리순자산" in holdings else None),
            "매도": holding_detail_records(stock_holdings, "매도", holdings["우리순자산"].sum() if "우리순자산" in holdings else None),
        }
    }
    fund_buttons = [{
        "key": "ALL",
        "name": "전체 펀드",
        "code": "ALL",
        "type": "전체",
        "meta": "",
    }]
    type_order = {"주식": 0, "멀티": 1, "롱숏": 2, "혼합": 3, "IPO": 4}
    funds_sorted = funds.assign(_type_order=funds["유형"].map(type_order).fillna(99)).sort_values(["_type_order", "펀드명"])
    for _, fund in funds_sorted.iterrows():
        code = fund["펀드코드"]
        h_all = holdings[holdings["협회펀드코드"] == code].copy()
        h_stock = stock_holdings[stock_holdings["협회펀드코드"] == code].copy()
        t_stock = stock_trades[stock_trades["협회펀드코드"] == code].copy()
        views[code] = make_view(fund["펀드명"], h_all, h_stock, stock_holdings, holdings, t_stock, funds, global_pl, investment_table, product_table, sector_large_labels, sector_mid_labels, make_time_series_tab(time_series, code, fund["펀드명"]))
        fund_denominator = h_all["우리순자산"].sum() if "우리순자산" in h_all else None
        holding_detail_data[code] = {
            "매수": holding_detail_records(h_stock, "매수", fund_denominator),
            "매도": holding_detail_records(h_stock, "매도", fund_denominator),
        }
        fund_buttons.append({
            "key": code,
            "name": fund["펀드명"],
            "code": code,
            "type": fund["유형"],
            "meta": "",
        })

    snapshot_dates = []
    if data_source == "supabase":
        try:
            snapshot_dates = available_supabase_holding_dates(start_date, None)
        except Exception:
            snapshot_dates = []
    if not snapshot_dates and "holdings_ts" in source_frames and not source_frames["holdings_ts"].empty:
        snapshot_dates = sorted(
            pd.to_datetime(source_frames["holdings_ts"]["스냅샷일"], errors="coerce")
            .dropna()
            .dt.strftime("%Y-%m-%d")
            .unique()
            .tolist()
        )
    current_snapshot_date = ""
    if not holdings.empty and "보유일" in holdings:
        dates = holdings["보유일"].dropna()
        if not dates.empty:
            current_snapshot_date = dates.max().strftime("%Y-%m-%d")
    if not current_snapshot_date and snapshot_dates:
        current_snapshot_date = snapshot_dates[-1]
    latest_snapshot_date = snapshot_dates[-1] if snapshot_dates else current_snapshot_date

    source_note = {
        "input_dir": str(BASE_DIR),
        "fund_count": int(len(funds)),
        "holding_stock_related_rows": int(len(stock_holdings)),
        "trade_stock_related_rows": int(len(stock_trades)),
        "quote_source": quote_source,
        "quote_count": len(quotes),
        "holding_source_file": f"{data_source}:KFR Partner API JSON/fund_holdings",
        "trade_source_file": f"{data_source}:KFR Partner API JSON/fund_trades",
        "direct_stock_file": INPUTS["direct_stocks"].name if INPUTS["direct_stocks"].exists() else "없음",
        "time_series_holding_files": time_series.get("files", {}).get("holdings", []),
        "time_series_trade_files": time_series.get("files", {}).get("trades", []),
        "fund_master_file": FUND_MASTER_VERSION_FILE.name if FUND_MASTER_VERSION_FILE.exists() else "없음",
        "fund_master_effective_date": fund_master.get("effective_date", "") if isinstance(fund_master, dict) else "",
        "fund_master_source": fund_master.get("source", "local") if isinstance(fund_master, dict) else "local",
        "fund_master_rows": fund_master.get("rows", int(len(funds))) if isinstance(fund_master, dict) else int(len(funds)),
        "data_source": data_source,
        "supabase_range": f"{start_date or ''}~{end_date or ''}" if data_source == "supabase" else "",
        "current_snapshot_date": current_snapshot_date,
        "latest_snapshot_date": latest_snapshot_date,
        "snapshot_dates": snapshot_dates,
        "amount_basis": "보유: 원본 금액 x raw 보유현황 지분율 / 매매: 원본 결제금액 x 보유현황 펀드 지분율",
    }

    html_text = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>주식 & 수익증권 대시보드</title>
  <style>
    :root {{ --hana:#00483a; --hana-light:#00a88e; --navy:#12372d; --ink:#16251f; --muted:#697872; --line:#dfe8e4; --bg:#f5f7f4; --panel:#fff; --soft:#edf5f1; --danger:#e7663f; }}
    * {{ box-sizing:border-box; }}
    html {{ scroll-behavior:smooth; }}
    body {{ margin:0; background:var(--bg); color:var(--ink); font-family:"Segoe UI","Malgun Gothic",Arial,sans-serif; }}
    .topbar {{ height:52px; background:linear-gradient(90deg,#f8fbf9 0%,#fff 44%,#edf7f3 100%); border-bottom:1px solid var(--line); display:flex; align-items:center; justify-content:space-between; gap:14px; padding:0 22px; position:sticky; top:0; z-index:20; }}
    .brand {{ display:flex; align-items:center; gap:12px; font-weight:900; color:var(--hana); letter-spacing:-.3px; font-size:28px; }}
    .topbar-left {{ display:flex; align-items:center; gap:12px; min-width:0; }}
    .refresh-button {{ border:1px solid var(--hana); background:#fff; color:var(--hana); border-radius:7px; padding:6px 10px; font-size:12px; font-weight:900; cursor:pointer; }}
    .refresh-button:hover {{ background:#e8f6f5; }}
    .quote-controls {{ display:flex; align-items:center; gap:6px; border-left:1px solid var(--line); padding-left:10px; }}
    .quote-controls select {{ border:1px solid #b7d4cd; border-radius:7px; background:#fff; color:var(--hana); padding:5px 7px; font-size:12px; font-weight:800; }}
    .quote-status {{ min-width:118px; color:var(--muted); font-size:11px; font-weight:800; }}
    .caption {{ color:var(--muted); font-size:12px; text-align:right; display:grid; gap:2px; }}
    .caption small {{ font-size:11px; color:var(--hana); font-weight:800; }}
    .layout {{ display:grid; grid-template-columns:120px minmax(0,1fr); min-height:calc(100vh - 52px); }}
    aside {{ background:#f7faf8; border-right:1px solid var(--line); padding:7px 5px 9px; position:sticky; top:52px; height:calc(100vh - 52px); overflow:hidden; display:flex; flex-direction:column; }}
    aside h1 {{ margin:0 1px 6px; padding:0 1px 6px; border-bottom:1px solid var(--line); font-size:12px; color:var(--navy); letter-spacing:0; }}
    .quick-nav {{ display:flex; align-items:center; gap:5px; flex:0 0 auto; }}
    .quick-nav button {{ border:1px solid #c9ddd7; background:#fff; color:var(--hana); border-radius:7px; padding:6px 10px; font-size:11.5px; font-weight:900; cursor:pointer; min-width:0; text-align:center; white-space:nowrap; }}
    .quick-nav button:hover,.quick-nav button.active {{ background:#00483a; color:#fff; border-color:#00483a; }}
    .snapshot-control {{ display:flex; align-items:center; gap:5px; padding-left:2px; }}
    .snapshot-control label {{ font-size:11px; color:#4b5f58; font-weight:900; white-space:nowrap; }}
    .snapshot-control select {{ height:29px; border:1px solid #9abeb6; border-radius:6px; background:#fff; color:var(--hana); font-size:11.5px; font-weight:900; padding:0 6px; }}
    .snapshot-control button {{ height:29px; border:1px solid var(--hana); border-radius:6px; background:#fff; color:var(--hana); font-size:11px; font-weight:900; padding:0 8px; cursor:pointer; }}
    .snapshot-control button:hover {{ background:#e8f6f5; }}
    .fund-toolbar {{ display:flex; align-items:center; justify-content:space-between; gap:4px; margin:0 0 6px; }}
    .fund-toolbar h3 {{ margin:0; color:var(--hana); font-size:11px; font-weight:900; }}
    .fund-actions {{ display:flex; gap:4px; }}
    .fund-actions button {{ border:1px solid #c7d9d4; background:#fff; color:var(--hana); border-radius:4px; padding:3px 4px; font-size:9.5px; font-weight:900; cursor:pointer; }}
    .fund-actions button:hover,.fund-actions button.active {{ background:#00483a; border-color:#00483a; color:#fff; }}
    .fund-list {{ display:block; overflow:auto; padding:0 1px 6px; }}
    .fund-group {{ margin:0 0 7px; }}
    .fund-group-title {{ display:flex; align-items:center; gap:5px; margin:6px 1px 4px; font-size:10px; font-weight:900; color:#51615d; }}
    .fund-group-title:after {{ content:""; height:1px; flex:1; background:var(--line); }}
    .fund-group-grid {{ display:grid; grid-template-columns:1fr; gap:4px; }}
    .fund-button {{ width:100%; min-height:27px; border:1px solid #d7e4df; background:#fff; color:var(--ink); border-radius:4px; padding:4px 5px; text-align:left; cursor:pointer; min-width:0; }}
    .fund-button:hover {{ border-color:#9abeb6; background:#f3fbfa; }}
    .fund-button.active {{ background:#00483a; border-color:#00483a; color:#fff; }}
    .fund-button strong {{ display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; font-size:9.8px; line-height:1.12; overflow:hidden; text-overflow:ellipsis; white-space:normal; overflow-wrap:anywhere; }}
    .fund-button small {{ display:none; }}
    main {{ padding:6px 14px 34px; overflow:auto; }}
    .summary-strip {{ display:flex; align-items:stretch; gap:12px; width:100%; margin-bottom:4px; }}
    .eyebrow {{ color:var(--hana); font-weight:800; font-size:12px; }}
    h2 {{ margin:3px 0 0; font-size:24px; color:var(--navy); }}
    .selected-block {{ flex:0 0 220px; min-width:0; }}
    .selected-block small {{ display:block; color:var(--muted); font-size:11px; font-weight:800; margin-top:3px; }}
    .metric-groups {{ flex:1 1 auto; display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:10px; min-width:0; }}
    .metric-group {{ display:grid; grid-template-columns:1.12fr 1fr 1fr 1fr; gap:7px; padding:7px; border:1px solid var(--line); border-radius:8px; background:rgba(255,255,255,.72); min-width:0; }}
    .metric-group .kpi:first-child {{ border-color:var(--hana); background:#eaf5f0; box-shadow:inset 4px 0 0 var(--hana); }}
    .period {{ color:var(--muted); font-size:12px; }}
    .tab-panel {{ display:none; }}
    .tab-panel.active {{ display:block; }}
    .section-block {{ scroll-margin-top:74px; margin-bottom:18px; }}
    .section-title {{ display:flex; justify-content:space-between; align-items:baseline; margin:2px 0 6px; }}
    .section-title h3 {{ margin:0; font-size:20px; color:var(--navy); }}
    .section-title span {{ color:var(--muted); font-size:12px; }}
    .kpis {{ display:grid; grid-template-columns:repeat(4,minmax(120px,1fr)); gap:10px; margin-bottom:12px; }}
    .kpi {{ background:#fff; border:1px solid var(--line); border-radius:6px; padding:7px 8px; min-height:58px; min-width:0; box-shadow:0 1px 0 rgba(0,72,58,.04); }}
    .kpi span {{ display:block; color:var(--muted); font-size:10.5px; margin-bottom:4px; }}
    .kpi strong {{ display:block; color:var(--navy); font-size:15px; line-height:1.1; white-space:nowrap; letter-spacing:0; }}
    .kpi small {{ display:block; color:var(--muted); font-size:10px; margin-top:4px; white-space:nowrap; }}
    .summary-grid {{ display:grid; grid-template-columns:minmax(295px,.68fr) minmax(300px,.69fr) minmax(700px,1.55fr); grid-template-rows:repeat(2,346px); gap:10px; align-items:stretch; }}
    .sector-row {{ grid-column:1 / -1; display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; align-items:start; }}
    .detail-grid {{ display:grid; grid-template-columns:1fr; gap:12px; align-items:start; }}
    .hold-grid {{ display:grid; grid-template-columns:1.22fr 1.05fr 1.31fr; gap:10px; align-items:start; }}
    .trade-grid {{ display:grid; grid-template-columns:minmax(560px,1.55fr) minmax(260px,.75fr) minmax(260px,.75fr); gap:12px; align-items:start; }}
    .timeseries-grid {{ display:grid; grid-template-columns:1fr; gap:12px; align-items:start; }}
    .ts-trend-panel {{ grid-column:1 / -1; }}
    .ts-daily-panel {{ grid-column:1 / -1; }}
    .ts-stock-panel {{ grid-column:1 / -1; }}
    .ts-fund-panel,.ts-change-panel,.ts-sector-panel {{ grid-column:auto; }}
    .panel {{ background:var(--panel); border:1px solid var(--line); border-radius:6px; padding:12px; min-width:0; overflow:hidden; box-shadow:0 2px 8px rgba(18,55,45,.04); }}
    .investment-panel {{ grid-column:1; grid-row:1; }}
    .product-panel {{ grid-column:1; grid-row:2; }}
    .top20-panel {{ grid-column:2; grid-row:1 / span 2; }}
    .fund-pl-panel {{ grid-column:3; grid-row:1 / span 2; }}
    .investment-panel,.product-panel,.top20-panel,.fund-pl-panel {{ height:100%; display:flex; flex-direction:column; }}
    .long-panel {{ grid-column:auto; grid-row:auto; }}
    .sector-large-panel {{ grid-column:auto; grid-row:auto; }}
    .sector-mid-panel {{ grid-column:auto; grid-row:auto; }}
    .short-panel {{ grid-column:auto; grid-row:auto; }}
    .sector-large-panel,.sector-mid-panel {{ height:560px; }}
    .trade-recent {{ grid-column:1; grid-row:1 / span 2; }}
    .net-buy-panel {{ grid-column:2; grid-row:1; }}
    .net-sell-panel {{ grid-column:3; grid-row:1; }}
    .chart-panel {{ grid-column:span 3; }}
    .trade-sector-panel {{ grid-column:1 / -1; }}
    .panel-title {{ display:flex; align-items:baseline; justify-content:space-between; gap:10px; margin-bottom:9px; }}
    h4 {{ margin:0; font-size:15px; color:var(--ink); }}
    .panel-title span {{ color:var(--muted); font-size:11px; text-align:right; }}
    .title-left {{ display:flex; align-items:center; gap:8px; min-width:0; }}
    .holding-title {{ justify-content:flex-start; align-items:center; }}
    .title-actions {{ display:flex; align-items:center; justify-content:flex-end; gap:8px; }}
    .column-help-button {{ border:1px solid #9abeb6; background:#fff; color:var(--hana); border-radius:6px; padding:5px 8px; font-size:11px; font-weight:900; cursor:pointer; white-space:nowrap; }}
    .column-help-button:hover {{ background:#e8f6f5; border-color:var(--hana); }}
    .modal-backdrop {{ position:fixed; inset:0; z-index:50; display:none; align-items:center; justify-content:center; padding:24px; background:rgba(14,26,22,.42); }}
    .modal-backdrop.active {{ display:flex; }}
    .column-help-modal {{ width:min(640px,100%); max-height:min(720px,90vh); overflow:auto; background:#fff; border:1px solid var(--line); border-radius:8px; box-shadow:0 18px 48px rgba(18,55,45,.22); }}
    .holding-fund-modal {{ width:min(820px,100%); max-height:min(720px,90vh); overflow:auto; background:#fff; border:1px solid var(--line); border-radius:8px; box-shadow:0 18px 48px rgba(18,55,45,.22); }}
    .modal-head {{ display:flex; align-items:center; justify-content:space-between; gap:12px; padding:14px 16px; border-bottom:1px solid var(--line); }}
    .modal-head h3 {{ margin:0; font-size:18px; color:var(--navy); }}
    .modal-close {{ width:30px; height:30px; border:1px solid var(--line); border-radius:6px; background:#fff; color:var(--ink); font-size:18px; font-weight:900; line-height:1; cursor:pointer; }}
    .modal-close:hover {{ background:#f3fbfa; border-color:#9abeb6; }}
    .column-help-list {{ margin:0; padding:12px 16px 16px; display:grid; gap:9px; }}
    .column-help-list div {{ display:grid; grid-template-columns:112px minmax(0,1fr); gap:12px; align-items:start; padding:8px 0; border-bottom:1px solid #edf3f0; }}
    .column-help-list div:last-child {{ border-bottom:0; }}
    .column-help-list dt {{ color:var(--hana); font-size:12px; font-weight:900; }}
    .column-help-list dd {{ margin:0; color:var(--ink); font-size:12px; line-height:1.5; }}
    .holding-fund-table {{ width:100%; border-collapse:collapse; table-layout:fixed; font-size:11px; }}
    .holding-fund-table th,.holding-fund-table td {{ border-bottom:1px solid var(--line); padding:7px 6px; text-align:center; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
    .holding-fund-table th:first-child,.holding-fund-table td:first-child {{ text-align:left; width:130px; }}
    .holding-fund-table th {{ background:var(--soft); color:#314840; font-size:10.5px; }}
    .chart {{ width:100%; height:auto; display:block; }}
    .axis {{ fill:#687381; font-size:12px; }}
    .big-axis {{ font-size:14px; font-weight:700; }}
    .daily-axis {{ font-size:19px; font-weight:800; }}
    .value {{ fill:#263847; font-size:12px; font-weight:700; }}
    .gridline {{ stroke:#e7ecef; stroke-width:1; }}
    .zero {{ stroke:#98a2b3; stroke-width:1; stroke-dasharray:3 3; }}
    .pie-wrap {{ display:grid; grid-template-columns:minmax(320px,430px) minmax(0,1fr); gap:16px; align-items:center; justify-items:center; }}
    .pie {{ width:min(420px,100%); height:auto; }}
    .mini-title {{ display:flex; align-items:center; gap:7px; margin:0 0 8px; color:var(--hana); font-size:15px; font-weight:900; }}
    .mini-icon {{ width:12px; height:14px; display:inline-block; border-left:2px solid var(--hana); border-bottom:2px solid var(--hana); background:linear-gradient(90deg,transparent 0 2px,#007c70 2px 4px,transparent 4px 6px,#00a88e 6px 8px,transparent 8px); }}
    .sector-pie {{ width:min(390px,100%); height:auto; display:block; margin:8px auto 6px; overflow:visible; }}
    .slice-tag {{ fill:#fff; font-size:13px; font-weight:900; paint-order:stroke; stroke:#00483a; stroke-width:4px; stroke-linejoin:round; }}
    .callout {{ stroke:#7d8f88; stroke-width:1; fill:none; }}
    .slice-callout {{ fill:#153c35; font-size:11px; font-weight:900; paint-order:stroke; stroke:#fff; stroke-width:3px; stroke-linejoin:round; }}
    .sector-bar {{ width:100%; height:auto; max-height:500px; display:block; }}
    .bar-grid {{ stroke:#e1e9e5; stroke-width:1; }}
    .bar-axis {{ fill:#52615d; font-size:11px; }}
    .bar-label {{ fill:#3b4845; font-size:12px; font-weight:800; }}
    .bar-value {{ fill:#13221d; font-size:12px; font-weight:900; }}
    .trade-category-chart {{ width:100%; height:480px; display:block; overflow:visible; }}
    .trade-axis {{ font-size:12px; fill:#5f6b67; }}
    .trade-label {{ fill:#3e4b47; font-size:13px; font-weight:800; }}
    .sector-legend {{ list-style:none; margin:4px auto 0; padding:0; display:grid; grid-template-columns:repeat(2, max-content); justify-content:center; gap:7px 36px; max-height:230px; overflow:auto; }}
    .sector-legend li {{ display:grid; grid-template-columns:11px max-content max-content; align-items:center; gap:7px; font-size:14px; }}
    .sector-legend span {{ width:9px; height:9px; border-radius:50%; }}
    .sector-legend b {{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:130px; font-weight:700; }}
    .sector-legend em {{ font-style:normal; color:var(--hana); font-weight:900; text-align:right; }}
    .sector-legend small {{ display:none; }}
    .legend {{ list-style:none; margin:0; padding:0; display:grid; gap:6px; width:100%; }}
    .legend li {{ display:grid; grid-template-columns:10px minmax(90px,1fr) 50px 76px; align-items:center; gap:6px; font-size:11px; }}
    .legend span {{ width:9px; height:9px; border-radius:50%; }}
    .legend em {{ font-style:normal; color:var(--hana); font-weight:800; text-align:right; }}
    .legend small {{ color:var(--muted); text-align:right; }}
    .table-wrap {{ overflow:auto; border:1px solid var(--line); border-radius:8px; max-height:660px; }}
    .table-wrap.tall {{ max-height:660px; }}
    .table-wrap.direct {{ max-height:360px; }}
    .table-wrap.fund-pl {{ max-height:760px; }}
    .long-panel .table-wrap,.short-panel .table-wrap {{ max-height:none; }}
    table {{ width:100%; border-collapse:collapse; font-size:11px; background:#fff; table-layout:auto; }}
    th,td {{ padding:6px 6px; border-bottom:1px solid var(--line); text-align:right; white-space:nowrap; }}
    th:first-child,td:first-child,th:nth-child(2),td:nth-child(2),th:nth-child(3),td:nth-child(3) {{ text-align:left; }}
    th {{ background:#eef5f1; color:#40515d; font-weight:800; position:sticky; top:0; z-index:1; }}
    th[data-sort-index] {{ cursor:pointer; user-select:none; }}
    th[data-sort-index]::after {{ content:""; display:none; }}
    th.sort-asc::after, th.sort-desc::after {{ content:""; display:none; }}
    .total-label {{ font-weight:800; color:var(--navy); }}
    tbody tr:hover td {{ background:#eaf6f1; }}
    tbody tr:has(.total-label) td, tbody tr.total-row td {{ background:#eef5f1; font-weight:800; border-top:1px solid #c8dcd5; }}
    .highlight-row {{ background:#fff7d6 !important; color:var(--navy); font-weight:900; }}
    .name-cell {{ max-width:82px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .fund-pl table {{ table-layout:fixed; min-width:600px; }}
    .fund-pl th,.fund-pl td {{ text-align:center !important; vertical-align:middle; padding:4px 3px; overflow:hidden; text-overflow:ellipsis; }}
    .fund-pl th {{ white-space:normal; line-height:1.12; font-size:10.7px; color:#314840; height:24px; }}
    .fund-pl td {{ white-space:nowrap; font-size:11px; }}
    .fund-pl thead tr:first-child th {{ background:#e7f1ed; border-bottom:1px solid #cddbd6; font-weight:900; }}
    .fund-pl thead tr:nth-child(2) th {{ background:#eef6f2; font-weight:800; }}
    .fund-pl thead th[rowspan="2"] {{ height:48px; padding-top:0; padding-bottom:0; }}
    .fund-pl thead th[colspan] {{ padding-top:4px; padding-bottom:4px; }}
    .fund-pl thead tr:nth-child(2) th[data-sort-index] {{ text-align:center !important; padding-left:5px; padding-right:5px; }}
    .fund-pl th:first-child,.fund-pl td:first-child {{ text-align:left !important; padding-left:5px; }}
    .fund-pl td:first-child {{ font-size:10.8px; }}
    .fund-pl .rate-bar {{ width:46px; max-width:46px; margin:0 auto; }}
    .fund-pl .rate-bar em {{ font-size:9.8px; }}
    .fund-pl tbody tr:hover td {{ background:#e8f5ef; }}
    .fund-pl tbody tr:has(.total-label) td {{ background:#eaf3ef; font-weight:900; border-top:1px solid #c8dcd5; }}
    .holding-detail table {{ table-layout:fixed; min-width:894px; }}
    .holding-detail th,.holding-detail td {{ text-align:center !important; vertical-align:middle; padding:6px 5px; overflow:hidden; text-overflow:ellipsis; }}
    .holding-detail th {{ white-space:normal; line-height:1.2; font-size:10.5px; color:#314840; }}
    .holding-detail td {{ white-space:nowrap; font-size:10.5px; }}
    .holding-detail th:first-child,.holding-detail td:first-child {{ text-align:left !important; padding-left:7px; }}
    .holding-detail td:first-child {{ font-size:10px; }}
    .holding-detail .rate-bar {{ width:54px; max-width:54px; margin:0 auto; }}
    .holding-detail tbody tr:hover td {{ background:#e8f5ef; }}
    .holding-detail tbody tr.total-row td {{ background:#eaf3ef; font-weight:900; border-top:1px solid #c8dcd5; }}
    .fund-count-button {{ border:1px solid #9abeb6; background:#f7fbf9; color:var(--hana); border-radius:5px; padding:2px 8px; font-size:10px; font-weight:900; cursor:pointer; min-width:32px; }}
    .fund-count-button:hover {{ background:#e2f1ec; border-color:var(--hana); }}
    .investment-panel .name-cell,.product-panel .name-cell {{ max-width:82px; }}
    .investment-panel .table-wrap.direct,.product-panel .table-wrap.direct,.top20-panel .table-wrap,.fund-pl-panel .table-wrap {{ flex:1; min-height:0; max-height:none; }}
    .table-wrap.direct {{ overflow-x:hidden; }}
    .table-wrap.direct table {{ table-layout:fixed; width:100% !important; min-width:0 !important; max-width:100%; }}
    .table-wrap.direct th,.table-wrap.direct td {{ text-align:center; padding:5px 4px; font-size:10.8px; overflow:hidden; text-overflow:ellipsis; }}
    .table-wrap.direct th:first-child,.table-wrap.direct td:first-child {{ text-align:left; width:23%; }}
    .table-wrap.direct th:nth-child(2),.table-wrap.direct td:nth-child(2) {{ width:17%; }}
    .table-wrap.direct th:nth-child(3),.table-wrap.direct td:nth-child(3) {{ width:13%; }}
    .table-wrap.direct th:nth-child(4),.table-wrap.direct td:nth-child(4) {{ width:18%; }}
    .table-wrap.direct th:nth-child(5),.table-wrap.direct td:nth-child(5) {{ width:14%; }}
    .table-wrap.direct th:nth-child(6),.table-wrap.direct td:nth-child(6) {{ width:15%; }}
    .table-wrap.direct .rate-bar {{ width:42px; max-width:42px; margin:0 auto; }}
    .table-wrap.direct .rate-bar em {{ font-size:9px; }}
    .top20-panel .table-wrap {{ max-height:674px; }}
    .top20-table table {{ table-layout:fixed; min-width:100%; }}
    .top20-table th,.top20-table td {{ text-align:center !important; padding:5px 4px; overflow:hidden; text-overflow:ellipsis; font-size:10.7px; }}
    .top20-table th:nth-child(1),.top20-table td:nth-child(1) {{ width:22%; }}
    .top20-table th:nth-child(2),.top20-table td:nth-child(2) {{ width:14%; }}
    .top20-table th:nth-child(3),.top20-table td:nth-child(3) {{ width:11%; }}
    .top20-table th:nth-child(4),.top20-table td:nth-child(4) {{ width:19%; }}
    .top20-table th:nth-child(5),.top20-table td:nth-child(5) {{ width:16%; }}
    .top20-table th:nth-child(6),.top20-table td:nth-child(6) {{ width:16%; }}
    .top20-table th[data-sort-index]::after {{ content:""; display:none; }}
    .top20-table th:first-child,.top20-table td:first-child {{ text-align:left !important; }}
    .top20-table .name-cell {{ max-width:56px; }}
    .top20-table .rate-bar {{ width:42px; max-width:42px; margin:0 auto; }}
    .top20-table .rate-bar em {{ font-size:9px; }}
    .investment-panel th:nth-child(2),.investment-panel td:nth-child(2),.product-panel th:nth-child(2),.product-panel td:nth-child(2) {{ max-width:62px; overflow:hidden; text-overflow:ellipsis; }}
    .investment-panel th:nth-child(3),.investment-panel td:nth-child(3),.product-panel th:nth-child(3),.product-panel td:nth-child(3) {{ max-width:54px; }}
    .long-panel .name-cell,.short-panel .name-cell {{ max-width:132px; }}
    .trade-recent th:nth-child(2),.trade-recent td:nth-child(2) {{ max-width:66px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .trade-recent th:nth-child(3),.trade-recent td:nth-child(3) {{ max-width:82px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .profit-cell {{ color:#d92d20; font-weight:800; }}
    .loss-cell {{ color:#2563eb; font-weight:800; }}
    .trade-side-badge {{ display:inline-flex; align-items:center; justify-content:center; min-width:38px; padding:2px 8px; border-radius:999px; font-size:10px; font-weight:900; border:1px solid currentColor; background:#fff; }}
    .trade-side-badge.buy {{ color:#d92d20; background:#fff0ec; }}
    .trade-side-badge.sell {{ color:#2563eb; background:#eff6ff; }}
    .trade-filter-link {{ appearance:none; border:0; background:transparent; color:var(--hana); font:inherit; font-weight:900; padding:0; cursor:pointer; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .trade-filter-link:hover {{ text-decoration:underline; }}
    .trade-filter-target {{ cursor:pointer; }}
    .ts-subtabs {{ display:flex; gap:5px; margin:0 0 8px; }}
    .ts-subtabs button {{ border:1px solid #c9ddd7; background:#fff; color:var(--hana); border-radius:5px; padding:6px 12px; font-size:11px; font-weight:900; cursor:pointer; }}
    .ts-subtabs button:hover,.ts-subtabs button.active {{ background:#00483a; border-color:#00483a; color:#fff; }}
    .ts-range-controls {{ display:flex; align-items:center; justify-content:space-between; gap:10px; margin:0 0 8px; padding:7px 8px; border:1px solid var(--line); border-radius:6px; background:#fff; flex-wrap:wrap; }}
    .ts-range-presets,.ts-range-dates {{ display:flex; align-items:center; gap:5px; flex-wrap:wrap; }}
    .ts-range-presets button,.ts-apply-button,.ts-download-button {{ border:1px solid #c9ddd7; background:#fff; color:var(--hana); border-radius:5px; padding:5px 9px; font-size:10.5px; font-weight:900; cursor:pointer; white-space:nowrap; }}
    .ts-range-presets button:hover,.ts-range-presets button.active,.ts-apply-button:hover,.ts-download-button:hover {{ background:#e8f6f2; border-color:#008485; }}
    .ts-date-input {{ width:126px; border:1px solid #9abeb6; border-radius:5px; padding:5px 7px; font-size:11px; }}
    .ts-sub-panel {{ display:none; }}
    .ts-sub-panel.active {{ display:block; }}
    .ts-chart-scroll {{ overflow:hidden; padding-bottom:4px; }}
    .timeseries-combo-chart {{ width:100%; height:auto; display:block; max-height:360px; }}
    .timeseries-chart {{ width:100%; height:auto; display:block; }}
    .ts-axis {{ font-size:10px; fill:#66736e; }}
    .ts-date {{ font-size:11px; fill:#55625d; font-weight:800; }}
    .ts-bar-label {{ fill:#fff; font-size:10px; font-weight:900; paint-order:stroke; stroke:#006d66; stroke-width:2px; stroke-linejoin:round; }}
    .ts-line-label {{ fill:#12372d; font-size:10px; font-weight:900; paint-order:stroke; stroke:#fff; stroke-width:3px; stroke-linejoin:round; }}
    .ts-legend {{ list-style:none; margin:0; padding:0; display:flex; gap:12px; align-items:center; font-size:11px; font-weight:900; color:#314840; }}
    .ts-legend li {{ display:flex; align-items:center; gap:5px; white-space:nowrap; }}
    .ts-legend span {{ width:9px; height:9px; border-radius:50%; display:inline-block; }}
    .timeseries-table {{ max-height:380px; }}
    .ts-daily-table {{ max-height:none; }}
    .timeseries-table table {{ table-layout:fixed; min-width:100%; }}
    .timeseries-table th,.timeseries-table td {{ text-align:center !important; padding:6px 5px; overflow:hidden; text-overflow:ellipsis; font-size:10.5px; }}
    .timeseries-table th:first-child,.timeseries-table td:first-child {{ text-align:left !important; }}
    .ts-stock-widget {{ display:grid; gap:8px; }}
    .ts-stock-search {{ width:220px; }}
    .ts-stock-candidates {{ min-height:29px; display:flex; flex-wrap:wrap; gap:5px; align-items:center; }}
    .ts-stock-choice {{ border:1px solid #c6dad4; background:#fff; color:#314840; border-radius:999px; padding:4px 9px; font-size:10.5px; font-weight:900; cursor:pointer; }}
    .ts-stock-choice:hover,.ts-stock-choice.active {{ background:#e6f4ef; border-color:#008485; color:#00483a; }}
    .ts-stock-chart {{ min-height:280px; border:1px solid var(--line); border-radius:8px; background:#fff; overflow:auto; }}
    .ts-stock-svg {{ height:auto; display:block; }}
    .ts-stock-bar-label {{ fill:#314840; font-size:11px; font-weight:800; }}
    .ts-stock-value {{ fill:#12372d; font-size:11px; font-weight:900; }}
    .mini-bar {{ position:relative; height:18px; background:#f1f5f3; border-radius:4px; overflow:hidden; min-width:90px; }}
    .mini-bar span {{ position:absolute; left:0; top:0; bottom:0; opacity:.22; }}
    .mini-bar span.profit-cell {{ background:#d92d20; }}
    .mini-bar span.loss-cell {{ background:#2563eb; }}
    .mini-bar em {{ position:relative; display:block; line-height:18px; text-align:right; padding-right:5px; font-style:normal; font-weight:900; }}
    .change-badge {{ display:inline-flex; align-items:center; justify-content:center; min-width:38px; border:1px solid currentColor; border-radius:999px; padding:2px 7px; font-size:10px; background:#fff; }}
    .buy-cell {{ color:#d92d20; font-weight:800; }}
    .sell-cell {{ color:#2563eb; font-weight:800; }}
    .sr-search {{ position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; }}
    .table-search {{ width:150px; border:1px solid #9abeb6; border-radius:5px; padding:5px 8px; font-size:11px; }}
    .trade-title {{ flex-wrap:wrap; justify-content:flex-start; align-items:center; }}
    .trade-title .table-search {{ margin-left:0; width:170px; }}
    .rate-bar {{ position:relative; height:18px; width:64px; max-width:64px; background:#f1f5f9; border-radius:4px; overflow:hidden; margin-left:auto; }}
    .rate-bar span {{ position:absolute; top:0; bottom:0; opacity:.72; }}
    .rate-bar .bar-zero {{ left:50%; width:1px; background:#667085; opacity:.8; }}
    .rate-bar .bar-pos {{ background:#f3a29b; }}
    .rate-bar .bar-neg {{ background:#93c5fd; }}
    .rate-bar em {{ position:relative; z-index:2; display:block; text-align:center; font-style:normal; font-weight:800; color:#172033; line-height:18px; font-size:10px; }}
    .has-tip {{ cursor:help; }}
    .has-tip:hover {{ background:#f3fbfa; }}
    .empty {{ padding:24px; color:var(--muted); text-align:center; border:1px dashed var(--line); border-radius:8px; }}
    .audit {{ color:var(--muted); font-size:11px; margin-top:14px; }}
    .trade-range {{ margin-left:auto;display:flex;align-items:center;gap:5px; flex-wrap:wrap; justify-content:flex-end; }}
    .trade-presets {{ display:flex; align-items:center; gap:3px; }}
    .trade-presets button {{ border:1px solid #c7d9d4; background:#fff; color:var(--hana); border-radius:5px; padding:4px 7px; font-size:10.5px; font-weight:900; cursor:pointer; }}
    .trade-presets button:hover,.trade-presets button.active {{ background:#00483a; border-color:#00483a; color:#fff; }}
    .trade-date {{ width:122px;border:1px solid #9abeb6;border-radius:4px;padding:4px 7px }}
    .trade-reset-button {{ border:1px solid #9abeb6; background:#fff; color:var(--hana); border-radius:5px; padding:4px 8px; font-size:10.5px; font-weight:900; cursor:pointer; }}
    .trade-reset-button:hover {{ background:#e8f6f5; }}
    .trade-filter-state {{ display:inline-flex; align-items:center; min-height:26px; max-width:170px; border:1px solid #cbded8; background:#f4faf7; color:#35534b; border-radius:999px; padding:3px 9px; font-size:10.5px; font-weight:900; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .trade-dynamic-table .name-cell {{ max-width:108px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .trade-dynamic-bars {{ display:grid; gap:7px; padding:2px 1px; }}
    .trade-dynamic-bar {{ display:grid; grid-template-columns:118px minmax(0,1fr) 78px; align-items:center; gap:8px; border:0; background:transparent; padding:2px 0; cursor:pointer; color:var(--ink); width:100%; text-align:left; }}
    .trade-dynamic-bar strong {{ font-size:11px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .trade-dynamic-bar .track {{ height:13px; background:#eef4f1; border-radius:999px; overflow:hidden; }}
    .trade-dynamic-bar .fill {{ display:block; height:100%; border-radius:999px; }}
    .trade-dynamic-bar .fill.buy {{ background:#d92d20; }}
    .trade-dynamic-bar .fill.sell {{ background:#2563eb; }}
    .trade-dynamic-bar em {{ font-style:normal; font-size:10.5px; font-weight:900; text-align:right; }}
    @media (max-width:1280px) {{ .hold-grid {{ grid-template-columns:1fr 1fr; }} .trade-grid {{ grid-template-columns:1fr 1fr; }} .trade-recent {{ grid-column:1 / -1; grid-row:auto; }} .net-buy-panel,.net-sell-panel,.long-panel,.short-panel,.chart-panel {{ grid-column:auto; grid-row:auto; }} }}
    @media (max-width:980px) {{ .topbar {{ height:auto;min-height:52px;padding:8px 10px;align-items:flex-start;gap:6px;flex-wrap:wrap }}.topbar-left {{ flex-wrap:wrap }}.brand {{ font-size:20px }}.quick-nav {{ order:3; width:100%; overflow:auto; padding-bottom:2px; }}.layout {{ grid-template-columns:1fr; }} aside {{ position:static; height:auto; border-right:0; border-bottom:1px solid var(--line);padding:8px }} .fund-list {{ max-height:220px; }} .fund-group-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)) }} main {{ padding:8px }}.kpis,.summary-grid,.sector-row,.hold-grid,.detail-grid,.trade-grid,.timeseries-grid,.pie-wrap {{ grid-template-columns:1fr; }} .trade-recent,.ts-trend-panel,.ts-daily-panel {{ grid-column:auto; }}.metric-groups {{ grid-template-columns:1fr }}.summary-strip {{ align-items:flex-start;flex-wrap:wrap }}.trade-range {{ width:100%;margin-left:0 }}.trade-date {{ width:calc(50% - 12px) }}.panel {{ padding:8px }} }}
  </style>
</head>
<body>
  <div class="topbar">
    <div class="topbar-left">
      <div class="brand"><span>주식 & 수익증권 대시보드</span><button type="button" id="refreshPage" class="refresh-button">새로고침</button></div>
      <div class="quick-nav">
        <button type="button" data-tab="summary">요약</button>
        <button type="button" data-tab="holdings">보유상세</button>
        <button type="button" data-tab="trades">매매상세</button>
        <button type="button" data-tab="timeseries">시계열</button>
      </div>
      <div class="quote-controls">
        <button type="button" id="refreshQuotes" class="refresh-button">시세 갱신</button>
        <select id="quoteRefreshInterval" aria-label="시세 자동갱신 주기">
          <option value="off">OFF</option>
          <option value="30000">30초</option>
          <option value="60000">1분</option>
        </select>
        <span id="quoteStatus" class="quote-status">시세 대기</span>
      </div>
      <div class="snapshot-control">
        <label for="snapshotDate">기준일</label>
        <select id="snapshotDate"></select>
        <button type="button" id="latestSnapshot">최신</button>
      </div>
    </div>
    <div class="caption"><span>작업 폴더 raw 데이터 · 지분율 반영 · 주식/주식관련 분석</span><small id="periodCaption"></small></div>
  </div>
  <div class="layout">
    <aside>
      <h1>펀드 목록</h1>
      <div class="fund-toolbar">
        <h3>펀드</h3>
        <div class="fund-actions">
          <button type="button" id="multiFundToggle">중복</button>
          <button type="button" id="clearFundSelection">해제</button>
        </div>
      </div>
      <div id="fundList" class="fund-list"></div>
    </aside>
    <main>
      <div id="dashboard"></div>
      <div class="audit">검증 메모: {esc(json.dumps(source_note, ensure_ascii=False))}</div>
    </main>
  </div>
  <div id="columnHelpModal" class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="columnHelpTitle">
    <section class="column-help-modal">
      <div class="modal-head">
        <h3 id="columnHelpTitle">수익증권 컬럼 설명</h3>
        <button type="button" class="modal-close" data-close-column-help aria-label="닫기">×</button>
      </div>
      <dl class="column-help-list">
        <div><dt>당행 평가액</dt><dd>하나은행 실제 출자금액 (BS상 평가액)</dd></div>
        <div><dt>펀드 Exp</dt><dd>펀드 평가액(레버리지 사용 후) * 당행 지분율</dd></div>
        <div><dt>주식 Exp</dt><dd>펀드 내 주식 비중</dd></div>
        <div><dt>주식 비중</dt><dd>당행 출자금액(평가액) 대비 주식 비중</dd></div>
      </dl>
    </section>
  </div>
  <div id="holdingFundModal" class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="holdingFundTitle">
    <section class="holding-fund-modal">
      <div class="modal-head">
        <h3 id="holdingFundTitle">보유펀드 상세</h3>
        <button type="button" class="modal-close" data-close-holding-fund aria-label="닫기">×</button>
      </div>
      <div id="holdingFundBody"></div>
    </section>
  </div>
  <script>
    const views = {json.dumps(views, ensure_ascii=False)};
    const funds = {json.dumps(fund_buttons, ensure_ascii=False)};
    const snapshotDates = {json.dumps(snapshot_dates, ensure_ascii=False)};
    const currentSnapshotDate = {json.dumps(current_snapshot_date, ensure_ascii=False)};
    const latestSnapshotDate = {json.dumps(latest_snapshot_date, ensure_ascii=False)};
    const FUND_MASTER_STORAGE_KEY = "stockFundMasterVersions.v1";
    const tradeHistory = {json.dumps(trade_history, ensure_ascii=False)};
    const holdingDetails = {json.dumps(holding_detail_data, ensure_ascii=False)};
    let quoteSensitiveData = {json.dumps(quote_sensitive_data, ensure_ascii=False)};
    const tradeDates = tradeHistory.map(row => row.date).filter(Boolean).sort();
    const tradeMax = tradeDates.at(-1) || "";
    const tradeMin = tradeDates[0] || "";
    const defaultTradeStart = tradeMax ? (() => {{ const d=new Date(`${{tradeMax}}T00:00:00`); d.setMonth(d.getMonth()-1); return d.toISOString().slice(0,10); }})() : "";
    let tradeStart = defaultTradeStart, tradeEnd = tradeMax;
    let tradePreset = "1m";
    let tradeSearch = "";
    let tradeFilterLabel = "";
    const fundList = document.getElementById("fundList");
    const dashboard = document.getElementById("dashboard");
    const columnHelpModal = document.getElementById("columnHelpModal");
    let currentKey = "ALL";
    let selectedFundKeys = ["ALL"];
    let multiFund = false;
    let activeTab = initialTabFromLocation();
    let tsRangeState = null;
    function normalizeFundCode(value) {{
      const text = String(value ?? "").trim().replace(/,/g, "");
      if (!text || text.toLowerCase() === "nan") return "";
      if (text.length >= 9 && text.startsWith("KR7") && /^\\d{{6}}$/.test(text.slice(3, 9))) return text.slice(3, 9);
      return /^\\d+$/.test(text) ? text.padStart(6, "0") : text;
    }}
    function loadLocalFundMaster() {{
      try {{
        const versions = JSON.parse(localStorage.getItem(FUND_MASTER_STORAGE_KEY) || "[]");
        if (!Array.isArray(versions) || !versions.length) return null;
        const latest = [...versions].sort((a, b) => String(a.effectiveDate || "").localeCompare(String(b.effectiveDate || ""))).at(-1);
        const byCode = new Map();
        (latest?.rows || []).forEach((row, index) => {{
          const code = normalizeFundCode(row["펀드코드"]);
          if (!code) return;
          byCode.set(code, {{
            name: String(row["펀드명(약식)"] || row["펀드명"] || "").trim(),
            type: String(row["유형"] || "기타").trim() || "기타",
            status: String(row["상태"] || "활성").trim() || "활성",
            order: index,
          }});
        }});
        return {{ effectiveDate: latest?.effectiveDate || "", byCode }};
      }} catch (error) {{
        console.warn("펀드 마스터 로컬 저장값을 읽지 못했습니다.", error);
        return null;
      }}
    }}
    function masterInfoFor(key) {{
      return loadLocalFundMaster()?.byCode.get(normalizeFundCode(key));
    }}
    function isFundActive(fund) {{
      if (fund.key === "ALL") return true;
      const info = masterInfoFor(fund.key);
      return !info || info.status !== "비활성";
    }}
    function displayFund(fund) {{
      if (fund.key === "ALL") return fund;
      const info = masterInfoFor(fund.key);
      return {{
        ...fund,
        name: info?.name || fund.name,
        type: info?.type || fund.type,
        masterOrder: info?.order ?? 9999,
      }};
    }}
    function visibleFunds() {{
      return funds.filter(isFundActive).map(displayFund).sort((a, b) => {{
        if (a.key === "ALL") return -1;
        if (b.key === "ALL") return 1;
        if ((a.masterOrder ?? 9999) !== (b.masterOrder ?? 9999)) return (a.masterOrder ?? 9999) - (b.masterOrder ?? 9999);
        return String(a.name).localeCompare(String(b.name), "ko");
      }});
    }}
    function setColumnHelp(open) {{
      if (!columnHelpModal) return;
      columnHelpModal.classList.toggle("active", open);
    }}
    function escHtml(value) {{
      return String(value ?? "").replace(/[&<>"']/g, (char) => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[char]));
    }}
    function fmtWon(value) {{
      return value == null || !Number.isFinite(Number(value)) ? "-" : Math.round(Number(value)).toLocaleString("ko-KR");
    }}
    function fmtEok(value) {{
      return value == null || !Number.isFinite(Number(value)) ? "-" : `${{(Number(value) / 100000000).toFixed(2)}}억`;
    }}
    function fmtPctJs(value) {{
      return value == null || !Number.isFinite(Number(value)) ? "-" : `${{(Number(value) * 100).toFixed(2)}}%`;
    }}
    function fmtPct1Js(value) {{
      return value == null || !Number.isFinite(Number(value)) ? "-" : `${{(Number(value) * 100).toFixed(1)}}%`;
    }}
    function fmtRateJs(value) {{
      return value == null || !Number.isFinite(Number(value)) ? "-" : `${{Number(value).toFixed(2)}}%`;
    }}
    function signedClass(value) {{
      return Number(value) < 0 ? "loss-cell" : "profit-cell";
    }}
    const SUPABASE_URL = "{DEFAULT_SUPABASE_URL}";
    const SUPABASE_KEY = "sb_publishable_T0q_8mB9yzcitTL7HH0SuA_W4DUcVtP";
    let liveQuotes = {{}};
    let quoteRefreshTimer = null;
    let stockSupabaseClient = null;
    function normalizeQuoteCode(value) {{
      const text = String(value ?? "").trim().replace(/,/g, "");
      if (!text || text.toLowerCase() === "nan") return "";
      if (text.length >= 9 && text.startsWith("KR7") && /^\\d{{6}}$/.test(text.slice(3, 9))) return text.slice(3, 9);
      return /^\\d+$/.test(text) ? text.padStart(6, "0") : text;
    }}
    function quoteForCode(code) {{
      return liveQuotes[normalizeQuoteCode(code)] || null;
    }}
    function quoteRateForCode(code) {{
      const quote = quoteForCode(code);
      const rate = quote?.change_rate ?? quote?.flu_rt;
      return Number.isFinite(Number(rate)) ? Number(rate) : null;
    }}
    function quotePriceForCode(code) {{
      const quote = quoteForCode(code);
      const price = quote?.price ?? quote?.cur_prc;
      return Number.isFinite(Number(price)) ? Math.abs(Number(price)) : null;
    }}
    function rateBarPct(value, limit = 5) {{
      if (value == null || !Number.isFinite(Number(value))) return "<td>-</td>";
      const rate = Number(value);
      const width = Math.min(50, Math.abs(rate / limit) * 50);
      const cls = rate >= 0 ? "bar-pos" : "bar-neg";
      const style = rate >= 0 ? `left:50%;width:${{width}}%` : `left:${{50 - width}}%;width:${{width}}%`;
      return `<td><div class="rate-bar"><span class="bar-zero"></span><span class="${{cls}}" style="${{style}}"></span><em>${{fmtRateJs(rate)}}</em></div></td>`;
    }}
    function activeStockRows(useAll = false) {{
      const rows = quoteSensitiveData.stockPositions || [];
      if (useAll || currentKey === "ALL") return rows;
      return rows.filter((row) => normalizeQuoteCode(row.fundCode) === normalizeQuoteCode(currentKey));
    }}
    function enrichedStockRows(rows) {{
      return rows.map((row) => {{
        const ratePct = quoteRateForCode(row.code);
        const marketPl = ratePct == null ? null : Number(row.eval || 0) * ratePct / 100;
        return {{
          ...row,
          ratePct,
          marketPl,
          pl: marketPl == null ? null : marketPl * Number(row.sign || 1),
          netExp: Number(row.eval || 0) * Number(row.sign || 1),
        }};
      }});
    }}
    function currentFundBasis() {{
      const rows = quoteSensitiveData.fundBases || [];
      if (currentKey === "ALL") {{
        return {{
          investment: rows.reduce((sum, row) => sum + Number(row.fundInvestment || 0), 0),
          fundExp: rows.reduce((sum, row) => sum + Number(row.fundExp || 0), 0),
        }};
      }}
      const row = rows.find((item) => normalizeQuoteCode(item.fundCode) === normalizeQuoteCode(currentKey));
      return {{ investment: Number(row?.fundInvestment || 0), fundExp: Number(row?.fundExp || 0) }};
    }}
    function directRows(kind) {{
      return (quoteSensitiveData.directStocks || []).filter((row) => row.kind === kind).map((row) => {{
        const price = quotePriceForCode(row.code);
        const ratePct = quoteRateForCode(row.code);
        const evalAmount = price == null ? null : Number(row.qty || 0) * price;
        return {{
          ...row,
          price,
          ratePct,
          eval: evalAmount,
          pl: evalAmount == null || ratePct == null ? null : evalAmount * ratePct / 100,
        }};
      }});
    }}
    function directPanel(kind, title, panelClass) {{
      const rows = directRows(kind).sort((a, b) => Number(b.eval || 0) - Number(a.eval || 0));
      const body = rows.map((row) => `<tr><td class="name-cell">${{escHtml(row.name)}}</td><td>${{fmtWon(row.qty)}}</td><td>${{fmtWon(row.price)}}</td><td>${{fmtEok(row.eval)}}</td>${{rateBarPct(row.ratePct, 10)}}<td class="${{signedClass(row.pl)}}">${{fmtEok1(row.pl)}}</td></tr>`).join("")
        + Array.from({{ length: Math.max(0, 8 - rows.length) }}, () => "<tr><td>&nbsp;</td><td></td><td></td><td></td><td></td><td></td></tr>").join("");
      const totalQty = rows.reduce((sum, row) => sum + Number(row.qty || 0), 0);
      const totalEval = rows.reduce((sum, row) => sum + Number(row.eval || 0), 0);
      const totalPl = rows.reduce((sum, row) => sum + Number(row.pl || 0), 0);
      const totalRow = `<tr class="total-row"><td class="total-label">합계</td><td>${{fmtWon(totalQty)}}</td><td></td><td>${{fmtEok(totalEval)}}</td><td></td><td class="${{signedClass(totalPl)}}">${{fmtEok1(totalPl)}}</td></tr>`;
      return `<article class="panel ${{panelClass}}"><div class="panel-title"><h4>${{title}}</h4><span>8행 슬롯 + 합계</span></div><div class="table-wrap direct"><table class="sortable-table"><thead><tr><th data-sort-index="0">종목명</th><th data-sort-index="1">수량</th><th data-sort-index="2">주가</th><th data-sort-index="3">평가액</th><th data-sort-index="4">등락율</th><th data-sort-index="5">PL</th></tr></thead><tbody>${{body}}${{totalRow}}</tbody></table></div></article>`;
    }}
    function renderLiveDirectPanels() {{
      const investment = dashboard.querySelector(".investment-panel");
      const product = dashboard.querySelector(".product-panel");
      if (investment) investment.outerHTML = directPanel("investment", "투자주식", "investment-panel");
      if (product) product.outerHTML = directPanel("product", "상품주식", "product-panel");
    }}
    function renderLiveTop20() {{
      const panel = dashboard.querySelector(".top20-panel");
      if (!panel) return;
      const rows = enrichedStockRows(activeStockRows()).reduce((map, row) => {{
        const key = `${{row.code}}|${{row.name}}`;
        const item = map.get(key) || {{ code: row.code, name: row.name, exp: 0, gross: 0, marketPl: 0, pl: 0, funds: new Set() }};
        item.exp += Number(row.netExp || 0);
        item.gross += Math.abs(Number(row.eval || 0));
        item.marketPl += Number(row.marketPl || 0);
        item.pl += Number(row.pl || 0);
        item.funds.add(row.fund);
        map.set(key, item);
        return map;
      }}, new Map());
      const denominator = currentFundBasis().investment;
      const tableRows = [...rows.values()].sort((a, b) => Math.abs(b.exp) - Math.abs(a.exp)).slice(0, 20);
      const body = tableRows.map((row) => {{
        const rate = row.gross ? row.marketPl / row.gross * 100 : null;
        return `<tr><td class="name-cell has-tip" title="${{escHtml(row.name)}}">${{escHtml(row.name)}}</td><td class="${{signedClass(row.exp)}}">${{fmtPctJs(denominator ? row.exp / denominator : null)}}</td><td>${{row.funds.size.toLocaleString("ko-KR")}}</td><td class="${{signedClass(row.exp)}}">${{fmtEok(row.exp)}}</td>${{rateBarPct(rate, 5)}}<td class="${{signedClass(row.pl)}}">${{fmtEok(row.pl)}}</td></tr>`;
      }}).join("");
      panel.innerHTML = `<div class="panel-title"><h4>보유내역 TOP20</h4><span>종목별 순노출 기준</span></div><div class="table-wrap top20-table"><table class="sortable-table"><thead><tr><th data-sort-index="0">종목명</th><th data-sort-index="1">비중</th><th data-sort-index="2">펀드수</th><th data-sort-index="3">Exp</th><th data-sort-index="4">등락율</th><th data-sort-index="5">손익</th></tr></thead><tbody>${{body}}</tbody></table></div>`;
    }}
    function renderLiveFundTable() {{
      const panel = dashboard.querySelector(".fund-pl-panel");
      if (!panel) return;
      const bases = new Map((quoteSensitiveData.fundBases || []).map((row) => [normalizeQuoteCode(row.fundCode), row]));
      const grouped = new Map();
      enrichedStockRows(activeStockRows(true)).forEach((row) => {{
        const key = normalizeQuoteCode(row.fundCode);
        const item = grouped.get(key) || {{ fundCode: key, fund: row.fund, exposure: 0, pl: 0, codes: new Set() }};
        item.exposure += Number(row.netExp || 0);
        item.pl += Number(row.pl || 0);
        item.codes.add(row.code);
        grouped.set(key, item);
      }});
      const catalog = (quoteSensitiveData.fundCatalog || []).filter((fund) => fund.fundCode);
      const rows = catalog.map((fund) => {{
        const key = normalizeQuoteCode(fund.fundCode);
        const stock = grouped.get(key) || {{ fundCode: key, fund: fund.fund, exposure: 0, pl: 0, codes: new Set() }};
        const base = bases.get(key) || {{}};
        const investment = Number(base.fundInvestment || 0);
        const fundExp = Number(base.fundExp || 0);
        const otherExp = fundExp - Number(stock.exposure || 0);
        return {{
          fundCode: key,
          fund: masterInfoFor(key)?.name || fund.fund || stock.fund,
          count: stock.codes.size,
          pl: Number(stock.pl || 0),
          investment,
          fundExp,
          exposure: Number(stock.exposure || 0),
          stockWeight: investment ? Number(stock.exposure || 0) / investment : null,
          otherExp,
          otherWeight: investment ? otherExp / investment : null,
          rate: investment ? Number(stock.pl || 0) / investment * 100 : null,
        }};
      }}).sort((a, b) => Number(b.rate ?? -999) - Number(a.rate ?? -999));
      const body = rows.map((row) => `<tr${{row.fundCode === normalizeQuoteCode(currentKey) ? " class='highlight-row'" : ""}}><td>${{escHtml(row.fund)}}</td><td>${{row.count.toLocaleString("ko-KR")}}</td>${{rateBarPct(row.rate, 5)}}<td class="${{signedClass(row.pl)}}">${{fmtEok1(row.pl)}}</td><td>${{fmtEok1(row.investment)}}</td><td>${{fmtEok1(row.fundExp)}}</td><td>${{fmtEok1(row.exposure)}}</td><td>${{fmtPct1Js(row.stockWeight)}}</td><td>${{fmtEok1(row.otherExp)}}</td><td>${{fmtPct1Js(row.otherWeight)}}</td></tr>`).join("");
      const totals = rows.reduce((acc, row) => {{
        acc.count += row.count; acc.pl += row.pl; acc.investment += row.investment; acc.fundExp += row.fundExp; acc.exposure += row.exposure; acc.otherExp += row.otherExp; return acc;
      }}, {{ count: 0, pl: 0, investment: 0, fundExp: 0, exposure: 0, otherExp: 0 }});
      const totalRate = totals.investment ? totals.pl / totals.investment * 100 : null;
      const totalRow = `<tr class="total-row"><td class="total-label">합계</td><td>${{totals.count.toLocaleString("ko-KR")}}</td>${{rateBarPct(totalRate, 5)}}<td class="${{signedClass(totals.pl)}}">${{fmtEok1(totals.pl)}}</td><td>${{fmtEok1(totals.investment)}}</td><td>${{fmtEok1(totals.fundExp)}}</td><td>${{fmtEok1(totals.exposure)}}</td><td>${{fmtPct1Js(totals.investment ? totals.exposure / totals.investment : null)}}</td><td>${{fmtEok1(totals.otherExp)}}</td><td>${{fmtPct1Js(totals.investment ? totals.otherExp / totals.investment : null)}}</td></tr>`;
      panel.innerHTML = `<div class="panel-title"><h4>수익증권</h4><div class="title-actions"><button type="button" class="column-help-button" data-open-column-help>컬럼 설명</button><span>투자금 기준</span></div></div><div class="table-wrap fund-pl"><table class="sortable-table"><colgroup><col style="width:78px"><col style="width:38px"><col style="width:52px"><col style="width:58px"><col style="width:72px"><col style="width:72px"><col style="width:62px"><col style="width:46px"><col style="width:66px"><col style="width:46px"></colgroup><thead><tr><th rowspan="2" data-sort-index="0">펀드명</th><th rowspan="2" data-sort-index="1">종목수</th><th rowspan="2" data-sort-index="2">등락율</th><th rowspan="2" data-sort-index="3">주식PL</th><th rowspan="2" data-sort-index="4">당행 평가액</th><th rowspan="2" data-sort-index="5">펀드 Exp</th><th colspan="2">주식</th><th colspan="2">채권 및 현금</th></tr><tr><th data-sort-index="6">Exp</th><th data-sort-index="7">비중</th><th data-sort-index="8">Exp</th><th data-sort-index="9">비중</th></tr></thead><tbody>${{body}}${{totalRow}}</tbody></table></div>`;
    }}
    function refreshLiveKpis() {{
      const rows = enrichedStockRows(activeStockRows());
      const fundPl = rows.reduce((sum, row) => sum + Number(row.pl || 0), 0);
      const investmentRows = directRows("investment");
      const productRows = directRows("product");
      const investmentPl = investmentRows.reduce((sum, row) => sum + Number(row.pl || 0), 0);
      const productPl = productRows.reduce((sum, row) => sum + Number(row.pl || 0), 0);
      const investmentExp = investmentRows.reduce((sum, row) => sum + Number(row.eval || 0), 0);
      const productExp = productRows.reduce((sum, row) => sum + Number(row.eval || 0), 0);
      const basis = currentFundBasis();
      const netExp = rows.reduce((sum, row) => sum + Number(row.netExp || 0), 0);
      const totalPl = fundPl + investmentPl + productPl;
      const totalExposure = netExp + investmentExp + productExp;
      const plValues = [totalPl, fundPl, investmentPl, productPl];
      dashboard.querySelectorAll(".pl-group .kpi strong").forEach((node, idx) => node.textContent = fmtEok(plValues[idx]));
      const expValues = [totalExposure, basis.investment, netExp, investmentExp + productExp];
      dashboard.querySelectorAll(".exposure-group .kpi strong").forEach((node, idx) => node.textContent = fmtEok(expValues[idx]));
      const netSub = dashboard.querySelectorAll(".exposure-group .kpi small")[2];
      if (netSub) netSub.textContent = `투자금 대비 ${{fmtPctJs(basis.investment ? netExp / basis.investment : null)}}`;
    }}
    function rebuildHoldingDetailsForCurrentFund() {{
      const denominator = currentFundBasis().investment;
      const groupedByPosition = {{ "매수": new Map(), "매도": new Map() }};
      enrichedStockRows(activeStockRows()).forEach((row) => {{
        const position = row.position === "매도" ? "매도" : "매수";
        const key = `${{row.code}}|${{row.name}}|${{position}}`;
        const item = groupedByPosition[position].get(key) || {{
          key, name: row.name, sector: row.sector, position, eval: 0, cost: 0, profit: 0, pl: 0, marketPl: 0, qty: 0, funds: new Map(),
        }};
        item.eval += Number(row.eval || 0);
        item.cost += Number(row.cost || 0);
        item.profit += Number(row.profit || 0);
        item.pl += Number(row.pl || 0);
        item.marketPl += Number(row.marketPl || 0);
        item.qty += Number(row.qty || 0);
        const fund = item.funds.get(row.fund) || {{ fund: row.fund, eval: 0, cost: 0, profit: 0, qty: 0, investment: Number(row.fundInvestment || 0) }};
        fund.eval += Number(row.eval || 0); fund.cost += Number(row.cost || 0); fund.profit += Number(row.profit || 0); fund.qty += Number(row.qty || 0);
        item.funds.set(row.fund, fund);
        groupedByPosition[position].set(key, item);
      }});
      const toRecords = (map, position) => [...map.values()].map((item) => {{
        const weight = denominator ? item.eval / denominator * (position === "매도" ? -1 : 1) : null;
        const details = [...item.funds.values()].map((fund) => ({{
          fund: fund.fund,
          weight: fund.investment ? fund.eval / fund.investment * (position === "매도" ? -1 : 1) : null,
          cost: fund.cost,
          eval: fund.eval,
          profit: fund.profit,
          avgPrice: fund.qty ? fund.cost / fund.qty : null,
          return: fund.cost ? fund.eval / fund.cost - 1 : null,
        }})).sort((a, b) => Math.abs(b.eval || 0) - Math.abs(a.eval || 0));
        return {{
          key: item.key,
          name: item.name,
          weight,
          rate: item.eval ? item.marketPl / item.eval : null,
          pl: item.pl,
          sector: item.sector,
          fundCount: item.funds.size,
          eval: item.eval,
          cost: item.cost,
          avgPrice: item.qty ? item.cost / item.qty : null,
          profit: item.profit,
          return: item.cost ? item.eval / item.cost - 1 : null,
          portfolioWeight: weight,
          details,
        }};
      }}).sort((a, b) => Math.abs(b.eval || 0) - Math.abs(a.eval || 0));
      holdingDetails[currentKey] = {{ "매수": toRecords(groupedByPosition["매수"], "매수"), "매도": toRecords(groupedByPosition["매도"], "매도") }};
    }}
    function renderLiveQuoteViews() {{
      if (!Object.keys(liveQuotes).length) return;
      refreshLiveKpis();
      renderLiveDirectPanels();
      renderLiveTop20();
      renderLiveFundTable();
      rebuildHoldingDetailsForCurrentFund();
      renderHoldingTables();
      bindSortableTables();
    }}
    async function getStockSupabaseClient() {{
      if (stockSupabaseClient) return stockSupabaseClient;
      if (window.parent !== window && window.parent.dashboardSupabase) {{
        stockSupabaseClient = window.parent.dashboardSupabase;
        return stockSupabaseClient;
      }}
      const {{ createClient }} = await import("https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm");
      stockSupabaseClient = createClient(SUPABASE_URL, SUPABASE_KEY, {{
        auth: {{ persistSession: true, autoRefreshToken: true }}
      }});
      return stockSupabaseClient;
    }}
    async function fetchSupabaseQuotes() {{
      const client = await getStockSupabaseClient();
      const {{ data, error }} = await client
        .from("kiwoom_realtime_quotes")
        .select("code,name,price,change_rate,industry,market,kiwoom_rest_code,proxy_code,error,payload,collected_at")
        .order("updated_at", {{ ascending: false }})
        .limit(2000);
      if (error) throw error;
      const stocks = {{}};
      (data || []).forEach((row) => {{
        const code = normalizeQuoteCode(row.code);
        if (!code || stocks[code]) return;
        stocks[code] = {{
          ...(row.payload && typeof row.payload === "object" ? row.payload : {{}}),
          name: row.name || row.payload?.name || code,
          price: row.price,
          change_rate: row.change_rate,
          industry: row.industry || "",
          market: row.market || "",
          kiwoom_rest_code: row.kiwoom_rest_code,
          proxy_code: row.proxy_code,
          error: row.error,
          collected_at: row.collected_at,
        }};
      }});
      return stocks;
    }}
    async function refreshQuotes(manual = false) {{
      const status = document.getElementById("quoteStatus");
      if (status) status.textContent = "시세 확인 중";
      try {{
        try {{
          const response = await fetch(`kiwoom_quotes.json?ts=${{Date.now()}}`, {{ cache: "no-store" }});
          if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
          const payload = await response.json();
          liveQuotes = payload.stocks || payload || {{}};
        }} catch (fileError) {{
          liveQuotes = await fetchSupabaseQuotes();
        }}
        renderLiveQuoteViews();
        const available = Object.values(liveQuotes).filter((item) => item && item.price != null).length;
        if (status) status.textContent = `${{new Date().toLocaleTimeString("ko-KR", {{ hour12:false }})}} · ${{available}}종목`;
      }} catch (error) {{
        if (status) status.textContent = manual ? "시세 조회 실패" : "시세 대기";
        if (manual) console.warn("시세 갱신 실패", error);
      }}
    }}
    function setQuoteAutoRefresh(value) {{
      if (quoteRefreshTimer) window.clearInterval(quoteRefreshTimer);
      quoteRefreshTimer = null;
      const ms = Number(value);
      if (Number.isFinite(ms) && ms > 0) {{
        refreshQuotes(false);
        quoteRefreshTimer = window.setInterval(() => refreshQuotes(false), ms);
      }}
    }}
    function snapshotFileName(date) {{
      return "fund_dashboard.html";
    }}
    function targetUrlForSnapshot(date) {{
      const params = new URLSearchParams();
      if (date) params.set("date", date);
      if (activeTab && activeTab !== "summary") params.set("tab", activeTab);
      const suffix = params.toString() ? `?${{params.toString()}}` : "";
      return `${{snapshotFileName(date)}}${{suffix}}`;
    }}
    function initialTabFromLocation() {{
      const tab = new URLSearchParams(window.location.search).get("tab");
      return ["summary", "holdings", "trades", "timeseries"].includes(tab) ? tab : "summary";
    }}
    async function loadExternalDataIfNeeded() {{
      if (views && Object.keys(views).length) return;
      const indexResponse = await fetch("data/fund_dashboard_index.json", {{ cache: "no-store" }});
      if (!indexResponse.ok) throw new Error("기준일 인덱스를 불러오지 못했습니다.");
      const index = await indexResponse.json();
      const requestedDate = new URLSearchParams(window.location.search).get("date");
      const selectedDate = requestedDate && index.dates?.includes(requestedDate) ? requestedDate : index.latestDate;
      const dataResponse = await fetch(`data/fund_dashboard_${{selectedDate}}.json`, {{ cache: "no-store" }});
      if (!dataResponse.ok) throw new Error(`대시보드 데이터를 불러오지 못했습니다: ${{selectedDate}}`);
      const data = await dataResponse.json();
      views = data.views || {{}};
      funds = data.funds || [];
      snapshotDates = data.snapshotDates || index.dates || [];
      currentSnapshotDate = data.currentSnapshotDate || selectedDate;
      latestSnapshotDate = data.latestSnapshotDate || index.latestDate || selectedDate;
      tradeHistory = data.tradeHistory || [];
      holdingDetails = data.holdingDetails || {{}};
      quoteSensitiveData = data.quoteSensitiveData || {{}};
      tradeDates = tradeHistory.map(row => row.date).filter(Boolean).sort();
      tradeMax = tradeDates.at(-1) || "";
      tradeMin = tradeDates[0] || "";
      defaultTradeStart = tradeMax ? (() => {{ const d=new Date(`${{tradeMax}}T00:00:00`); d.setMonth(d.getMonth()-1); return d.toISOString().slice(0,10); }})() : "";
      tradeStart = defaultTradeStart;
      tradeEnd = tradeMax;
    }}
    function bindSnapshotSelector() {{
      const select = document.getElementById("snapshotDate");
      if (!select) return;
      const dates = (snapshotDates.length ? snapshotDates : (currentSnapshotDate ? [currentSnapshotDate] : [])).slice().sort((a, b) => b.localeCompare(a));
      select.innerHTML = dates.map((date) => `<option value="${{date}}">${{date}}${{date === latestSnapshotDate ? " 최신" : ""}}</option>`).join("");
      select.value = currentSnapshotDate || latestSnapshotDate || dates.at(-1) || "";
      select.onchange = () => {{
        if (!select.value || select.value === currentSnapshotDate) return;
        window.location.href = targetUrlForSnapshot(select.value);
      }};
      const latestButton = document.getElementById("latestSnapshot");
      if (latestButton) latestButton.onclick = () => {{
        if (latestSnapshotDate && latestSnapshotDate !== currentSnapshotDate) window.location.href = targetUrlForSnapshot(latestSnapshotDate);
      }};
    }}
    function holdingTableShell(rowsHtml) {{
      return `<div class="table-wrap holding-detail"><table class="sortable-table">
        <colgroup><col style="width:132px"><col style="width:62px"><col style="width:66px"><col style="width:74px"><col style="width:84px"><col style="width:58px"><col style="width:82px"><col style="width:82px"><col style="width:76px"><col style="width:98px"><col style="width:82px"></colgroup>
        <thead><tr><th data-sort-index="0">종목명</th><th data-sort-index="1">편입비</th><th data-sort-index="2">등락율</th><th data-sort-index="3">예상PL</th><th data-sort-index="4">업종</th><th data-sort-index="5">보유펀드</th><th data-sort-index="6">평가액</th><th data-sort-index="7">취득원가</th><th data-sort-index="8">취득단가</th><th data-sort-index="9">평가손익(전일기준)</th><th data-sort-index="10">평단수익률</th></tr></thead>
        <tbody>${{rowsHtml}}</tbody></table></div>`;
    }}
    function holdingRateBar(value) {{
      if (value == null || !Number.isFinite(Number(value))) return "<td>-</td>";
      const pct = Number(value) * 100;
      const width = Math.min(50, Math.abs(pct) / 5 * 50);
      const cls = pct >= 0 ? "bar-pos" : "bar-neg";
      const style = pct >= 0 ? `left:50%;width:${{width}}%` : `right:50%;width:${{width}}%`;
      return `<td><div class="rate-bar"><span class="bar-zero"></span><span class="${{cls}}" style="${{style}}"></span><em>${{pct.toFixed(2)}}%</em></div></td>`;
    }}
    function sumRows(rows, key) {{
      return rows.reduce((total, row) => total + (Number.isFinite(Number(row[key])) ? Number(row[key]) : 0), 0);
    }}
    function holdingTotalRow(rows) {{
      const weight = sumRows(rows, "weight");
      const pl = sumRows(rows, "pl");
      const evalAmount = sumRows(rows, "eval");
      const cost = sumRows(rows, "cost");
      return `
        <tr class="total-row">
          <td class="total-label">합계</td>
          <td>${{fmtPctJs(weight)}}</td>
          <td></td>
          <td class="${{signedClass(pl)}}">${{fmtEok(pl)}}</td>
          <td></td>
          <td></td>
          <td>${{fmtEok(evalAmount)}}</td>
          <td>${{fmtEok(cost)}}</td>
          <td></td>
          <td></td>
          <td></td>
        </tr>`;
    }}
    function renderHoldingTables() {{
      const data = holdingDetails[currentKey] || holdingDetails.ALL || {{}};
      dashboard.querySelectorAll("[data-holding-position]").forEach((host) => {{
        const position = host.dataset.holdingPosition;
        const input = dashboard.querySelector(`[data-holding-search="${{position}}"]`);
        const query = (input?.value || "").trim().toLowerCase();
        let totalBasisRows = [...(data[position] || [])];
        if (query) totalBasisRows = totalBasisRows.filter((row) => `${{row.name}} ${{row.sector}} ${{(row.details || []).map((item) => item.fund).join(" ")}}`.toLowerCase().includes(query));
        const rows = query ? totalBasisRows : totalBasisRows.slice(0, 20);
        if (!rows.length) {{
          host.innerHTML = `<div class="empty">${{position}} 포지션 보유내역이 없습니다.</div>`;
          return;
        }}
        const bodyRows = rows.map((row) => `
          <tr>
            <td class="name-cell">${{escHtml(row.name)}}</td>
            <td>${{fmtPctJs(row.weight)}}</td>
            ${{holdingRateBar(row.rate)}}
            <td class="${{signedClass(row.pl)}}">${{fmtEok(row.pl)}}</td>
            <td>${{escHtml(row.sector)}}</td>
            <td><button type="button" class="fund-count-button" data-holding-key="${{escHtml(row.key)}}">${{Number(row.fundCount || 0).toLocaleString("ko-KR")}}</button></td>
            <td>${{fmtEok(row.eval)}}</td>
            <td>${{fmtEok(row.cost)}}</td>
            <td>${{fmtWon(row.avgPrice)}}</td>
            <td class="${{signedClass(row.profit)}}">${{fmtEok(row.profit)}}</td>
            <td class="${{signedClass(row.return)}}">${{fmtPctJs(row.return)}}</td>
          </tr>`).join("") + holdingTotalRow(totalBasisRows);
        host.innerHTML = holdingTableShell(bodyRows);
        const table = host.querySelector("table");
        if (table) {{
          table.dataset.sortableBound = "";
          bindSortableTables(table);
        }}
        if (input && input.dataset.bound !== "1") {{
          input.dataset.bound = "1";
          input.addEventListener("input", renderHoldingTables);
        }}
      }});
    }}
    function setHoldingFundModal(open, row = null) {{
      const modal = document.getElementById("holdingFundModal");
      const body = document.getElementById("holdingFundBody");
      if (!modal || !body) return;
      if (!open || !row) {{
        modal.classList.remove("active");
        return;
      }}
      const detailRows = (row.details || []).map((item) => `
        <tr>
          <td title="${{escHtml(item.fund)}}">${{escHtml(item.fund)}}</td>
          <td>${{fmtPctJs(item.weight)}}</td>
          <td>${{fmtEok(item.cost)}}</td>
          <td>${{fmtEok(item.eval)}}</td>
          <td class="${{signedClass(item.profit)}}">${{fmtEok(item.profit)}}</td>
          <td>${{fmtWon(item.avgPrice)}}</td>
          <td class="${{signedClass(item.return)}}">${{fmtPctJs(item.return)}}</td>
        </tr>`).join("");
      const totalWeight = row.portfolioWeight;
      const totalCost = sumRows(row.details || [], "cost");
      const totalEval = sumRows(row.details || [], "eval");
      const totalProfit = sumRows(row.details || [], "profit");
      const totalReturn = totalCost ? totalEval / totalCost - 1 : null;
      const totalRow = `<tr class="total-row"><td class="total-label">합계</td><td>${{fmtPctJs(totalWeight)}}</td><td>${{fmtEok(totalCost)}}</td><td>${{fmtEok(totalEval)}}</td><td class="${{signedClass(totalProfit)}}">${{fmtEok(totalProfit)}}</td><td></td><td class="${{signedClass(totalReturn)}}">${{fmtPctJs(totalReturn)}}</td></tr>`;
      body.innerHTML = `<table class="holding-fund-table"><thead><tr><th>펀드명</th><th>펀드내 편입비</th><th>취득원가</th><th>평가액</th><th>평가손익(전일기준)</th><th>평단가</th><th>평단수익률</th></tr></thead><tbody>${{detailRows}}${{totalRow}}</tbody></table>`;
      modal.classList.add("active");
    }}
    function fmtEok1(value) {{
      if (value == null || Number.isNaN(Number(value))) return "-";
      const sign = Number(value) < 0 ? "-" : "";
      return `${{sign}}${{(Math.abs(Number(value)) / 100000000).toLocaleString("ko-KR", {{minimumFractionDigits:1, maximumFractionDigits:1}})}}억`;
    }}
    function parseTsData(panel) {{
      try {{ return JSON.parse(panel.querySelector(".ts-daily-data")?.innerHTML || "[]"); }}
      catch (error) {{ return []; }}
    }}
    function monthStartFrom(endDate, months) {{
      const date = new Date(`${{endDate}}T00:00:00`);
      date.setMonth(date.getMonth() - Number(months || 1));
      date.setDate(date.getDate() + 1);
      return date.toISOString().slice(0, 10);
    }}
    function dayStartFrom(endDate, days) {{
      const date = new Date(`${{endDate}}T00:00:00`);
      date.setDate(date.getDate() - Number(days || 1) + 1);
      return date.toISOString().slice(0, 10);
    }}
    function currentTsRange(panel) {{
      const start = panel.querySelector("[data-ts-start]")?.value || "";
      const end = panel.querySelector("[data-ts-end]")?.value || "";
      return {{ start, end }};
    }}
    function setTsRangeState(panel, mode = "custom", months = null) {{
      const range = currentTsRange(panel);
      tsRangeState = {{ mode, months, start: range.start, end: range.end }};
    }}
    function filterTsRows(rows, range) {{
      return rows.filter((row) => (!range.start || row.date >= range.start) && (!range.end || row.date <= range.end));
    }}
    function sampleTsRows(rows, target = 24) {{
      if (rows.length <= target) return rows;
      const lastIndex = rows.length - 1;
      const step = Math.ceil(rows.length / target);
      const sampled = rows.filter((_, idx) => idx % step === 0 || idx === lastIndex);
      if (sampled.at(-1)?.date !== rows.at(-1)?.date) sampled.push(rows.at(-1));
      return sampled.slice(-target);
    }}
    function renderTsComboChart(host, rows) {{
      if (!host || !rows.length) {{
        if (host) host.innerHTML = `<div class="empty">선택한 기간의 시계열 데이터가 없습니다.</div>`;
        return;
      }}
      const width = Math.max(760, host.clientWidth || 1100), height = 350;
      const left = 70, right = 64, top = 42, bottom = 58;
      const plotW = width - left - right, plotH = height - top - bottom;
      const chartRows = sampleTsRows(rows);
      const maxExp = Math.max(1, ...chartRows.map((row) => Number(row.stockExp || 0)));
      const maxWeight = Math.max(0.0001, ...chartRows.map((row) => Number(row.stockWeight || 0)));
      const step = plotW / Math.max(1, chartRows.length);
      const barW = Math.max(4, Math.min(34, step * .52));
      const labelStride = 1;
      const valueStride = 1;
      const yExp = (v) => top + plotH - plotH * Number(v || 0) / maxExp;
      const yWeight = (v) => top + plotH - plotH * Number(v || 0) / maxWeight;
      let svg = `<svg viewBox="0 0 ${{width}} ${{height}}" class="timeseries-combo-chart">`;
      svg += `<text x="16" y="20" class="ts-axis">주식 Exp(좌)</text><text x="${{width - 12}}" y="20" text-anchor="end" class="ts-axis">주식비중(우)</text>`;
      for (let i = 0; i < 5; i++) {{
        const y = top + plotH * i / 4;
        const expTick = maxExp * (4 - i) / 4;
        const weightTick = maxWeight * (4 - i) / 4;
        svg += `<line x1="${{left}}" y1="${{y}}" x2="${{width - right}}" y2="${{y}}" class="bar-grid"></line>`;
        svg += `<text x="${{left - 8}}" y="${{y + 4}}" text-anchor="end" class="ts-axis">${{fmtEok1(expTick)}}</text>`;
        svg += `<text x="${{width - 8}}" y="${{y + 4}}" text-anchor="end" class="ts-axis">${{(weightTick * 100).toFixed(1)}}%</text>`;
      }}
      const points = [];
      chartRows.forEach((row, idx) => {{
        const x = left + step * (idx + .5);
        const barY = yExp(row.stockExp);
        const barH = top + plotH - barY;
        svg += `<rect x="${{x - barW / 2}}" y="${{barY}}" width="${{barW}}" height="${{Math.max(1, barH)}}" rx="2" fill="#008485"></rect>`;
        if (idx % valueStride === 0 || idx === chartRows.length - 1) svg += `<text x="${{x}}" y="${{barY + Math.max(13, barH / 2)}}" text-anchor="middle" class="ts-bar-label">${{fmtEok1(row.stockExp)}}</text>`;
        points.push([x, yWeight(row.stockWeight), row.stockWeight]);
        if (idx % labelStride === 0 || idx === chartRows.length - 1) svg += `<text x="${{x}}" y="${{height - 24}}" text-anchor="middle" class="ts-date">${{row.date.slice(5)}}</text>`;
      }});
      svg += `<path d="${{points.map((p,i)=>`${{i ? "L" : "M"}} ${{p[0].toFixed(1)}} ${{p[1].toFixed(1)}}`).join(" ")}}" fill="none" stroke="#12372d" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>`;
      points.forEach((p, idx) => {{
        svg += `<circle cx="${{p[0]}}" cy="${{p[1]}}" r="3.6" fill="#12372d" stroke="#fff" stroke-width="1.3"></circle>`;
        if (idx % valueStride === 0 || idx === chartRows.length - 1) svg += `<text x="${{p[0]}}" y="${{p[1] - 9}}" text-anchor="middle" class="ts-line-label">${{(Number(p[2] || 0) * 100).toFixed(1)}}%</text>`;
      }});
      svg += `</svg>`;
      host.innerHTML = `<div class="ts-chart-scroll">${{svg}}</div>`;
    }}
    function renderTsDailyTable(host, rows) {{
      if (!host || !rows.length) {{
        if (host) host.innerHTML = `<div class="empty">선택한 기간의 일별 요약이 없습니다.</div>`;
        return;
      }}
      const body = [...rows].sort((a,b) => b.date.localeCompare(a.date)).map((row) => `<tr><td>${{row.date}}</td><td>${{fmtEok1(row.bankValue)}}</td><td>${{fmtEok1(row.fundExp)}}</td><td class="${{signedClass(row.stockExp)}}">${{fmtEok1(row.stockExp)}}</td><td class="${{signedClass(row.stockWeight)}}">${{fmtPctJs(row.stockWeight)}}</td><td>${{Number(row.stockCount || 0).toLocaleString("ko-KR")}}</td></tr>`).join("");
      host.innerHTML = `<div class="table-wrap timeseries-table ts-daily-table"><table class="sortable-table"><thead><tr><th data-sort-index="0">기준일</th><th data-sort-index="1">당행 평가액</th><th data-sort-index="2">펀드 Exp</th><th data-sort-index="3">주식 Exp</th><th data-sort-index="4">주식비중</th><th data-sort-index="5">종목수</th></tr></thead><tbody>${{body}}</tbody></table></div>`;
      const table = host.querySelector("table");
      if (table) bindSortableTables(table);
    }}
    function renderTsStockDailyTable(host, row) {{
      if (!host || !row) return;
      const panel = dashboard.querySelector('[data-panel="timeseries"]');
      const range = panel ? currentTsRange(panel) : {{ start:"", end:"" }};
      const history = (row.history || []).filter((item) => (!range.start || item.date >= range.start) && (!range.end || item.date <= range.end));
      if (!history.length) {{
        host.innerHTML = `<div class="empty">선택한 기간의 종목별 일별 데이터가 없습니다.</div>`;
        return;
      }}
      const body = [...history].sort((a,b) => b.date.localeCompare(a.date)).map((item) => `<tr><td>${{item.date}}</td><td class="${{signedClass(item.exp)}}">${{fmtEok1(item.exp)}}</td><td class="${{signedClass(item.weight)}}">${{fmtPctJs(item.weight)}}</td></tr>`).join("");
      host.innerHTML = `<div class="panel-title ts-stock-daily-title"><h4>${{escHtml(row.name)}} 일별 요약</h4><span>날짜 내림차순</span></div><div class="table-wrap timeseries-table ts-stock-daily-table"><table class="sortable-table"><thead><tr><th data-sort-index="0">기준일</th><th data-sort-index="1">Exp</th><th data-sort-index="2">편입비</th></tr></thead><tbody>${{body}}</tbody></table></div>`;
      const table = host.querySelector("table");
      if (table) bindSortableTables(table);
    }}
    function downloadTsDailyCsv(panel, rows) {{
      const header = ["기준일","당행 평가액","펀드 Exp","주식 Exp","주식비중","종목수"];
      const lines = [header.join(",")].concat([...rows].sort((a,b) => b.date.localeCompare(a.date)).map((row) => [
        row.date,
        Math.round(Number(row.bankValue || 0)),
        Math.round(Number(row.fundExp || 0)),
        Math.round(Number(row.stockExp || 0)),
        row.stockWeight == null ? "" : (Number(row.stockWeight) * 100).toFixed(4) + "%",
        Number(row.stockCount || 0)
      ].join(",")));
      const blob = new Blob(["\ufeff" + lines.join("\\n")], {{ type:"text/csv;charset=utf-8" }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `timeseries_daily_${{currentKey}}_${{panel.querySelector("[data-ts-start]")?.value || "start"}}_${{panel.querySelector("[data-ts-end]")?.value || "end"}}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    }}
    function renderTimeSeriesOverview(panel) {{
      const rows = parseTsData(panel);
      if (!rows.length) return;
      const range = currentTsRange(panel);
      const filtered = filterTsRows(rows, range);
      renderTsComboChart(panel.querySelector(".ts-overview-chart"), filtered);
      renderTsDailyTable(panel.querySelector(".ts-daily-host"), filtered);
      const latest = filtered[filtered.length - 1];
      const prev = filtered.length > 1 ? filtered[filtered.length - 2] : null;
      if (latest) {{
        panel.querySelector("[data-ts-kpi='date']").textContent = latest.date;
        panel.querySelector("[data-ts-kpi='stockExp']").textContent = fmtEok(latest.stockExp);
        panel.querySelector("[data-ts-kpi='stockWeight']").textContent = fmtPctJs(latest.stockWeight);
        panel.querySelector("[data-ts-kpi='stockCount']").textContent = `${{Number(latest.stockCount || 0).toLocaleString("ko-KR")}}개`;
        const expNote = panel.querySelector("[data-ts-kpi-note='stockExp']");
        const weightNote = panel.querySelector("[data-ts-kpi-note='stockWeight']");
        if (expNote) expNote.textContent = prev ? `전일 대비 ${{fmtEok(Number(latest.stockExp || 0) - Number(prev.stockExp || 0))}}` : "비교일 없음";
        if (weightNote) weightNote.textContent = prev && latest.stockWeight != null && prev.stockWeight != null ? `전일 대비 ${{fmtPctJs(Number(latest.stockWeight) - Number(prev.stockWeight))}}` : "비교일 없음";
      }}
      panel.__tsFilteredRows = filtered;
      const activeStock = panel.querySelector('[data-ts-subpanel="stock"]')?.classList.contains("active");
      if (activeStock) bindTimeSeriesStockWidgets(true);
    }}
    function bindTimeSeriesControls() {{
      const panel = dashboard.querySelector('[data-panel="timeseries"]');
      if (!panel) return;
      const rows = parseTsData(panel);
      if (!rows.length) return;
      const startInput = panel.querySelector("[data-ts-start]");
      const endInput = panel.querySelector("[data-ts-end]");
      const minDate = rows[0].date;
      const maxDate = rows[rows.length - 1].date;
      [startInput, endInput].forEach((input) => {{ if (input) {{ input.min = minDate; input.max = maxDate; }} }});
      if (!panel.dataset.rangeInitialized) {{
        panel.dataset.rangeInitialized = "1";
        const defaultStart = monthStartFrom(maxDate, 1) < minDate ? minDate : monthStartFrom(maxDate, 1);
        const state = tsRangeState || {{ mode:"preset", months:"1" }};
        if (state.mode === "preset") {{
          const months = state.months || "1";
          const presetStart = monthStartFrom(maxDate, months) < minDate ? minDate : monthStartFrom(maxDate, months);
          if (endInput) endInput.value = maxDate;
          if (startInput) startInput.value = presetStart;
          panel.querySelectorAll("[data-ts-months]").forEach((button) => button.classList.toggle("active", button.dataset.tsMonths === String(months)));
        }} else {{
          if (endInput) endInput.value = state.end || maxDate;
          if (startInput) startInput.value = state.start || defaultStart;
          panel.querySelectorAll("[data-ts-months]").forEach((button) => button.classList.remove("active"));
        }}
      }}
      if (panel.dataset.rangeBound !== "1") {{
        panel.dataset.rangeBound = "1";
        panel.querySelectorAll("[data-ts-months]").forEach((button) => button.addEventListener("click", () => {{
          panel.querySelectorAll("[data-ts-months]").forEach((item) => item.classList.toggle("active", item === button));
          if (endInput) endInput.value = maxDate;
          if (startInput) startInput.value = monthStartFrom(maxDate, button.dataset.tsMonths) < minDate ? minDate : monthStartFrom(maxDate, button.dataset.tsMonths);
          setTsRangeState(panel, "preset", button.dataset.tsMonths);
          renderTimeSeriesOverview(panel);
        }}));
        panel.querySelector("[data-ts-apply]")?.addEventListener("click", () => {{
          panel.querySelectorAll("[data-ts-months]").forEach((item) => item.classList.remove("active"));
          setTsRangeState(panel, "custom", null);
          renderTimeSeriesOverview(panel);
        }});
        panel.querySelector("[data-ts-download]")?.addEventListener("click", () => downloadTsDailyCsv(panel, panel.__tsFilteredRows || filterTsRows(rows, currentTsRange(panel))));
      }}
      renderTimeSeriesOverview(panel);
    }}
    function renderTsRankChart(host, rows) {{
      const width = 980, height = Math.max(290, 42 + rows.length * 28);
      const left = 132, right = 92, top = 22, rowH = 26;
      const maxAbs = Math.max(0.0001, ...rows.map((row) => Math.abs(Number(row.deltaWeight || 0))));
      let svg = `<svg viewBox="0 0 ${{width}} ${{height}}" class="ts-stock-svg" style="width:${{width}}px;max-width:none">`;
      svg += `<line x1="${{left}}" y1="14" x2="${{left}}" y2="${{height - 18}}" class="zero"></line>`;
      rows.forEach((row, idx) => {{
        const y = top + idx * rowH;
        const value = Number(row.deltaWeight || 0);
        const widthPx = Math.abs(value) / maxAbs * (width - left - right);
        const color = value >= 0 ? "#008485" : "#d92d20";
        svg += `<text x="8" y="${{y + 15}}" class="ts-stock-bar-label">${{escHtml(row.name).slice(0, 16)}}</text>`;
        svg += `<rect x="${{left}}" y="${{y + 4}}" width="${{widthPx}}" height="15" rx="3" fill="${{color}}" opacity=".82"></rect>`;
        svg += `<text x="${{left + widthPx + 8}}" y="${{y + 16}}" class="ts-stock-value">${{(value * 100).toFixed(2)}}% · ${{fmtEok1(row.deltaExp)}}</text>`;
      }});
      svg += `</svg>`;
      host.innerHTML = svg;
    }}
    function renderTsSelectedChart(host, row) {{
      const panel = dashboard.querySelector('[data-panel="timeseries"]');
      const range = panel ? currentTsRange(panel) : {{ start:"", end:"" }};
      const fullHistory = (row.history || []).filter((item) => (!range.start || item.date >= range.start) && (!range.end || item.date <= range.end));
      const history = sampleTsRows(fullHistory);
      if (!history.length) {{
        host.innerHTML = `<div class="empty">선택한 종목의 시계열 데이터가 없습니다.</div>`;
        return;
      }}
      const width = Math.max(760, host.clientWidth || 1100), height = 340, left = 66, right = 66, top = 42, bottom = 64;
      const plotW = width - left - right, plotH = height - top - bottom;
      const expVals = history.map((item) => Number(item.exp || 0));
      const weightVals = history.map((item) => Number(item.weight || 0));
      const maxExp = Math.max(1, ...expVals);
      const maxWeight = Math.max(0.0001, ...weightVals);
      const step = plotW / Math.max(1, history.length);
      const barW = Math.max(4, Math.min(34, step * .52));
      const labelStride = 1;
      const valueStride = 1;
      const yExp = (v) => top + plotH - plotH * Number(v || 0) / maxExp;
      const yWeight = (v) => top + plotH - plotH * Number(v || 0) / maxWeight;
      let svg = `<svg viewBox="0 0 ${{width}} ${{height}}" class="ts-stock-svg" style="width:100%">`;
      svg += `<text x="16" y="20" class="ts-axis">${{escHtml(row.name)}} · Exp/편입비</text>`;
      for (let i=0;i<5;i++) {{
        const y = top + plotH * i / 4;
        svg += `<line x1="${{left}}" y1="${{y}}" x2="${{width - right}}" y2="${{y}}" class="bar-grid"></line>`;
      }}
      const points = [];
      history.forEach((item, idx) => {{
        const x = left + step * (idx + .5);
        const barY = yExp(item.exp);
        svg += `<rect x="${{x - barW / 2}}" y="${{barY}}" width="${{barW}}" height="${{top + plotH - barY}}" rx="3" fill="#008485"></rect>`;
        if (idx % valueStride === 0 || idx === history.length - 1) svg += `<text x="${{x}}" y="${{barY + Math.max(14, (top + plotH - barY) / 2)}}" text-anchor="middle" class="ts-bar-label">${{fmtEok1(item.exp)}}</text>`;
        points.push([x, yWeight(item.weight)]);
        if (idx % labelStride === 0 || idx === history.length - 1) svg += `<text x="${{x}}" y="${{height - 22}}" text-anchor="middle" class="ts-date">${{item.date.slice(5)}}</text>`;
      }});
      svg += `<path d="${{points.map((p,i)=>`${{i ? "L" : "M"}} ${{p[0].toFixed(1)}} ${{p[1].toFixed(1)}}`).join(" ")}}" fill="none" stroke="#12372d" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>`;
      points.forEach((p, idx) => {{
        const weight = history[idx]?.weight == null ? null : Number(history[idx].weight);
        svg += `<circle cx="${{p[0]}}" cy="${{p[1]}}" r="4" fill="#12372d" stroke="#fff" stroke-width="1.5"></circle>`;
        if (idx % valueStride === 0 || idx === history.length - 1) svg += `<text x="${{p[0]}}" y="${{p[1] - 9}}" text-anchor="middle" class="ts-line-label">${{weight == null ? "-" : (weight * 100).toFixed(1) + "%"}}</text>`;
      }});
      svg += `</svg>`;
      host.innerHTML = svg;
    }}
    function bindTimeSeriesSubtabs() {{
      const panel = dashboard.querySelector('[data-panel="timeseries"]');
      if (!panel || panel.dataset.subtabsBound === "1") return;
      panel.dataset.subtabsBound = "1";
      panel.querySelectorAll("[data-ts-subtab]").forEach((button) => {{
        button.addEventListener("click", () => {{
          const target = button.dataset.tsSubtab;
          panel.querySelectorAll("[data-ts-subtab]").forEach((item) => item.classList.toggle("active", item === button));
          panel.querySelectorAll("[data-ts-subpanel]").forEach((item) => item.classList.toggle("active", item.dataset.tsSubpanel === target));
          if (target === "stock") bindTimeSeriesStockWidgets(true);
        }});
      }});
    }}
    function bindTimeSeriesStockWidgets(force = false) {{
      dashboard.querySelectorAll(".ts-stock-widget").forEach((widget) => {{
        const dataEl = widget.querySelector(".ts-stock-data");
        const search = widget.querySelector(".ts-stock-search");
        const candidates = widget.querySelector(".ts-stock-candidates");
        const chart = widget.querySelector(".ts-stock-chart");
        const dailyHost = widget.querySelector(".ts-stock-daily-host");
        let rows = [];
        try {{ rows = JSON.parse(dataEl?.innerHTML || "[]"); }} catch (error) {{ rows = []; }}
        rows.sort((a,b) => Math.abs(Number(b.deltaWeight || 0)) - Math.abs(Number(a.deltaWeight || 0)));
        const topRows = rows.slice(0, 15);
        const defaultRow = rows.find((row) => row.name === "SK하이닉스" || row.code === "000660") || rows[0];
        const currentRow = rows.find((row) => row.key === widget.dataset.selectedStockKey) || defaultRow;
        if (force && chart && currentRow) {{
          renderTsSelectedChart(chart, currentRow);
          renderTsStockDailyTable(dailyHost, currentRow);
        }}
        if (widget.dataset.bound === "1") return;
        widget.dataset.bound = "1";
        const drawCandidates = (term = "") => {{
          const q = term.trim().toLowerCase();
          const matches = (q ? rows.filter((row) => `${{row.name}} ${{row.code}}`.toLowerCase().includes(q)) : topRows).slice(0, 10);
          candidates.innerHTML = matches.map((row) => `<button type="button" class="ts-stock-choice" data-key="${{escHtml(row.key)}}">${{escHtml(row.name)}} <small>${{escHtml(row.code)}}</small></button>`).join("");
          candidates.querySelectorAll(".ts-stock-choice").forEach((item) => item.classList.toggle("active", defaultRow && item.dataset.key === defaultRow.key && !q));
        }};
        if (defaultRow) widget.dataset.selectedStockKey = defaultRow.key;
        if (chart && defaultRow) {{
          renderTsSelectedChart(chart, defaultRow);
          renderTsStockDailyTable(dailyHost, defaultRow);
        }}
        else if (chart) renderTsRankChart(chart, topRows);
        drawCandidates("");
        search?.addEventListener("input", () => drawCandidates(search.value));
        candidates?.addEventListener("click", (event) => {{
          const button = event.target.closest(".ts-stock-choice");
          if (!button) return;
          const row = rows.find((item) => item.key === button.dataset.key);
          if (row) widget.dataset.selectedStockKey = row.key;
          candidates.querySelectorAll(".ts-stock-choice").forEach((item) => item.classList.toggle("active", item === button));
          if (row && chart) {{
            renderTsSelectedChart(chart, row);
            renderTsStockDailyTable(dailyHost, row);
          }}
        }});
      }});
    }}
    function showTab(tab) {{
      activeTab = tab || "summary";
      dashboard.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.dataset.panel === activeTab));
      document.querySelectorAll(".quick-nav button").forEach((button) => button.classList.toggle("active", button.dataset.tab === activeTab));
      if (activeTab === "holdings") renderHoldingTables();
      if (activeTab === "trades") renderTradeHistory();
      if (activeTab === "timeseries") {{
        bindTimeSeriesSubtabs();
        bindTimeSeriesControls();
        if (dashboard.querySelector('[data-ts-subpanel="stock"]')?.classList.contains("active")) bindTimeSeriesStockWidgets();
      }}
    }}
    function filteredTradeRows(includeSearch = true) {{
      const query = tradeSearch.trim().toLowerCase();
      return tradeHistory.filter(row => {{
        const haystack = `${{row.date}} ${{row.fund}} ${{row.name}} ${{row.sector || ""}} ${{row.side}}`.toLowerCase();
        return (currentKey === "ALL" || row.fundCode === currentKey) && (!tradeStart || row.date >= tradeStart) && (!tradeEnd || row.date <= tradeEnd) && (!includeSearch || !query || haystack.includes(query));
      }});
    }}
    function renderTradeNetTable(hostId, direction) {{
      const host = document.getElementById(hostId);
      if (!host) return;
      const grouped = new Map();
      filteredTradeRows(false).forEach((row) => {{
        const sign = row.side === "매도" ? -1 : 1;
        const key = `${{row.name}}|${{row.sector || ""}}`;
        const item = grouped.get(key) || {{ name: row.name, sector: row.sector || "", amount: 0, funds: new Set() }};
        item.amount += Number(row.amount || 0) * sign;
        item.funds.add(row.fund);
        grouped.set(key, item);
      }});
      let rows = [...grouped.values()].filter((row) => direction === "buy" ? row.amount > 0 : row.amount < 0);
      rows.sort((a, b) => direction === "buy" ? b.amount - a.amount : a.amount - b.amount);
      rows = rows.slice(0, 24);
      if (!rows.length) {{
        host.innerHTML = `<div class="empty">해당 순매매 종목이 없습니다.</div>`;
        return;
      }}
      const body = rows.map((row) => `<tr><td class="name-cell"><button type="button" class="trade-filter-link" data-trade-filter="${{escHtml(row.name)}}">${{escHtml(row.name)}}</button></td><td>${{escHtml(row.sector)}}</td><td>${{row.funds.size.toLocaleString("ko-KR")}}</td><td class="${{signedClass(row.amount)}}">${{fmtEok(row.amount)}}</td></tr>`).join("");
      host.innerHTML = `<div class="table-wrap trade-dynamic-table"><table class="sortable-table"><thead><tr><th data-sort-index="0">종목명</th><th data-sort-index="1">업종</th><th data-sort-index="2">펀드</th><th data-sort-index="3">순매수금액</th></tr></thead><tbody>${{body}}</tbody></table></div>`;
      bindSortableTables(host);
    }}
    function renderTradeSectorBars(hostId, sectorKey) {{
      const host = document.getElementById(hostId);
      if (!host) return;
      const grouped = new Map();
      filteredTradeRows(false).forEach((row) => {{
        const label = row[sectorKey] || row.sector || "미분류";
        const sign = row.side === "매도" ? -1 : 1;
        grouped.set(label, (grouped.get(label) || 0) + Number(row.amount || 0) * sign);
      }});
      const rows = [...grouped.entries()].filter(([, value]) => Math.abs(value) > 0).sort((a, b) => b[1] - a[1]).slice(0, 24);
      if (!rows.length) {{
        host.innerHTML = `<div class="empty">업종별 매매 데이터가 없습니다.</div>`;
        return;
      }}
      const width = Math.max(760, host.clientWidth || 1180);
      const height = 470;
      const left = 58, right = 28, top = 34, bottom = 148;
      const plotW = width - left - right;
      const plotH = height - top - bottom;
      const maxAbs = Math.max(...rows.map(([, value]) => Math.abs(value)), 1);
      const step = plotW / Math.max(rows.length, 1);
      const barW = Math.max(8, Math.min(34, step * 0.58));
      const zeroY = top + plotH / 2;
      let svg = `<svg viewBox="0 0 ${{width}} ${{height}}" class="trade-category-chart">`;
      svg += `<line x1="${{left}}" y1="${{zeroY}}" x2="${{width - right}}" y2="${{zeroY}}" class="zero"></line>`;
      [-1, -0.5, 0.5, 1].forEach((tick) => {{
        const y = zeroY - tick * plotH / 2;
        svg += `<line x1="${{left}}" y1="${{y}}" x2="${{width - right}}" y2="${{y}}" class="bar-grid"></line>`;
        svg += `<text x="8" y="${{y + 4}}" class="axis trade-axis">${{fmtEok(maxAbs * tick)}}</text>`;
      }});
      rows.forEach(([label, value], idx) => {{
        const x = left + step * (idx + 0.5);
        const h = Math.max(1, Math.abs(value) / maxAbs * (plotH / 2));
        const y = value >= 0 ? zeroY - h : zeroY;
        const fill = value >= 0 ? "#d92d20" : "#2563eb";
        const labelY = height - 78;
        const shortLabel = label.length > 10 ? `${{label.slice(0, 10)}}…` : label;
        svg += `<rect x="${{x - barW / 2}}" y="${{y}}" width="${{barW}}" height="${{h}}" rx="3" fill="${{fill}}" class="trade-filter-target" data-trade-filter="${{escHtml(label)}}"></rect>`;
        svg += `<text x="${{x}}" y="${{value >= 0 ? y - 7 : y + h + 14}}" text-anchor="middle" class="trade-axis ${{signedClass(value)}}">${{fmtEok(value)}}</text>`;
        svg += `<text x="${{x}}" y="${{labelY}}" text-anchor="end" transform="rotate(-42 ${{x}} ${{labelY}})" class="trade-label trade-filter-target" data-trade-filter="${{escHtml(label)}}">${{escHtml(shortLabel)}}</text>`;
      }});
      svg += `</svg>`;
      host.innerHTML = svg;
    }}
    function setTradePreset(preset) {{
      tradePreset = preset;
      const end = tradeEnd || tradeMax;
      if (!end) return;
      if (preset === "1d") tradeStart = end;
      if (preset === "1w") tradeStart = dayStartFrom(end, 7);
      if (preset === "1m") tradeStart = monthStartFrom(end, 1);
      if (preset === "3m") tradeStart = monthStartFrom(end, 3);
      renderTradeHistory();
    }}
    function renderTradeHistory() {{
      const table = document.getElementById("stockTradeTable");
      if (!table) return;
      const rows = filteredTradeRows(true).sort((a,b)=>b.date.localeCompare(a.date)).slice(0,500);
      table.classList.add("sortable-table");
      table.innerHTML = `<thead><tr><th data-sort-index="0">기준일</th><th data-sort-index="1">펀드명</th><th data-sort-index="2">종목명</th><th data-sort-index="3">거래</th><th data-sort-index="4">평단가</th><th data-sort-index="5">금액(백만원)</th><th data-sort-index="6">편입비</th></tr></thead><tbody>${{rows.map(row=>{{ const sign = row.side === "매도" ? -1 : 1; const signedAmount = row.amount * sign; const signedWeight = row.weight == null ? null : row.weight * sign; const cls = signedAmount >= 0 ? "profit-cell" : "loss-cell"; const sideClass = row.side === "매도" ? "sell" : "buy"; return `<tr><td>${{row.date}}</td><td>${{row.fund}}</td><td>${{row.name}}</td><td><span class="trade-side-badge ${{sideClass}}">${{row.side}}</span></td><td>${{row.avgPrice == null ? "-" : Math.round(row.avgPrice).toLocaleString("ko-KR")}}</td><td class="${{cls}}">${{Math.round(signedAmount / 1000000).toLocaleString("ko-KR")}}</td><td class="${{cls}}">${{signedWeight == null ? "-" : (signedWeight * 100).toFixed(2) + "%"}}</td></tr>`; }}).join("")}}</tbody>`;
      for (const [id,value] of [["tradeStart",tradeStart],["tradeEnd",tradeEnd]]) {{ const input=document.getElementById(id); if(!input)continue; input.min=tradeMin;input.max=tradeMax;input.value=value;input.onchange=e=>{{tradePreset="custom"; if(id==="tradeStart")tradeStart=e.target.value;else tradeEnd=e.target.value;renderTradeHistory();}}; }}
      document.querySelectorAll("[data-trade-preset]").forEach((button) => {{
        button.classList.toggle("active", button.dataset.tradePreset === tradePreset);
        button.onclick = () => setTradePreset(button.dataset.tradePreset);
      }});
      const searchInput = document.getElementById("tradeSearch");
      if (searchInput) {{ searchInput.value = tradeSearch; searchInput.oninput = (event) => {{ tradeSearch = event.target.value; tradeFilterLabel = ""; renderTradeHistory(); }}; }}
      const resetButton = document.getElementById("tradeFilterReset");
      if (resetButton) resetButton.onclick = () => {{ tradeSearch = ""; tradeFilterLabel = ""; setTradePreset("1m"); }};
      const state = document.getElementById("tradeFilterState");
      if (state) {{
        const label = tradeFilterLabel || tradeSearch;
        state.textContent = label ? `필터: ${{label}}` : "전체";
        state.title = label || "전체";
      }}
      bindSortableTables(table);
      renderTradeNetTable("netBuyHost", "buy");
      renderTradeNetTable("netSellHost", "sell");
      renderTradeSectorBars("tradeSectorMidHost", "sector");
      renderTradeSectorBars("tradeSectorLargeHost", "sectorLarge");
    }}
    function bindPanelSearches() {{
      dashboard.querySelectorAll(".searchable-panel").forEach((panel) => {{
        const input = panel.querySelector(".table-search");
        const rows = [...panel.querySelectorAll("tbody tr")];
        if (!input || input.id === "tradeSearch" || input.dataset.holdingSearch) return;
        input.oninput = () => {{
          const query = input.value.trim().toLowerCase();
          rows.forEach((row) => row.style.display = !query || row.textContent.toLowerCase().includes(query) ? "" : "none");
        }};
      }});
    }}
    function sortableValue(row, index) {{
      const cell = row.children[index];
      if (!cell) return {{ type:"text", value:"" }};
      const text = cell.textContent.trim();
      if (!text || text === "-") return {{ type:"empty", value:null }};
      const numeric = Number(text.replace(/[,%억원\\s]/g, ""));
      if (Number.isFinite(numeric) && /[0-9]/.test(text)) return {{ type:"number", value:numeric }};
      return {{ type:"text", value:text.toLowerCase() }};
    }}
    function bindSortableTables(root = dashboard) {{
      const tables = root.matches?.(".sortable-table") ? [root] : [...root.querySelectorAll(".sortable-table")];
      tables.forEach((table) => {{
        if (table.dataset.sortableBound === "1") return;
        table.dataset.sortableBound = "1";
        table.querySelectorAll("th[data-sort-index]").forEach((th) => {{
          th.addEventListener("click", () => {{
            const tbody = table.tBodies[0];
            if (!tbody) return;
            const index = Number(th.dataset.sortIndex);
            const direction = th.classList.contains("sort-asc") ? "desc" : "asc";
            table.querySelectorAll("th").forEach((header) => header.classList.remove("sort-asc", "sort-desc"));
            th.classList.add(direction === "asc" ? "sort-asc" : "sort-desc");
            const rows = [...tbody.rows];
            const totalRows = rows.filter((row) => row.cells[0]?.textContent.trim() === "합계");
            const sortableRows = rows.filter((row) => row.cells[0]?.textContent.trim() !== "합계");
            sortableRows.sort((a, b) => {{
              const av = sortableValue(a, index);
              const bv = sortableValue(b, index);
              if (av.type === "empty" && bv.type !== "empty") return 1;
              if (bv.type === "empty" && av.type !== "empty") return -1;
              let result = 0;
              if (av.type === "number" && bv.type === "number") result = av.value - bv.value;
              else result = String(av.value ?? "").localeCompare(String(bv.value ?? ""), "ko");
              return direction === "asc" ? result : -result;
            }});
            [...sortableRows, ...totalRows].forEach((row) => tbody.appendChild(row));
          }});
        }});
      }});
    }}
    function activeViewKey() {{
      if (!selectedFundKeys.length || selectedFundKeys.includes("ALL")) return "ALL";
      if (selectedFundKeys.length === 1) return selectedFundKeys[0];
      return selectedFundKeys[0];
    }}
    function updateFundButtons() {{
      document.getElementById("multiFundToggle")?.classList.toggle("active", multiFund);
      document.querySelectorAll(".fund-button").forEach((button) => button.classList.toggle("active", selectedFundKeys.includes(button.dataset.key)));
    }}
    function render(key) {{
      if (!visibleFunds().some((fund) => fund.key === key)) key = "ALL";
      currentKey = key;
      dashboard.innerHTML = views[key] || views["ALL"];
      if (key !== "ALL") {{
        const title = dashboard.querySelector(".selected-block h2");
        const info = masterInfoFor(key);
        if (title && info?.name) title.textContent = info.name;
      }}
      const period = dashboard.querySelector(".period-data")?.dataset.period || "";
      document.getElementById("periodCaption").textContent = period ? `매매기간 ${{period}}` : "";
      renderHoldingTables();
      showTab(activeTab);
      bindPanelSearches();
      bindSortableTables();
      renderTradeHistory();
      renderLiveQuoteViews();
      updateFundButtons();
    }}
    function selectFund(key) {{
      if (key === "ALL") {{
        selectedFundKeys = ["ALL"];
        render("ALL");
        return;
      }}
      if (!visibleFunds().some((fund) => fund.key === key)) {{
        selectedFundKeys = ["ALL"];
        render("ALL");
        return;
      }}
      if (multiFund) {{
        selectedFundKeys = selectedFundKeys.filter((item) => item !== "ALL");
        if (selectedFundKeys.includes(key)) selectedFundKeys = selectedFundKeys.filter((item) => item !== key);
        else selectedFundKeys.push(key);
        if (!selectedFundKeys.length) selectedFundKeys = ["ALL"];
      }} else {{
        selectedFundKeys = [key];
      }}
      render(activeViewKey());
    }}
    function drawList(term = "") {{
      const normalized = "";
      fundList.innerHTML = "";
      const order = ["전체", "주식", "멀티", "롱숏", "혼합", "IPO"];
      const filtered = visibleFunds().filter((fund) => !normalized || `${{fund.name}} ${{fund.code}} ${{fund.type}}`.toLowerCase().includes(normalized));
      order.concat([...new Set(filtered.map((fund) => fund.type).filter((type) => !order.includes(type)))]).forEach((type) => {{
        const groupFunds = filtered.filter((fund) => fund.type === type);
        if (!groupFunds.length) return;
        const group = document.createElement("div");
        group.className = "fund-group";
        group.innerHTML = `<div class="fund-group-title">${{type}}</div><div class="fund-group-grid"></div>`;
        const grid = group.querySelector(".fund-group-grid");
        groupFunds.forEach((fund) => {{
          const button = document.createElement("button");
          button.className = "fund-button";
          button.dataset.key = fund.key;
          button.innerHTML = `<strong>${{fund.name}}</strong>`;
          button.addEventListener("click", () => selectFund(fund.key));
          grid.appendChild(button);
        }});
        fundList.appendChild(group);
      }});
      updateFundButtons();
    }}
    document.querySelectorAll(".quick-nav button").forEach((button) => {{
      button.addEventListener("click", () => showTab(button.dataset.tab));
    }});
    dashboard.addEventListener("click", (event) => {{
      if (event.target.closest("[data-open-column-help]")) setColumnHelp(true);
      const tradeFilter = event.target.closest("[data-trade-filter]");
      if (tradeFilter) {{
        tradeSearch = tradeFilter.dataset.tradeFilter || "";
        tradeFilterLabel = tradeSearch;
        showTab("trades");
        renderTradeHistory();
      }}
      const fundButton = event.target.closest(".fund-count-button");
      if (fundButton) {{
        const key = fundButton.dataset.holdingKey;
        const rows = Object.values(holdingDetails[currentKey] || holdingDetails.ALL || {{}}).flat();
        const row = rows.find((item) => item.key === key);
        if (row) setHoldingFundModal(true, row);
      }}
    }});
    document.querySelector("[data-close-column-help]")?.addEventListener("click", () => setColumnHelp(false));
    document.querySelector("[data-close-holding-fund]")?.addEventListener("click", () => setHoldingFundModal(false));
    columnHelpModal?.addEventListener("click", (event) => {{
      if (event.target === columnHelpModal) setColumnHelp(false);
    }});
    document.getElementById("holdingFundModal")?.addEventListener("click", (event) => {{
      if (event.target === document.getElementById("holdingFundModal")) setHoldingFundModal(false);
    }});
    document.addEventListener("keydown", (event) => {{
      if (event.key === "Escape") setColumnHelp(false);
      if (event.key === "Escape") setHoldingFundModal(false);
    }});
    document.getElementById("refreshPage")?.addEventListener("click", () => location.reload());
    document.getElementById("refreshQuotes")?.addEventListener("click", () => refreshQuotes(true));
    document.getElementById("quoteRefreshInterval")?.addEventListener("change", (event) => setQuoteAutoRefresh(event.target.value));
    document.getElementById("multiFundToggle")?.addEventListener("click", () => {{
      multiFund = !multiFund;
      if (!multiFund && selectedFundKeys.length > 1) selectedFundKeys = [selectedFundKeys[0]];
      render(activeViewKey());
    }});
    document.getElementById("clearFundSelection")?.addEventListener("click", () => {{
      selectedFundKeys = ["ALL"];
      render("ALL");
    }});
    (async () => {{
      try {{
        await loadExternalDataIfNeeded();
        bindSnapshotSelector();
        drawList();
        render("ALL");
      }} catch (error) {{
        console.error(error);
        dashboard.innerHTML = `<div class="empty">대시보드 데이터를 불러오지 못했습니다. ${{escHtml(error.message || error)}}</div>`;
      }}
    }})();
  </script>
</body>
</html>
"""
    target = output_path or OUTPUT
    target.write_text(html_text, encoding="utf-8")
    return target


def available_supabase_holding_dates(start_date: str | None = None, end_date: str | None = None) -> list[str]:
    client = supabase_client()
    snapshots = fetch_kfr_snapshots(client, "fund_holdings", start_date=start_date, end_date=end_date)
    return sorted({str(snapshot["business_date"]) for snapshot in snapshots})


def available_holding_dates(data_source: str, start_date: str | None = None, end_date: str | None = None) -> list[str]:
    if data_source == "supabase":
        return available_supabase_holding_dates(start_date, end_date)
    dates = available_kfr_dates(KFR_DATA_DIR, "fund_holdings")
    return [date for date in dates if (not start_date or date >= start_date) and (not end_date or date <= end_date)]


def _extract_json_const(script: str, name: str, next_name: str | None) -> object:
    start_match = re.search(rf"(?:^|\n)\s*(?:const|let) {re.escape(name)} = ", script)
    if not start_match:
        raise RuntimeError(f"{name} 상수를 찾지 못했습니다.")
    start_index = start_match.end()
    if next_name:
        end_match = re.search(rf";\n\s*(?:const|let) {re.escape(next_name)} = ", script[start_index:])
    else:
        end_match = re.search(r";\n\s*const FUND_MASTER_STORAGE_KEY", script[start_index:])
    if not end_match:
        raise RuntimeError(f"{name} 상수의 끝을 찾지 못했습니다.")
    end_index = start_index + end_match.start()
    return json.loads(script[start_index:end_index])


def extract_dashboard_data(html_path: Path, data_dir: Path = DATA_DIR) -> dict[str, object]:
    html_text = html_path.read_text(encoding="utf-8")
    match = re.search(r"<script>\s*(.*?)\s*</script>", html_text, re.S)
    if not match:
        raise RuntimeError("대시보드 스크립트를 찾지 못했습니다.")
    script = match.group(1)
    data = {
        "views": _extract_json_const(script, "views", "funds"),
        "funds": _extract_json_const(script, "funds", "snapshotDates"),
        "snapshotDates": _extract_json_const(script, "snapshotDates", "currentSnapshotDate"),
        "currentSnapshotDate": _extract_json_const(script, "currentSnapshotDate", "latestSnapshotDate"),
        "latestSnapshotDate": _extract_json_const(script, "latestSnapshotDate", None),
        "tradeHistory": _extract_json_const(script, "tradeHistory", "holdingDetails"),
        "holdingDetails": _extract_json_const(script, "holdingDetails", "quoteSensitiveData"),
        "quoteSensitiveData": _extract_json_const(script, "quoteSensitiveData", "tradeDates"),
    }
    data_dir.mkdir(parents=True, exist_ok=True)
    date = str(data["currentSnapshotDate"])
    target = data_dir / f"fund_dashboard_{date}.json"
    target.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return data


def write_dashboard_shell_from_inline_html(html_path: Path, output_path: Path = OUTPUT) -> Path:
    html_text = html_path.read_text(encoding="utf-8")
    replacements = [
        (
            r"    const views = .*?;\n    const funds = .*?;\n    const snapshotDates = .*?;\n    const currentSnapshotDate = .*?;\n    const latestSnapshotDate = .*?;",
            "    let views = {};\n    let funds = [];\n    let snapshotDates = [];\n    let currentSnapshotDate = \"\";\n    let latestSnapshotDate = \"\";",
        ),
        (r"    const tradeHistory = .*?;\n    const holdingDetails = .*?;\n    let quoteSensitiveData = .*?;\n", "    let tradeHistory = [];\n    let holdingDetails = {};\n    let quoteSensitiveData = {};\n"),
        (r"    const tradeDates = ", "    let tradeDates = "),
        (r"    const tradeMax = ", "    let tradeMax = "),
        (r"    const tradeMin = ", "    let tradeMin = "),
        (r"    const defaultTradeStart = ", "    let defaultTradeStart = "),
    ]
    for pattern, replacement in replacements:
        html_text = re.sub(pattern, replacement, html_text, count=1, flags=re.S)
    output_path.write_text(html_text, encoding="utf-8")
    return output_path


def build_static_data_bundle(
    data_source: str = "json",
    start_date: str | None = None,
    end_date: str | None = None,
    selected_dates: list[str] | None = None,
    recent_snapshots: int | None = None,
) -> Path:
    dates = available_holding_dates(data_source, start_date, end_date)
    if not dates:
        raise RuntimeError("생성할 KFR API 보유 스냅샷이 없습니다.")
    if selected_dates:
        requested = {date.strip() for date in selected_dates if date.strip()}
        missing = sorted(requested - set(dates))
        if missing:
            raise RuntimeError(f"KFR API 보유 스냅샷에 없는 기준일입니다: {', '.join(missing)}")
        dates = [date for date in dates if date in requested]
        if not dates:
            raise RuntimeError("선택한 기준일이 없습니다.")
    elif recent_snapshots and recent_snapshots > 0:
        dates = dates[-recent_snapshots:]
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp_html = BASE_DIR / ".fund_dashboard_inline_tmp.html"
    generated_dates: list[str] = []
    for date in dates:
        build_dashboard(data_source, start_date, date, temp_html)
        data = extract_dashboard_data(temp_html, DATA_DIR)
        generated_dates.append(str(data["currentSnapshotDate"]))
    latest = generated_dates[-1]
    (DATA_DIR / "fund_dashboard_index.json").write_text(
        json.dumps({"dates": generated_dates, "latestDate": latest}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    write_dashboard_shell_from_inline_html(temp_html, OUTPUT)
    try:
        temp_html.unlink()
    except OSError:
        pass
    return OUTPUT


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["json", "supabase"], default=os.getenv("DASHBOARD_DATA_SOURCE", "json"))
    parser.add_argument("--start", default=os.getenv("DASHBOARD_START_DATE") or None)
    parser.add_argument("--end", default=os.getenv("DASHBOARD_END_DATE") or None)
    parser.add_argument("--date-versions", action="store_true", help="Supabase 보유 스냅샷별 HTML 파일을 함께 생성합니다.")
    parser.add_argument("--force-date-versions", action="store_true", help="이미 생성된 과거 기준일 HTML도 다시 씁니다.")
    parser.add_argument("--static-data-bundle", action="store_true", help="단일 HTML + 기준일별 JSON 데이터 구조로 생성합니다.")
    parser.add_argument("--dates", default="", help="쉼표로 구분한 특정 기준일만 생성합니다. 예: 2026-06-30,2026-07-31,2026-08-18")
    parser.add_argument("--recent-snapshots", type=int, default=0, help="정적 데이터 번들 생성 시 최근 N개 기준일만 생성합니다.")
    args = parser.parse_args()
    if args.static_data_bundle:
        selected_dates = [date.strip() for date in args.dates.split(",") if date.strip()] if args.dates else None
        print(build_static_data_bundle(args.source, args.start, args.end, selected_dates, args.recent_snapshots or None))
    elif args.date_versions:
        dates = available_holding_dates(args.source, args.start, args.end)
        for date in dates:
            target = OUTPUT if date == dates[-1] else BASE_DIR / f"fund_dashboard_{date}.html"
            if target.exists() and date != dates[-1] and not args.force_date_versions:
                print(target)
                continue
            print(build_dashboard(args.source, args.start, date, target))
    else:
        print(build_dashboard(args.source, args.start, args.end))


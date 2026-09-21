from __future__ import annotations

import json
import math
import os
import re
import sys
import urllib.request
import urllib.parse
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
KFR_MODULE_DIR = REPO_ROOT / "automation" / "kfr"
if str(KFR_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(KFR_MODULE_DIR))
from kfr_api import load_frame as load_kfr_frame  # noqa: E402

STOCK_MODULE_DIR = REPO_ROOT / "apps" / "stock"
if str(STOCK_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(STOCK_MODULE_DIR))
from build_fund_dashboard import build_benchmark_sector_weights, read_industry_map  # noqa: E402

KFR_DATA_DIR = Path(os.getenv("KFR_JSON_DIR", str(REPO_ROOT / "data" / "kfr")))
OUTPUT = ROOT / "메자닌_대시보드.html"
ALIAS_FILE = ROOT / "instrument_aliases.csv"
ADDITIONS_FILE = ROOT / "instrument_additions.json"
DELTA_HISTORY_FILE = ROOT / "delta_history.json"
CORP_CODES_FILE = ROOT / "opendart_corp_codes.json"
QUOTE_CANDIDATES = [ROOT / "kiwoom_quotes.json", ROOT.parent / "stock" / "kiwoom_quotes.json"]
BENCHMARK_CACHE_FILES = {
    "KOSPI": ROOT / "kospi_benchmark.json",
    "KOSDAQ": ROOT / "kosdaq_benchmark.json",
}
FUND_NAV_FILE = Path(os.getenv("FUND_NAV_FILE", str(REPO_ROOT / "data" / "manual" / "fund_fund_nav.json")))
DEFAULT_SUPABASE_URL = "https://esqakvzvchcunhzjlyry.supabase.co"
NAMESPACE = uuid.UUID("63ed6f6f-a40b-42da-bab7-835798a8f6be")
ISSUER_NAME_ALIASES = {
    "티에스인베스트먼트": "TS인베스트먼트",
    "케이비아이메탈": "KBI메탈",
}


def clean(value: object) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return re.sub(r"\s+", "", str(value).strip())


def code(value: object) -> str:
    text = clean(value).upper()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text.zfill(6) if text.isdigit() and len(text) < 6 else text


def issuer_from_security_name(security_name: object) -> tuple[str, str]:
    """메자닌 종목명에서 발행사명을 추출하고 OpenDART 상장코드와 정확히 매칭한다."""
    name = clean(security_name)
    issuer = re.sub(r"\([^)]*\)$", "", name)
    issuer = re.sub(r"\d+(?:CB|BW|EB)$", "", issuer, flags=re.IGNORECASE)
    issuer = ISSUER_NAME_ALIASES.get(issuer, issuer)
    if not issuer or not CORP_CODES_FILE.exists():
        return issuer, ""
    try:
        maps = json.loads(CORP_CODES_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return issuer, ""
    matches = [
        item for item in maps.get("by_corp_code", {}).values()
        if item.get("stock_code") and clean(item.get("corp_name")).casefold() == issuer.casefold()
    ]
    if len(matches) != 1:
        return issuer, ""
    return clean(matches[0].get("corp_name")), code(matches[0].get("stock_code"))


def number(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def finite_number(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def read_raw(dataset: str, *, latest_only: bool = False) -> pd.DataFrame:
    return load_kfr_frame(KFR_DATA_DIR, dataset, latest_only=latest_only).drop(
        columns=["스냅샷일", "원천파일"], errors="ignore"
    )


def read_master() -> pd.DataFrame:
    df = pd.read_excel(ROOT / "종목정보.xlsx")
    df = df[df["KR코드"].notna()].copy()
    for col in ("KR코드", "발행코드", "교환코드"):
        df[col] = df[col].map(code)
    return df


def economic_key(row: pd.Series) -> str:
    # KR코드와 달리 콜/풋/전환 이벤트에도 유지되는 경제적 식별자.
    return "|".join([clean(row.get("발행사명")).lower(), clean(row.get("구분")).upper(), clean(row.get("회차"))])


def build_aliases(master: pd.DataFrame) -> pd.DataFrame:
    existing = pd.read_csv(ALIAS_FILE, dtype=str).fillna("") if ALIAS_FILE.exists() else pd.DataFrame()
    old_by_key = dict(zip(existing.get("economic_key", []), existing.get("instrument_id", [])))
    rows = []
    for _, row in master.iterrows():
        key = economic_key(row)
        linked_id = clean(row.get("_linked_instrument_id"))
        instrument_id = linked_id or old_by_key.get(key) or str(uuid.uuid5(NAMESPACE, key))
        rows.append({
            "instrument_id": instrument_id,
            "economic_key": key,
            "security_code": code(row.get("KR코드")),
            "issuer": clean(row.get("발행사명")),
            "security_type": clean(row.get("구분")),
            "round": clean(row.get("회차")),
            "active_from": "",
            "active_to": "",
            "is_primary": "true",
        })
    fresh = pd.DataFrame(rows)
    if not existing.empty:
        # 수동으로 추가한 과거 코드는 보존하고 동일 alias만 최신 행으로 대체한다.
        merged = pd.concat([existing, fresh], ignore_index=True)
        merged = merged.drop_duplicates(["instrument_id", "security_code"], keep="last")
    else:
        merged = fresh
    merged.to_csv(ALIAS_FILE, index=False, encoding="utf-8-sig")
    return merged


def delta_history_columns(master: pd.DataFrame) -> list[tuple[object, pd.Timestamp]]:
    start = list(master.columns).index("추정델타") + 1 if "추정델타" in master.columns else len(master.columns)
    found = []
    for col in master.columns[start:]:
        dt = pd.to_datetime(col, errors="coerce")
        if pd.notna(dt):
            found.append((col, dt.normalize()))
    return sorted(found, key=lambda item: item[1], reverse=True)


def estimated_delta(row: pd.Series, history_cols: list[tuple[object, pd.Timestamp]]) -> tuple[float, int, list[dict]]:
    observations = []
    for col, dt in history_cols:
        raw = pd.to_numeric(pd.Series([row.get(col)]), errors="coerce").iloc[0]
        if pd.isna(raw):
            continue
        value = float(raw)
        valid = 0 <= value <= 1
        observations.append({"date": dt.strftime("%Y-%m-%d"), "dailyDelta": value, "valid": valid})
        if len(observations) >= 10:
            break
    valid_values = [x["dailyDelta"] for x in observations if x["valid"]]
    # 신규 편입 첫날(유효 과거 관측치가 1개 이하)은 약정한 초기 델타 40%를 적용한다.
    if len(observations) <= 1:
        return 0.40, 0, observations
    return (sum(valid_values) / len(valid_values) if valid_values else 0.40, len(valid_values), observations)


def shared_deltas(master: pd.DataFrame, aliases: pd.DataFrame) -> dict[str, tuple[float, int, list[dict]]]:
    """동일 instrument_id의 모든 KR코드가 가장 풍부한 델타 이력을 공유한다."""
    history_cols = delta_history_columns(master)
    id_by_code = dict(zip(aliases["security_code"].map(code), aliases["instrument_id"]))
    result: dict[str, tuple[float, int, list[dict]]] = {}
    for _, row in master.iterrows():
        iid = id_by_code.get(code(row.get("KR코드")), "")
        calculated = estimated_delta(row, history_cols)
        if iid and (iid not in result or len(calculated[2]) > len(result[iid][2])):
            result[iid] = calculated
    return result


def database_deltas(
    aliases: pd.DataFrame,
    fallback: dict[str, tuple[float, int, list[dict]]] | None = None,
) -> dict[str, tuple[float, int, list[dict]]]:
    """Calculate the latest 10-day valid-delta average from persisted daily observations."""
    if not DELTA_HISTORY_FILE.exists():
        return fallback or {}
    try:
        raw = json.loads(DELTA_HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback or {}
    id_by_code = dict(zip(aliases["security_code"].map(code), aliases["instrument_id"]))
    grouped: dict[tuple[str, str], list[float]] = {}
    invalid: set[tuple[str, str]] = set()
    for row in raw:
        security_code = code(row.get("security_code"))
        instrument_id = id_by_code.get(security_code, "")
        business_date = str(row.get("business_date") or "")[:10]
        numeric = finite_number(row.get("daily_delta"))
        if not instrument_id or not business_date:
            continue
        key = (instrument_id, business_date)
        if numeric is not None and bool(row.get("is_valid")) and 0 <= numeric <= 1:
            grouped.setdefault(key, []).append(numeric)
        else:
            invalid.add(key)
    by_instrument: dict[str, list[dict]] = {}
    keys = set(grouped) | invalid
    for instrument_id, business_date in keys:
        values = grouped.get((instrument_id, business_date), [])
        by_instrument.setdefault(instrument_id, []).append({
            "date": business_date,
            "dailyDelta": sum(values) / len(values) if values else None,
            "valid": bool(values),
        })
    result: dict[str, tuple[float, int, list[dict]]] = dict(fallback or {})
    for instrument_id, observations in by_instrument.items():
        latest = sorted(observations, key=lambda item: item["date"], reverse=True)[:10]
        valid_values = [item["dailyDelta"] for item in latest if item["valid"]]
        if valid_values:
            result[instrument_id] = (sum(valid_values) / len(valid_values), len(valid_values), latest)
    return result


def load_quotes() -> tuple[dict[str, dict], str, dict[str, float]]:
    for path in QUOTE_CANDIDATES:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            raw = payload.get("quotes") or payload.get("stocks") or payload
            market_master = payload.get("market_master") or {}
            quotes = {}
            for raw_code, item in raw.items():
                if not isinstance(item, dict):
                    continue
                normalized_code = code(raw_code)
                master_item = market_master.get(raw_code) or market_master.get(normalized_code) or {}
                quotes[normalized_code] = {
                    **item,
                    "market": clean(item.get("market")) or clean(master_item.get("market")),
                }
            index_returns = {}
            for symbol, item in (payload.get("indices") or {}).items():
                if not isinstance(item, dict):
                    continue
                value = finite_number(item.get("change_rate", item.get("changeRate")))
                if value is not None:
                    index_returns[str(symbol).upper()] = value / 100.0
            return quotes, str(payload.get("updated_at") or payload.get("generated_at") or path.stat().st_mtime), index_returns
        except (OSError, ValueError):
            pass
    return {}, "미연결", {}


def load_stock_market_map(stock_codes: set[str]) -> dict[str, str]:
    """Load KOSPI/KOSDAQ membership for the exchange/underlying company codes."""
    secret = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not secret or not stock_codes:
        return {}
    base_url = os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL).rstrip("/")
    headers = {"apikey": secret}
    if secret.count(".") == 2:
        headers["Authorization"] = f"Bearer {secret}"
    result: dict[str, str] = {}
    normalized = sorted(value for value in stock_codes if re.fullmatch(r"\d{6}", value))
    for start in range(0, len(normalized), 100):
        batch = normalized[start:start + 100]
        params = urllib.parse.urlencode({"select": "code,market", "code": f"in.({','.join(batch)})"}, safe=".,()")
        request = urllib.request.Request(
            f"{base_url}/rest/v1/stock_market_master?{params}", headers=headers
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                rows = json.loads(response.read())
        except (OSError, ValueError):
            continue
        for row in rows:
            market = clean(row.get("market"))
            if market in {"코스피", "코스닥"}:
                result[code(row.get("code"))] = market
    return result


def load_manual_fund_nav() -> pd.DataFrame:
    """Load the long fund NAV history restored from Supabase manual_file_rows."""
    if not FUND_NAV_FILE.is_file():
        return pd.DataFrame()
    try:
        payload = json.loads(FUND_NAV_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return pd.DataFrame()
    rows: list[dict] = []
    for sheet in payload.get("sheets", []):
        rows.extend(item for item in sheet.get("rows", []) if isinstance(item, dict))
    return pd.DataFrame(rows)


def quote_change(quotes: dict[str, dict], stock_code: str) -> float | None:
    q = quotes.get(code(stock_code), {})
    value = q.get("change_rate", q.get("changeRate"))
    if value is None or value == "":
        return None
    rate = number(value)
    # Kiwoom 캐시는 1.23 = 1.23% 형식이다.
    return rate / 100.0


def quote_price(quotes: dict[str, dict], stock_code: str) -> float | None:
    value = quotes.get(code(stock_code), {}).get("price")
    return number(value) if value not in (None, "") else None


def records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", force_ascii=False, date_format="iso"))


def load_market_series(symbol: str, count: int = 800) -> list[dict]:
    """Load a daily market-index close series, retaining the last successful response as a cache."""
    normalized_symbol = symbol.upper()
    cache_file = BENCHMARK_CACHE_FILES[normalized_symbol]
    url = (
        "https://fchart.stock.naver.com/sise.nhn?"
        f"symbol={normalized_symbol}&timeframe=day&count={count}&requestType=0"
    )
    items: list[dict] = []
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=12) as response:
            content = response.read()
        root = ET.fromstring(content.decode("euc-kr", errors="replace"))
        for node in root.findall(".//item"):
            parts = str(node.attrib.get("data") or "").split("|")
            if len(parts) < 5:
                continue
            date_text = parts[0]
            close = finite_number(parts[4])
            if close is None or not re.fullmatch(r"\d{8}", date_text):
                continue
            items.append({"date": f"{date_text[:4]}-{date_text[4:6]}-{date_text[6:]}", "close": close})
        if items:
            cache_file.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    except (OSError, ValueError, ET.ParseError):
        try:
            items = json.loads(cache_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            items = []
    items = sorted(items, key=lambda item: item["date"])
    previous = None
    cumulative_base = items[0]["close"] if items else None
    for item in items:
        item["dailyReturn"] = item["close"] / previous - 1 if previous else 0.0
        item["cumulativeReturn"] = item["close"] / cumulative_base - 1 if cumulative_base else 0.0
        previous = item["close"]
    return items


def build_fund_return_series(kfr_history: pd.DataFrame, funds: pd.DataFrame) -> list[dict]:
    """Build actual fund-NAV return series from the KFR fund price history."""
    required = {"기준일", "예탁원펀드코드", "일수익률"}
    if kfr_history.empty or not required.issubset(kfr_history.columns):
        return []
    fund_meta = {
        code(row.get("펀드코드")): {
            "fund": clean(row.get("펀드명")),
            "manager": clean(row.get("운용사")),
        }
        for _, row in funds.iterrows()
    }

    def fund_name_key(value: object) -> str:
        text = clean(value).lower()
        for token in ("mezzanine", "mezz", "메자닌", "일반사모투자신탁", "사모투자신탁", "전문투자자", "제", "호"):
            text = text.replace(token, "")
        return re.sub(r"[^0-9a-z가-힣]", "", text)

    code_by_name_key = {
        fund_name_key(row.get("펀드명")): code(row.get("펀드코드"))
        for _, row in funds.iterrows()
        if fund_name_key(row.get("펀드명"))
    }
    frame = kfr_history.copy()
    frame["fundCode"] = frame["예탁원펀드코드"].map(code)
    missing_code = ~frame["fundCode"].isin(fund_meta)
    frame.loc[missing_code, "fundCode"] = frame.loc[missing_code, "펀드명"].map(
        lambda value: code_by_name_key.get(fund_name_key(value), "")
    )
    frame = frame[frame["fundCode"].isin(fund_meta)].copy()
    frame["date"] = pd.to_datetime(frame["기준일"], errors="coerce")
    frame["rate"] = pd.to_numeric(frame["일수익률"], errors="coerce") / 100.0
    frame = frame.dropna(subset=["date", "rate"])
    rows: list[dict] = []
    for fund_code, fund_rows in frame.groupby("fundCode"):
        cumulative = 1.0
        for business_date, daily in fund_rows.groupby("date"):
            # -100%는 이후 기준가가 다시 존재하는 KFR 결측 센티널이므로 실제 수익률로 누적하지 않는다.
            valid = daily[daily["rate"].gt(-1) & daily["rate"].le(1)].copy()
            if valid.empty:
                continue
            daily_return = float(valid["rate"].mean())
            cumulative *= 1.0 + daily_return
            meta = fund_meta[fund_code]
            rows.append({
                "date": business_date.strftime("%Y-%m-%d"),
                "fundCode": fund_code,
                "fund": meta["fund"],
                "manager": meta["manager"],
                "dailyReturn": daily_return,
                "cumulativeReturn": cumulative - 1.0,
                "assetCount": 1,
            })
    return sorted(rows, key=lambda item: (item["date"], item["manager"], item["fund"]))


def build_data() -> dict:
    funds = pd.read_excel(ROOT / "펀드정보.xlsx", dtype={"펀드코드": str, "협회코드": str}).fillna("")
    holdings = read_raw("fund_holdings", latest_only=True)
    trades = read_raw("fund_trades")
    kfr = read_raw("mezzanine_price", latest_only=True)
    fund_price_history = read_raw("fund_prices")
    manual_fund_nav = load_manual_fund_nav()
    if not manual_fund_nav.empty:
        fund_price_history = pd.concat([manual_fund_nav, fund_price_history], ignore_index=True)
        if {"기준일", "예탁원펀드코드"}.issubset(fund_price_history.columns):
            fund_price_history = fund_price_history.drop_duplicates(
                ["기준일", "예탁원펀드코드"], keep="last"
            )
    master = read_master().astype(object)
    if ADDITIONS_FILE.exists():
        try:
            additions = json.loads(ADDITIONS_FILE.read_text(encoding="utf-8"))
            addition_rows = []
            for item in additions:
                if not isinstance(item, dict):
                    continue
                fields = dict(item.get("fields", item))
                fields["_linked_instrument_id"] = item.get("linked_instrument_id", "")
                addition_rows.append(fields)
            if addition_rows:
                master = pd.concat([master, pd.DataFrame(addition_rows)], ignore_index=True).astype(object)
        except (OSError, ValueError):
            pass
    aliases = build_aliases(master)
    override_path = ROOT / "instrument_overrides.json"
    if override_path.exists():
        try:
            manual_by_id = json.loads(override_path.read_text(encoding="utf-8"))
            source_id_by_code = dict(zip(aliases["security_code"].map(code), aliases["instrument_id"]))
            for idx, row in master.iterrows():
                manual = manual_by_id.get(source_id_by_code.get(code(row.get("KR코드")), ""), {})
                for field, value in manual.items():
                    if field in master.columns and value not in (None, ""):
                        master.at[idx, field] = value
            aliases = build_aliases(master)
        except (OSError, ValueError):
            pass
    quotes, quote_updated, current_index_returns = load_quotes()
    market_by_code = load_stock_market_map({
        code(row.get("교환코드")) or code(row.get("발행코드"))
        for _, row in master.iterrows()
    })

    fund_by_ksd = {code(r["펀드코드"]): r for _, r in funds.iterrows()}
    fund_by_assoc = {code(r["협회코드"]): r for _, r in funds.iterrows()}

    def matched_fund(ksd_value: object, assoc_value: object) -> pd.Series | None:
        found = fund_by_ksd.get(code(ksd_value))
        return found if found is not None else fund_by_assoc.get(code(assoc_value))

    security_by_code = {code(r["KR코드"]): r for _, r in master.iterrows()}
    issuer_code_by_name = {
        clean(r.get("발행사명")): code(r.get("발행코드"))
        for _, r in master.iterrows()
        if clean(r.get("발행사명")) and code(r.get("발행코드"))
    }
    id_by_code = dict(zip(aliases["security_code"].map(code), aliases["instrument_id"]))
    manual_delta_by_instrument = shared_deltas(master, aliases)
    delta_by_instrument = database_deltas(aliases, manual_delta_by_instrument)

    security_rows = []
    delta_by_code: dict[str, float] = {}
    for _, row in master.iterrows():
        sec_code = code(row["KR코드"])
        iid = id_by_code.get(sec_code, "")
        delta, sample_count, history = delta_by_instrument.get(iid, (0.40, 0, []))
        underlying_code = code(row.get("교환코드") or row.get("발행코드"))
        change = quote_change(quotes, underlying_code)
        current_price = quote_price(quotes, underlying_code)
        delta_by_code[sec_code] = delta
        security_rows.append({
            "instrumentId": id_by_code.get(sec_code, ""), "code": sec_code,
            "name": clean(row.get("메자닌종목명")), "issuer": clean(row.get("발행사명")),
            "underlying": clean(row.get("교환대상명")), "underlyingCode": underlying_code,
            "issuerCode": code(row.get("발행코드")),
            "type": clean(row.get("구분")), "round": clean(row.get("회차")),
            "sectorLarge": clean(row.get("업종(대)")) or "미분류", "sectorMid": clean(row.get("업종(중)")) or "미분류",
            "coupon": number(row.get("Coupon")), "ytm": number(row.get("YTM")),
            "issueAmount": number(row.get("발행금액")) * 100_000_000,
            "conversionPrice": number(row.get("전환가")), "floor": number(row.get("Floor")),
            "conversionStart": str(row.get("전환시작일") or "")[:10], "conversionEnd": str(row.get("전환종료일") or "")[:10],
            "putDate": str(row.get("PUT") or "")[:10], "callDate": str(row.get("CALL") or "")[:10],
            "delta": delta, "deltaSamples": sample_count, "deltaHistory": history,
            "underlyingChange": change,
            "underlyingPrice": current_price,
        })

    security_by_base_name = {
        re.sub(r"\s+", "", item["name"].split("(", 1)[0]).lower(): item
        for item in security_rows if item.get("name")
    }
    underlying_code_by_name = {
        clean(item.get("underlying")): code(item.get("underlyingCode"))
        for item in security_rows if clean(item.get("underlying")) and code(item.get("underlyingCode"))
    }

    holding_rows = []
    latest_hold_date = ""
    for _, row in holdings.iterrows():
        fund = matched_fund(row.get("예탁원코드"), row.get("협회펀드코드"))
        sec_code = code(row.get("종목코드"))
        sec = security_by_code.get(sec_code)
        if fund is None:
            continue
        if sec is None:
            raw_name = clean(row.get("종목명"))
            kind_match = re.search(r"(CB|BW|EB)", raw_name, re.IGNORECASE)
            if clean(row.get("자산군")) != "채권" or not kind_match:
                continue
            value, cost, share = number(row.get("평가금")), number(row.get("취득가액")), number(fund.get("지분율"), 1.0)
            lookthrough = value * share
            hold_date = str(row.get("보유일") or "")[:10]
            latest_hold_date = max(latest_hold_date, hold_date)
            issuer_name, issuer_code = issuer_from_security_name(raw_name)
            issuer_code = issuer_code or issuer_code_by_name.get(issuer_name, "")
            similar = security_by_base_name.get(re.sub(r"\s+", "", raw_name.split("(", 1)[0]).lower())
            similar_underlying_code = code(similar.get("underlyingCode")) if similar else ""
            similar_delta = number(similar.get("delta"), 0.40) if similar else 0.40
            holding_rows.append({
                "date": hold_date, "manager": clean(fund.get("운용사")), "fund": clean(fund.get("펀드명")),
                "fundCode": code(fund.get("펀드코드")), "share": share, "instrumentId": clean(similar.get("instrumentId")) if similar else "", "code": sec_code,
                "name": raw_name, "issuer": clean(similar.get("issuer")) if similar else issuer_name, "underlying": clean(similar.get("underlying")) if similar else "", "type": kind_match.group(1).upper(), "sector": clean(similar.get("sectorLarge")) if similar else "미분류",
                "quantity": number(row.get("수량")), "value": value, "cost": cost, "lookthrough": lookthrough,
                "bookPnl": (value - cost) * share, "delta": similar_delta, "underlyingCode": similar_underlying_code, "issuerCode": code(similar.get("issuerCode")) if similar else issuer_code,
                "underlyingChange": quote_change(quotes, similar_underlying_code), "estimatedPnl": lookthrough * (quote_change(quotes, similar_underlying_code) or 0) * similar_delta, "underlyingPrice": quote_price(quotes, similar_underlying_code), "parity": None,
                "_conversionPrice": number(similar.get("conversionPrice")) if similar else 0,
                "conversionStart": clean(similar.get("conversionStart")) if similar else "", "putDate": clean(similar.get("putDate")) if similar else "", "deltaExposure": lookthrough * similar_delta, "needsRegistration": True,
                "creditRating": clean(row.get("신용등급")), "maturityDate": str(row.get("만기일") or "")[:10],
                "sectorLarge": clean(similar.get("sectorLarge")) if similar else "미분류", "sectorMid": clean(similar.get("sectorMid")) if similar else "미분류", "market": market_by_code.get(similar_underlying_code, "미분류"),
            })
            continue
        value = number(row.get("평가금"))
        cost = number(row.get("취득가액"))
        share = number(fund.get("지분율"), 1.0)
        delta = delta_by_code.get(sec_code, 0)
        ucode = code(sec.get("교환코드") or sec.get("발행코드"))
        if not ucode:
            underlying_name = clean(sec.get("교환대상명"))
            legacy_match = re.search(r"구\.([^\)]+)", underlying_name)
            ucode = underlying_code_by_name.get(underlying_name, "")
            if not ucode and legacy_match:
                ucode = underlying_code_by_name.get(clean(legacy_match.group(1)), "")
        change = quote_change(quotes, ucode)
        current_price = quote_price(quotes, ucode)
        lookthrough = value * share
        estimated_pnl = lookthrough * (change or 0.0) * delta
        hold_date = str(row.get("보유일") or "")[:10]
        latest_hold_date = max(latest_hold_date, hold_date)
        holding_rows.append({
            "date": hold_date, "manager": clean(fund.get("운용사")), "fund": clean(fund.get("펀드명")),
            "fundCode": code(fund.get("펀드코드")), "share": share, "instrumentId": id_by_code.get(sec_code, ""),
            "code": sec_code, "name": clean(row.get("종목명")), "issuer": clean(sec.get("발행사명")),
            "underlying": clean(sec.get("교환대상명")),
            "issuerCode": code(sec.get("발행코드")),
            "type": clean(sec.get("구분")), "sector": clean(sec.get("업종(대)")) or "미분류",
            "quantity": number(row.get("수량")), "value": value, "cost": cost, "lookthrough": lookthrough,
            "bookPnl": (value - cost) * share, "delta": delta, "underlyingCode": ucode,
            "underlyingChange": change, "estimatedPnl": estimated_pnl,
            "underlyingPrice": current_price,
            "parity": (current_price / number(sec.get("전환가"))) if current_price and number(sec.get("전환가")) else None,
            "_conversionPrice": number(sec.get("전환가")),
            "conversionStart": str(sec.get("전환시작일") or "")[:10],
            "putDate": str(sec.get("PUT") or "")[:10],
            "deltaExposure": lookthrough * delta,
            "needsRegistration": False,
            "creditRating": clean(row.get("신용등급")), "maturityDate": str(row.get("만기일") or "")[:10],
            "sectorLarge": clean(sec.get("업종(대)")) or "미분류",
            "sectorMid": clean(sec.get("업종(중)")) or "미분류",
            "market": market_by_code.get(ucode) or clean(quotes.get(ucode, {}).get("market")) or "미분류",
        })

    stock_rows = []
    for _, row in holdings.iterrows():
        fund = matched_fund(row.get("예탁원코드"), row.get("협회펀드코드"))
        if fund is None or clean(row.get("자산군")) != "주식":
            continue
        stock_code = code(row.get("종목코드"))
        change = quote_change(quotes, stock_code)
        share = number(fund.get("지분율"), 1.0)
        value = number(row.get("평가금")) * share
        stock_rows.append({
            "manager": clean(fund.get("운용사")), "fund": clean(fund.get("펀드명")),
            "code": stock_code, "name": clean(row.get("종목명")), "lookthrough": value,
            "change": change, "pnl": value * (change or 0.0),
        })

    trade_rows = []
    for _, row in trades.iterrows():
        fund = matched_fund(row.get("예탁원펀드코드"), row.get("협회펀드코드"))
        sec_code = code(row.get("종목코드"))
        if fund is None:
            continue
        sec = security_by_code.get(sec_code)
        if sec is None:
            raw_name = clean(row.get("종목명"))
            kind_match = re.search(r"(CB|BW|EB)", raw_name, re.IGNORECASE)
            if clean(row.get("자산구분")) != "채권" or not kind_match:
                continue
        trade_rows.append({
            "date": str(row.get("기준일") or "")[:10], "manager": clean(fund.get("운용사")), "fund": clean(fund.get("펀드명")),
            "code": sec_code, "name": clean(row.get("종목명")), "side": clean(row.get("거래구분")),
            "quantity": number(row.get("매매수량")), "price": number(row.get("매매가격")), "amount": number(row.get("결제금액")),
            "share": number(fund.get("지분율"), 1.0),
            "lookthroughAmount": number(row.get("결제금액")) * number(fund.get("지분율"), 1.0),
            "needsRegistration": sec is None,
        })

    raw_trade_dates = sorted({
        str(value)[:10]
        for value in pd.to_datetime(trades.get("기준일"), errors="coerce").dropna()
    })
    kfr_date = str(kfr["거래일"].max())[:10] if not kfr.empty else ""
    kospi_series = load_market_series("KOSPI")
    kosdaq_series = load_market_series("KOSDAQ")
    benchmark_file = ROOT.parent / "stock" / "benchmark_weights.json"
    benchmark_weights = json.loads(benchmark_file.read_text(encoding="utf-8")) if benchmark_file.exists() else {}
    industry_large_by_code, industry_mid_by_code = read_industry_map()
    benchmark_sectors = build_benchmark_sector_weights(
        benchmark_weights,
        industry_large_by_code,
        industry_mid_by_code,
    )
    return {
        "generatedAt": datetime.now().isoformat(timespec="seconds"), "holdingDate": latest_hold_date,
        "kfrDate": kfr_date, "quoteUpdated": quote_updated, "currentIndexReturns": current_index_returns,
        "funds": records(funds), "securities": security_rows, "holdings": holding_rows, "stockHoldings": stock_rows, "trades": trade_rows,
        "fundReturnSeries": build_fund_return_series(fund_price_history, funds),
        "benchmark": {"name": "KOSDAQ", "series": kosdaq_series},
        "benchmarks": {"KOSPI": kospi_series, "KOSDAQ": kosdaq_series},
        "benchmarkWeights": benchmark_weights,
        "benchmarkSectors": benchmark_sectors,
        "tradeMin": raw_trade_dates[0] if raw_trade_dates else "", "tradeMax": raw_trade_dates[-1] if raw_trade_dates else "",
        "methodology": {"window": 10, "exclude": "일일 델타 < 0 또는 > 100%", "identity": "발행사+증권종류+회차 기반 UUID와 종목코드 alias"},
    }


HTML = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>메자닌 대시보드</title>
<style>
:root{--deep:#064e43;--teal:#0b7465;--mint:#d9eee8;--line:#377d70;--ink:#173b35;--bg:#f2f7f5;--red:#c33636;--blue:#2166a5}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#172b27;font-family:"Malgun Gothic",Arial,sans-serif}.app{display:grid;grid-template-columns:248px 1fr;grid-template-rows:auto 1fr;min-height:100vh}.top{grid-column:1/-1;display:flex;align-items:center;gap:18px;background:white;border-bottom:3px solid var(--deep);padding:9px 14px}.title{font-size:25px;font-weight:900;color:var(--ink);min-width:310px}.tabs{display:flex;gap:6px}.tab{border:1px solid var(--line);background:#edf6f3;color:var(--ink);padding:8px 17px;border-radius:5px;font-weight:800;cursor:pointer}.tab.active{background:var(--deep);color:white}.stamp{margin-left:auto;text-align:right;font-size:11px;line-height:1.55;color:#58716c}.side{background:white;border-right:2px solid var(--line);padding:10px;position:sticky;top:0;height:calc(100vh - 55px);overflow:auto}.filter{border:1px solid #a8c8c1;border-radius:6px;padding:8px;margin-bottom:8px}.filter b{font-size:12px;color:var(--ink)}select,input{width:100%;border:1px solid #9abeb6;border-radius:4px;padding:6px;margin-top:6px;background:white}.note{font-size:11px;color:#5b706c;line-height:1.55;background:#eef7f4;padding:8px;border-radius:5px}.main{padding:10px;min-width:0}.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-bottom:9px}.kpi{background:white;border:1.5px solid var(--line);border-radius:7px;padding:9px;min-height:70px}.kpi span{font-size:11px;color:#52716b;font-weight:700}.kpi b{display:block;text-align:right;color:var(--deep);font-size:20px;margin-top:10px}.grid{display:grid;grid-template-columns:1.2fr .8fr;gap:9px}.panel{background:white;border:1.5px solid var(--line);border-radius:13px;padding:10px;min-width:0}.wide{grid-column:1/-1}.panel h2{font-size:13px;color:var(--ink);margin:0 0 8px}.tablewrap{overflow:auto;max-height:510px}table{width:100%;border-collapse:collapse;font-size:11px;white-space:nowrap}th{position:sticky;top:0;background:var(--teal);color:white;padding:5px;cursor:pointer}td{padding:4px 5px;border-bottom:1px solid #e1ece9}tr:nth-child(even){background:#f6faf9}.num{text-align:right}.pos{color:var(--red)}.neg{color:var(--blue)}.barrow{display:grid;grid-template-columns:115px 1fr 75px;gap:8px;align-items:center;font-size:11px;margin:8px 0}.bar{height:17px;background:#e3efec;border-radius:3px;overflow:hidden}.bar i{display:block;height:100%;background:var(--teal)}.empty{padding:45px;text-align:center;color:#788d88}.method{font-size:11px;line-height:1.7;color:#526d67}.tabpane{display:none}.tabpane.active{display:block}@media(max-width:1100px){.app{grid-template-columns:1fr}.side{position:static;height:auto;border-right:0}.main{grid-column:1}.kpis{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}.wide{grid-column:auto}}
</style></head><body><div class="app"><header class="top"><div class="title">메자닌 투자 대시보드</div><nav class="tabs"><button class="tab active" data-tab="overview">보유 현황</button><button class="tab" data-tab="delta">델타 분석</button><button class="tab" data-tab="trade">매매 현황</button><button class="tab" data-tab="security">종목 정보</button></nav><div class="stamp" id="stamp"></div></header>
<aside class="side"><div class="filter"><b>운용사</b><select id="manager"></select></div><div class="filter"><b>펀드</b><select id="fund"></select></div><div class="filter"><b>종목 검색</b><input id="search" placeholder="종목명·발행사·코드"></div><button class="tab" id="reset" style="width:100%;margin-bottom:10px">필터 초기화</button><div class="note"><b>추정손익</b><br>룩스루 평가금 × 기초자산 실시간 등락률 × 추정 델타<br><br><b>추정 델타</b><br>최근 10영업일 중 방향 불일치 및 100% 초과 관측치를 제외한 평균</div></aside>
<main class="main"><section id="overview" class="tabpane active"><div class="kpis" id="kpis"></div><div class="grid"><article class="panel"><h2>운용사별 룩스루 평가금</h2><div id="managerChart"></div></article><article class="panel"><h2>유형별 익스포저</h2><div id="typeChart"></div></article><article class="panel wide"><h2>메자닌 보유 상세</h2><div class="tablewrap"><table id="holdTable"></table></div></article></div></section>
<section id="delta" class="tabpane"><div class="grid"><article class="panel wide"><h2>종목별 추정 델타 및 실시간 추정손익</h2><div class="tablewrap"><table id="deltaTable"></table></div></article><article class="panel wide"><h2>산출 기준</h2><div class="method" id="method"></div></article></div></section>
<section id="trade" class="tabpane"><article class="panel"><h2>메자닌 매매 내역</h2><div class="tablewrap"><table id="tradeTable"></table></div></article></section>
<section id="security" class="tabpane"><article class="panel"><h2>메자닌 종목 마스터</h2><div class="tablewrap"><table id="securityTable"></table></div></article></section></main></div>
<script>const DATA=__DATA__;const $=s=>document.querySelector(s),fmt=n=>Number(n||0).toLocaleString('ko-KR',{maximumFractionDigits:0}),pct=n=>(Number(n||0)*100).toFixed(2)+'%',cls=n=>n>0?'pos':n<0?'neg':'';let state={manager:'전체',fund:'전체',search:''};
function options(el,vals){el.innerHTML=['전체',...vals].map(v=>`<option>${v}</option>`).join('')}options($('#manager'),[...new Set(DATA.holdings.map(x=>x.manager))].sort());options($('#fund'),[...new Set(DATA.holdings.map(x=>x.fund))].sort());
function filtered(){let q=state.search.toLowerCase();return DATA.holdings.filter(x=>(state.manager==='전체'||x.manager===state.manager)&&(state.fund==='전체'||x.fund===state.fund)&&(!q||[x.name,x.issuer,x.code].join(' ').toLowerCase().includes(q)))}
function table(el,cols,rows){el.innerHTML=`<thead><tr>${cols.map(c=>`<th>${c[0]}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${cols.map(c=>`<td class="${c[2]||''} ${c[3]?cls(c[3](r)):''}">${c[1](r)}</td>`).join('')}</tr>`).join('')}</tbody>`}
function bars(el,rows){let max=Math.max(...rows.map(x=>x[1]),1);el.innerHTML=rows.slice(0,12).map(x=>`<div class="barrow"><span>${x[0]}</span><div class="bar"><i style="width:${x[1]/max*100}%"></i></div><b class="num">${fmt(x[1]/1e8)}억</b></div>`).join('')||'<div class="empty">데이터 없음</div>'}
function group(rows,key,val){let m={};rows.forEach(x=>m[x[key]]=(m[x[key]]||0)+x[val]);return Object.entries(m).sort((a,b)=>b[1]-a[1])}
function render(){let h=filtered(),total=h.reduce((s,x)=>s+x.lookthrough,0),pnl=h.reduce((s,x)=>s+x.estimatedPnl,0),book=h.reduce((s,x)=>s+x.bookPnl,0),wd=total?h.reduce((s,x)=>s+x.lookthrough*x.delta,0)/total:0;$('#kpis').innerHTML=[['룩스루 평가금',fmt(total/1e8)+'억'],['장부 평가손익',fmt(book/1e8)+'억'],['실시간 추정손익',fmt(pnl/1e8)+'억'],['가중평균 델타',pct(wd)],['보유 종목',new Set(h.map(x=>x.instrumentId)).size+'개'],['기초자산 연결',h.filter(x=>x.underlyingChange!==null).length+'건']].map(x=>`<div class="kpi"><span>${x[0]}</span><b>${x[1]}</b></div>`).join('');bars($('#managerChart'),group(h,'manager','lookthrough'));bars($('#typeChart'),group(h,'type','lookthrough'));
table($('#holdTable'),[['운용사',x=>x.manager],['펀드',x=>x.fund],['종목',x=>x.name],['코드',x=>x.code],['유형',x=>x.type],['지분율',x=>pct(x.share),'num'],['룩스루 평가금',x=>fmt(x.lookthrough),'num'],['델타',x=>pct(x.delta),'num'],['기초 등락률',x=>pct(x.underlyingChange),'num',x=>x.underlyingChange],['추정손익',x=>fmt(x.estimatedPnl),'num',x=>x.estimatedPnl]],h.sort((a,b)=>b.lookthrough-a.lookthrough));
let byId={};h.forEach(x=>{let z=byId[x.instrumentId]||{...x,lookthrough:0,estimatedPnl:0};z.lookthrough+=x.lookthrough;z.estimatedPnl+=x.estimatedPnl;byId[x.instrumentId]=z});table($('#deltaTable'),[['종목',x=>x.name],['발행사',x=>x.issuer],['기초코드',x=>x.underlyingCode],['평가금',x=>fmt(x.lookthrough),'num'],['추정델타',x=>pct(x.delta),'num'],['기초 등락률',x=>pct(x.underlyingChange),'num',x=>x.underlyingChange],['추정손익',x=>fmt(x.estimatedPnl),'num',x=>x.estimatedPnl]],Object.values(byId).sort((a,b)=>b.lookthrough-a.lookthrough));}
table($('#tradeTable'),[['일자',x=>x.date],['운용사',x=>x.manager],['펀드',x=>x.fund],['종목',x=>x.name],['구분',x=>x.side],['수량',x=>fmt(x.quantity),'num'],['가격',x=>fmt(x.price),'num'],['결제금액',x=>fmt(x.amount),'num']],DATA.trades.sort((a,b)=>b.date.localeCompare(a.date)));
table($('#securityTable'),[['내부 ID',x=>x.instrumentId.slice(0,8)],['KR코드',x=>x.code],['종목',x=>x.name],['발행사',x=>x.issuer],['유형',x=>x.type],['회차',x=>x.round,'num'],['기초자산',x=>x.underlying],['기초코드',x=>x.underlyingCode],['델타',x=>pct(x.delta),'num'],['유효표본',x=>x.deltaSamples+' / 10','num'],['전환가',x=>fmt(x.conversionPrice),'num'],['PUT',x=>x.putDate],['CALL',x=>x.callDate]],DATA.securities);
$('#method').innerHTML=`내부 식별자는 <b>발행사 + 증권종류 + 회차</b>로 생성한 UUID를 사용하며 KR코드는 alias로 관리합니다. 코드가 변경되면 instrument_aliases.csv에 새 코드를 같은 instrument_id로 추가하면 과거 이력이 이어집니다.<br>델타 윈도우: 최근 ${DATA.methodology.window}개 관측치 / 제외조건: ${DATA.methodology.exclude}. 표본이 없으면 종목정보의 기존 델타를 fallback으로 사용합니다.`;$('#stamp').innerHTML=`보유 ${DATA.holdingDate} · KFR ${DATA.kfrDate}<br>Kiwoom ${DATA.quoteUpdated}`;
$('#manager').onchange=e=>{state.manager=e.target.value;render()};$('#fund').onchange=e=>{state.fund=e.target.value;render()};$('#search').oninput=e=>{state.search=e.target.value;render()};$('#reset').onclick=()=>{state={manager:'전체',fund:'전체',search:''};$('#manager').value=$('#fund').value='전체';$('#search').value='';render()};document.querySelectorAll('.tab[data-tab]').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tab[data-tab],.tabpane').forEach(x=>x.classList.remove('active'));b.classList.add('active');$('#'+b.dataset.tab).classList.add('active')});render();</script></body></html>'''


def main() -> None:
    data = build_data()
    template_path = ROOT / "dashboard_template.html"
    template = template_path.read_text(encoding="utf-8") if template_path.exists() else HTML
    template = template.replace(
        '../manual-edit/index.html?domain=mezzanine&amp;', '../mezzanine-admin/?'
    ).replace(
        '../manual-edit/index.html?domain=mezzanine', '../mezzanine-admin/'
    ).replace('disclosure_view.html', '../mezzanine-disclosures/')
    OUTPUT.write_text(template.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":"))), encoding="utf-8")
    print(f"created: {OUTPUT}")
    print(f"holdings={len(data['holdings'])}, securities={len(data['securities'])}, trades={len(data['trades'])}")


if __name__ == "__main__":
    main()


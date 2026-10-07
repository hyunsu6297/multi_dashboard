from __future__ import annotations

import os
import re
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Callable

import pandas as pd

import build_fund_dashboard as dashboard
from fetch_kiwoom_quotes import (
    DEFAULT_HOST,
    derivative_proxy_code,
    is_derivative_code,
    is_preferred_name,
    kiwoom_rest_code,
    load_credentials,
    load_derivative_code_map,
    load_stock_future_proxy_map,
    post_json,
    request_token,
)


MARKETS = {"코스피": "001", "코스닥": "101"}
INDEX_PROXY_MARKETS = {"069500": "코스피", "229200": "코스닥"}
ETF_NAME_PREFIXES = ("KODEX ", "TIGER ", "SOL ", "ACE ", "PLUS ", "RISE ", "HANARO ", "KBSTAR ")
DERIVATIVE_CODE_MAP = load_derivative_code_map()
STOCK_FUTURE_PROXY_MAP = load_stock_future_proxy_map()


def _number(value: object, default: float = 0.0) -> float:
    try:
        parsed = float(value)
        return parsed if parsed == parsed else default
    except (TypeError, ValueError):
        return default


def _validate_period(start_date: str, end_date: str) -> None:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start_date) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", end_date):
        raise ValueError("조회 기간이 올바르지 않습니다.")
    if start_date > end_date:
        raise ValueError("시작일은 종료일보다 늦을 수 없습니다.")


def _fetch_index_closes(start_date: str, end_date: str) -> dict[str, dict[str, float]]:
    appkey, secretkey = load_credentials()
    if not appkey or not secretkey:
        raise RuntimeError("키움 일봉 조회용 KIWOOM_APPKEY/KIWOOM_SECRETKEY가 설정되지 않았습니다.")
    host = os.getenv("KIWOOM_HOST", DEFAULT_HOST)
    token = os.getenv("KIWOOM_ACCESS_TOKEN") or request_token(host, appkey, secretkey, 20.0)
    result: dict[str, dict[str, float]] = {}
    for market in MARKETS:
        response = post_json(
            host,
            "/api/dostk/chart",
            {"inds_cd": MARKETS[market], "base_dt": end_date.replace("-", "")},
            headers={
                "authorization": f"Bearer {token}",
                "api-id": "ka20006",
                "cont-yn": "N",
                "next-key": "0",
            },
            timeout=30.0,
        )
        rows = response.get("inds_dt_pole_qry", [])
        market_cache = result.setdefault(market, {})
        for row in rows if isinstance(rows, list) else []:
            day = str(row.get("dt") or "")
            if len(day) == 8:
                day = f"{day[:4]}-{day[4:6]}-{day[6:]}"
            close = abs(_number(row.get("cur_prc"))) / 100.0
            if day and close:
                market_cache[day] = close
    return result


def _stored_index_returns(
    supabase_get: Callable[[str], list[dict]], start_date: str, end_date: str
) -> dict[str, dict[str, float]]:
    markets = {"INDEX_KOSPI": "코스피", "INDEX_KOSDAQ": "코스닥"}
    result: dict[str, dict[str, float]] = {market: {} for market in MARKETS}
    daily_rows = supabase_get(
        "kiwoom_daily_prices?select=business_date,code,change_rate"
        f"&business_date=gte.{start_date}&business_date=lte.{end_date}"
        "&code=in.(INDEX_KOSPI,INDEX_KOSDAQ)"
    )
    for row in daily_rows:
        market = markets.get(str(row.get("code") or ""))
        day = str(row.get("business_date") or "")
        if market and day and row.get("change_rate") is not None:
            result[market][day] = _number(row["change_rate"]) * 100
    rows = supabase_get(
        "kiwoom_realtime_quotes?select=code,change_rate,collected_at"
        "&code=in.(INDEX_KOSPI,INDEX_KOSDAQ)"
    )
    for row in rows:
        market = markets.get(str(row.get("code") or ""))
        collected_at = str(row.get("collected_at") or "")
        day = collected_at[:10]
        rate = row.get("change_rate")
        if market and start_date <= day <= end_date and rate is not None and day not in result[market]:
            result[market][day] = _number(rate)
    return result


def _index_returns(
    supabase_get: Callable[[str], list[dict]], start_date: str, end_date: str
) -> dict[str, dict[str, float]]:
    stored = _stored_index_returns(supabase_get, start_date, end_date)
    if start_date == end_date and all(start_date in stored[market] for market in MARKETS):
        return stored

    closes = _fetch_index_closes(start_date, end_date)
    result: dict[str, dict[str, float]] = {}
    for market, values in closes.items():
        ordered = sorted((day, _number(value)) for day, value in values.items() if value and day <= end_date)
        previous = None
        rates: dict[str, float] = {}
        for day, close in ordered:
            if previous and start_date <= day <= end_date:
                rates[day] = (close / previous - 1) * 100
            previous = close
        result[market] = {**rates, **stored.get(market, {})}
    return result


def _stock_prices(
    supabase_get: Callable[[str], list[dict]],
    supabase_upsert: Callable[[str, list[dict], str], list[dict]],
    start_date: str,
    end_date: str,
    required_codes: dict[str, str],
    required_by_date: dict[str, set[str]],
) -> dict[str, dict[str, dict]]:
    by_date: dict[str, dict[str, dict]] = defaultdict(dict)
    offset = 0
    while True:
        query = (
            "kiwoom_daily_prices?select=business_date,code,name,close_price,change_rate,source"
            f"&business_date=gte.{start_date}&business_date=lte.{end_date}"
            f"&order=business_date.asc,code.asc&limit=1000&offset={offset}"
        )
        page = supabase_get(query)
        for row in page:
            day = str(row.get("business_date") or "")
            code = dashboard.normalize_code(row.get("code"))
            if day and code:
                by_date[day][code] = row
        if len(page) < 1000:
            break
        offset += 1000
    missing_codes = {
        code: name for code, name in required_codes.items()
        if code and any(
            code in codes and code not in by_date.get(day, {})
            for day, codes in required_by_date.items()
        )
    }
    if missing_codes:
        print(f"Kiwoom daily-chart backfill: {len(missing_codes)} codes, request delay >=1s", flush=True)
        fetched = _fetch_missing_stock_prices(
            missing_codes, start_date, end_date, supabase_upsert, by_date, required_by_date
        )
        for row in fetched:
            day = str(row.get("business_date") or "")
            code = dashboard.normalize_code(row.get("code"))
            if day and code:
                by_date[day][code] = row
    return dict(by_date)


def _fetch_missing_stock_prices(
    missing_codes: dict[str, str],
    start_date: str,
    end_date: str,
    supabase_upsert: Callable[[str, list[dict], str], list[dict]],
    existing_by_date: dict[str, dict[str, dict]],
    required_by_date: dict[str, set[str]],
) -> list[dict]:
    appkey, secretkey = load_credentials()
    if not appkey or not secretkey:
        print("Kiwoom daily-chart credentials unavailable; using saved daily prices.", file=sys.stderr)
        return []
    host = os.getenv("KIWOOM_HOST", DEFAULT_HOST)
    try:
        token = os.getenv("KIWOOM_ACCESS_TOKEN") or request_token(host, appkey, secretkey, 20.0)
    except RuntimeError as exc:
        print(f"Kiwoom daily-chart token unavailable ({exc}); using saved daily prices.", file=sys.stderr)
        return []
    pending: list[dict] = []
    fetched: list[dict] = []
    request_delay = max(1.0, _number(os.getenv("KIWOOM_HISTORY_REQUEST_DELAY_SECONDS"), 1.0))
    for request_number, (code, name) in enumerate(missing_codes.items(), 1):
        if request_number == 1 or request_number % 25 == 0:
            print(f"Kiwoom daily-chart progress: {request_number}/{len(missing_codes)}", flush=True)
        rest_code = kiwoom_rest_code(code, DERIVATIVE_CODE_MAP, name)
        if not rest_code and is_derivative_code(code):
            rest_code = derivative_proxy_code(code, name, STOCK_FUTURE_PROXY_MAP)
        if not rest_code:
            continue
        response = None
        for attempt in range(3):
            try:
                response = post_json(
                    host,
                    "/api/dostk/chart",
                    {"stk_cd": rest_code, "base_dt": end_date.replace("-", ""), "upd_stkpc_tp": "1"},
                    headers={
                        "authorization": f"Bearer {token}",
                        "api-id": "ka10081",
                        "cont-yn": "N",
                        "next-key": "0",
                    },
                    timeout=30.0,
                )
                if str(response.get("return_code", "0")) != "0":
                    raise RuntimeError(str(response.get("return_msg") or response.get("return_code")))
                break
            except RuntimeError as exc:
                print(f"Kiwoom daily chart {code}: attempt {attempt + 1}/3 failed: {exc}", file=sys.stderr)
                time.sleep(request_delay * (2 ** attempt))
        time.sleep(request_delay)
        if response is None or str(response.get("return_code", "0")) != "0":
            continue
        raw_rows = response.get("stk_dt_pole_chart_qry", [])
        closes = []
        for row in raw_rows if isinstance(raw_rows, list) else []:
            day = str(row.get("dt") or "")
            if len(day) == 8:
                day = f"{day[:4]}-{day[4:6]}-{day[6:]}"
            close = abs(_number(row.get("cur_prc")))
            if day and close:
                closes.append((day, close))
        previous = None
        for day, close in sorted(closes):
            change_rate = close / previous - 1 if previous else None
            if (start_date <= day <= end_date and change_rate is not None
                    and code in required_by_date.get(day, set())
                    and code not in existing_by_date.get(day, {})):
                record = {
                    "business_date": day,
                    "code": code,
                    "name": name,
                    "close_price": close,
                    "change_rate": change_rate,
                    "source": "ka10081",
                }
                pending.append(record)
                if start_date <= day <= end_date:
                    fetched.append(record)
            previous = close
        if len(pending) >= 500:
            supabase_upsert("kiwoom_daily_prices", pending, "business_date,code")
            pending = []
    if pending:
        supabase_upsert("kiwoom_daily_prices", pending, "business_date,code")
    return fetched


def _performance_reference_code(code: str, name: str) -> str:
    normalized = dashboard.normalize_code(code)
    if is_derivative_code(normalized):
        return (
            derivative_proxy_code(normalized, name, STOCK_FUTURE_PROXY_MAP)
            or dashboard.normalize_code(DERIVATIVE_CODE_MAP.get(normalized))
        )
    if re.fullmatch(r"\d{6}", normalized) and is_preferred_name(name) and normalized.endswith(("1", "2", "5", "7")):
        return f"{normalized[:5]}0"
    return normalized


def _market_master(supabase_get: Callable[[str], list[dict]]) -> dict[str, str]:
    result: dict[str, str] = {}
    offset = 0
    while True:
        rows = supabase_get(
            "stock_market_master?select=code,market&order=code.asc"
            f"&limit=1000&offset={offset}"
        )
        if not rows:
            break
        for row in rows:
            code = dashboard.normalize_code(row.get("code"))
            if code:
                result[code] = str(row.get("market") or "미분류")
        if len(rows) < 1000:
            break
        offset += 1000
    offset = 0
    while True:
        rows = supabase_get(
            "kiwoom_realtime_quotes?select=code,market&order=code.asc"
            f"&limit=1000&offset={offset}"
        )
        for row in rows:
            code = dashboard.normalize_code(row.get("code"))
            market = str(row.get("market") or "")
            if code and market in MARKETS and result.get(code) not in MARKETS:
                result[code] = market
        if len(rows) < 1000:
            break
        offset += 1000
    return result


def _benchmark_rows(
    supabase_get: Callable[[str], list[dict]], start_date: str, end_date: str
) -> list[dict]:
    lookback = (date.fromisoformat(start_date) - timedelta(days=10)).isoformat()
    return supabase_get(
        "stock_benchmark_snapshots?select=market,business_date,weights,scale"
        f"&business_date=gte.{lookback}&business_date=lte.{end_date}"
        "&order=business_date.asc,market.asc&limit=100"
    )


def _benchmark_for_day(rows: list[dict], market: str, day: str) -> dict[str, float]:
    candidates = [row for row in rows if str(row.get("market") or "") == market]
    if not candidates:
        return {}
    # Daily attribution uses weights known at the start of the session.
    eligible = [row for row in candidates if str(row.get("business_date") or "") < day]
    chosen = eligible[-1] if eligible else candidates[0]
    raw = chosen.get("weights") if isinstance(chosen.get("weights"), dict) else {}
    return {
        dashboard.normalize_code(code): _number(value.get("weight") if isinstance(value, dict) else value)
        for code, value in raw.items()
        if dashboard.normalize_code(code)
    }


def _daily_summary_text(payload: dict) -> str:
    parts = []
    positions = payload.get("positions", [])
    for market in MARKETS:
        rows = [row for row in positions if row.get("market") == market]
        exposure = sum(_number(row.get("exp")) for row in rows)
        profit = sum(_number(row.get("pl")) for row in rows)
        actual = profit / exposure * 100 if exposure else 0.0
        benchmark = _number(payload.get("marketIndexReturns", {}).get(market))
        relative = actual - benchmark
        direction = "상회" if relative > 0 else "하회" if relative < 0 else "동일"
        parts.append(
            f"[{market}] 포트폴리오 수익률은 {actual:+.2f}%로 BM {benchmark:+.2f}% 대비 "
            f"{relative:+.2f}%p {direction}했습니다."
        )
    return "\n\n".join(parts)


def build_historical_snapshots(
    supabase_get: Callable[[str], list[dict]],
    supabase_upsert: Callable[[str, list[dict], str], list[dict]],
    start_date: str,
    end_date: str,
    fund_scope: str,
) -> list[dict]:
    _validate_period(start_date, end_date)
    lookback = (date.fromisoformat(start_date) - timedelta(days=10)).isoformat()
    client = dashboard.supabase_client()
    fund_versions = dashboard.fetch_stock_fund_info_versions(client)
    prior_snapshots = dashboard.fetch_kfr_snapshots(
        client, "fund_holdings", start_date=lookback, end_date=start_date, include_excel=True
    )
    prior_dates = [str(row["business_date"]) for row in prior_snapshots if str(row["business_date"]) < start_date]
    holdings_start = max(prior_dates) if prior_dates else start_date
    holdings_raw = dashboard.fetch_kfr_rows(
        client, "fund_holdings", start_date=holdings_start, end_date=end_date, include_excel=True
    )
    if holdings_raw.empty:
        return []

    large_by_code, mid_by_code = dashboard.read_industry_map()
    prepared = []
    ratio_source_dates: dict[str, str] = {}
    master_sheets: dict[str, str] = {}
    holdings_by_date = {
        str(day): frame.copy() for day, frame in holdings_raw.groupby("스냅샷일")
    }
    for holding_date, day_raw in holdings_by_date.items():
        sheet = dashboard.choose_effective_sheet(list(fund_versions), str(holding_date))
        if not sheet:
            raise RuntimeError(f"No fund master for holdings date {holding_date}")
        master_sheets[holding_date] = sheet
        funds = dashboard.fund_info_from_version_records(fund_versions[sheet])
        fund_codes = set(funds["펀드코드"])
        selected = day_raw[day_raw["협회펀드코드"].map(dashboard.normalize_code).isin(fund_codes)]
        if holding_date == "2026-06-30" and not selected.empty and selected["지분율"].isna().all():
            source_date = "2026-07-01"
            source = holdings_by_date.get(source_date)
            if source is None:
                raise RuntimeError("June 30 share ratios require the July 1 KFR holdings snapshot")
            source_ratios = source[["협회펀드코드", "지분율"]].copy()
            source_ratios["협회펀드코드"] = source_ratios["협회펀드코드"].map(dashboard.normalize_code)
            source_ratios["지분율"] = pd.to_numeric(source_ratios["지분율"], errors="coerce")
            ratios = source_ratios.dropna().groupby("협회펀드코드")["지분율"].agg(["first", "nunique"])
            selected_codes = set(selected["협회펀드코드"].map(dashboard.normalize_code))
            if any(code not in ratios.index or ratios.loc[code, "nunique"] != 1 for code in selected_codes):
                raise RuntimeError("June 30 fund share ratios could not be verified from July 1")
            day_raw = day_raw.copy()
            day_raw["지분율"] = day_raw["협회펀드코드"].map(dashboard.normalize_code).map(ratios["first"])
            ratio_source_dates[holding_date] = source_date
            selected = day_raw[day_raw["협회펀드코드"].map(dashboard.normalize_code).isin(fund_codes)]
        if not selected.empty and selected["지분율"].isna().any():
            raise RuntimeError(f"Missing share ratios for active funds on {holding_date}")
        day_prepared = dashboard.prepare_holdings_frame(
            day_raw, funds, large_by_code, mid_by_code
        )
        if not day_prepared.empty:
            prepared.append(day_prepared)
    if not prepared:
        return []
    holdings = pd.concat(prepared, ignore_index=True)
    holdings["스냅샷일"] = holdings["스냅샷일"].astype(str)
    holdings = holdings[dashboard.is_equity_related(holdings, "자산군")].copy()
    if fund_scope not in {"전체 펀드", "전체 펀드 통합", "ALL"}:
        holdings = holdings[holdings["보유펀드명"].astype(str) == fund_scope].copy()

    required_codes = {
        dashboard.normalize_code(row.get("종목코드정규")): str(row.get("종목명") or "")
        for _, row in holdings.iterrows()
        if dashboard.normalize_code(row.get("종목코드정규"))
    }
    market_by_code = _market_master(supabase_get)
    tradable_codes = {
        code: name for code, name in required_codes.items()
        if (market_by_code.get(code) in MARKETS
            or market_by_code.get(_performance_reference_code(code, name)) in MARKETS
            or (is_derivative_code(code) and _performance_reference_code(code, name) in INDEX_PROXY_MARKETS)
            or (re.fullmatch(r"\d{6}", code) and name.startswith(ETF_NAME_PREFIXES)))
    }
    holding_dates = sorted(set(holdings["스냅샷일"]))
    performance_dates = [
        str(row["business_date"])
        for row in dashboard.fetch_kfr_snapshots(
            client, "fund_prices", start_date=start_date, end_date=end_date
        )
    ]
    required_by_date: dict[str, set[str]] = {}
    for performance_date in performance_dates:
        prior_dates = [day for day in holding_dates if day < performance_date]
        if not prior_dates:
            continue
        day_holdings = holdings[holdings["스냅샷일"] == prior_dates[-1]]
        required_by_date[performance_date] = {
            code for code in day_holdings["종목코드정규"] if code in tradable_codes
        }
    prices = _stock_prices(
        supabase_get, supabase_upsert, start_date, end_date, tradable_codes, required_by_date
    )
    index_rates = _index_returns(supabase_get, start_date, end_date)
    benchmark_snapshots = _benchmark_rows(supabase_get, start_date, end_date)
    snapshots: list[dict] = []

    for performance_date in sorted(prices):
        prior_dates = [day for day in holding_dates if day < performance_date]
        if not prior_dates:
            continue
        holdings_date = prior_dates[-1]
        day_holdings = holdings[holdings["스냅샷일"] == holdings_date]
        day_prices = prices[performance_date]
        positions = []
        priced_positions = 0
        for _, row in day_holdings.iterrows():
            code = dashboard.normalize_code(row.get("종목코드정규"))
            price = day_prices.get(code)
            if not code:
                continue
            name = str(row.get("종목명") or (price or {}).get("name") or code)
            reference_code = _performance_reference_code(code, name)
            market = market_by_code.get(code) or market_by_code.get(reference_code, "미분류")
            if is_derivative_code(code) and reference_code in INDEX_PROXY_MARKETS:
                market = INDEX_PROXY_MARKETS[reference_code]
            exposure = _number(row.get("우리평가금")) * _number(row.get("포지션부호"), 1.0)
            has_price = bool(price and price.get("change_rate") is not None)
            change_pct = _number(price.get("change_rate")) * 100 if has_price else 0.0
            if has_price:
                priced_positions += 1
            positions.append({
                "fund": str(row.get("보유펀드명") or ""),
                "name": name,
                "code": code,
                "market": market,
                "sectorLarge": str(
                    row.get("업종대분류")
                    if str(row.get("업종대분류") or "미분류") != "미분류"
                    else large_by_code.get(reference_code, "미분류")
                ),
                "sectorMid": str(
                    row.get("업종중분류")
                    if str(row.get("업종중분류") or "미분류") != "미분류"
                    else mid_by_code.get(reference_code, "미분류")
                ),
                "exp": exposure,
                "pl": exposure * change_pct / 100,
                "changeRatePct": change_pct,
                "priceAvailable": has_price,
                "benchmarkCode": reference_code,
                "benchmarkKey": f"{market}|{reference_code}",
                "benchmarkWeight": 0.0,
            })

        benchmark_sectors: dict[str, dict] = {}
        for market in MARKETS:
            weights = _benchmark_for_day(benchmark_snapshots, market, performance_date)
            sector_payload = dashboard.build_benchmark_sector_weights(
                {"weights": {market: weights}}, large_by_code, mid_by_code
            ).get(market, {})
            benchmark_sectors[market] = sector_payload
            for position in positions:
                if position["market"] == market:
                    position["benchmarkWeight"] = weights.get(position["benchmarkCode"], 0.0)

        payload = {
            "asOfDate": performance_date,
            "holdingsSnapshotDate": holdings_date,
            "selectedFund": fund_scope,
            "marketIndexReturns": {
                market: index_rates.get(market, {}).get(performance_date)
                for market in MARKETS
            },
            "benchmarkSectors": benchmark_sectors,
            "positions": positions,
            "snapshotSchemaVersion": 2,
            "calculationBasis": "previous_holding_snapshot_x_kiwoom_daily_close_return",
            "dailyAnalysis": {
                "title": "일별 성과 요약",
                "analysis": "",
                "model": "Python 엔진",
            },
            "coverage": {
                "holdingRows": len(day_holdings),
                "positionRows": len(positions),
                "pricedPositions": priced_positions,
                "unpricedPositions": max(0, len(positions) - priced_positions),
                "excludedPositions": max(0, len(day_holdings) - len(positions)),
                "sameDayTradesIncluded": False,
                "directStocksIncluded": False,
                "fundMasterSheet": master_sheets.get(holdings_date),
                "estimatedShareRatioFrom": ratio_source_dates.get(holdings_date),
            },
        }
        payload["dailyAnalysis"]["analysis"] = _daily_summary_text(payload)
        snapshots.append({
            "performance_date": performance_date,
            "holdings_snapshot_date": holdings_date,
            "fund_scope": fund_scope,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "calculation_version": "historical-close-v5",
            "payload": payload,
        })
    return snapshots

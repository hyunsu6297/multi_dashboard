from __future__ import annotations

import os
import re
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Callable

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


def _index_returns(start_date: str, end_date: str) -> dict[str, dict[str, float]]:
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
        result[market] = rates
    return result


def _stock_prices(
    supabase_get: Callable[[str], list[dict]],
    supabase_upsert: Callable[[str, list[dict], str], list[dict]],
    start_date: str,
    end_date: str,
    required_codes: dict[str, str],
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
        if code and (not by_date or any(code not in by_date.get(day, {}) for day in by_date))
    }
    if missing_codes:
        fetched = _fetch_missing_stock_prices(
            missing_codes, start_date, end_date, supabase_upsert
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
) -> list[dict]:
    appkey, secretkey = load_credentials()
    if not appkey or not secretkey:
        raise RuntimeError("키움 일봉 조회용 KIWOOM_APPKEY/KIWOOM_SECRETKEY가 설정되지 않았습니다.")
    host = os.getenv("KIWOOM_HOST", DEFAULT_HOST)
    token = os.getenv("KIWOOM_ACCESS_TOKEN") or request_token(host, appkey, secretkey, 20.0)
    minimum_date = (date.fromisoformat(start_date) - timedelta(days=10)).isoformat()
    pending: list[dict] = []
    fetched: list[dict] = []
    for code, name in missing_codes.items():
        rest_code = kiwoom_rest_code(code, DERIVATIVE_CODE_MAP, name)
        if not rest_code and is_derivative_code(code):
            rest_code = derivative_proxy_code(code, name, STOCK_FUTURE_PROXY_MAP)
        if not rest_code:
            continue
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
        except RuntimeError:
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
            if minimum_date <= day <= end_date and change_rate is not None:
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
        time.sleep(0.12)
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
    fund_rows = dashboard.fetch_stock_fund_info_rows(client, end_date)
    funds = dashboard.normalize_fund_info_frame(fund_rows)
    funds, _ = dashboard.apply_fund_master(funds)
    holdings_raw = dashboard.fetch_kfr_rows(
        client, "fund_holdings", start_date=lookback, end_date=end_date
    )
    if holdings_raw.empty:
        return []

    large_by_code, mid_by_code = dashboard.read_industry_map()
    holdings = dashboard.prepare_holdings_frame(
        holdings_raw, funds, large_by_code, mid_by_code
    )
    holdings["스냅샷일"] = holdings["스냅샷일"].astype(str)
    holdings = holdings[dashboard.is_equity_related(holdings, "자산군")].copy()
    if fund_scope not in {"전체 펀드", "전체 펀드 통합", "ALL"}:
        holdings = holdings[holdings["보유펀드명"].astype(str) == fund_scope].copy()

    required_codes = {
        dashboard.normalize_code(row.get("종목코드정규")): str(row.get("종목명") or "")
        for _, row in holdings.iterrows()
        if dashboard.normalize_code(row.get("종목코드정규"))
    }
    prices = _stock_prices(
        supabase_get, supabase_upsert, start_date, end_date, required_codes
    )
    index_rates = _index_returns(start_date, end_date)
    market_by_code = _market_master(supabase_get)
    benchmark_snapshots = _benchmark_rows(supabase_get, start_date, end_date)
    holding_dates = sorted(set(holdings["스냅샷일"]))
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

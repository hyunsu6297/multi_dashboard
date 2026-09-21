from __future__ import annotations

import gzip
import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HOST = "127.0.0.1"
PORT = 8765
MODEL = "gpt-5.4-mini"
MAX_REQUEST_BYTES = 512 * 1024
BASE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = BASE_DIR.parents[1]
LOCAL_KFR_DIR = REPOSITORY_ROOT / "data" / "kfr"
DEFAULT_SUPABASE_URL = "https://esqakvzvchcunhzjlyry.supabase.co"
SNAPSHOT_ENVIRONMENT = "local_test"
SNAPSHOT_CALCULATION_VERSION = "v1"

FUND_RETURN_CODE_BY_NAME = {
    "밸류알레그로": "KRZ502611211",
    "밸류프레스토": "KRZ502630622",
    "웰컴하이일드1호": "KRZ502619770",
    "웰컴공모주2호": "KRZ502593210",
    "이지스드래곤4호": "KRZ502620720",
    "코람코하이일드45호": "KRZ502628640",
    "보고빌드업": "KRZ502578863",
    "현대인베1호": "KRZ502627860",
    "DB알파3호": "KRZ502609750",
    "브이엠하이일드": "KRZ502493854",
    "W1000": "KRZ502327923",
    "안다블루칩": "KRZ502363413",
    "VIP올인원": "KRZ502274243",
    "보고VOYAGE": "KRZ502575043",
    "블래쉬2호": "KRZ502671172",
    "타임폴리오EH": "KRZ502421551",
    "DB하이일드3호": "KRZ502641190",
    "빌리언폴드LS": "KRZ502501108",
}
FUND_RETURN_CACHE: dict[str, dict] = {}
FUND_PRICE_SNAPSHOTS: list[dict] | None = None
LOCAL_FUND_PRICE_ROWS: dict[str, list[dict]] | None = None


def api_key() -> str:
    value = os.environ.get("OPENAI_API_KEY", "").strip()
    if value or sys.platform != "win32":
        return value
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, "OPENAI_API_KEY")
            return str(value).strip()
    except (FileNotFoundError, OSError):
        return ""


def service_role_key() -> str:
    return (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SECRET_KEY") or "").strip()


def supabase_get(path: str) -> list[dict]:
    key = service_role_key()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY가 설정되지 않았습니다.")
    url = f"{os.environ.get('SUPABASE_URL', DEFAULT_SUPABASE_URL).rstrip('/')}/rest/v1/{path}"
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            rows = json.loads(response.read().decode("utf-8") or "[]")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase 조회 실패 HTTP {exc.code}: {detail[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Supabase 조회 연결 실패: {exc.reason}") from exc
    return rows if isinstance(rows, list) else []


def fund_price_snapshots() -> list[dict]:
    global FUND_PRICE_SNAPSHOTS
    if FUND_PRICE_SNAPSHOTS is not None:
        return FUND_PRICE_SNAPSHOTS
    query = urllib.parse.urlencode(
        {
            "select": "id,business_date",
            "source_key": "eq.fund_prices",
            "source_format": "eq.kfr_partner_api_json",
            "order": "business_date.asc,downloaded_at.asc",
        },
        safe=".,()",
    )
    snapshots_by_date = {
        str(row.get("business_date") or ""): {
            "id": int(row["id"]),
            "business_date": str(row.get("business_date") or ""),
        }
        for row in supabase_get(f"kfr_source_snapshots?{query}")
        if row.get("id") is not None and row.get("business_date")
    }
    FUND_PRICE_SNAPSHOTS = [snapshots_by_date[key] for key in sorted(snapshots_by_date)]
    return FUND_PRICE_SNAPSHOTS


def local_fund_price_rows() -> dict[str, list[dict]]:
    global LOCAL_FUND_PRICE_ROWS
    if LOCAL_FUND_PRICE_ROWS is not None:
        return LOCAL_FUND_PRICE_ROWS
    target_codes = set(FUND_RETURN_CODE_BY_NAME.values())
    by_code_date: dict[str, dict[str, dict]] = defaultdict(dict)
    files = sorted(LOCAL_KFR_DIR.glob("prices_*.json"))
    legacy = LOCAL_KFR_DIR / "prices_legacy_history.json.gz"
    if legacy.is_file():
        files.insert(0, legacy)
    for path in files:
        try:
            if path.suffix == ".gz":
                with gzip.open(path, "rt", encoding="utf-8") as file:
                    payload = json.load(file)
            else:
                payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, gzip.BadGzipFile, json.JSONDecodeError):
            continue
        rows = payload.get("content", []) if isinstance(payload, dict) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = str(row.get("fund_ksd_code") or "").strip()
            trade_date = str(row.get("trade_day") or "").strip()[:10]
            if code in target_codes and re.fullmatch(r"\d{4}-\d{2}-\d{2}", trade_date):
                by_code_date[code][trade_date] = row
    LOCAL_FUND_PRICE_ROWS = {
        code: [dates[key] for key in sorted(dates)]
        for code, dates in by_code_date.items()
    }
    return LOCAL_FUND_PRICE_ROWS


def load_fund_return_series(fund_name: str) -> dict:
    name = fund_name.strip()
    if not name or len(name) > 100:
        raise ValueError("조회 대상 펀드가 올바르지 않습니다.")
    code = FUND_RETURN_CODE_BY_NAME.get(name)
    if not code:
        raise ValueError(f"{name}의 기준가 매핑이 없습니다.")
    if code in FUND_RETURN_CACHE:
        return FUND_RETURN_CACHE[code]

    source_rows = [{"payload": row} for row in local_fund_price_rows().get(code, [])]
    if not source_rows:
        offset = 0
        while True:
            query = urllib.parse.urlencode(
                {
                    "select": "row_no,payload",
                    "domain": "eq.fund",
                    "file_key": "eq.fund_nav",
                    "payload->>예탁원펀드코드": f"eq.{code}",
                    "order": "row_no.asc",
                    "limit": "1000",
                    "offset": str(offset),
                },
                safe=".,()->>",
            )
            batch = supabase_get(f"manual_file_rows?{query}")
            if not batch:
                break
            source_rows.extend(batch)
            if len(batch) < 1000:
                break
            offset += 1000
    manual_dates = []
    for item in source_rows:
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        trade_date = str(payload.get("trade_day") or payload.get("기준일") or "").strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", trade_date):
            manual_dates.append(trade_date)
    manual_latest = max(manual_dates, default="")
    snapshot_ids = [
        snapshot["id"]
        for snapshot in fund_price_snapshots()
        if not manual_latest or snapshot["business_date"] > manual_latest
    ]
    for start in range(0, len(snapshot_ids), 40):
        id_filter = ",".join(str(value) for value in snapshot_ids[start:start + 40])
        query = urllib.parse.urlencode(
            {
                "select": "snapshot_id,row_no,payload",
                "snapshot_id": f"in.({id_filter})",
                "payload->>fund_ksd_code": f"eq.{code}",
                "order": "snapshot_id.asc,row_no.asc",
                "limit": "1000",
            },
            safe=".,()->>",
        )
        batch = supabase_get(f"kfr_source_rows?{query}")
        source_rows.extend(batch)
    if not source_rows:
        raise ValueError(f"{name}의 기준가 데이터가 없습니다.")

    by_date: dict[str, dict] = {}
    for item in source_rows:
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        trade_date = str(payload.get("trade_day") or payload.get("기준일") or "").strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", trade_date):
            continue
        def optional_float(*keys: str) -> float | None:
            for key in keys:
                try:
                    value = payload.get(key)
                    if value not in (None, ""):
                        return float(value)
                except (TypeError, ValueError):
                    continue
            return None

        cumulative_return = optional_float("cul_ret", "누적수익률")
        if cumulative_return is None:
            continue
        fund_level = 1000 + cumulative_return * 10

        by_date[trade_date] = {
            "date": trade_date,
            "fund": fund_level,
            "kospi": optional_float("kospi", "KOSPI"),
            "kosdaq": optional_float("kosdaq", "KOSDAQ"),
        }
    rows = [by_date[key] for key in sorted(by_date)]
    if len(rows) < 2:
        raise ValueError(f"{name}의 기준가 관측치가 부족합니다.")
    result = {
        "fund": {"name": name, "code": code},
        "dateMin": rows[0]["date"],
        "dateMax": rows[-1]["date"],
        "rows": rows,
    }
    FUND_RETURN_CACHE[code] = result
    return result


def fund_analysis_stats(rows: list[dict], key: str) -> dict:
    series = [(str(row.get("date") or ""), number(row.get(key))) for row in rows if number(row.get(key)) > 0]
    if len(series) < 2:
        return {}
    first = series[0][1]
    last = series[-1][1]
    daily = [series[index][1] / series[index - 1][1] - 1 for index in range(1, len(series))]
    period_return = last / first - 1
    average = sum(daily) / len(daily)
    variance = sum((value - average) ** 2 for value in daily) / max(1, len(daily) - 1)
    volatility = math.sqrt(variance) * math.sqrt(252)
    annual_return = (1 + period_return) ** (252 / len(daily)) - 1 if period_return > -1 else -1
    peak = first
    mdd = 0.0
    for _, value in series:
        peak = max(peak, value)
        mdd = min(mdd, value / peak - 1)
    return {
        "observations": len(series),
        "periodReturnPct": rounded(period_return * 100),
        "annualReturnPct": rounded(annual_return * 100),
        "annualVolatilityPct": rounded(volatility * 100),
        "sharpe": rounded(annual_return / volatility if volatility else None),
        "mddPct": rounded(mdd * 100),
        "dailyReturns": daily,
    }


def fund_analysis_months(rows: list[dict], key: str) -> list[dict]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        value = number(row.get(key))
        row_date = str(row.get("date") or "")
        if value > 0 and len(row_date) >= 7:
            grouped[row_date[:7]].append(value)
    result = []
    for month, values in grouped.items():
        if len(values) > 1 and values[0]:
            result.append({"month": month, "returnPct": rounded((values[-1] / values[0] - 1) * 100)})
    return result


def fund_analysis_market_profile(positions: list[dict]) -> dict:
    gross = sum(abs(number(row.get("exp"))) for row in positions)
    market_values: dict[str, float] = defaultdict(float)
    sector_values: dict[str, float] = defaultdict(float)
    stock_values: list[tuple[str, float]] = []
    for row in positions:
        value = abs(number(row.get("exp")))
        market_values[str(row.get("market") or "미분류")] += value
        sector_values[str(row.get("sectorMid") or row.get("sectorLarge") or "미분류")] += value
        stock_values.append((str(row.get("name") or "미분류"), value))
    weights = [value / gross for _, value in stock_values if gross and value > 0]
    hhi = sum(weight ** 2 for weight in weights)
    top_stocks = sorted(stock_values, key=lambda item: item[1], reverse=True)[:5]
    weighted = lambda source: [
        {"name": name, "weightPct": rounded(value / gross * 100 if gross else 0)}
        for name, value in sorted(source.items(), key=lambda item: item[1], reverse=True)
    ]
    return {
        "stockCount": len([value for _, value in stock_values if value > 0]),
        "effectiveStockCount": rounded(1 / hhi if hhi else 0, 1),
        "top1WeightPct": rounded(top_stocks[0][1] / gross * 100 if gross and top_stocks else 0),
        "top5WeightPct": rounded(sum(value for _, value in top_stocks) / gross * 100 if gross else 0),
        "markets": weighted(market_values),
        "sectors": weighted(sector_values)[:6],
    }


def prepare_fund_analysis_summary(data: dict) -> dict:
    fund_name = str(data.get("fundName") or "").strip()
    start_date = str(data.get("startDate") or "").strip()
    end_date = str(data.get("endDate") or "").strip()
    benchmark_key = "kosdaq" if str(data.get("benchmark") or "").lower() == "kosdaq" else "kospi"
    benchmark_name = "KOSDAQ" if benchmark_key == "kosdaq" else "KOSPI"
    if not fund_name or fund_name == "전체 펀드":
        raise ValueError("개별 펀드를 선택해 주세요.")
    for label, value in (("시작일", start_date), ("종료일", end_date)):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError(f"{label}이 올바르지 않습니다.")
        date.fromisoformat(value)
    if start_date > end_date:
        raise ValueError("시작일은 종료일보다 늦을 수 없습니다.")

    payload = load_fund_return_series(fund_name)
    rows = [
        row for row in payload.get("rows", [])
        if start_date <= str(row.get("date") or "") <= end_date
        and number(row.get("fund")) > 0
        and number(row.get(benchmark_key)) > 0
    ]
    if len(rows) < 2:
        raise ValueError("선택 기간의 펀드·BM 기준가 관측치가 부족합니다.")
    actual_start = str(rows[0]["date"])
    actual_end = str(rows[-1]["date"])
    fund_stats = fund_analysis_stats(rows, "fund")
    benchmark_stats = fund_analysis_stats(rows, benchmark_key)
    fund_daily = fund_stats.pop("dailyReturns", [])
    benchmark_daily = benchmark_stats.pop("dailyReturns", [])
    pair_count = min(len(fund_daily), len(benchmark_daily))
    covariance = variance = correlation = None
    if pair_count > 1:
        fund_values = fund_daily[-pair_count:]
        benchmark_values = benchmark_daily[-pair_count:]
        fund_mean = sum(fund_values) / pair_count
        benchmark_mean = sum(benchmark_values) / pair_count
        covariance = sum((fund_values[i] - fund_mean) * (benchmark_values[i] - benchmark_mean) for i in range(pair_count)) / (pair_count - 1)
        variance = sum((value - benchmark_mean) ** 2 for value in benchmark_values) / (pair_count - 1)
        fund_variance = sum((value - fund_mean) ** 2 for value in fund_values) / (pair_count - 1)
        if variance > 0 and fund_variance > 0:
            correlation = covariance / math.sqrt(variance * fund_variance)
    beta = covariance / variance if covariance is not None and variance else None
    relative_pp = number(fund_stats.get("periodReturnPct")) - number(benchmark_stats.get("periodReturnPct"))
    monthly = fund_analysis_months(rows, "fund")
    best_months = sorted(monthly, key=lambda row: number(row.get("returnPct")), reverse=True)[:2]
    worst_months = sorted(monthly, key=lambda row: number(row.get("returnPct")))[:2]

    raw_positions = data.get("positions") if isinstance(data.get("positions"), list) else []
    positions = [row for row in raw_positions[:3000] if isinstance(row, dict) and str(row.get("name") or "").strip()]
    raw_trades = data.get("trades") if isinstance(data.get("trades"), list) else []
    trades = [
        row for row in raw_trades[:10000]
        if isinstance(row, dict) and start_date <= str(row.get("date") or "") <= end_date
    ]
    investment = abs(number(data.get("investment")))
    gross_trades = sum(abs(number(row.get("amount"))) for row in trades)
    annualization = min(4.0, 252 / max(1, len(rows) - 1))
    turnover = gross_trades / (2 * investment) * annualization if investment else None
    volatility_ratio = (
        number(fund_stats.get("annualVolatilityPct")) / number(benchmark_stats.get("annualVolatilityPct"))
        if number(benchmark_stats.get("annualVolatilityPct")) else None
    )
    if beta is not None and volatility_ratio is not None:
        style_label = "공격적" if beta >= 1.10 or volatility_ratio >= 1.10 else "방어적" if beta <= 0.90 and volatility_ratio <= 0.90 else "중립적"
    else:
        style_label = "판단 유보"

    trade_by_name: dict[str, dict] = defaultdict(lambda: {"buy": 0.0, "sell": 0.0, "sector": "미분류"})
    for row in trades:
        name = str(row.get("name") or "미분류")
        item = trade_by_name[name]
        side = str(row.get("side") or "")
        amount = abs(number(row.get("amount")))
        if side == "매도":
            item["sell"] += amount
        else:
            item["buy"] += amount
        item["sector"] = str(row.get("sector") or item["sector"])
    changes = []
    current_names = {str(row.get("name") or "") for row in positions if abs(number(row.get("exp"))) > 0}
    for name, item in trade_by_name.items():
        net = item["buy"] - item["sell"]
        changes.append({
            "name": name,
            "sector": item["sector"],
            "buyEok": rounded(item["buy"] / 100_000_000),
            "sellEok": rounded(item["sell"] / 100_000_000),
            "netEok": rounded(net / 100_000_000),
            "netWeightPct": rounded(net / investment * 100 if investment else None),
            "currentlyHeld": name in current_names,
        })
    net_buys = sorted((row for row in changes if number(row.get("netEok")) > 0), key=lambda row: number(row.get("netEok")), reverse=True)[:5]
    net_sells = sorted((row for row in changes if number(row.get("netEok")) < 0), key=lambda row: number(row.get("netEok")))[:5]
    entrants = [row for row in net_buys if row["currentlyHeld"]][:3]
    exits = [row for row in net_sells if not row["currentlyHeld"]][:3]

    contribution_rows = []
    for row in positions:
        cost = abs(number(row.get("cost")))
        profit = number(row.get("profit"))
        contribution_rows.append({
            "name": str(row.get("name") or "미분류"),
            "market": str(row.get("market") or "미분류"),
            "sector": str(row.get("sectorMid") or row.get("sectorLarge") or "미분류"),
            "profitEok": rounded(profit / 100_000_000),
            "returnPct": rounded(profit / cost * 100 if cost else None),
            "portfolioContributionPct": rounded(profit / investment * 100 if investment else None),
        })
    contributors = sorted(
        (row for row in contribution_rows if number(row.get("profitEok")) > 0),
        key=lambda row: number(row.get("profitEok")),
        reverse=True,
    )[:5]
    detractors = sorted(
        (row for row in contribution_rows if number(row.get("profitEok")) < 0),
        key=lambda row: number(row.get("profitEok")),
    )[:5]
    trade_dates = sorted(str(row.get("date") or "") for row in raw_trades if str(row.get("date") or ""))
    trade_data_start = str(data.get("tradeDataStart") or "").strip() or (trade_dates[0] if trade_dates else None)
    trade_data_end = str(data.get("tradeDataEnd") or "").strip() or (trade_dates[-1] if trade_dates else None)

    return {
        "fund": fund_name,
        "period": {"requestedStart": start_date, "requestedEnd": end_date, "actualStart": actual_start, "actualEnd": actual_end},
        "benchmark": benchmark_name,
        "performance": {
            "fund": fund_stats,
            "benchmark": benchmark_stats,
            "relativePp": rounded(relative_pp),
            "beta": rounded(beta),
            "correlation": rounded(correlation),
            "bestMonths": best_months,
            "worstMonths": worst_months,
        },
        "style": {
            **fund_analysis_market_profile(positions),
            "annualizedTurnoverPct": rounded(turnover * 100 if turnover is not None else None),
            "beta": rounded(beta),
            "volatilityRatio": rounded(volatility_ratio),
            "profile": style_label,
        },
        "portfolioChanges": {
            "netBuys": net_buys,
            "netSells": net_sells,
            "newEntryCandidates": entrants,
            "fullExitCandidates": exits,
        },
        "contribution": {"contributors": contributors, "detractors": detractors},
        "coverage": {
            "priceObservations": len(rows),
            "tradeRows": len(trades),
            "tradeDataStart": trade_data_start,
            "tradeDataEnd": trade_data_end,
            "contributionBasis": "현재 보유 포지션의 누적 평가손익 기준이며 선택 기간의 정밀 성과귀속은 아님",
            "changeBasis": "선택 기간 순매수·순매도와 현재 보유 여부를 결합한 약식 분류",
        },
    }


def save_performance_snapshot(data: dict) -> dict:
    performance_date = str(data.get("asOfDate") or "").strip()
    fund_scope = str(data.get("selectedFund") or "").strip()
    holdings_date = str(data.get("holdingsSnapshotDate") or "").strip() or None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", performance_date):
        raise ValueError("성과 기준일이 올바르지 않습니다.")
    date.fromisoformat(performance_date)
    if holdings_date:
        date.fromisoformat(holdings_date)
    if not fund_scope or len(fund_scope) > 200:
        raise ValueError("저장 대상 펀드가 올바르지 않습니다.")
    positions = data.get("positions")
    if not isinstance(positions, list) or not positions:
        raise ValueError("저장할 종목별 성과 데이터가 없습니다.")
    if len(positions) > 5000:
        raise ValueError("저장할 종목별 성과 데이터가 너무 많습니다.")

    key = service_role_key()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY가 설정되지 않았습니다.")
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "performance_date": performance_date,
        "holdings_snapshot_date": holdings_date,
        "fund_scope": fund_scope,
        "captured_at": now,
        "environment": SNAPSHOT_ENVIRONMENT,
        "calculation_version": SNAPSHOT_CALCULATION_VERSION,
        "payload": data,
        "updated_at": now,
    }
    query = urllib.parse.urlencode(
        {"on_conflict": "performance_date,fund_scope,environment"},
        safe=",",
    )
    url = f"{os.environ.get('SUPABASE_URL', DEFAULT_SUPABASE_URL).rstrip('/')}/rest/v1/stock_performance_snapshots?{query}"
    request = urllib.request.Request(
        url,
        data=json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        method="POST",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            saved_rows = json.loads(response.read().decode("utf-8") or "[]")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase 스냅샷 저장 실패 HTTP {exc.code}: {detail[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Supabase 스냅샷 저장 연결 실패: {exc.reason}") from exc
    saved = saved_rows[0] if saved_rows else record
    return {
        "saved": True,
        "performanceDate": saved.get("performance_date", performance_date),
        "holdingsSnapshotDate": saved.get("holdings_snapshot_date", holdings_date),
        "selectedFund": saved.get("fund_scope", fund_scope),
        "capturedAt": saved.get("captured_at", now),
        "environment": saved.get("environment", SNAPSHOT_ENVIRONMENT),
        "positionCount": len(positions),
    }


def load_performance_snapshots(fund_scope: str, start_date: str, end_date: str) -> list[dict]:
    if not fund_scope or len(fund_scope) > 200:
        raise ValueError("조회 대상 펀드가 올바르지 않습니다.")
    for value in (start_date, end_date):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("조회 기간이 올바르지 않습니다.")
        date.fromisoformat(value)
    if start_date > end_date:
        raise ValueError("시작일은 종료일보다 늦을 수 없습니다.")
    key = service_role_key()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY가 설정되지 않았습니다.")
    query = urllib.parse.urlencode(
        {
            "select": "performance_date,holdings_snapshot_date,fund_scope,captured_at,calculation_version,payload",
            "environment": f"eq.{SNAPSHOT_ENVIRONMENT}",
            "fund_scope": f"eq.{fund_scope}",
            "performance_date": f"gte.{start_date}",
            "and": f"(performance_date.lte.{end_date})",
            "order": "performance_date.asc",
        },
        safe=".,()",
    )
    url = f"{os.environ.get('SUPABASE_URL', DEFAULT_SUPABASE_URL).rstrip('/')}/rest/v1/stock_performance_snapshots?{query}"
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            rows = json.loads(response.read().decode("utf-8") or "[]")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase 스냅샷 조회 실패 HTTP {exc.code}: {detail[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Supabase 스냅샷 조회 연결 실패: {exc.reason}") from exc
    return rows if isinstance(rows, list) else []


def compounded_return(rates: list[float]) -> float | None:
    if not rates:
        return None
    factor = 1.0
    for rate in rates:
        factor *= 1 + rate / 100
    return (factor - 1) * 100


def prepare_period_summary(rows: list[dict], start_date: str, end_date: str, fund_scope: str) -> dict:
    market_names = ("코스피", "코스닥")
    market_rates = {market: {"actual": [], "benchmark": []} for market in market_names}
    market_days = {market: 0 for market in market_names}
    sectors: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"portfolioWeightSum": 0.0, "benchmarkWeightSum": 0.0, "contributionPp": 0.0}
    )
    stocks: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"name": "", "weightSum": 0.0, "contributionPp": 0.0, "returns": []}
    )
    snapshot_dates: list[str] = []
    saved_daily_analysis = None

    for record in rows:
        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        positions = [item for item in payload.get("positions", []) if isinstance(item, dict)]
        snapshot_date = str(record.get("performance_date") or payload.get("asOfDate") or "")
        if snapshot_date:
            snapshot_dates.append(snapshot_date)
        if start_date == end_date and isinstance(payload.get("dailyAnalysis"), dict):
            saved_daily_analysis = payload["dailyAnalysis"]
        index_returns = payload.get("marketIndexReturns") if isinstance(payload.get("marketIndexReturns"), dict) else {}
        benchmark_sectors = payload.get("benchmarkSectors") if isinstance(payload.get("benchmarkSectors"), dict) else {}

        for market in market_names:
            market_positions = [item for item in positions if str(item.get("market") or "") == market]
            market_exp = sum(number(item.get("exp")) for item in market_positions)
            market_pl = sum(number(item.get("pl")) for item in market_positions)
            if not market_exp:
                continue
            market_days[market] += 1
            market_rates[market]["actual"].append(market_pl / market_exp * 100)
            benchmark_rate = index_returns.get(market)
            if benchmark_rate is not None:
                market_rates[market]["benchmark"].append(number(benchmark_rate))

            sector_positions: dict[str, list[dict]] = defaultdict(list)
            for item in market_positions:
                sector_positions[str(item.get("sectorMid") or item.get("sectorLarge") or "미분류")].append(item)
            market_benchmark = benchmark_sectors.get(market) if isinstance(benchmark_sectors.get(market), dict) else {}
            benchmark_mid = market_benchmark.get("mid") if isinstance(market_benchmark.get("mid"), dict) else {}
            sector_names = set(sector_positions) | {str(name) for name in benchmark_mid}
            for sector in sector_names:
                items = sector_positions.get(sector, [])
                sector_exp = sum(number(item.get("exp")) for item in items)
                sector_pl = sum(number(item.get("pl")) for item in items)
                benchmark_item = benchmark_mid.get(sector)
                benchmark_weight = number(
                    benchmark_item.get("weight") if isinstance(benchmark_item, dict) else benchmark_item
                )
                aggregate = sectors[(market, sector)]
                aggregate["portfolioWeightSum"] += sector_exp / market_exp * 100
                aggregate["benchmarkWeightSum"] += benchmark_weight * 100
                aggregate["contributionPp"] += sector_pl / market_exp * 100

            for item in market_positions:
                code = str(item.get("code") or item.get("name") or "")
                aggregate = stocks[(market, code)]
                aggregate["name"] = str(item.get("name") or code)
                aggregate["weightSum"] += number(item.get("exp")) / market_exp * 100
                aggregate["contributionPp"] += number(item.get("pl")) / market_exp * 100
                change = item.get("changeRatePct")
                if change is not None:
                    aggregate["returns"].append(number(change))

    market_rows = []
    for market in market_names:
        actual = compounded_return(market_rates[market]["actual"])
        benchmark = compounded_return(market_rates[market]["benchmark"])
        market_rows.append(
            {
                "market": market,
                "days": market_days[market],
                "actualReturnPct": rounded(actual),
                "benchmarkReturnPct": rounded(benchmark),
                "relativePp": rounded(actual - benchmark if actual is not None and benchmark is not None else None),
            }
        )

    sector_rows = []
    for (market, sector), item in sectors.items():
        divisor = market_days[market] or 1
        portfolio_weight = item["portfolioWeightSum"] / divisor
        benchmark_weight = item["benchmarkWeightSum"] / divisor
        sector_rows.append(
            {
                "market": market,
                "sector": sector,
                "portfolioWeightPct": rounded(portfolio_weight),
                "benchmarkWeightPct": rounded(benchmark_weight),
                "activeWeightPp": rounded(portfolio_weight - benchmark_weight),
                "contributionPp": rounded(item["contributionPp"]),
            }
        )
    sector_rows.sort(key=lambda item: abs(number(item.get("contributionPp"))), reverse=True)

    stock_rows = []
    for (market, code), item in stocks.items():
        divisor = market_days[market] or 1
        stock_rows.append(
            {
                "market": market,
                "code": code,
                "name": item["name"],
                "averageWeightPct": rounded(item["weightSum"] / divisor),
                "periodReturnPct": rounded(compounded_return(item["returns"])),
                "contributionPp": rounded(item["contributionPp"]),
            }
        )
    stock_rows.sort(key=lambda item: abs(number(item.get("contributionPp"))), reverse=True)

    return {
        "startDate": start_date,
        "endDate": end_date,
        "selectedFund": fund_scope,
        "environment": SNAPSHOT_ENVIRONMENT,
        "snapshotCount": len(rows),
        "snapshotDates": snapshot_dates,
        "marketRows": market_rows,
        "sectorRows": sector_rows,
        "stockRows": stock_rows,
        "savedDailyAnalysis": saved_daily_analysis,
    }


def extract_output_text(response: dict) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    parts: list[str] = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(str(content["text"]))
    return "\n".join(parts).strip()


def number(value: object, default: float = 0.0) -> float:
    try:
        parsed = float(value)
        return parsed if parsed == parsed else default
    except (TypeError, ValueError):
        return default


def rounded(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


def compact_position(row: dict) -> dict:
    return {
        "name": str(row.get("name") or "미분류"),
        "returnPct": rounded(number(row.get("changeRatePct"))),
    }


def relative_assessment(relative_pp: float | None) -> str | None:
    if relative_pp is None:
        return None
    magnitude = "소폭" if abs(relative_pp) < 0.20 else "다소" if abs(relative_pp) < 0.50 else "큰 폭"
    direction = "강세" if relative_pp > 0 else "약세"
    return f"{magnitude} {direction}"


def prepare_analysis_summary(data: dict) -> dict:
    positions = [row for row in data.get("positions", []) if isinstance(row, dict)]
    total_exp = sum(number(row.get("exp")) for row in positions)
    total_pl = sum(number(row.get("pl")) for row in positions)
    index_returns = data.get("marketIndexReturns") if isinstance(data.get("marketIndexReturns"), dict) else {}
    benchmark_sectors = data.get("benchmarkSectors") if isinstance(data.get("benchmarkSectors"), dict) else {}
    has_full_benchmark_sectors = any(
        isinstance(benchmark_sectors.get(market), dict)
        and isinstance(benchmark_sectors[market].get("mid"), dict)
        for market in ("코스피", "코스닥")
    )

    markets: dict[str, dict] = defaultdict(lambda: {"codes": set(), "exp": 0.0, "pl": 0.0})
    market_sectors: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "codes": set(),
            "benchmarkKeys": set(),
            "benchmarkWeight": 0.0,
            "hasBenchmark": False,
            "exp": 0.0,
            "pl": 0.0,
            "rows": [],
        }
    )
    for row in positions:
        market = str(row.get("market") or "미분류")
        sector = str(row.get("sectorMid") or row.get("sectorLarge") or "미분류")
        code = str(row.get("code") or row.get("name") or "")
        exp = number(row.get("exp"))
        pl = number(row.get("pl"))
        markets[market]["codes"].add(code)
        markets[market]["exp"] += exp
        markets[market]["pl"] += pl
        market_item = market_sectors[(market, sector)]
        market_item["codes"].add(code)
        market_item["exp"] += exp
        market_item["pl"] += pl
        market_item["rows"].append(row)
        if not has_full_benchmark_sectors:
            benchmark_weight = row.get("benchmarkWeight")
            benchmark_key = str(row.get("benchmarkKey") or f"{market}|{code}")
            if benchmark_weight is not None and benchmark_key not in market_item["benchmarkKeys"]:
                market_item["benchmarkKeys"].add(benchmark_key)
                market_item["benchmarkWeight"] += number(benchmark_weight)
                market_item["hasBenchmark"] = True

    if has_full_benchmark_sectors:
        for market_name in ("코스피", "코스닥"):
            market_payload = benchmark_sectors.get(market_name)
            sector_payload = market_payload.get("mid") if isinstance(market_payload, dict) else None
            if not isinstance(sector_payload, dict):
                continue
            for sector, benchmark_item in sector_payload.items():
                item = market_sectors[(market_name, str(sector or "미분류"))]
                item["benchmarkWeight"] = number(
                    benchmark_item.get("weight") if isinstance(benchmark_item, dict) else benchmark_item
                )
                item["hasBenchmark"] = True

    market_rows = []
    expected_total = 0.0
    has_expected = False
    for name in ("코스피", "코스닥", "미분류"):
        item = markets.get(name, {"codes": set(), "exp": 0.0, "pl": 0.0})
        exp = item["exp"]
        actual_return = item["pl"] / exp * 100 if exp else None
        index_return = index_returns.get(name)
        index_return = number(index_return) if index_return is not None else None
        expected_pl = exp * index_return / 100 if index_return is not None else None
        if expected_pl is not None:
            expected_total += expected_pl
            has_expected = True
        relative_pp = actual_return - index_return if actual_return is not None and index_return is not None else None
        relative_contribution = (
            (item["pl"] - expected_pl) / total_exp * 100
            if total_exp and expected_pl is not None
            else (item["pl"] / total_exp * 100 if total_exp and name == "미분류" else None)
        )
        market_rows.append({
            "market": name,
            "stockCount": len(item["codes"]),
            "weightPct": rounded(exp / total_exp * 100 if total_exp else None),
            "actualReturnPct": rounded(actual_return),
            "indexReturnPct": rounded(index_return),
            "relativePp": rounded(relative_pp),
            "relativeAssessment": relative_assessment(relative_pp),
            "relativeDisplay": (
                f"{'Over' if relative_pp >= 0 else 'Under'} {relative_pp:+.2f}%p"
                if relative_pp is not None
                else None
            ),
            "isNearBenchmark": bool(relative_pp is not None and abs(relative_pp) <= 0.50),
            "relativeContributionPp": rounded(relative_contribution),
            "actualPlEok": rounded(item["pl"] / 100_000_000),
            "expectedPlEok": rounded(expected_pl / 100_000_000 if expected_pl is not None else 0.0),
        })

    market_sector_signals: dict[str, dict[str, list[dict]]] = {}
    for market_name in ("코스피", "코스닥"):
        market_exp = markets.get(market_name, {}).get("exp", 0.0)
        signals = []
        for (market, sector), item in market_sectors.items():
            if market != market_name or not item["hasBenchmark"]:
                continue
            portfolio_weight = item["exp"] / market_exp * 100 if market_exp else 0.0
            benchmark_weight = item["benchmarkWeight"] * 100
            active_weight = portfolio_weight - benchmark_weight
            sector_return = item["pl"] / item["exp"] * 100 if item["exp"] else None
            contribution = item["pl"] / market_exp * 100 if market_exp else None
            allocation_signal = active_weight * sector_return / 100 if sector_return is not None else None
            ranked_stocks = sorted(item["rows"], key=lambda row: abs(number(row.get("pl"))), reverse=True)
            signals.append({
                "sector": sector,
                "portfolioWeightPct": rounded(portfolio_weight),
                "benchmarkWeightPct": rounded(benchmark_weight),
                "activeWeightPp": rounded(active_weight),
                "sectorReturnPct": rounded(sector_return),
                "portfolioContributionPp": rounded(contribution),
                "allocationSignalPp": rounded(allocation_signal),
                "topStocks": [compact_position(row) for row in ranked_stocks[:3]],
            })
        support = sorted(
            (row for row in signals if (row["allocationSignalPp"] or 0) > 0),
            key=lambda row: row["allocationSignalPp"],
            reverse=True,
        )[:3]
        drag = sorted(
            (row for row in signals if (row["allocationSignalPp"] or 0) < 0),
            key=lambda row: row["allocationSignalPp"],
        )[:3]
        notable_stocks = []
        for row in positions:
            if str(row.get("market") or "미분류") != market_name or row.get("benchmarkWeight") is None:
                continue
            stock_exp = number(row.get("exp"))
            stock_return = number(row.get("changeRatePct"))
            portfolio_weight = stock_exp / market_exp * 100 if market_exp else 0.0
            benchmark_weight = number(row.get("benchmarkWeight")) * 100
            active_weight = portfolio_weight - benchmark_weight
            contribution = number(row.get("pl")) / market_exp * 100 if market_exp else 0.0
            impact_signal = active_weight * stock_return / 100
            if abs(active_weight) < 0.50 or abs(stock_return) < 1.00 or abs(contribution) < 0.01:
                continue
            notable_stocks.append({
                "name": str(row.get("name") or "미분류"),
                "portfolioWeightPct": rounded(portfolio_weight),
                "benchmarkWeightPct": rounded(benchmark_weight),
                "activeWeightPp": rounded(active_weight),
                "returnPct": rounded(stock_return),
                "contributionPp": rounded(contribution),
                "impactSignalPp": rounded(impact_signal),
            })
        support_stocks = sorted(
            (row for row in notable_stocks if (row["impactSignalPp"] or 0) > 0),
            key=lambda row: row["impactSignalPp"],
            reverse=True,
        )[:3]
        drag_stocks = sorted(
            (row for row in notable_stocks if (row["impactSignalPp"] or 0) < 0),
            key=lambda row: row["impactSignalPp"],
        )[:3]
        market_sector_signals[market_name] = {
            "support": support,
            "drag": drag,
            "supportStocks": support_stocks,
            "dragStocks": drag_stocks,
        }

    expected_return = expected_total / total_exp * 100 if total_exp and has_expected else None
    actual_return = total_pl / total_exp * 100 if total_exp else None
    relative_gap = actual_return - expected_return if actual_return is not None and expected_return is not None else None
    market_analysis = []
    for market_name in ("코스피", "코스닥"):
        performance = next(row for row in market_rows if row["market"] == market_name)
        signals = market_sector_signals.get(
            market_name,
            {"support": [], "drag": [], "supportStocks": [], "dragStocks": []},
        )
        is_under = number(performance.get("relativePp")) < 0
        is_near = bool(performance.get("isNearBenchmark"))
        primary_key = "drag" if is_under else "support"
        offset_key = "support" if is_under else "drag"
        market_analysis.append({
            "market": market_name,
            "calculationBasis": (
                "포트폴리오는 코스피 Net Exp를 100%로, BM은 KODEX 코스피 전체 구성종목을 100%로 둔 기준"
                if market_name == "코스피"
                else "포트폴리오는 코스닥 Net Exp를 100%로, BM은 KODEX 코스닥150 전체 구성비를 50% 축소하고 나머지를 미분류로 채운 기준"
            ),
            "performance": performance,
            "analysisDirection": "약세 원인" if is_under else "강세 원인",
            "sectorSignals": {
                "primary": signals[primary_key],
                "primaryStocks": signals[f"{primary_key}Stocks"],
                "offset": signals[offset_key] if is_near else [],
                "offsetStocks": signals[f"{offset_key}Stocks"] if is_near else [],
            },
        })

    return {
        "asOfDate": data.get("asOfDate"),
        "selectedFund": data.get("selectedFund"),
        "portfolio": {
            "stockCount": len({str(row.get("code") or row.get("name") or "") for row in positions}),
            "stockExpEok": rounded(total_exp / 100_000_000),
            "actualPlEok": rounded(total_pl / 100_000_000),
            "actualReturnPct": rounded(actual_return),
            "benchmarkReturnPct": rounded(expected_return),
            "relativePp": rounded(relative_gap),
        },
        "marketAnalysis": market_analysis,
        "limitations": [
            "코스피 BM 섹터 비중은 KODEX 코스피 전체 구성종목을 업종별로 합산하고 100%로 정규화함",
            "코스닥 BM 섹터 비중은 KODEX 코스닥150 전체 구성종목 비중을 50%로 축소하고 남은 비중을 미분류로 채운 약식 기준임",
            "각 시장의 포트폴리오 섹터 비중은 해당 시장 보유 종목의 Net Exp를 100%로 계산함",
            "섹터 배분 신호는 시장 내 BM 대비 비중 차이와 보유 섹터 수익률을 결합한 약식 방향성 지표",
            "섹터별 BM 자체 수익률이 없어 정밀 성과귀속으로 해석할 수 없음",
        ],
    }


def analyze_performance(data: dict) -> dict:
    key = api_key()
    if not key:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다. OpenAI_API키_설정.cmd를 먼저 실행해 주세요.")

    summary = prepare_analysis_summary(data)
    instructions = """기관투자자용 BM 대비 상대성과 분석을 자연스러운 한국어 존댓말로 작성하십시오.
모든 계산과 선별은 로컬 파이썬에서 끝났습니다. 제공된 숫자만 해석하고 재계산, 외부 추정, 뉴스, 전망, 종목 펀더멘털을 추가하지 마십시오. 섹터는 모두 중분류 기준입니다.

입력의 marketAnalysis는 시장별로 완전히 분리되어 있습니다. 코스피 문단은 market='코스피' 객체 안의 performance와 sectorSignals만 사용하고, 코스닥 문단은 market='코스닥' 객체 안의 값만 사용하십시오. 다른 시장이나 전체 portfolio의 섹터·종목·비중을 가져오거나 두 시장을 합산하지 마십시오. sectorSignals의 portfolioWeightPct와 activeWeightPp는 해당 시장의 Net Exp를 100%로 계산한 값이므로 그대로 인용하십시오.

sectorSignals.primary에는 실제 상대성과 방향과 일치하는 핵심 원인만 들어 있습니다. Under이면 약세 원인, Over이면 강세 원인이므로 두 번째 문장은 반드시 primary만 사용하십시오. sectorSignals.offset은 상대성과 절대값이 0.50%p 이하인 강보합·약보합권에서만 제공되는 반대 방향의 상쇄 요인입니다. offset이 비어 있으면 반대 방향 요인을 언급하지 마십시오.

출력 형식은 반드시 다음 구조를 지키십시오. 대괄호 표시는 그대로 출력하십시오.
[코스피]
코스피 분석 문단

[코스닥]
코스닥 분석 문단

시장별 문단 작성 규칙:
1. 첫 문장은 반드시 '포트폴리오는 코스피보다 [relativeAssessment]입니다([relativeDisplay]).' 또는 '포트폴리오는 코스닥보다 [relativeAssessment]입니다([relativeDisplay]).' 형식으로 짧게 끝내십시오. relativeDisplay는 입력값을 그대로 쓰고 부호나 Over/Under를 바꾸지 마십시오.
2. 두 번째 문장은 sectorSignals.primary에서 가장 중요한 중분류 섹터 하나를 골라 비중 차이와 섹터 수익률의 관계를 설명하십시오. 섹터 비중은 반드시 '필수-식음료 비중이 BM 대비 +8.66%p 높았으나'처럼 BM 대비라는 표현과 activeWeightPp를 함께 쓰십시오. Under이면 불리한 원인, Over이면 유리한 원인만 선택하십시오.
3. offset이 비어 있으면 세 번째 문장은 primary와 primaryStocks만 사용해 같은 방향의 원인을 보강하십시오. offset이 있으면 세 번째 문장은 반드시 offset과 offsetStocks만 사용해 반대 방향 요인이 주된 효과를 일부 만회하거나 제한했다고 설명하십시오. 이때도 섹터를 언급하면 반드시 'BM 대비 비중이 +1.93%p 높은 IT-하드웨어'처럼 BM 대비라는 표현과 activeWeightPp를 함께 쓰고, primary나 primaryStocks를 다시 쓰지 마십시오. 예: 약보합이면 '다만 BM 대비 비중이 +1.93%p 높은 IT-하드웨어의 강세와 삼성전기(+3.20%)가 약세를 일부 만회했습니다.' 강보합이면 '다만 BM 대비 비중이 +2.10%p 높은 필수-식음료의 부진과 삼양식품(-2.10%)이 상승 폭을 제한했습니다.'
4. 시장별 문단은 반드시 정확히 세 문장만 작성하십시오. 상대성과가 BM과 가깝더라도 첫 문장의 강세·약세 표현은 유지하고, 세 번째 문장에서만 반대 요인의 상쇄 효과를 설명하십시오. 네 번째 문장을 추가하지 마십시오.
5. 한 문장에는 하나의 핵심 내용만 담고, 쉼표로 여러 섹터와 종목을 길게 연결하지 마십시오. 각 문장은 가능하면 70자를 넘기지 마십시오. '불리하게 작용했습니다.'처럼 의미가 완결되는 곳에서 문장을 끝내고 다음 문장을 시작하십시오.
6. '비중이 높았고 수익률이 상승했다'면 '높은데, 수익률도 강세를 보였다'처럼 자연스럽게 연결하십시오. 비중은 높지만 수익률이 하락했다면 '높았으나, 수익률이 부진했다'를 사용하십시오. 조사와 접속사는 앞뒤 내용에 맞게 선택하십시오.

숫자와 표현 규칙:
- 양수인 수익률, 상대성과, BM 대비 비중 차이에는 반드시 + 부호를 붙이십시오. 음수에는 - 부호를 사용하십시오.
- 모든 숫자는 소수점 둘째 자리까지 반올림해 두 자리로 표시하십시오. 비중·수익률은 %, 상대성과와 BM 대비 비중 차이는 %p로 표시하십시오.
- 모든 섹터 설명에는 'BM 대비'라는 문구와 해당 섹터의 activeWeightPp를 빠짐없이 포함하십시오. 단순히 '비중이 +8.66%p 높다'라고 쓰지 마십시오.
- 특징적인 종목은 같은 시장의 primaryStocks 또는 offsetStocks에서만 고르십시오. 시장별 최대 3개만 '종목명(+3.66%)' 형식으로 표시하고, 양수 종목에도 반드시 + 부호를 붙이십시오.
- 핵심 결론과 가장 중요한 섹터명·종목명은 **굵게** 표시하되 문장 전체를 굵게 표시하지 마십시오.
- 본문에는 기여도 수치, 내부 JSON 필드명, 분석 방법론, 제목, 기준일을 쓰지 마십시오.
- 섹터 배분 신호는 약식 지표이므로 정밀 성과귀속이나 확정 원인으로 단정하지 마십시오. 데이터가 없으면 '확인 가능한 배분 요인이 없습니다.'라고만 쓰십시오."""
    request_body = json.dumps(
        {
            "model": MODEL,
            "reasoning": {"effort": "low"},
            "store": False,
            "max_output_tokens": 1600,
            "instructions": instructions,
            "input": json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
            "text": {"verbosity": "low"},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=request_body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            message = json.loads(detail).get("error", {}).get("message", detail)
        except json.JSONDecodeError:
            message = detail
        raise RuntimeError(f"OpenAI API HTTP {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI API 연결 실패: {exc.reason}") from exc

    if payload.get("status") == "incomplete":
        reason = (payload.get("incomplete_details") or {}).get("reason", "unknown")
        raise RuntimeError(f"AI 분석 응답이 완성되기 전에 종료되었습니다: {reason}")

    analysis = extract_output_text(payload)
    if not analysis:
        raise RuntimeError("OpenAI API 응답에 분석 문장이 없습니다.")
    return {"analysis": analysis, "model": payload.get("model", MODEL), "usage": payload.get("usage", {})}


def analyze_period_performance(summary: dict) -> dict:
    key = api_key()
    if not key:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다. OpenAI_API키_설정.cmd를 먼저 실행해 주세요.")
    compact = {
        "startDate": summary.get("startDate"),
        "endDate": summary.get("endDate"),
        "selectedFund": summary.get("selectedFund"),
        "snapshotCount": summary.get("snapshotCount"),
        "marketRows": summary.get("marketRows", []),
        "sectorRows": summary.get("sectorRows", [])[:16],
        "stockRows": summary.get("stockRows", [])[:20],
    }
    instructions = """기관투자자용 기간별 BM 상대성과 분석을 자연스러운 한국어 존댓말로 작성하십시오.
입력 수치는 Python에서 계산됐으므로 재계산하거나 외부 뉴스·전망·펀더멘털을 추가하지 마십시오.
코스피와 코스닥을 분리하여 각각 한 문단으로 작성하십시오. 각 문단은 3~4문장으로 제한하십시오.
첫 문장에는 기간 누적 포트폴리오 수익률, BM 수익률, 상대성과를 명확히 쓰십시오.
이후에는 같은 시장의 sectorRows와 stockRows만 이용해 강세 또는 약세의 핵심 원인을 설명하십시오.
섹터는 평균 포트폴리오 비중, 평균 BM 비중, BM 대비 비중 차이와 기간 기여도를 함께 고려하십시오.
종목은 기간 기여도가 특징적인 경우에만 시장별 최대 3개를 언급하십시오.
숫자는 소수점 둘째 자리까지 표시하고 양수에는 + 부호를 붙이십시오.
snapshotCount가 적으면 분석 첫머리에 데이터 커버리지가 제한적임을 짧게 알리십시오.
출력은 반드시 [코스피] 문단, 빈 줄, [코스닥] 문단 순서로 작성하십시오.
중요한 결론과 핵심 섹터·종목명은 **굵게** 표시하십시오."""
    request_body = json.dumps(
        {
            "model": MODEL,
            "reasoning": {"effort": "low"},
            "store": False,
            "max_output_tokens": 1800,
            "instructions": instructions,
            "input": json.dumps(compact, ensure_ascii=False, separators=(",", ":")),
            "text": {"verbosity": "low"},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=request_body,
        method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            message = json.loads(detail).get("error", {}).get("message", detail)
        except json.JSONDecodeError:
            message = detail
        raise RuntimeError(f"OpenAI API HTTP {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI API 연결 실패: {exc.reason}") from exc
    if payload.get("status") == "incomplete":
        reason = (payload.get("incomplete_details") or {}).get("reason", "unknown")
        raise RuntimeError(f"기간 AI 분석 응답이 완성되기 전에 종료되었습니다: {reason}")
    analysis = extract_output_text(payload)
    if not analysis:
        raise RuntimeError("OpenAI API 응답에 기간 분석 문장이 없습니다.")
    return {"analysis": analysis, "model": payload.get("model", MODEL), "usage": payload.get("usage", {})}


def fund_analysis_value(value: object, suffix: str = "", signed: bool = False) -> str:
    numeric = number(value)
    prefix = "+" if signed and numeric > 0 else ""
    return f"{prefix}{numeric:.2f}{suffix}"


def fund_analysis_named_values(rows: list[dict], value_key: str, suffix: str, limit: int = 3) -> str:
    values = []
    for row in rows[:limit]:
        name = str(row.get("name") or "미분류")
        values.append(f"**{name}** {fund_analysis_value(row.get(value_key), suffix, signed=True)}")
    return ", ".join(values)


def build_fund_analysis_text(summary: dict) -> str:
    performance = summary.get("performance") or {}
    fund = performance.get("fund") or {}
    benchmark = performance.get("benchmark") or {}
    benchmark_name = str(summary.get("benchmark") or "BM")
    relative = number(performance.get("relativePp"))
    relative_label = "상회" if relative > 0 else "하회" if relative < 0 else "동일"
    performance_lines = [
        f"펀드 기간수익률은 **{fund_analysis_value(fund.get('periodReturnPct'), '%', True)}**로, "
        f"{benchmark_name} 수익률 {fund_analysis_value(benchmark.get('periodReturnPct'), '%', True)} 대비 "
        f"**{fund_analysis_value(relative, '%p', True)} {relative_label}**했습니다."
    ]
    best = performance.get("bestMonths") or []
    worst = performance.get("worstMonths") or []
    month_parts = []
    if best:
        month_parts.append("강세 구간은 " + ", ".join(
            f"**{row.get('month')}({fund_analysis_value(row.get('returnPct'), '%', True)})**" for row in best
        ))
    if worst:
        month_parts.append("약세 구간은 " + ", ".join(
            f"**{row.get('month')}({fund_analysis_value(row.get('returnPct'), '%', True)})**" for row in worst
        ))
    if month_parts:
        performance_lines.append("이며, ".join(month_parts) + "입니다.")
    performance_lines.append(
        f"연환산 변동성은 {fund_analysis_value(fund.get('annualVolatilityPct'), '%')}이고 "
        f"Sharpe는 {fund_analysis_value(fund.get('sharpe'))}, 최대낙폭은 {fund_analysis_value(fund.get('mddPct'), '%')}입니다."
    )

    style = summary.get("style") or {}
    markets = style.get("markets") or []
    sectors = style.get("sectors") or []
    market_text = ", ".join(
        f"**{row.get('name')}** {fund_analysis_value(row.get('weightPct'), '%')}" for row in markets[:2]
    ) or "시장 정보 부족"
    sector_text = ", ".join(
        f"**{row.get('name')}** {fund_analysis_value(row.get('weightPct'), '%')}" for row in sectors[:3]
    ) or "섹터 정보 부족"
    style_lines = [
        f"시장 비중은 {market_text}이며, 주요 섹터는 {sector_text}입니다.",
        f"상위 1개 종목 비중은 {fund_analysis_value(style.get('top1WeightPct'), '%')}, 상위 5개는 "
        f"{fund_analysis_value(style.get('top5WeightPct'), '%')}이고 실질 분산 종목 수는 "
        f"{number(style.get('effectiveStockCount')):.1f}개입니다.",
        f"연환산 추정 회전율은 {fund_analysis_value(style.get('annualizedTurnoverPct'), '%')}, "
        f"베타는 {fund_analysis_value(style.get('beta'))}, 변동성비율은 "
        f"{fund_analysis_value(style.get('volatilityRatio'))}으로 **{style.get('profile') or '판단 유보'} 성향**입니다.",
    ]

    changes = summary.get("portfolioChanges") or {}
    buy_text = fund_analysis_named_values(changes.get("netBuys") or [], "netEok", "억원")
    sell_text = fund_analysis_named_values(changes.get("netSells") or [], "netEok", "억원")
    change_lines = []
    if buy_text:
        change_lines.append(f"주요 순매수는 {buy_text}입니다.")
    if sell_text:
        change_lines.append(f"주요 순매도는 {sell_text}입니다.")
    entrants = [str(row.get("name") or "") for row in (changes.get("newEntryCandidates") or [])[:3] if row.get("name")]
    exits = [str(row.get("name") or "") for row in (changes.get("fullExitCandidates") or [])[:3] if row.get("name")]
    candidate_parts = []
    if entrants:
        candidate_parts.append("신규 편입 후보는 " + ", ".join(f"**{name}**" for name in entrants))
    if exits:
        candidate_parts.append("전량 매도 후보는 " + ", ".join(f"**{name}**" for name in exits))
    if candidate_parts:
        change_lines.append("이며, ".join(candidate_parts) + "입니다.")
    coverage = summary.get("coverage") or {}
    requested_start = str((summary.get("period") or {}).get("requestedStart") or "")
    trade_start = str(coverage.get("tradeDataStart") or "")
    trade_end = str(coverage.get("tradeDataEnd") or "")
    if trade_start and requested_start and trade_start > requested_start:
        change_lines.append(f"가용 매매 데이터가 **{trade_start}~{trade_end}**로 제한되어 이전 변화는 포함되지 않았습니다.")
    if not change_lines:
        change_lines.append("선택 기간에 확인 가능한 주요 매매 변화가 없습니다.")

    contribution = summary.get("contribution") or {}
    contribution_lines = []
    for label, rows in (("성과 기여 상위", contribution.get("contributors") or []), ("성과 훼손 상위", contribution.get("detractors") or [])):
        values = []
        for row in rows[:3]:
            values.append(
                f"**{row.get('name') or '미분류'}** "
                f"{fund_analysis_value(row.get('returnPct'), '%', True)}, "
                f"{fund_analysis_value(row.get('profitEok'), '억원', True)}"
            )
        if values:
            contribution_lines.append(f"{label} 종목은 " + ", ".join(values) + "입니다.")
    contribution_lines.append("기여도는 현재 보유 포지션의 누적 평가손익 기준이며 선택 기간의 정밀 성과귀속은 아닙니다.")

    return "\n\n".join([
        "[성과 요약]\n" + " ".join(performance_lines),
        "[운용 스타일]\n" + " ".join(style_lines),
        "[포트폴리오 변화]\n" + " ".join(change_lines),
        "[성과 기여]\n" + " ".join(contribution_lines),
    ])


def analyze_fund(data: dict) -> dict:
    summary = prepare_fund_analysis_summary(data)
    return {
        "analysis": build_fund_analysis_text(summary),
        "model": "Python 엔진",
        "usage": {},
        "summary": summary,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/health":
            self.send_json(HTTPStatus.OK, {"ok": True, "apiKeyConfigured": bool(api_key()), "model": MODEL})
            return
        if parsed.path == "/api/fund-return-series":
            try:
                query = urllib.parse.parse_qs(parsed.query)
                fund_name = str(query.get("fund", [""])[0])
                self.send_json(HTTPStatus.OK, load_fund_return_series(fund_name))
            except ValueError as exc:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            except RuntimeError as exc:
                self.send_json(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
            except Exception as exc:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"기준가 조회 오류: {exc}"})
            return
        if parsed.path == "/api/performance-period":
            try:
                query = urllib.parse.parse_qs(parsed.query)
                fund_scope = str(query.get("fundScope", [""])[0])
                start_date = str(query.get("start", [""])[0])
                end_date = str(query.get("end", [""])[0])
                rows = load_performance_snapshots(fund_scope, start_date, end_date)
                self.send_json(HTTPStatus.OK, prepare_period_summary(rows, start_date, end_date, fund_scope))
            except ValueError as exc:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except RuntimeError as exc:
                self.send_json(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
            except Exception as exc:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"기간분석 조회 오류: {exc}"})
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path not in {"/api/performance-analysis", "/api/performance-snapshot", "/api/period-performance-analysis", "/api/fund-analysis"}:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "지원하지 않는 API 경로입니다."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_REQUEST_BYTES:
                raise ValueError("요청 데이터 크기가 올바르지 않습니다.")
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("성과분석 데이터는 JSON 객체여야 합니다.")
            if self.path == "/api/fund-analysis":
                self.send_json(HTTPStatus.OK, analyze_fund(data))
            elif self.path == "/api/performance-snapshot":
                self.send_json(HTTPStatus.OK, save_performance_snapshot(data))
            elif self.path == "/api/period-performance-analysis":
                fund_scope = str(data.get("fundScope") or "")
                start_date = str(data.get("start") or "")
                end_date = str(data.get("end") or "")
                rows = load_performance_snapshots(fund_scope, start_date, end_date)
                summary = prepare_period_summary(rows, start_date, end_date, fund_scope)
                if not rows:
                    raise ValueError("선택한 기간에 저장된 마감 스냅샷이 없습니다.")
                result = analyze_period_performance(summary)
                self.send_json(HTTPStatus.OK, {**result, "summary": summary})
            else:
                self.send_json(HTTPStatus.OK, analyze_performance(data))
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except RuntimeError as exc:
            self.send_json(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
        except Exception as exc:
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"로컬 분석 서버 오류: {exc}"})


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
    print(f"Stock dashboard: http://{HOST}:{PORT}/fund_dashboard.html")
    print(f"OpenAI model: {MODEL}")
    print(f"OPENAI_API_KEY: {'configured' if api_key() else 'not configured'}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

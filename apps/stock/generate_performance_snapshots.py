from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any

from historical_performance import build_historical_snapshots


DEFAULT_SUPABASE_URL = "https://esqakvzvchcunhzjlyry.supabase.co"
ALL_FUNDS = "전체 펀드"


def service_role_key() -> str:
    return (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY") or "").strip()


def supabase_url() -> str:
    return (os.getenv("SUPABASE_URL") or DEFAULT_SUPABASE_URL).rstrip("/")


def supabase_get(path: str) -> list[dict[str, Any]]:
    key = service_role_key()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required.")
    request = urllib.request.Request(
        f"{supabase_url()}/rest/v1/{path}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8") or "[]")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase GET failed ({exc.code}): {detail[:1000]}") from exc
    return payload if isinstance(payload, list) else []


def supabase_upsert(table: str, rows: list[dict[str, Any]], conflict: str) -> list[dict[str, Any]]:
    if table not in {"kiwoom_daily_prices", "stock_performance_snapshots"}:
        raise ValueError(f"Unsupported upsert table: {table}")
    if not rows:
        return []
    key = service_role_key()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required.")
    query = urllib.parse.urlencode({"on_conflict": conflict}, safe=",")
    saved: list[dict[str, Any]] = []
    batch_size = 250 if table == "kiwoom_daily_prices" else 10
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        request = urllib.request.Request(
            f"{supabase_url()}/rest/v1/{table}?{query}",
            data=json.dumps(batch, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            method="POST",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=representation",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                payload = json.loads(response.read().decode("utf-8") or "[]")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Supabase upsert failed ({exc.code}): {detail[:1000]}") from exc
        if isinstance(payload, list):
            saved.extend(payload)
    return saved


def daily_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    markets = []
    positions = payload.get("positions") if isinstance(payload.get("positions"), list) else []
    indices = payload.get("marketIndexReturns") if isinstance(payload.get("marketIndexReturns"), dict) else {}
    for market in ("코스피", "코스닥"):
        rows = [row for row in positions if str(row.get("market") or "") == market]
        exposure = sum(float(row.get("exp") or 0) for row in rows)
        profit = sum(float(row.get("pl") or 0) for row in rows)
        benchmark = indices.get(market)
        if not exposure:
            continue
        actual = profit / exposure * 100
        benchmark_number = float(benchmark) if benchmark is not None else None
        markets.append({
            "market": market,
            "actualReturnPct": round(actual, 3),
            "benchmarkReturnPct": round(benchmark_number, 3) if benchmark_number is not None else None,
            "relativePp": round(actual - benchmark_number, 3) if benchmark_number is not None else None,
        })
    return {"title": "일별 성과 요약", "analysis": "", "model": "Python 엔진", "markets": markets}


def split_fund_records(records: list[dict[str, Any]], environment: str) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for source in records:
        payload = source.get("payload") if isinstance(source.get("payload"), dict) else {}
        positions = payload.get("positions") if isinstance(payload.get("positions"), list) else []
        fund_names = sorted({str(row.get("fund") or "").strip() for row in positions if str(row.get("fund") or "").strip()})
        # The all-funds row is written last and acts as a completion marker for the day.
        for fund_scope in [*fund_names, ALL_FUNDS]:
            fund_payload = deepcopy(payload)
            if fund_scope != ALL_FUNDS:
                fund_payload["positions"] = [row for row in positions if str(row.get("fund") or "").strip() == fund_scope]
            fund_payload["selectedFund"] = fund_scope
            fund_payload["dailyAnalysis"] = daily_analysis(fund_payload)
            output.append({
                **{key: value for key, value in source.items() if key != "payload"},
                "fund_scope": fund_scope,
                "environment": environment,
                "calculation_version": "historical-close-v6",
                "payload": fund_payload,
            })
    return output


def snapshot_complete(performance_date: str, environment: str) -> bool:
    query = urllib.parse.urlencode({
        "select": "performance_date",
        "performance_date": f"eq.{performance_date}",
        "fund_scope": f"eq.{ALL_FUNDS}",
        "environment": f"eq.{environment}",
        "calculation_version": "eq.historical-close-v6",
        "limit": "1",
    }, safe=".,")
    return bool(supabase_get(f"stock_performance_snapshots?{query}"))


def generate_snapshots(start_date: str, end_date: str, environment: str, *, skip_completed: bool = True) -> list[dict[str, Any]]:
    if skip_completed and start_date == end_date and snapshot_complete(start_date, environment):
        print(f"performance snapshot already complete: date={start_date}, environment={environment}")
        return []
    base_records = build_historical_snapshots(
        supabase_get,
        supabase_upsert,
        start_date,
        end_date,
        ALL_FUNDS,
    )
    records = split_fund_records(base_records, environment)
    if not records:
        raise RuntimeError(f"No completed market-day snapshot could be built for {start_date}..{end_date}.")
    saved = supabase_upsert(
        "stock_performance_snapshots",
        records,
        "performance_date,fund_scope,environment",
    )
    dates = sorted({str(row.get("performance_date") or "") for row in records})
    funds = {str(row.get("fund_scope") or "") for row in records}
    print(f"performance snapshots upserted: dates={','.join(dates)}, funds={len(funds)}, rows={len(records)}")
    return saved or records


def main() -> None:
    parser = argparse.ArgumentParser(description="Build immutable daily stock performance snapshots.")
    parser.add_argument("--start", required=True, help="First performance date (YYYY-MM-DD).")
    parser.add_argument("--end", help="Last performance date; defaults to --start.")
    parser.add_argument("--environment", choices=("production", "local_test"), default="production")
    parser.add_argument("--output", type=Path, help="Optional JSON audit output.")
    parser.add_argument("--force", action="store_true", help="Rebuild a completed single-day snapshot.")
    args = parser.parse_args()
    end_date = args.end or args.start
    saved = generate_snapshots(args.start, end_date, args.environment, skip_completed=not args.force)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

"""Persist Kiwoom daily prices and calculate mezzanine daily/10-day deltas."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parents[1]
STOCK_DIR = REPOSITORY_ROOT / "apps" / "stock"
if str(STOCK_DIR) not in sys.path:
    sys.path.insert(0, str(STOCK_DIR))

from fetch_kiwoom_quotes import (  # noqa: E402
    DEFAULT_HOST,
    load_credentials,
    post_json,
    request_token,
)


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


def text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    result = str(value).strip()
    return result[:-2] if result.endswith(".0") and result[:-2].isdigit() else result


def number(value: object) -> float | None:
    try:
        return abs(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


class SupabaseRest:
    def __init__(self) -> None:
        self.base_url = f"{required_env('SUPABASE_URL').rstrip('/')}/rest/v1"
        key = required_env("SUPABASE_SERVICE_ROLE_KEY")
        self.headers = {"apikey": key, "Content-Type": "application/json"}
        if key.count(".") == 2:
            self.headers["Authorization"] = f"Bearer {key}"

    def request(self, method: str, path: str, body: Any = None, prefer: str | None = None) -> Any:
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(f"{self.base_url}/{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Supabase HTTP {exc.code}: {detail[:1000]}") from exc
        return json.loads(payload) if payload else None

    def get_all(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode(params, safe=".,()")
        result = []
        for start in range(0, 1_000_000, 1000):
            page_params = f"{query}&offset={start}&limit=1000"
            page = self.request("GET", f"{table}?{page_params}") or []
            result.extend(page)
            if len(page) < 1000:
                return result
        raise RuntimeError(f"Pagination limit exceeded: {table}")

    def upsert(self, table: str, rows: list[dict[str, Any]], conflict: str) -> None:
        for start in range(0, len(rows), 500):
            self.request(
                "POST",
                f"{table}?on_conflict={urllib.parse.quote(conflict)}",
                rows[start : start + 500],
                "resolution=merge-duplicates,return=minimal",
            )


def load_instrument_map() -> tuple[dict[str, str], dict[str, str]]:
    frame = pd.read_excel(ROOT / "종목정보.xlsx", dtype=object).fillna("")
    underlying_by_security = {}
    name_by_underlying = {}
    for _, row in frame.iterrows():
        security_code = text(row.get("KR코드"))
        underlying_code = text(row.get("교환코드") or row.get("발행코드")).zfill(6)
        if not security_code or not underlying_code:
            continue
        underlying_by_security[security_code] = underlying_code
        name_by_underlying.setdefault(underlying_code, text(row.get("교환대상명") or row.get("발행사명")))
    return underlying_by_security, name_by_underlying


def fetch_daily_prices(host: str, token: str, code: str, base_date: date, timeout: float) -> list[dict]:
    data = post_json(
        host,
        "/api/dostk/chart",
        {"stk_cd": code, "base_dt": base_date.strftime("%Y%m%d"), "upd_stkpc_tp": "1"},
        headers={
            "authorization": f"Bearer {token}",
            "api-id": "ka10081",
            "cont-yn": "N",
            "next-key": "",
        },
        timeout=timeout,
    )
    rows = data.get("stk_dt_pole_chart_qry") or data.get("stk_dt_chart_qry") or []
    return rows if isinstance(rows, list) else []


def normalize_daily_prices(code: str, name: str, rows: list[dict], keep_days: int) -> list[dict]:
    values = []
    for row in rows:
        raw_date = text(row.get("dt") or row.get("date"))[:8]
        close_price = number(row.get("cur_prc") or row.get("close_pric"))
        if len(raw_date) != 8 or close_price in (None, 0):
            continue
        values.append({"business_date": datetime.strptime(raw_date, "%Y%m%d").date(), "close_price": close_price})
    values.sort(key=lambda item: item["business_date"])
    output = []
    for index, item in enumerate(values[-(keep_days + 1) :]):
        prior = values[-(keep_days + 1) :][index - 1]["close_price"] if index else None
        output.append({
            "business_date": item["business_date"].isoformat(),
            "code": code,
            "name": name,
            "close_price": item["close_price"],
            "change_rate": item["close_price"] / prior - 1.0 if prior else None,
            "source": "ka10081",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    return output[-keep_days:]


def read_current_nav() -> tuple[str, list[dict]]:
    frame = pd.read_excel(ROOT / "메자닌 기준가.xlsx", sheet_name="Data", header=1).dropna(how="all")
    frame["_business_date"] = pd.to_datetime(frame["거래일"], errors="coerce").dt.date
    frame = frame[frame["_business_date"].notna()]
    business_date = frame["_business_date"].max().isoformat()
    rows = []
    for _, row in frame.iterrows():
        security_code = text(row.get("상품코드"))
        nav = number(row.get("기준가"))
        if not security_code or nav is None:
            continue
        rows.append({
            "business_date": row["_business_date"].isoformat(),
            "security_code": security_code,
            "security_name": text(row.get("종목명")),
            "fund_name": text(row.get("펀드명")),
            "nav": nav,
            "source": "kfr_daily",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    return business_date, rows


def upsert_current_quotes(client: SupabaseRest, business_date: str, names: dict[str, str]) -> int:
    path = STOCK_DIR / "kiwoom_quotes.json"
    if not path.exists():
        return 0
    existing_daily = client.get_all("kiwoom_daily_prices", {
        "select": "code,source,change_rate",
        "business_date": f"eq.{business_date}",
    })
    protected_codes = {
        row["code"]
        for row in existing_daily
        if row.get("source") == "ka10081" and row.get("change_rate") not in (None, "", "0", "0.0", 0, 0.0)
    }
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows_by_code: dict[str, dict[str, Any]] = {}
    for source_code, quote in (payload.get("stocks") or {}).items():
        rest_code = text(quote.get("kiwoom_rest_code") or source_code).zfill(6)
        close_price = number(quote.get("price"))
        change_rate = quote.get("change_rate")
        if rest_code in protected_codes:
            continue
        if rest_code not in names or close_price in (None, 0) or change_rate in (None, ""):
            continue
        numeric_change = float(change_rate)
        if numeric_change == 0:
            continue
        rows_by_code[rest_code] = {
            "business_date": business_date,
            "code": rest_code,
            "name": names.get(rest_code, text(quote.get("name"))),
            "close_price": close_price,
            "change_rate": numeric_change / 100.0,
            "source": "ka10095",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    rows = list(rows_by_code.values())
    client.upsert("kiwoom_daily_prices", rows, "business_date,code")
    return len(rows)


def recalculate_deltas(client: SupabaseRest, underlying_by_security: dict[str, str], current_nav: list[dict]) -> int:
    history = client.get_all("mezzanine_delta_history", {
        "select": "business_date,security_code,security_name,fund_name,nav,source,source_snapshot_id",
        "order": "security_code.asc,fund_name.asc,business_date.asc",
    })
    by_key = {(row["business_date"], row["security_code"], row["fund_name"]): row for row in history}
    for row in current_nav:
        by_key[(row["business_date"], row["security_code"], row["fund_name"])] = row
    prices = client.get_all("kiwoom_daily_prices", {
        "select": "business_date,code,change_rate",
        "order": "business_date.asc",
    })
    change_by_key = {(row["business_date"], row["code"]): row.get("change_rate") for row in prices}
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in by_key.values():
        grouped.setdefault((row["security_code"], row["fund_name"]), []).append(row)
    output = []
    for (security_code, _), rows in grouped.items():
        rows.sort(key=lambda item: item["business_date"])
        prior_nav = None
        underlying_code = underlying_by_security.get(security_code, "")
        for row in rows:
            nav = float(row["nav"])
            nav_return = nav / prior_nav - 1.0 if prior_nav else None
            underlying_change = change_by_key.get((row["business_date"], underlying_code))
            daily_delta = (
                nav_return / float(underlying_change)
                if nav_return is not None and underlying_change not in (None, 0, 0.0)
                else None
            )
            output.append({
                "business_date": row["business_date"],
                "security_code": row["security_code"],
                "security_name": row.get("security_name", ""),
                "fund_name": row.get("fund_name", ""),
                "nav": nav,
                "nav_return": nav_return,
                "underlying_change_rate": underlying_change,
                "daily_delta": daily_delta,
                "is_valid": daily_delta is not None and 0 <= daily_delta <= 1,
                "source": row["source"],
                "source_snapshot_id": row.get("source_snapshot_id"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            prior_nav = nav
    client.upsert("mezzanine_delta_history", output, "business_date,security_code,fund_name")
    DELTA_HISTORY_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(output)


def run_update(
    *,
    host: str,
    token: str | None = None,
    history_days: int = 30,
    request_delay: float = 0.7,
    timeout: float = 20.0,
    skip_backfill: bool = False,
    use_current_quotes: bool = False,
) -> None:
    client = SupabaseRest()
    underlying_by_security, names = load_instrument_map()
    business_date, current_nav = read_current_nav()

    if not skip_backfill:
        cutoff = (date.fromisoformat(business_date) - timedelta(days=history_days * 2)).isoformat()
        existing = client.get_all("kiwoom_daily_prices", {
            "select": "code,business_date,source,change_rate",
            "business_date": f"gte.{cutoff}",
        })
        counts: dict[str, int] = {}
        valid_daily: set[tuple[str, str]] = set()
        for row in existing:
            if row.get("source") == "ka10081" and row.get("change_rate") not in (None, "", "0", "0.0", 0, 0.0):
                counts[row["code"]] = counts.get(row["code"], 0) + 1
                valid_daily.add((row["code"], row["business_date"]))
        missing = [
            code for code in sorted(names)
            if counts.get(code, 0) < 10 or (code, business_date) not in valid_daily
        ]
        if missing:
            if not token:
                appkey, secretkey = load_credentials()
                if not appkey or not secretkey:
                    raise RuntimeError("KIWOOM_APPKEY and KIWOOM_SECRETKEY are required for backfill")
                token = request_token(host, appkey, secretkey, timeout)
            for index, code_value in enumerate(missing, start=1):
                rows = fetch_daily_prices(host, token, code_value, date.fromisoformat(business_date), timeout)
                normalized = normalize_daily_prices(code_value, names[code_value], rows, history_days)
                client.upsert("kiwoom_daily_prices", normalized, "business_date,code")
                print(f"ka10081 {index}/{len(missing)}: {code_value}, rows={len(normalized)}")
                if index < len(missing):
                    time.sleep(max(0.2, request_delay))

    quote_rows = upsert_current_quotes(client, business_date, names) if use_current_quotes else 0
    delta_rows = recalculate_deltas(client, underlying_by_security, current_nav)
    print(f"delta update complete: quote_rows={quote_rows}, delta_rows={delta_rows}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("KIWOOM_HOST", DEFAULT_HOST))
    parser.add_argument("--history-days", type=int, default=30)
    parser.add_argument("--request-delay", type=float, default=0.7)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--skip-backfill", action="store_true")
    parser.add_argument("--use-current-quotes", action="store_true")
    args = parser.parse_args()
    run_update(
        host=args.host,
        history_days=args.history_days,
        request_delay=args.request_delay,
        timeout=args.timeout,
        skip_backfill=args.skip_backfill,
        use_current_quotes=args.use_current_quotes,
    )


if __name__ == "__main__":
    main()

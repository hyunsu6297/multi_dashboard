# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd

from build_fund_dashboard import (
    INPUTS,
    build_dashboard,
    is_equity_related,
    normalize_code,
    parse_float,
    read_inputs,
)


BASE_DIR = Path(__file__).resolve().parent
OUTPUT = BASE_DIR / "kiwoom_quotes.json"
DERIVATIVE_MAP_PATH = BASE_DIR / "kiwoom_derivative_code_map.json"
OPENAPI_STOCK_FUTURE_CODE_PATH = Path("C:/OpenAPI/data/sfcode.dat")
DEFAULT_HOST = "https://api.kiwoom.com"
DEFAULT_CYCLE_SECONDS = 20.0
DEFAULT_BATCH_SIZE = 80
KOSPI200_PROXY_CODE = "069500"
KOSDAQ150_PROXY_CODE = "229200"

COL_FUND_CODE = "\ud380\ub4dc\ucf54\ub4dc"
COL_LOOKUP_FUND_CODE = "\uc870\ud68c\ud380\ub4dc\ucf54\ub4dc"
COL_ASSOC_FUND_CODE = "\ud611\ud68c\ud380\ub4dc\ucf54\ub4dc"
COL_ASSET = "\uc790\uc0b0\uad70"
COL_ITEM_CODE = "\uc885\ubaa9\ucf54\ub4dc"
COL_ITEM_NAME = "\uc885\ubaa9\uba85"
SHEET_INVESTMENT = "\ud22c\uc790\uc8fc\uc2dd"
SHEET_PRODUCT = "\uc0c1\ud488\uc8fc\uc2dd"


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig").strip()


def first_existing(pattern: str) -> Path | None:
    return next(iter(sorted(BASE_DIR.glob(pattern))), None)


def load_credentials() -> tuple[str | None, str | None]:
    appkey = os.getenv("KIWOOM_APPKEY") or os.getenv("KIWOOM_API_KEY")
    secretkey = os.getenv("KIWOOM_SECRETKEY") or os.getenv("KIWOOM_API_SECRET")
    if not appkey:
        appkey_path = first_existing("*_appkey.txt")
        if appkey_path:
            appkey = read_text_file(appkey_path)
    if not secretkey:
        secretkey_path = first_existing("*_secretkey.txt")
        if secretkey_path:
            secretkey = read_text_file(secretkey_path)
    return appkey, secretkey


def post_json(
    host: str,
    endpoint: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    request = urllib.request.Request(
        host.rstrip("/") + endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json;charset=UTF-8", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON response: {body[:500]}") from exc
    return parsed if isinstance(parsed, dict) else {"response": parsed}


def request_token(host: str, appkey: str, secretkey: str, timeout: float) -> str:
    data = post_json(
        host,
        "/oauth2/token",
        {"grant_type": "client_credentials", "appkey": appkey, "secretkey": secretkey},
        timeout=timeout,
    )
    token = data.get("token") or data.get("access_token")
    if not token:
        raise RuntimeError(f"Token request failed: {data.get('return_msg') or data}")
    return str(token)


def load_derivative_code_map() -> dict[str, str]:
    if not DERIVATIVE_MAP_PATH.exists():
        return {}
    data = json.loads(DERIVATIVE_MAP_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"{DERIVATIVE_MAP_PATH.name} must be a JSON object.")
    return {normalize_code(k): str(v).strip() for k, v in data.items() if str(v).strip()}


def load_stock_future_proxy_map() -> dict[str, str]:
    if not OPENAPI_STOCK_FUTURE_CODE_PATH.exists():
        return {}
    try:
        text = OPENAPI_STOCK_FUTURE_CODE_PATH.read_bytes().decode("cp949", errors="ignore")
    except Exception:
        return {}
    proxy_map: dict[str, str] = {}
    pattern = re.compile(r"(1[A-Z0-9]{2})W[0-9C]{4}.{0,220}?(KR7\d{9})")
    for match in pattern.finditer(text):
        base_key = match.group(1)[1:]
        proxy_map.setdefault(base_key, normalize_code(match.group(2)))
    return proxy_map


def is_derivative_code(code: str) -> bool:
    return code.startswith("KR4")


def is_preferred_name(name: str) -> bool:
    compact = str(name or "").replace(" ", "")
    return compact.endswith("우") or "우B" in compact or "우C" in compact or "우(" in compact


def kiwoom_rest_code(code: str, derivative_map: dict[str, str], name: str = "") -> str | None:
    code = normalize_code(code)
    if is_derivative_code(code):
        return derivative_map.get(code)
    if len(code) >= 9 and code.startswith("KR7"):
        return code[3:9]
    if code.isdigit() and len(code) == 6 and is_preferred_name(name):
        if "2우" in str(name).replace(" ", "") and code.endswith("2"):
            return code[:5] + "7"
        if code.endswith("1"):
            return code[:5] + "5"
    return code


def derivative_proxy_code(code: str, name: str, stock_future_proxy_map: dict[str, str]) -> str | None:
    code = normalize_code(code)
    if not is_derivative_code(code):
        return None
    clean_name = str(name or "").replace(" ", "")
    if code.startswith(("KR4B", "KR4C")) or "옵션" in clean_name:
        return None
    if code.startswith(("KR4A01", "KR4A05")) or "코스피200" in clean_name or "미니코스피200" in clean_name:
        return KOSPI200_PROXY_CODE
    if code.startswith("KR4A06") or "코스닥150" in clean_name:
        return KOSDAQ150_PROXY_CODE
    if "개별선물" in clean_name or re.search(r"선물\d{4}", clean_name) or (code.startswith("KR4A") and code[4:6] not in {"01", "05", "06"}):
        base_key = code[4:6]
        return stock_future_proxy_map.get(base_key)
    return None


def value_from(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def normalize_quote(data: dict[str, Any], fallback_name: str = "") -> dict[str, float | str | None]:
    name = value_from(data, "stk_nm", "name") or fallback_name
    price = value_from(data, "cur_prc", "close_pric", "price")
    change_rate = value_from(data, "flu_rt", "change_rate")
    return {
        "name": str(name).strip(),
        "price": abs(parse_float(price, 0.0) or 0.0),
        "change_rate": parse_float(change_rate, None),
    }


def collect_codes() -> dict[str, str]:
    codes: dict[str, str] = {}
    funds, _, holdings = read_inputs()
    fund_codes = set(funds[COL_FUND_CODE].map(normalize_code))
    fund_code_col = COL_LOOKUP_FUND_CODE if COL_LOOKUP_FUND_CODE in holdings.columns else COL_ASSOC_FUND_CODE
    holdings = holdings[holdings[fund_code_col].map(normalize_code).isin(fund_codes)]
    holdings = holdings[is_equity_related(holdings, COL_ASSET)]
    for _, row in holdings.iterrows():
        code = normalize_code(row.get(COL_ITEM_CODE))
        name = str(row.get(COL_ITEM_NAME) or code).strip()
        if code:
            codes.setdefault(code, name)

    if INPUTS["direct_stocks"].exists():
        for sheet_name in (SHEET_INVESTMENT, SHEET_PRODUCT):
            try:
                direct = pd.read_excel(INPUTS["direct_stocks"], sheet_name=sheet_name).dropna(how="all")
            except Exception:
                continue
            for _, row in direct.iterrows():
                code = normalize_code(row.get(COL_ITEM_CODE))
                name = str(row.get(COL_ITEM_NAME) or code).strip()
                if code:
                    codes.setdefault(code, name)
    return codes


def chunks(items: list[tuple[str, str, str]], size: int) -> list[list[tuple[str, str, str]]]:
    return [items[idx : idx + size] for idx in range(0, len(items), size)]


def fetch_quote_batch(host: str, token: str, rest_codes: list[str], timeout: float) -> list[dict[str, Any]]:
    data = post_json(
        host,
        "/api/dostk/stkinfo",
        {"stk_cd": "|".join(rest_codes)},
        headers={
            "authorization": f"Bearer {token}",
            "api-id": "ka10095",
            "cont-yn": "N",
            "next-key": "0",
        },
        timeout=timeout,
    )
    rows = data.get("atn_stk_infr", [])
    return rows if isinstance(rows, list) else []


def load_previous_quotes(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def fetch_all_quotes(
    host: str,
    token: str,
    codes: dict[str, str],
    batch_size: int,
    timeout: float,
    output: Path,
    limit: int | None = None,
    only_code: str | None = None,
) -> dict[str, Any]:
    derivative_map = load_derivative_code_map()
    stock_future_proxy_map = load_stock_future_proxy_map()
    if only_code:
        code = normalize_code(only_code)
        codes = {code: codes.get(code, code)}
    selected_codes = dict(list(codes.items())[:limit]) if limit else codes

    previous = load_previous_quotes(output).get("stocks", {})
    rest_items: list[tuple[str, str, str, str | None]] = []
    skipped_derivatives: list[str] = []
    proxied_derivatives: dict[str, str] = {}
    stocks: dict[str, Any] = {}

    for source_code, name in selected_codes.items():
        rest_code = kiwoom_rest_code(source_code, derivative_map, name)
        proxy_code = None
        if not rest_code and is_derivative_code(source_code):
            proxy_code = derivative_proxy_code(source_code, name, stock_future_proxy_map)
            rest_code = proxy_code
        if rest_code:
            rest_items.append((source_code, rest_code, name, proxy_code))
            if proxy_code:
                proxied_derivatives[source_code] = proxy_code
        else:
            skipped_derivatives.append(source_code)
            stocks[source_code] = {
                "name": name,
                "price": None,
                "change_rate": None,
                "industry": "",
                "market": "",
                "error": "unsupported_derivative_code: no REST code or proxy mapping",
            }

    failed = 0
    batches = chunks(rest_items, max(1, batch_size))
    for idx, batch in enumerate(batches, start=1):
        rest_codes = list(dict.fromkeys(item[1] for item in batch))
        try:
            rows = fetch_quote_batch(host, token, rest_codes, timeout)
            quote_by_rest: dict[str, dict[str, float | str | None]] = {}
            for rest_code, row in zip(rest_codes, rows):
                returned_code = str(row.get("stk_cd") or "").strip()
                key = returned_code if returned_code in rest_codes else rest_code
                quote_by_rest[key] = normalize_quote(row)
            for source_code, rest_code, fallback_name, proxy_code in batch:
                quote = quote_by_rest.get(rest_code)
                if not quote:
                    failed += 1
                    prev = previous.get(source_code, {}) if isinstance(previous, dict) else {}
                    stocks[source_code] = {
                        "name": fallback_name,
                        "price": prev.get("price") if proxy_code else None,
                        "change_rate": prev.get("change_rate") if proxy_code else None,
                        "industry": "",
                        "market": "",
                        "kiwoom_rest_code": rest_code,
                        "proxy_code": proxy_code,
                        "error": "missing_batch_response",
                    }
                    continue
                if quote["price"] in (None, 0.0):
                    failed += 1
                    prev = previous.get(source_code, {}) if isinstance(previous, dict) else {}
                    stocks[source_code] = {
                        "name": fallback_name,
                        "price": prev.get("price"),
                        "change_rate": prev.get("change_rate"),
                        "industry": "",
                        "market": "",
                        "kiwoom_rest_code": rest_code,
                        "proxy_code": proxy_code,
                        "error": "empty_quote_from_rest",
                    }
                else:
                    stocks[source_code] = {
                        "name": fallback_name if proxy_code else quote["name"] or fallback_name,
                        "price": quote["price"],
                        "change_rate": quote["change_rate"],
                        "industry": "",
                        "market": "",
                        "kiwoom_rest_code": rest_code,
                        "proxy_code": proxy_code,
                        "proxy_name": quote["name"] if proxy_code else "",
                    }
        except Exception as exc:
            failed += len(batch)
            for source_code, rest_code, fallback_name, proxy_code in batch:
                stocks[source_code] = {
                    "name": fallback_name,
                    "price": None,
                    "change_rate": None,
                    "industry": "",
                    "market": "",
                    "kiwoom_rest_code": rest_code,
                    "proxy_code": proxy_code,
                    "error": str(exc)[:300],
                }
        print(f"batch {idx}/{len(batches)}: {len(batch)} codes")

    return {
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(selected_codes),
        "source": "kiwoom_rest_api_ka10095",
        "batch_size": batch_size,
        "failed": failed,
        "skipped_derivatives": skipped_derivatives,
        "proxied_derivatives": proxied_derivatives,
        "stocks": stocks,
    }


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def run_refresh(args: argparse.Namespace, token: str, codes: dict[str, str]) -> dict[str, Any]:
    output = args.output if args.output.is_absolute() else BASE_DIR / args.output
    started = time.monotonic()
    quotes = fetch_all_quotes(args.host, token, codes, args.batch_size, args.timeout, output, args.limit, args.code)
    write_json_atomic(output, quotes)
    if args.build_dashboard:
        print(build_dashboard())
    elapsed = time.monotonic() - started
    available = sum(
        1
        for item in quotes["stocks"].values()
        if isinstance(item, dict) and item.get("price") not in (None, 0, 0.0)
    )
    print(
        f"refresh done: {quotes['count']} codes, price_available={available}, "
        f"failed={quotes['failed']}, elapsed={elapsed:.2f}s"
    )
    return quotes


def main() -> None:
    parser = argparse.ArgumentParser(description="Continuously refresh Kiwoom REST API quotes.")
    parser.add_argument("--host", default=os.getenv("KIWOOM_HOST", DEFAULT_HOST))
    parser.add_argument("--cycle-seconds", type=float, default=DEFAULT_CYCLE_SECONDS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--code", default=None)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--build-dashboard", action="store_true")
    parser.add_argument("--once", action="store_true", help="Run one refresh and exit.")
    args = parser.parse_args()

    token = os.getenv("KIWOOM_ACCESS_TOKEN")
    if not token:
        appkey, secretkey = load_credentials()
        if not appkey or not secretkey:
            raise SystemExit("KIWOOM_APPKEY/KIWOOM_SECRETKEY or *_appkey.txt/*_secretkey.txt is required.")
        token = request_token(args.host, appkey, secretkey, args.timeout)

    codes = collect_codes()
    if not codes:
        raise SystemExit("No quote codes found.")

    while True:
        started = time.monotonic()
        run_refresh(args, token, codes)
        if args.once:
            break
        sleep_for = max(0.0, args.cycle_seconds - (time.monotonic() - started))
        print(f"next refresh in {sleep_for:.2f}s")
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()


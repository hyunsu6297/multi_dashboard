from __future__ import annotations

import argparse
import json
import mimetypes
import re
import threading
import time
import webbrowser
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
API_PATHS = {"/api/emp-market", "/api/fund-raw", "/api/etf-discovery"}
FIELDS = {
    "CUR_MKT_CAP": "marketCap",
    "TURNOVER_AVG_3M": "avgTurnover3m",
    "VOLUME_AVG_3M": "avgVolume3m",
    "PX_LAST": "price",
    "PX_CLOSE_1D": "prevClose",
    "CHG_PCT_1D": "change",
    "CRNCY": "currency",
    "TICKER": "ticker",
    "ID_ISIN": "isin",
    "SECURITY_TYP": "securityType",
    "SECURITY_TYP2": "securityType2",
    "MARKET_SECTOR_DES": "marketSector",
    "GICS_SECTOR_NAME": "gicsLevel1",
    "GICS_INDUSTRY_GROUP_NAME": "gicsLevel2",
}
ETF_DISCOVERY_FIELDS = {
    "NAME": "name", "LONG_COMP_NAME": "longName",
    "EXCH_CODE": "exchangeCode", "FUND_GEO_FOCUS": "geoFocus",
    "FUND_ASSET_CLASS_FOCUS": "assetClassFocus", "FUND_BENCHMARK": "benchmark",
}
KST = timezone(timedelta(hours=9))
FX_CUTOFF = "KST_1530"


def element_value(element, field: str):
    if not element.hasElement(field):
        return None
    value = element.getElement(field)
    if value.isNull():
        return None
    result = value.getValue()
    if isinstance(result, (datetime, date)):
        return result.isoformat()
    return result


def fx_bar_before_1530(session, service, blpapi, day: date) -> float | None:
    """Last one-minute USD/KRW trade bar ending no later than 15:30 KST."""
    cutoff = datetime(day.year, day.month, day.day, 15, 30, tzinfo=KST).astimezone(timezone.utc)
    start = cutoff - timedelta(minutes=30)
    request = service.createRequest("IntradayBarRequest")
    request.set("security", "USDKRW Curncy")
    request.set("eventType", "TRADE")
    request.set("interval", 1)
    request.set("startDateTime", start.strftime("%Y-%m-%dT%H:%M:%S"))
    request.set("endDateTime", cutoff.strftime("%Y-%m-%dT%H:%M:%S"))
    request.set("gapFillInitialBar", True)
    session.sendRequest(request)
    latest = None
    deadline = time.monotonic() + 30
    while True:
        if time.monotonic() > deadline:
            raise RuntimeError("USD/KRW 15:30 분봉 조회 시간 초과")
        event = session.nextEvent(1000)
        for message in event:
            if message.hasElement("responseError"):
                raise RuntimeError(message.getElement("responseError").toString())
            if not message.hasElement("barData"):
                continue
            bars = message.getElement("barData").getElement("barTickData")
            for index in range(bars.numValues()):
                bar = bars.getValueAsElement(index)
                stamp = element_value(bar, "time")
                close = element_value(bar, "close")
                if stamp is None or close is None:
                    continue
                bar_time = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
                if bar_time.tzinfo is None:
                    bar_time = bar_time.replace(tzinfo=timezone.utc)
                if start <= bar_time < cutoff and float(close) > 0:
                    if latest is None or bar_time > latest[0]:
                        latest = (bar_time, float(close))
        if event.eventType() == blpapi.Event.RESPONSE:
            return latest[1] if latest else None


def fx_change_at_1530(session, service, blpapi, as_of: datetime) -> dict:
    """Compare two consecutive available Korean 15:30 USD/KRW fixes."""
    korean_now = as_of.astimezone(KST)
    day = korean_now.date()
    if korean_now.time() < datetime.strptime("15:30", "%H:%M").time():
        day -= timedelta(days=1)
    fixes = []
    for offset in range(14):
        candidate = day - timedelta(days=offset)
        if candidate.weekday() >= 5:
            continue
        value = fx_bar_before_1530(session, service, blpapi, candidate)
        if value is not None:
            fixes.append((candidate.isoformat(), value))
            if len(fixes) == 2:
                break
    if len(fixes) != 2:
        raise RuntimeError("USD/KRW 15:30 환율 2거래일치를 조회하지 못했습니다")
    (today, current), (previous_day, previous) = fixes
    return {"fxChange": current / previous - 1, "fxAt1530": current,
            "fxPreviousAt1530": previous, "fxAt1530Date": today,
            "fxPreviousAt1530Date": previous_day, "fxChangeBasis": FX_CUTOFF}


def fetch_reference(securities: list[str], host: str, port: int, as_of: datetime | None = None,
                    metadata_only: bool = False) -> dict:
    try:
        import blpapi
    except ImportError as exc:
        raise RuntimeError("blpapi 모듈을 찾지 못했습니다. Bloomberg Desktop API Python 패키지를 설치한 뒤 다시 시도하세요.") from exc

    if not isinstance(securities, list) or len(securities) > 5000 or any(not isinstance(s, str) or len(s) > 180 for s in securities):
        raise ValueError("종목 식별자 목록이 올바르지 않습니다.")
    requested = [s.strip() for s in securities if s.strip()]
    all_securities = list(dict.fromkeys(requested + ([] if metadata_only else ["USDKRW Curncy"])))
    if not all_securities:
        raise ValueError("조회할 종목이 없습니다.")
    options = blpapi.SessionOptions()
    options.setServerHost(host)
    options.setServerPort(port)
    session = blpapi.Session(options)
    if not session.start():
        raise RuntimeError("Bloomberg 세션을 시작하지 못했습니다. Terminal 로그인 상태를 확인하세요.")
    try:
        if not session.openService("//blp/refdata"):
            raise RuntimeError("Bloomberg //blp/refdata 서비스를 열지 못했습니다.")
        service = session.getService("//blp/refdata")
        request = service.createRequest("ReferenceDataRequest")
        for security in all_securities:
            request.getElement("securities").appendValue(security)
        fields = {**FIELDS, **ETF_DISCOVERY_FIELDS} if metadata_only else FIELDS
        for field in fields:
            request.getElement("fields").appendValue(field)
        session.sendRequest(request)
        output: dict[str, dict] = {}
        errors: dict[str, str] = {}
        deadline = time.monotonic() + 60
        while True:
            if time.monotonic() > deadline:
                raise RuntimeError("Bloomberg 조회 시간이 초과되었습니다. Terminal 연결 상태를 확인하세요.")
            event = session.nextEvent(1000)
            for message in event:
                if message.hasElement("responseError"):
                    raise RuntimeError(message.getElement("responseError").toString())
                if not message.hasElement("securityData"):
                    continue
                security_data = message.getElement("securityData")
                for index in range(security_data.numValues()):
                    item = security_data.getValueAsElement(index)
                    security = str(element_value(item, "security") or "")
                    sequence = element_value(item, "sequenceNumber")
                    if isinstance(sequence, int) and 0 <= sequence < len(all_securities):
                        security = all_securities[sequence]
                    if item.hasElement("securityError"):
                        errors[security] = item.getElement("securityError").toString()
                        continue
                    field_data = item.getElement("fieldData")
                    row = {target: element_value(field_data, source) for source, target in fields.items()}
                    if row.get("change") is not None:
                        row["change"] = float(row["change"]) / 100
                    if row.get("avgTurnover3m") is None and row.get("avgVolume3m") is not None and row.get("price") is not None:
                        row["avgTurnover3m"] = float(row["avgVolume3m"]) * float(row["price"])
                    row.pop("avgVolume3m", None)
                    if row.get("prevClose") is None and row.get("price") is not None and row.get("change") not in (None, -1):
                        row["prevClose"] = float(row["price"]) / (1 + float(row["change"]))
                    output[security] = {key: value for key, value in row.items() if value is not None}
            if event.eventType() == blpapi.Event.RESPONSE:
                break
        if metadata_only:
            return {"securities": output, "errors": errors,
                    "updatedAt": datetime.now(timezone.utc).isoformat()}
        fx_reference = output.pop("USDKRW Curncy", {})
        fx_price = fx_reference.get("price")
        fx = float(fx_price) if fx_price else None
        fx_prev_close = fx_reference.get("prevClose")
        try:
            fx_fix = fx_change_at_1530(session, service, blpapi, as_of or datetime.now(KST))
        except (RuntimeError, ValueError) as exc:
            errors["USDKRW 15:30"] = str(exc)
            fx_fix = {"fxChange": None, "fxAt1530": None, "fxPreviousAt1530": None,
                      "fxAt1530Date": None, "fxPreviousAt1530Date": None,
                      "fxChangeBasis": FX_CUTOFF}
        return {"securities": output, "fx": fx,
                "fxPrevClose": fx_prev_close, **fx_fix, "errors": errors,
                "asOf": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
                "updatedAt": datetime.now(timezone.utc).isoformat()}
    finally:
        session.stop()


def fetch_fund_raw(payload: dict) -> dict:
    """Query every browser-managed fund, regardless of its display type."""
    from build_global_dashboard import load_etfs, load_holdings, load_trades
    from supabase_raw import load_raw

    incoming = payload.get("funds")
    if not isinstance(incoming, list) or len(incoming) > 200:
        raise ValueError("펀드 목록은 최대 200개까지 조회할 수 있습니다.")
    funds = []
    seen = set()
    for item in incoming:
        if not isinstance(item, dict):
            raise ValueError("펀드 정보 형식이 올바르지 않습니다.")
        code = str(item.get("assocCode") or "").strip()
        name = str(item.get("fund") or "").strip()
        if not code:
            continue
        if not re.fullmatch(r"[A-Za-z0-9]{1,32}", code) or len(name) > 200:
            raise ValueError("펀드코드는 영문·숫자 32자 이내로 입력하세요.")
        if code not in seen:
            funds.append({"fund": name or code, "assocCode": code})
            seen.add(code)
    if not funds:
        return {"holdings": [], "trades": [], "coverage": [], "asOf": "", "sources": {"provider": "supabase"}}
    h, t, daily_nav, sources = load_raw([f["assocCode"] for f in funds], allow_empty=True)
    etfs = payload.get("etfs", None)
    if etfs is None:
        etfs = load_etfs()
    if not isinstance(etfs, list) or len(etfs) > 5000 or any(not isinstance(e, dict) for e in etfs):
        raise ValueError("ETF 정보 형식이 올바르지 않습니다.")
    # Parser lookups expect these optional workbook columns to exist.
    etfs = [{**{key: "" for key in ("isin", "name", "ticker")}, **e} for e in etfs]
    holdings = load_holdings(funds, etfs, h)
    trades = load_trades(funds, etfs, holdings, t, daily_nav)
    coverage = [{**f, "holdings": sum(r["fundCode"] == f["assocCode"] for r in holdings),
                 "trades": sum(r["fundCode"] == f["assocCode"] for r in trades)} for f in funds]
    return {"holdings": holdings, "trades": trades, "coverage": coverage,
            "asOf": sources["holdingsDate"], "sources": sources}


class Handler(BaseHTTPRequestHandler):
    server_version = "GlobalDashboard/2.7"

    def allowed_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if origin in (None, "null"):
            return True
        return origin in {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        target = ROOT / ("index.html" if parsed.path in {"/", "/index.html"} else parsed.path.lstrip("/"))
        try:
            resolved = target.resolve()
            if not resolved.is_file() or (resolved != ROOT.resolve() and ROOT.resolve() not in resolved.parents):
                self.send_error(404)
                return
            body = resolved.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(resolved.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except OSError as exc:
            self.send_error(500, str(exc))

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in API_PATHS:
            self.send_error(404)
            return
        try:
            if not self.allowed_origin():
                self.write_json({"error": "로컬 대시보드에서만 조회할 수 있습니다."}, 403)
                return
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 2_000_000:
                raise ValueError("요청 데이터 크기가 올바르지 않습니다.")
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("요청 형식이 올바르지 않습니다.")
            result = (fetch_fund_raw(payload) if path == "/api/fund-raw" else
                      fetch_reference(payload.get("securities", []), self.server.blp_host,
                                      self.server.blp_port, metadata_only=path == "/api/etf-discovery"))
            self.write_json(result, 200)
        except Exception as exc:
            self.write_json({"error": str(exc)}, 400)

    def do_OPTIONS(self) -> None:
        if urlparse(self.path).path not in API_PATHS:
            self.send_error(404)
            return
        if not self.allowed_origin():
            self.send_error(403)
            return
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def send_cors_headers(self) -> None:
        if self.allowed_origin():
            self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin") or "null")
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def write_json(self, payload: dict, status: int) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        print(f"{self.address_string()} - {format % args}")


def main() -> int:
    parser = argparse.ArgumentParser(description="글로벌대시보드 + Bloomberg Desktop API 서버")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--blp-host", default="localhost")
    parser.add_argument("--blp-port", type=int, default=8194)
    parser.add_argument("--open-browser", action="store_true", help="Open the dashboard after the server starts")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.blp_host = args.blp_host
    server.blp_port = args.blp_port
    print(f"글로벌대시보드: http://{args.host}:{args.port}")
    if args.open_browser:
        timer = threading.Timer(0.5, webbrowser.open, args=(f"http://{args.host}:{args.port}/",))
        timer.daemon = True
        timer.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

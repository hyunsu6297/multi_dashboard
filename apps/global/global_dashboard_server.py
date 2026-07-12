from __future__ import annotations

import argparse
import json
import mimetypes
import os
import shutil
import subprocess
import time
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
FIELDS = {
    "CUR_MKT_CAP": "marketCap",
    "TURNOVER_AVG_3M": "avgTurnover3m",
    "VOLUME_AVG_3M": "avgVolume3m",
    "PX_LAST": "price",
    "PX_PREV_CLOSE": "prevClose",
    "CHG_PCT_1D": "change",
}

KIWOOM_US_EXCHANGES = ("NY", "ND", "NA")
KIWOOM_US_EXCHANGE_NAMES = {"NY": "NYSE", "ND": "NASDAQ", "NA": "AMEX"}


def clean_number(value, default: float = 0.0) -> float:
    if value is None:
        return default
    text = str(value).strip().replace(",", "")
    if not text:
        return default
    text = text.replace("+", "")
    try:
        return float(text)
    except ValueError:
        return default


def clean_abs_number(value, default: float = 0.0) -> float:
    return abs(clean_number(value, default))


def normalize_security(security: str) -> str:
    return " ".join(str(security or "").strip().split())


def security_code(security: str) -> str:
    return normalize_security(security).split(" ")[0].upper()


def is_ks_security(security: str) -> bool:
    text = normalize_security(security).upper()
    return " KS " in f" {text} " or text.endswith(" KS EQUITY")


def is_us_security(security: str) -> bool:
    text = normalize_security(security).upper()
    return " US " in f" {text} " or text.endswith(" US EQUITY")


def kiwoom_env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


class KiwoomClient:
    def __init__(self) -> None:
        self.base_url = kiwoom_env("KIWOOM_BASE_URL", "https://api.kiwoom.com").rstrip("/")
        self.appkey = kiwoom_env("KIWOOM_APPKEY")
        self.secretkey = kiwoom_env("KIWOOM_SECRETKEY")
        self.token = kiwoom_env("KIWOOM_ACCESS_TOKEN")
        self.token_expires_at = 0.0
        self.exchange_cache: dict[str, str] = {}
        self.fx_candidates: list[float] = []
        if not self.token and (not self.appkey or not self.secretkey):
            raise RuntimeError("KIWOOM_APPKEY와 KIWOOM_SECRETKEY 환경변수를 설정하세요.")

    def request_json(self, path: str, api_id: str, body: dict, *, retry: bool = True) -> dict:
        token = self.get_token()
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = Request(
            f"{self.base_url}{path}",
            data=payload,
            headers={
                "Content-Type": "application/json;charset=UTF-8",
                "authorization": f"Bearer {token}",
                "api-id": api_id,
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=20) as res:
                raw = res.read().decode("utf-8", errors="replace")
        except Exception:
            if retry and not kiwoom_env("KIWOOM_ACCESS_TOKEN"):
                self.token = ""
                return self.request_json(path, api_id, body, retry=False)
            raise
        data = json.loads(raw or "{}")
        code = str(data.get("return_code", "0"))
        if code not in {"0", ""}:
            raise RuntimeError(data.get("return_msg") or f"Kiwoom {api_id} failed: {code}")
        return data

    def get_token(self) -> str:
        if self.token and (kiwoom_env("KIWOOM_ACCESS_TOKEN") or time.time() < self.token_expires_at - 60):
            return self.token
        payload = json.dumps({
            "grant_type": "client_credentials",
            "appkey": self.appkey,
            "secretkey": self.secretkey,
        }).encode("utf-8")
        req = Request(
            f"{self.base_url}/oauth2/token",
            data=payload,
            headers={"Content-Type": "application/json;charset=UTF-8"},
            method="POST",
        )
        with urlopen(req, timeout=20) as res:
            data = json.loads(res.read().decode("utf-8", errors="replace") or "{}")
        if str(data.get("return_code", "0")) not in {"0", ""}:
            raise RuntimeError(data.get("return_msg") or "Kiwoom token request failed")
        self.token = data.get("token") or ""
        expires_dt = str(data.get("expires_dt") or "")
        try:
            self.token_expires_at = datetime.strptime(expires_dt[:14], "%Y%m%d%H%M%S").timestamp()
        except ValueError:
            self.token_expires_at = time.time() + 60 * 50
        if not self.token:
            raise RuntimeError("Kiwoom token response did not include token")
        return self.token

    def us_exchange(self, ticker: str) -> str:
        ticker = ticker.upper()
        if ticker in self.exchange_cache:
            return self.exchange_cache[ticker]
        errors: list[str] = []
        for exchange in KIWOOM_US_EXCHANGES:
            try:
                data = self.request_json("/api/us/stkinfo", "usa10100", {"stex_tp": exchange, "stk_cd": ticker})
                if data.get("stk_cd") or data.get("stk_nm") or data.get("stk_enm"):
                    self.exchange_cache[ticker] = data.get("stex_tp") or exchange
                    return self.exchange_cache[ticker]
            except Exception as exc:
                errors.append(f"{exchange}/usa10100: {exc}")
        for exchange in KIWOOM_US_EXCHANGES:
            try:
                data = self.request_json("/api/us/mrkcond", "usa20100", {"stex_tp": exchange, "stk_cd": ticker})
                if data.get("cur_prc") or data.get("stk_cd") or data.get("stk_nm"):
                    self.exchange_cache[ticker] = data.get("stex_tp") or exchange
                    return self.exchange_cache[ticker]
            except Exception as exc:
                errors.append(f"{exchange}/usa20100: {exc}")
        detail = f" ({'; '.join(errors[:2])})" if errors else ""
        raise RuntimeError(f"{ticker}의 키움 미국주식 거래소구분을 찾지 못했습니다.{detail}")

    def fetch_us(self, security: str) -> dict:
        ticker = security_code(security)
        exchange = self.us_exchange(ticker)
        quote = self.request_json("/api/us/mrkcond", "usa20100", {"stex_tp": exchange, "stk_cd": ticker})
        daily = self.request_json("/api/us/mrkcond", "usa20590", {
            "stex_tp": exchange,
            "stk_cd": ticker,
            "base_dt": datetime.now().strftime("%Y%m%d"),
        })
        day = (daily.get("result_list") or [{}])[0] or {}
        price = clean_abs_number(quote.get("cur_prc") or day.get("cur_prc"))
        pred_pre = clean_number(quote.get("pred_pre") or day.get("pred_pre"))
        prev_close = clean_abs_number(quote.get("base_close_pric")) or (price - pred_pre if price else 0)
        base_exrt = clean_abs_number(quote.get("base_exrt"))
        if 1_000 <= base_exrt <= 2_000:
            self.fx_candidates.append(base_exrt)
        return {
            "marketCap": clean_abs_number(quote.get("mac")) * 1_000,
            "avgTurnover3m": clean_abs_number(day.get("trde_prica")),
            "price": price,
            "prevClose": abs(prev_close),
            "change": clean_number(quote.get("flu_rt") or day.get("flu_rt")) / 100,
            "kiwoomExchange": exchange,
            "kiwoomExchangeName": KIWOOM_US_EXCHANGE_NAMES.get(exchange, exchange),
        }

    def fetch_kr(self, security: str) -> dict:
        code = security_code(security)
        quote = self.request_json("/api/dostk/stkinfo", "ka10001", {"stk_cd": code})
        daily = self.request_json("/api/dostk/mrkcond", "ka10086", {
            "stk_cd": code,
            "qry_dt": datetime.now().strftime("%Y%m%d"),
            "indc_tp": "1",
        })
        rows = daily.get("daly_stkpc") or []
        today = datetime.now().strftime("%Y%m%d")
        day = next((row for row in rows if str(row.get("date") or "") < today), rows[0] if rows else {})
        price = clean_abs_number(quote.get("cur_prc") or day.get("close_pric"))
        pred_pre = clean_number(quote.get("pred_pre") or day.get("pred_rt"))
        prev_close = clean_abs_number(quote.get("base_pric")) or (price - pred_pre if price else 0)
        return {
            "marketCap": clean_abs_number(quote.get("mac")) * 100_000_000,
            "avgTurnover3m": clean_abs_number(day.get("amt_mn")) * 1_000_000,
            "price": price,
            "prevClose": abs(prev_close),
            "change": clean_number(quote.get("flu_rt") or day.get("flu_rt")) / 100,
        }

    def fetch_fx(self) -> float:
        if self.fx_candidates:
            values = sorted(self.fx_candidates)
            return values[len(values) // 2]
        for exch_tp in ("1", "2"):
            try:
                data = self.request_json("/api/us/exchange", "ust31301", {"exch_tp": exch_tp})
                fx = clean_abs_number(data.get("spcl_bf_exrt") or data.get("aplc_exrt"))
                if 1_000 <= fx <= 2_000:
                    return fx
            except Exception:
                continue
        return 0.0

    def fetch_reference(self, securities: list[str]) -> dict:
        self.fx_candidates = []
        output: dict[str, dict] = {}
        errors: dict[str, str] = {}
        for raw in securities:
            security = normalize_security(raw)
            if not security:
                continue
            try:
                if is_ks_security(security):
                    output[security] = self.fetch_kr(security)
                elif is_us_security(security) or len(security.split()) == 1:
                    output[security] = self.fetch_us(security)
            except Exception as exc:
                errors[security] = str(exc)
        fx = self.fetch_fx() or 1
        return {"securities": output, "fx": fx, "errors": errors, "asOf": datetime.now().strftime("%Y-%m-%d %H:%M"), "source": "kiwoom"}


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


def fetch_reference(securities: list[str], host: str, port: int) -> dict:
    try:
        import blpapi
    except ImportError:
        return fetch_reference_dotnet(securities, host, port)

    requested = [s.strip() for s in securities if s and s.strip()]
    all_securities = list(dict.fromkeys(requested + ["USDKRW Curncy"]))
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
        for field in FIELDS:
            request.getElement("fields").appendValue(field)
        session.sendRequest(request)
        output: dict[str, dict] = {}
        errors: dict[str, str] = {}
        while True:
            event = session.nextEvent(10000)
            for message in event:
                if message.hasElement("responseError"):
                    raise RuntimeError(message.getElement("responseError").toString())
                if not message.hasElement("securityData"):
                    continue
                security_data = message.getElement("securityData")
                for index in range(security_data.numValues()):
                    item = security_data.getValueAsElement(index)
                    security = str(element_value(item, "security") or "")
                    if item.hasElement("securityError"):
                        errors[security] = item.getElement("securityError").toString()
                        continue
                    field_data = item.getElement("fieldData")
                    row = {target: element_value(field_data, source) for source, target in FIELDS.items()}
                    if row.get("change") is not None:
                        row["change"] = float(row["change"]) / 100
                    if row.get("avgTurnover3m") is None and row.get("avgVolume3m") is not None and row.get("price") is not None:
                        row["avgTurnover3m"] = float(row["avgVolume3m"]) * float(row["price"])
                    row.pop("avgVolume3m", None)
                    if row.get("prevClose") is None and row.get("price") is not None and row.get("change") not in (None, -1):
                        row["prevClose"] = float(row["price"]) / (1 + float(row["change"]))
                    output[security] = row
            if event.eventType() == blpapi.Event.RESPONSE:
                break
        fx = float(output.pop("USDKRW Curncy", {}).get("price") or 1)
        return {"securities": output, "fx": fx, "errors": errors, "asOf": datetime.now().strftime("%Y-%m-%d %H:%M")}
    finally:
        session.stop()


def fetch_reference_dotnet(securities: list[str], host: str, port: int) -> dict:
    helper = ROOT / "fetch_bloomberg_dotnet.ps1"
    if not helper.is_file():
        raise RuntimeError("blpapi 모듈이 없고 .NET Bloomberg helper도 찾지 못했습니다.")
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        raise RuntimeError("PowerShell 실행 파일을 찾지 못했습니다. blpapi 설치 또는 PowerShell 실행 경로가 필요합니다.")
    payload = json.dumps({"securities": securities}, ensure_ascii=False)
    completed = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(helper),
            "-BlpHost",
            host,
            "-BlpPort",
            str(port),
        ],
        input=payload,
        text=True,
        capture_output=True,
        timeout=90,
        encoding="utf-8",
        errors="replace",
    )
    raw = completed.stdout.strip()
    try:
        result = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        detail = (completed.stderr or raw or "").strip()
        raise RuntimeError(f"Bloomberg .NET helper 응답을 해석하지 못했습니다: {detail[:1000]}") from exc
    if completed.returncode != 0:
        raise RuntimeError(result.get("error") or completed.stderr.strip() or "Bloomberg .NET helper 실행 실패")
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "GlobalDashboard/1.0"

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
        if urlparse(self.path).path != "/api/emp-market":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if self.server.provider == "kiwoom":
                result = self.server.kiwoom.fetch_reference(payload.get("securities", []))
            else:
                result = fetch_reference(payload.get("securities", []), self.server.blp_host, self.server.blp_port)
            self.write_json(result, 200)
        except Exception as exc:
            self.write_json({"error": str(exc)}, 400)

    def do_OPTIONS(self) -> None:
        if urlparse(self.path).path != "/api/emp-market":
            self.send_error(404)
            return
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")

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
    parser = argparse.ArgumentParser(description="글로벌전략 대시보드 로컬 시세 API 서버")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--provider", choices=["kiwoom", "bloomberg"], default="kiwoom")
    parser.add_argument("--blp-host", default="localhost")
    parser.add_argument("--blp-port", type=int, default=8194)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.provider = args.provider
    server.blp_host = args.blp_host
    server.blp_port = args.blp_port
    if args.provider == "kiwoom":
        server.kiwoom = KiwoomClient()
    print(f"Provider: {args.provider}")
    print(f"글로벌대시보드: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

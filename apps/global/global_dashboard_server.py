from __future__ import annotations

import argparse
import json
import mimetypes
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
FIELDS = {
    "CUR_MKT_CAP": "marketCap",
    "TURNOVER_AVG_3M": "avgTurnover3m",
    "VOLUME_AVG_3M": "avgVolume3m",
    "PX_LAST": "price",
    "PX_PREV_CLOSE": "prevClose",
    "CHG_PCT_1D": "change",
}


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
    except ImportError as exc:
        raise RuntimeError("blpapi 모듈을 찾지 못했습니다. Bloomberg Desktop API Python 패키지를 설치한 뒤 다시 시도하세요.") from exc

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
    parser = argparse.ArgumentParser(description="글로벌대시보드 + Bloomberg Desktop API 서버")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--blp-host", default="localhost")
    parser.add_argument("--blp-port", type=int, default=8194)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.blp_host = args.blp_host
    server.blp_port = args.blp_port
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

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HOST = "127.0.0.1"
PORT = 8765
MODEL = "gpt-5.4-mini"
MAX_REQUEST_BYTES = 512 * 1024
BASE_DIR = Path(__file__).resolve().parent


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
        if self.path == "/api/health":
            self.send_json(HTTPStatus.OK, {"ok": True, "apiKeyConfigured": bool(api_key()), "model": MODEL})
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path != "/api/performance-analysis":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "지원하지 않는 API 경로입니다."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_REQUEST_BYTES:
                raise ValueError("요청 데이터 크기가 올바르지 않습니다.")
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("성과분석 데이터는 JSON 객체여야 합니다.")
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

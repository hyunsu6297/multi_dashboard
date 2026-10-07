from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
OUTPUT = ROOT / "index.html"


def clean(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return text[:-2] if text.endswith(".0") else text


def number(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def iso_date(value: object) -> str:
    date = pd.to_datetime(value, errors="coerce")
    return "" if pd.isna(date) else date.strftime("%Y-%m-%d")


def read_table(path: Path, header: int = 0) -> pd.DataFrame:
    frame = pd.read_excel(path, sheet_name=0, header=header)
    return frame.dropna(axis=1, how="all").dropna(how="all").reset_index(drop=True)


def find_shared(name: str) -> Path | None:
    candidates = [ROOT / name, PROJECT_ROOT / name]
    candidates += list((PROJECT_ROOT / "apps").glob(f"*/{name}"))
    return next((path for path in candidates if path.is_file()), None)


def find_shared_matches(fragment: str) -> list[Path]:
    roots = [ROOT, PROJECT_ROOT]
    roots += [path for path in (PROJECT_ROOT / "apps").glob("*") if path.is_dir()]
    seen, matches = set(), []
    for root in roots:
        for path in root.glob("*.xlsx"):
            if path.name.startswith("~$"):
                continue
            if fragment in path.name and path not in seen:
                seen.add(path)
                matches.append(path)
    return sorted(matches, key=lambda path: path.name)


def load_funds() -> list[dict]:
    rows = []
    for _, row in read_table(ROOT / "펀드정보.xlsx").iterrows():
        rows.append({
            "fund": clean(row.get("펀드명")),
            "assocCode": clean(row.get("펀드코드")) or clean(row.get("협회코드")),
            "type": clean(row.get("유형")),
        })
    return rows


def raw_share(value: object) -> float:
    share = number(value, 1.0)
    return share / 100 if share > 1 else share


def load_etfs() -> list[dict]:
    rows = []
    for _, row in read_table(ROOT / "ETF정보.xlsx").iterrows():
        rows.append({
            "isin": clean(row.get("ISIN")), "fullName": clean(row.get("FULL NAME")),
            "koreanName": clean(row.get("KOREAN NAME")), "ticker": clean(row.get("TICKER")),
            "name": clean(row.get("NAME")), "listing": clean(row.get("상장")),
            "country": clean(row.get("투자국가")), "large": clean(row.get("자산군")) or "미분류",
            "underlyingAsset": clean(row.get("해외투자여부")) or ("N" if clean(row.get("투자국가")) == "한국" else "Y"),
            "mid": clean(row.get("대분류")) or "미분류", "small": clean(row.get("소분류")) or "미분류",
            "benchmark": clean(row.get("추종지수")),
            "source": clean(row.get("조회출처")),
            "emp": clean(row.get("EMP")),
        })
    return rows


def read_shared(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()
    frame = pd.read_excel(path, sheet_name="Data", header=1)
    return frame.drop(columns=["Unnamed: 0"], errors="ignore").dropna(how="all")


def match_etf(row: pd.Series, by_isin: dict, by_ticker: dict) -> dict:
    code = clean(row.get("종목코드"))
    name = clean(row.get("종목명"))
    ticker = clean(row.get("티커")) or code.split()[0]
    return by_isin.get(code) or by_ticker.get(ticker.upper()) or by_ticker.get(name.split()[0].upper()) or {}


def load_holdings(funds: list[dict], etfs: list[dict], frame: pd.DataFrame | None = None) -> list[dict]:
    if frame is None:
        frame = read_shared(find_shared("전체펀드 보유현황.xlsx"))
    frame = frame.copy()
    if frame.empty:
        return []
    fund_map = {f["assocCode"]: f for f in funds}
    isin_map = {e["isin"]: e for e in etfs if e["isin"]}
    ticker_map = {e["name"].upper(): e for e in etfs if e["name"]}
    frame["협회펀드코드"] = frame.get("협회펀드코드", "").map(clean)
    frame = frame[frame["협회펀드코드"].isin(fund_map)].drop_duplicates()
    rows = []
    for _, row in frame.iterrows():
        fund = fund_map[clean(row.get("협회펀드코드"))]
        etf = match_etf(row, isin_map, ticker_map)
        original = number(row.get("평가금"))
        invest_value = row.get("원천투자금")
        raw_invest_amt = None if pd.isna(invest_value) else number(invest_value)
        share = raw_share(row.get("지분율"))
        lookthrough = original * share
        asset = clean(row.get("자산구분") or row.get("자산군"))
        is_fx = asset == "선물옵션파생"
        rows.append({
            "date": iso_date(row.get("보유일")), "fund": fund["fund"], "fundCode": fund["assocCode"],
            "asset": asset, "market": clean(row.get("시장구분")), "position": clean(row.get("포지션")),
            "code": clean(row.get("종목코드")), "name": clean(row.get("종목명")),
            "qty": number(row.get("수량")), "price": number(row.get("평가가격")),
            "original": original, "rawInvestAmt": raw_invest_amt,
            "fundShare": share, "lookthrough": lookthrough,
            "netAssets": number(row.get("순자산")), "investment": number(row.get("순자산")) * share,
            "isFx": is_fx, "fxExposure": lookthrough if is_fx else 0, "change": 0,
            "country": "FX" if is_fx else etf.get("country", "미분류"), "large": "FX" if is_fx else etf.get("large", "미분류"),
            "underlyingAsset": etf.get("underlyingAsset", ""),
            "mid": etf.get("mid", "미분류"), "small": etf.get("small", "미분류"),
            "ticker": etf.get("name", ""), "security": etf.get("ticker", "") or etf.get("name", "") or clean(row.get("종목코드")),
            "emp": etf.get("emp", ""),
        })
    return rows


def trade_day_nav(daily_nav_frame: pd.DataFrame | None = None) -> dict[tuple[str, str], dict]:
    totals = {}
    if daily_nav_frame is not None and not daily_nav_frame.empty:
        for _, row in daily_nav_frame.iterrows():
            key = (iso_date(row.get("기준일")), clean(row.get("협회펀드코드")))
            nav = number(row.get("순자산"))
            item = totals.setdefault(key, {"nav": 0.0, "investment": 0.0})
            item["nav"] += nav
            item["investment"] += nav * raw_share(row.get("지분율"))
    return {key: {**item, "share": item["investment"] / item["nav"]}
            for key, item in totals.items() if item["nav"] > 0 and item["investment"] > 0}


def load_trades(funds: list[dict], etfs: list[dict], holdings: list[dict], frame: pd.DataFrame | None = None,
                daily_nav_frame: pd.DataFrame | None = None) -> list[dict]:
    if frame is None:
        frames = [read_shared(path) for path in find_shared_matches("매매현황")]
        frames = [item for item in frames if not item.empty]
        frame = pd.concat(frames, ignore_index=True).drop_duplicates() if frames else pd.DataFrame()
    frame = frame.copy()
    if frame.empty:
        return []
    fund_map = {f["assocCode"]: f for f in funds}
    holding_shares = {}
    for holding in sorted(holdings, key=lambda item: item["date"], reverse=True):
        holding_shares.setdefault(holding["fundCode"], holding["fundShare"])
    day_nav = trade_day_nav(daily_nav_frame)
    isin_map = {e["isin"]: e for e in etfs if e["isin"]}
    ticker_map = {e["name"].upper(): e for e in etfs if e["name"]}
    frame["협회펀드코드"] = frame.get("협회펀드코드", "").map(clean)
    frame = frame[frame["협회펀드코드"].isin(fund_map)]
    rows = []
    for _, row in frame.iterrows():
        fund = fund_map[clean(row.get("협회펀드코드"))]
        etf = match_etf(row, isin_map, ticker_map)
        side = clean(row.get("거래구분"))
        original = abs(number(row.get("결제금액")))
        sign = -1 if side == "매도" else 1
        date = iso_date(row.get("기준일"))
        nav = day_nav.get((date, fund["assocCode"]))
        share = nav["share"] if nav else raw_share(row.get("지분율", holding_shares.get(fund["assocCode"], 1.0)))
        if not nav and pd.isna(row.get("지분율")):
            share = holding_shares.get(fund["assocCode"], 1.0)
        rows.append({
            "date": date, "fund": fund["fund"], "fundCode": fund["assocCode"],
            "asset": clean(row.get("자산구분")), "market": clean(row.get("시장구분")),
            "code": clean(row.get("종목코드")), "name": clean(row.get("종목명")), "side": side,
            "qty": number(row.get("매매수량")), "price": number(row.get("매매가격")),
            "original": original, "fundShare": share, "lookthrough": original * share * sign,
            "tradeNav": nav["investment"] if nav else None,
            "country": etf.get("country", "미분류"), "large": etf.get("large", "미분류"),
            "mid": etf.get("mid", "미분류"), "small": etf.get("small", "미분류"),
            "ticker": etf.get("name", ""), "emp": etf.get("emp", ""),
        })
    return rows


def load_emp() -> dict:
    path = ROOT / "EMP보유현황.xlsx"
    if not path.is_file():
        return {"principals": {}, "portfolios": {}}
    principal_frame = pd.read_excel(path, sheet_name="전체")
    principals = {
        clean(row.get("구분")): number(row.get("원금"))
        for _, row in principal_frame.iterrows()
        if clean(row.get("구분"))
    }
    portfolios = {}
    for name in ("EMP1", "EMP2", "EMP3", "EMP4"):
        frame = pd.read_excel(path, sheet_name=name)
        rows = []
        for _, row in frame.iterrows():
            security = clean(row.get("종목"))
            if not security:
                continue
            if " " not in security:
                security = f"{security.zfill(6)} KS Equity"
            change = number(row.get("등락율"))
            rows.append({
                "security": security,
                "marketCap": number(row.get("시총")),
                "avgTurnover3m": number(row.get("3M Avg Vol.")),
                "quantity": number(row.get("보유수량")),
                "price": number(row.get("종가")),
                "change": change,
                "targetWeight": number(row.get("목표비중")),
            })
        portfolios[name] = rows
    return {"principals": principals, "portfolios": portfolios}


def build_data(data_source: str = "supabase", start: str | None = None, end: str | None = None) -> dict:
    funds, etfs = load_funds(), load_etfs()
    if data_source == "supabase":
        from supabase_raw import load_raw
        h_frame, t_frame, daily_nav_frame, sources = load_raw([f["assocCode"] for f in funds if f["assocCode"]], start, end)
        holdings = load_holdings(funds, etfs, h_frame)
        trades = load_trades(funds, etfs, holdings, t_frame, daily_nav_frame)
    elif data_source == "excel":
        holdings = load_holdings(funds, etfs)
        trades = load_trades(funds, etfs, holdings)
        sources = {"provider": "excel", "holdings": str(find_shared("전체펀드 보유현황.xlsx") or ""), "trades": "; ".join(str(p) for p in find_shared_matches("매매현황"))}
    else:
        raise ValueError(f"지원하지 않는 데이터 소스: {data_source}")
    dates = [r["date"] for r in holdings + trades if r["date"]]
    return {
        "funds": funds, "etfs": etfs, "holdings": holdings, "trades": trades,
        "emp": load_emp(),
        "asOf": sources.get("holdingsDate") or (max(dates) if dates else "원천데이터 미연결"),
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sources": sources,
    }


HTML = r'''<!doctype html>
<html lang="ko" class="dashboardBooting"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>수익증권 대시보드</title>
<style>html.dashboardBooting .app{visibility:hidden}html.dashboardBooting body::before{content:"대시보드 준비 중…";position:fixed;inset:0;display:grid;place-items:center;color:#6c7f7b;background:#f4f8f7;font:14px Arial,sans-serif}html.dashboardBootError body::before{content:"대시보드를 불러오지 못했습니다. Ctrl+F5로 다시 시도해주세요."}</style>
<script>window.addEventListener("error",function(e){if(document.documentElement.classList.contains("dashboardBooting")&&(!e.target.tagName||e.target.tagName==="SCRIPT"))document.documentElement.classList.add("dashboardBootError")},true);window.addEventListener("load",function(){if(document.documentElement.classList.contains("dashboardBooting"))document.documentElement.classList.add("dashboardBootError")});</script>
<noscript><style>html.dashboardBooting body::before{content:"대시보드를 사용하려면 JavaScript를 활성화해주세요."}</style></noscript>
<style>
:root{--deep:#064e43;--teal:#2a7569;--mint:#e9f2ef;--line:#609d91;--ink:#173a34;--muted:#6c7f7b;--red:#c2413a;--bg:#f4f8f7}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#243a36;font-family:Pretendard,"Noto Sans KR",Arial,sans-serif}.app{display:grid;grid-template-columns:244px minmax(0,1fr);grid-template-rows:76px 1fr;min-height:100vh}.top{grid-column:1/-1;display:flex;align-items:center;gap:22px;background:#fff;border-bottom:1px solid #c9dcd7;padding:0 18px}.brand{font-size:27px;font-weight:900;color:var(--ink);border-top:2px solid var(--line);border-bottom:11px solid var(--deep);padding:8px 40px 8px 6px}.tabs{display:flex;gap:7px}.tab{border:1.5px solid var(--line);background:var(--mint);color:var(--ink);font-weight:800;border-radius:5px;padding:9px 18px;cursor:pointer}.tab.active{background:var(--deep);color:#fff}.stamp{margin-left:auto;text-align:right;font-size:11px;color:var(--muted)}.side{grid-column:1;grid-row:2;background:#fff;border-right:2px solid var(--line);padding:8px 10px}.asof{display:grid;grid-template-columns:52px 1fr;gap:6px 8px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:7px 2px;font-size:12px}.reset{grid-column:1/-1;border:1px solid var(--line);background:var(--mint);color:var(--ink);border-radius:4px;padding:5px 8px;cursor:pointer;font-weight:800}.filter{border:1.5px solid var(--line);border-radius:5px;padding:6px;margin:8px 0;background:#fcfffe}.filterHead{display:flex;align-items:center;gap:4px;margin-bottom:6px}.filter h3{margin:0;color:var(--ink);font-size:12px;flex:1}.miniAll,.multiBtn{border:1px solid #b6d1ca;background:var(--mint);color:var(--ink);border-radius:3px;padding:2px 6px;font-size:10px;cursor:pointer}.multiBtn.active{background:var(--deep);color:#fff}.chips{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px}.chip{border:0;background:var(--teal);color:#fff;border-radius:3px;padding:5px 6px;text-align:left;font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer}.chip.active{background:#092f2a;box-shadow:inset 0 0 0 2px #9ad0c1}.main{grid-column:2;grid-row:2;padding:10px;overflow:hidden}.pane{display:none}.pane.active{display:block}.notice{border:1px solid #b8d2cc;background:#f8fcfb;color:#365c54;border-radius:6px;padding:8px 11px;font-size:11px;margin-bottom:8px}.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:8px}.kpi{background:#fff;border:1.5px solid var(--line);border-radius:6px;padding:9px 11px;min-height:66px}.kpi span{color:var(--ink);font-weight:800;font-size:11px}.kpi b{display:block;color:var(--deep);font-size:20px;text-align:right;margin-top:11px}.grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px}.panel{background:#fff;border:1.5px solid var(--line);border-radius:14px;padding:10px;min-width:0}.panel.wide{grid-column:1/-1}.panel h2{font-size:13px;color:var(--ink);margin:0 0 8px;display:flex;align-items:center;gap:6px}.panel h2:before{content:"";width:18px;height:11px;background:linear-gradient(90deg,var(--teal),#b9dbd4);border-radius:7px}.shareRows{height:300px;overflow:auto}.shareRow{display:grid;grid-template-columns:180px 1fr 48px;align-items:center;gap:8px;margin:7px 0;font-size:11px}.shareRow.subtotal{margin-top:11px;font-weight:900}.shareRow.subtotal .track{height:19px}.shareRow.subtotal .fill{background:var(--deep)}.shareLabel{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.track{height:15px;background:#e4efec;border-radius:3px;overflow:hidden}.fill{height:100%;background:linear-gradient(90deg,#8ab8ae,#2a7569)}.shareValue{text-align:right;font-weight:800;color:var(--deep)}.tablewrap{overflow:auto;max-height:430px}table{width:100%;border-collapse:collapse;font-size:10px;white-space:nowrap}th{position:sticky;top:0;background:var(--teal);color:#fff;text-align:left;padding:5px 6px}td{border-bottom:1px solid #e5eeec;padding:4px 6px}tr:nth-child(even){background:#f7fbfa}.num{text-align:right}.neg{color:var(--red)}.toolbar{display:flex;gap:7px;margin-bottom:7px}.search{border:1px solid #9bbcb5;border-radius:4px;padding:6px 8px;width:100%}.empty{height:120px;display:grid;place-items:center;color:var(--muted);font-size:12px}.meta{font-size:11px;color:var(--muted);margin-top:8px;text-align:right}.masterGrid{display:grid;gap:8px}@media(max-width:1100px){.app{grid-template-columns:1fr;grid-template-rows:auto auto auto}.top{flex-wrap:wrap;padding:10px}.brand{width:100%}.stamp{margin-left:0}.side{grid-column:1;grid-row:2;border-right:0;border-bottom:2px solid var(--line)}.main{grid-column:1;grid-row:3}.kpis{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}.panel.wide{grid-column:auto}}
 .empMenu{display:none}.empMenu.active{display:block}.empMenu h3{font-size:12px;color:var(--ink);margin:12px 2px 7px}.empNav{display:grid;gap:6px}.empNav button{border:1.5px solid var(--line);background:var(--mint);color:var(--ink);font-weight:900;border-radius:5px;padding:10px;text-align:left;cursor:pointer}.empNav button.active{background:var(--deep);color:#fff}.empSummary{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:8px}.empCard{background:#fff;border:1.5px solid var(--line);border-radius:7px;padding:10px}.empCard span{display:block;font-size:10px;color:var(--muted);font-weight:800}.empCard b{display:block;margin-top:7px;text-align:right;color:var(--deep);font-size:17px}.empActions{display:flex;gap:7px;align-items:center;margin-bottom:8px}.actionBtn{border:1px solid var(--line);background:var(--mint);color:var(--ink);border-radius:4px;padding:6px 10px;font-weight:800;cursor:pointer}.actionBtn.primary{background:var(--deep);color:#fff}.empStatus{font-size:11px;color:var(--muted);margin-left:auto}.editable{background:#fff8d8!important}.editable input{width:88px;border:1px solid #c7b35a;border-radius:3px;padding:3px;text-align:right;background:#fffdf3}.tickerInput{width:150px!important;text-align:left!important}.deleteBtn{border:0;background:#fee2e2;color:#b42318;border-radius:3px;padding:3px 7px;cursor:pointer}.pos{color:#087f5b}.empCharts{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px}.compactChart{height:220px;overflow:auto}.empTableWrap{max-height:calc(100vh - 340px)}
</style></head><body><div class="app">
<header class="top"><div class="brand">수익증권 대시보드</div><nav class="tabs"><button class="tab active" data-tab="dashboard">통합현황</button><button class="tab" data-tab="emp">EMP상세</button><button class="tab" data-tab="master">기준정보</button></nav><div class="stamp"><span id="generated"></span></div></header>
<aside class="side"><div class="asof"><b>기준일</b><span id="asOf"></span><button class="reset" id="reset">전체 초기화</button></div><div id="filters"></div><div class="empMenu" id="empMenu"><h3>EMP 포트폴리오</h3><div class="empNav" id="empNav"></div></div></aside>
<main class="main"><section class="pane active" id="dashboard"><div class="notice" id="notice"></div><div class="kpis"><div class="kpi"><span>선택 펀드</span><b id="kFunds"></b></div><div class="kpi"><span>현재 분류 기준</span><b id="kDimension"></b></div><div class="kpi"><span>보유 종목</span><b id="kHoldings"></b></div><div class="kpi"><span>ETF 분류 매핑률</span><b id="kMapped"></b></div><div class="kpi"><span>순매매 / 보유</span><b id="kTradeShare"></b></div></div>
<div class="grid"><div class="panel wide"><h2 id="chartTitle">투자국가별 자산 비중</h2><div class="shareRows" id="assetChart"></div></div>
<div class="panel"><div class="toolbar"><input class="search" id="holdingSearch" placeholder="보유 펀드·종목·티커 검색"></div><h2>글로벌 보유현황</h2><div class="tablewrap"><table id="holdingTable"></table></div></div><div class="panel"><div class="toolbar"><input class="search" id="tradeSearch" placeholder="매매 펀드·종목·티커 검색"></div><h2>글로벌 매매현황</h2><div class="tablewrap"><table id="tradeTable"></table></div></div></div></section>
<section class="pane" id="emp"><div class="empSummary"><div class="empCard"><span>배정 원금</span><b id="ePrincipal"></b></div><div class="empCard"><span>평가금액(원화)</span><b id="eValue"></b></div><div class="empCard"><span>평가 비중</span><b id="eWeight"></b></div><div class="empCard"><span>일 손익(원화)</span><b id="ePnl"></b></div><div class="empCard"><span>원·달러 환율</span><b id="eFx"></b></div></div><div class="empCharts"><div class="panel"><h2>EMP 자산 비중</h2><div class="compactChart" id="empAssetChart"></div></div><div class="panel"><h2>현재 수익증권 자산 비중</h2><div class="compactChart" id="fundAssetChart"></div></div></div><div class="panel"><div class="empActions"><button class="actionBtn primary" id="refreshMarket">블룸버그 데이터 업데이트</button><button class="actionBtn" id="addEmpRow">행 추가</button><span class="empStatus" id="empStatus"></span></div><h2 id="empTitle"></h2><div class="tablewrap empTableWrap"><table id="empTable"></table></div></div></section>
<section class="pane" id="master"><div class="masterGrid"><div class="panel"><h2>펀드정보</h2><div class="tablewrap"><table id="fundTable"></table></div></div><div class="panel"><div class="toolbar"><input class="search" id="etfSearch" placeholder="ETF명·티커·ISIN 검색"></div><h2>ETF정보</h2><div class="tablewrap"><table id="etfTable"></table></div></div></div></section><div class="meta" id="meta"></div></main></div>
<script>const DATA=__DATA__;const state={fund:[],dimensions:["large"],multiFund:false,holdingSearch:"",tradeSearch:"",etfSearch:"",activeTab:"dashboard",emp:"EMP1",fx:1};
const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));const pct=v=>`${(Number(v||0)*100).toFixed(1)}%`;
const dimensionDefs=[["large","대분류"],["country","투자국가"],["mid","중분류"],["small","소분류"]];
function fundBase(rows){return rows.filter(r=>!state.fund.length||state.fund.includes(r.fund))}
function toggleFilter(key,value){const list=state[key],idx=list.indexOf(value);if(key==="fund"&&state.multiFund){if(idx>=0)list.splice(idx,1);else list.push(value)}else state[key]=idx>=0?[]:[value]}
function renderFilters(){const box=document.getElementById("filters"),funds=DATA.funds.map(x=>x.fund);box.innerHTML=`<div class="filter"><div class="filterHead"><h3>분류 기준 · 중복 선택</h3></div><div class="chips">${dimensionDefs.map(([key,label])=>`<button class="chip ${state.dimensions.includes(key)?"active":""}" data-dimension="${key}">${label}</button>`).join("")}</div></div><div class="filter"><div class="filterHead"><h3>펀드</h3><button class="multiBtn ${state.multiFund?"active":""}" data-action="multi">중복</button><button class="miniAll" data-key="fund" data-action="clear">해제</button></div><div class="chips">${funds.map(v=>`<button title="${esc(v)}" class="chip ${state.fund.includes(v)?"active":""}" data-key="fund" data-value="${esc(v)}">${esc(v)}</button>`).join("")}</div></div>`;box.querySelectorAll("button").forEach(b=>b.onclick=()=>{if(b.dataset.dimension){const i=state.dimensions.indexOf(b.dataset.dimension);if(i>=0&&state.dimensions.length>1)state.dimensions.splice(i,1);else if(i<0)state.dimensions.push(b.dataset.dimension);state.dimensions=dimensionDefs.map(x=>x[0]).filter(x=>state.dimensions.includes(x))}else if(b.dataset.action==="multi"){state.multiFund=!state.multiFund;if(!state.multiFund&&state.fund.length>1)state.fund=state.fund.slice(0,1)}else if(b.dataset.action==="clear"){state.fund=[];state.multiFund=false}else toggleFilter("fund",b.dataset.value);render()})}
function hierarchical(rows,keys,denom){const out=[];function walk(part,depth,path){const key=keys[depth],groups={};part.forEach(r=>{const value=r[key]||"미분류";(groups[value]??=[]).push(r)});Object.entries(groups).map(([label,list])=>[label,list,list.reduce((s,x)=>s+Number(x.lookthrough||0),0)]).sort((a,b)=>b[2]-a[2]).forEach(([label,list,amount])=>{const last=depth===keys.length-1;out.push({label:last&&keys.length===1?label:`${label}${last?"":" 소계"}`,share:denom?amount/denom:0,depth,subtotal:!last});if(!last)walk(list,depth+1,[...path,label])})}walk(rows,0,[]);return out}
function shares(el,entries){const max=Math.max(...entries.map(x=>x.share),.0001);el.innerHTML=entries.length?entries.map(x=>`<div class="shareRow ${x.subtotal?"subtotal":""}"><span class="shareLabel" style="padding-left:${x.depth*18}px" title="${esc(x.label)}">${x.depth?"└ ":""}${esc(x.label)}</span><div class="track"><div class="fill" style="width:${Math.max(1,x.share/max*100)}%"></div></div><span class="shareValue">${pct(x.share)}</span></div>`).join(""):`<div class="empty">표시할 데이터가 없습니다.</div>`}
function table(el,cols,rows){el.innerHTML=`<thead><tr>${cols.map(c=>`<th class="${c[2]||""}">${c[0]}</th>`).join("")}</tr></thead><tbody>${rows.length?rows.map(r=>`<tr>${cols.map(c=>`<td class="${c[2]||""}">${c[1](r)}</td>`).join("")}</tr>`).join(""):`<tr><td colspan="${cols.length}"><div class="empty">표시할 데이터가 없습니다.</div></td></tr>`}</tbody>`}
function render(){renderFilters();const h=fundBase(DATA.holdings),t=fundBase(DATA.trades),denom=h.reduce((s,x)=>s+Number(x.investment||0),0),tradeAmt=t.reduce((s,x)=>s+Number(x.lookthrough||0),0),fundCount=state.fund.length||DATA.funds.length,mapped=h.filter(x=>x.ticker).reduce((s,x)=>s+Number(x.lookthrough||0),0),labels=state.dimensions.map(k=>dimensionDefs.find(x=>x[0]===k)[1]);document.getElementById("kFunds").textContent=`${fundCount}개`;document.getElementById("kDimension").textContent=labels.join(" → ");document.getElementById("kHoldings").textContent=`${new Set(h.map(x=>x.code||x.name)).size}개`;document.getElementById("kMapped").textContent=pct(denom?mapped/denom:0);document.getElementById("kTradeShare").textContent=pct(denom?tradeAmt/denom:0);document.getElementById("chartTitle").textContent=`${labels.join(" → ")} 자산 비중`;shares(document.getElementById("assetChart"),hierarchical(h,state.dimensions,denom));renderTables(h,t,denom)}
function renderTables(h,t,denom){let q=state.holdingSearch.toLowerCase();h=h.filter(x=>!q||[x.fund,x.name,x.ticker,x.code].join(" ").toLowerCase().includes(q));table(document.getElementById("holdingTable"),[["펀드",x=>esc(x.fund)],["종목",x=>esc(x.name)],["티커",x=>esc(x.ticker)],["투자국가",x=>esc(x.country)],["대분류",x=>esc(x.large)],["중분류",x=>esc(x.mid)],["소분류",x=>esc(x.small)],["전체 비중",x=>pct(denom?x.lookthrough/denom:0),"num"]],h.sort((a,b)=>b.lookthrough-a.lookthrough).slice(0,1000));q=state.tradeSearch.toLowerCase();t=t.filter(x=>!q||[x.fund,x.name,x.ticker,x.code].join(" ").toLowerCase().includes(q));table(document.getElementById("tradeTable"),[["기준일",x=>x.date],["펀드",x=>esc(x.fund)],["거래",x=>esc(x.side)],["종목",x=>esc(x.name)],["티커",x=>esc(x.ticker)],["투자국가",x=>esc(x.country)],["분류",x=>esc([x.large,x.mid,x.small].filter(Boolean).join(" > "))],["보유 대비",x=>`<span class="${x.lookthrough<0?"neg":""}">${pct(denom?x.lookthrough/denom:0)}</span>`,"num"]],t.sort((a,b)=>Math.abs(b.lookthrough)-Math.abs(a.lookthrough)).slice(0,1000));table(document.getElementById("fundTable"),[["펀드명",x=>esc(x.fund)],["펀드코드",x=>esc(x.assocCode)]],DATA.funds);q=state.etfSearch.toLowerCase();const e=DATA.etfs.filter(x=>!q||[x.koreanName,x.fullName,x.name,x.ticker,x.isin].join(" ").toLowerCase().includes(q));table(document.getElementById("etfTable"),[["ISIN",x=>esc(x.isin)],["티커",x=>esc(x.name)],["한글명",x=>esc(x.koreanName)],["상장",x=>esc(x.listing)],["투자국가",x=>esc(x.country)],["대분류",x=>esc(x.large)],["중분류",x=>esc(x.mid)],["소분류",x=>esc(x.small)],["EMP",x=>esc(x.emp)]],e)}
document.getElementById("asOf").textContent=DATA.asOf;document.getElementById("generated").textContent=`보유현황 기준일 ${DATA.asOf}`;document.getElementById("notice").textContent="분류 위계는 대분류 → 투자국가 → 중분류 → 소분류입니다. 여러 기준을 선택하면 상위 분류 소계와 하위 구성 비중을 함께 표시합니다.";document.getElementById("meta").textContent=`로컬 원천 · 보유 ${DATA.holdings.length.toLocaleString()}건 · 매매 ${DATA.trades.length.toLocaleString()}건 · ETF ${DATA.etfs.length.toLocaleString()}건`;
document.querySelectorAll(".tab").forEach(b=>b.onclick=()=>{document.querySelectorAll(".tab,.pane").forEach(x=>x.classList.remove("active"));b.classList.add("active");document.getElementById(b.dataset.tab).classList.add("active")});document.getElementById("reset").onclick=()=>{state.fund=[];state.dimensions=["large"];state.multiFund=false;render()};[["holdingSearch","holdingSearch"],["tradeSearch","tradeSearch"],["etfSearch","etfSearch"]].forEach(([id,key])=>document.getElementById(id).oninput=e=>{state[key]=e.target.value;render()});render();</script>
<script>
const empSaved=JSON.parse(localStorage.getItem("globalDashboard.emp")||"null");if(empSaved?.portfolios)DATA.emp.portfolios=empSaved.portfolios;if(empSaved?.fx)state.fx=empSaved.fx;
const won=v=>`${Math.round(Number(v||0)).toLocaleString("ko-KR")}원`,amount=v=>Number(v||0).toLocaleString("ko-KR",{maximumFractionDigits:2}),isUsd=s=>/\bUS\s+Equity$/i.test(s),rateFor=s=>isUsd(s)?state.fx:1;
function saveEmp(){localStorage.setItem("globalDashboard.emp",JSON.stringify({portfolios:DATA.emp.portfolios,fx:state.fx}))}function empRows(){return DATA.emp.portfolios[state.emp]||[]}
function empMetrics(row){const value=Number(row.quantity||0)*Number(row.price||0),krw=value*rateFor(row.security),change=Number(row.change||0),pnl=value*change*rateFor(row.security),principal=Number(DATA.emp.principals[state.emp]||0),current=principal?value/principal:0,target=Number(row.targetWeight||0),prev=Number(row.prevClose||row.price||0),gap=target-current,tradeQty=prev?Math.round((target*principal-value)/prev):0;return{value,krw,pnl,current,target,gap,prev,tradeQty,tradeAmount:tradeQty*prev}}
function renderEmpMenu(){const nav=document.getElementById("empNav");nav.innerHTML=Object.keys(DATA.emp.portfolios).map(n=>`<button class="${n===state.emp?"active":""}" data-emp="${n}">${n}호 · 원금 ${amount(DATA.emp.principals[n])}</button>`).join("");nav.querySelectorAll("button").forEach(b=>b.onclick=()=>{state.emp=b.dataset.emp;renderEmpMenu();renderEmp()})}
function editEmp(index,key,value){const row=empRows()[index];row[key]=key==="security"?value:Number(value||0);saveEmp();renderEmp()}
function renderEmp(){const rows=empRows(),principal=Number(DATA.emp.principals[state.emp]||0),metrics=rows.map(empMetrics),total=metrics.reduce((s,x)=>s+x.value,0),totalKrw=metrics.reduce((s,x)=>s+x.krw,0),pnl=metrics.reduce((s,x)=>s+x.pnl,0);document.getElementById("empTitle").textContent=`${state.emp}호 보유·리밸런싱`;document.getElementById("ePrincipal").textContent=amount(principal);document.getElementById("eValue").textContent=won(totalKrw);document.getElementById("eWeight").textContent=pct(principal?total/principal:0);document.getElementById("ePnl").textContent=won(pnl);document.getElementById("ePnl").className=pnl<0?"neg":"pos";document.getElementById("eFx").textContent=state.fx===1?"조회 전":amount(state.fx);
const etfMap=Object.fromEntries(DATA.etfs.map(e=>[(e.name||e.ticker||"").toUpperCase(),e]));const grouped={};rows.forEach((r,i)=>{const key=r.security.split(" ")[0].toUpperCase(),e=etfMap[key]||{},label=e.large||"미분류";grouped[label]=(grouped[label]||0)+metrics[i].value});shares(document.getElementById("empAssetChart"),Object.entries(grouped).sort((a,b)=>b[1]-a[1]).map(([label,v])=>({label,share:total?v/total:0,depth:0,subtotal:false})));const h=DATA.holdings,denom=h.reduce((s,x)=>s+Number(x.investment||0),0);shares(document.getElementById("fundAssetChart"),hierarchical(h,["large"],denom));
const head=["삭제","종목","시총","3개월 일평균 거래대금","보유수량","종가","평가금액","등락율(전일)","손익(원화)","현재비중","목표비중","차이","거래방향","거래수량","거래금액(전일종가)"];document.getElementById("empTable").innerHTML=`<thead><tr>${head.map(x=>`<th>${x}</th>`).join("")}</tr></thead><tbody>${rows.map((r,i)=>{const m=metrics[i],side=m.tradeQty>0?"매수":m.tradeQty<0?"매도":"유지";return`<tr><td><button class="deleteBtn" data-del="${i}">삭제</button></td><td class="editable"><input class="tickerInput" data-i="${i}" data-key="security" value="${esc(r.security)}"></td><td class="num">${amount(r.marketCap)}</td><td class="num">${amount(r.avgTurnover3m)}</td><td class="editable"><input data-i="${i}" data-key="quantity" type="number" value="${r.quantity||0}"></td><td class="num">${amount(r.price)}</td><td class="num">${amount(m.value)}</td><td class="num ${r.change<0?"neg":"pos"}">${pct(r.change)}</td><td class="num ${m.pnl<0?"neg":"pos"}">${won(m.pnl)}</td><td class="num">${pct(m.current)}</td><td class="editable"><input data-i="${i}" data-key="targetWeight" type="number" step="0.0001" value="${r.targetWeight||0}"></td><td class="num ${m.gap<0?"neg":"pos"}">${pct(m.gap)}</td><td>${side}</td><td class="num">${m.tradeQty.toLocaleString()}</td><td class="num">${amount(m.tradeAmount)}</td></tr>`}).join("")}</tbody>`;document.querySelectorAll("#empTable input").forEach(x=>x.onchange=()=>editEmp(Number(x.dataset.i),x.dataset.key,x.value));document.querySelectorAll("#empTable [data-del]").forEach(x=>x.onclick=()=>{empRows().splice(Number(x.dataset.del),1);saveEmp();renderEmp()})}
async function refreshMarket(){const status=document.getElementById("empStatus"),button=document.getElementById("refreshMarket");status.textContent="Bloomberg 조회 중…";button.disabled=true;try{const res=await fetch("/api/emp-market",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({securities:empRows().map(x=>x.security)})}),payload=await res.json();if(!res.ok)throw new Error(payload.error||"조회 실패");state.fx=Number(payload.fx||1);const map=payload.securities||{};empRows().forEach(r=>Object.assign(r,map[r.security]||{}));saveEmp();renderEmp();status.textContent=`${payload.asOf||""} · ${Object.keys(map).length}종목 갱신`}catch(e){status.textContent=`오류: ${e.message}`}finally{button.disabled=false}}
</script><script src="fund_master_storage.js?v=20260929type"></script><script src="fund_market_identifiers.js?v=20260930hedgeassets"></script><script src="fund_snapshot_storage.js?v=20260929snapshot"></script><script src="fund_performance.js?v=20261002etfdb"></script><script src="fund_holding_groups.js?v=20261002assetgroup"></script><script src="fund_allocation_view.js?v=20261008sectorindex"></script><script src="fund_trade_netting.js?v=20261006daynav"></script><script src="etf_db_schema.js?v=20261006gicsmerge"></script><script src="fund_etf_discovery.js?v=20261007missingetf"></script><script src="emp_dashboard_upgrade.js?v=20261008stickyheader"></script></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description="글로벌전략 대시보드 생성")
    parser.add_argument("--data-source", choices=["supabase", "excel"], default="supabase")
    parser.add_argument("--start", help="매매 조회 시작일 YYYY-MM-DD")
    parser.add_argument("--end", help="조회 종료일 YYYY-MM-DD")
    parser.add_argument("--etf-only", action="store_true", help="기존 보유·매매 데이터는 유지하고 ETF DB만 갱신")
    args = parser.parse_args()
    if args.etf_only:
        current = OUTPUT.read_text(encoding="utf-8")
        match = re.search(r"const DATA=(\{.*?\});const state=", current, re.S)
        if not match:
            raise RuntimeError("기존 대시보드 DATA를 찾지 못했습니다")
        data = json.loads(match.group(1))
        data["etfs"] = load_etfs()
        updated = current[:match.start(1)] + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + current[match.end(1):]
        updated = updated.replace("fund_performance.js?v=20261001holdingpl", "fund_performance.js?v=20261002etfdb")
        updated = updated.replace("<script src=\"emp_dashboard_upgrade.js?v=20261002fundcount\"", "<script src=\"etf_db_schema.js?v=20261002etfdb\"></script><script src=\"emp_dashboard_upgrade.js?v=20261002etfdb\"")
        if "fund_allocation_view.js" not in updated:
            updated = updated.replace("<script src=\"etf_db_schema.js", "<script src=\"fund_allocation_view.js?v=20261002regionindex2\"></script><script src=\"etf_db_schema.js")
        if "fund_trade_netting.js" not in updated:
            updated = updated.replace("<script src=\"etf_db_schema.js", "<script src=\"fund_trade_netting.js?v=20261006daynav\"></script><script src=\"etf_db_schema.js")
        updated = updated.replace("emp_dashboard_upgrade.js?v=20261002etfdb", "emp_dashboard_upgrade.js?v=20261002regionindex")
        updated = re.sub(r"fund_allocation_view\.js\?v=[^\"]+", "fund_allocation_view.js?v=20261006gicsko", updated)
        updated = re.sub(r"fund_trade_netting\.js\?v=[^\"]+", "fund_trade_netting.js?v=20261006daynav", updated)
        updated = re.sub(r"etf_db_schema\.js\?v=[^\"]+", "etf_db_schema.js?v=20261006gicsmerge", updated)
        if "fund_etf_discovery.js" not in updated:
            updated = updated.replace("<script src=\"emp_dashboard_upgrade.js", "<script src=\"fund_etf_discovery.js?v=20261007missingetf\"></script><script src=\"emp_dashboard_upgrade.js")
        updated = re.sub(r"fund_allocation_view\.js\?v=[^\"]+", "fund_allocation_view.js?v=20261008sectorindex", updated)
        updated = re.sub(r"emp_dashboard_upgrade\.js\?v=[^\"]+", "emp_dashboard_upgrade.js?v=20261008stickyheader", updated)
        if "global_web_bridge.js" not in updated:
            updated = updated.replace('<script src="emp_dashboard_upgrade.js',
                                      '<script src="global_web_bridge.js?v=20261008"></script><script src="emp_dashboard_upgrade.js')
        OUTPUT.write_text(updated, encoding="utf-8")
    else:
        data = build_data(args.data_source, args.start, args.end)
        document = HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        document = document.replace('<script src="emp_dashboard_upgrade.js',
                                    '<script src="global_web_bridge.js?v=20261008"></script><script src="emp_dashboard_upgrade.js')
        OUTPUT.write_text(document, encoding="utf-8")
    print(OUTPUT)
    print(json.dumps({key: len(data[key]) for key in ("funds", "etfs", "holdings", "trades")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

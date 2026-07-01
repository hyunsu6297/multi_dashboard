from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
TRADE_PARQUET_DIR = ROOT / "parquet_history" / "trades"
HOLDING_PARQUET_DIR = ROOT / "parquet_history" / "holdings"


def read_raw_xlsx(path: str) -> pd.DataFrame:
    return read_raw_xlsx_file(ROOT / path)


def read_raw_xlsx_file(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0, header=1)
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    df = df.dropna(how="all").reset_index(drop=True)
    return df


def as_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.date


def clean_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def num(value, default=0.0) -> float:
    if pd.isna(value):
        return default
    try:
        if math.isfinite(float(value)):
            return float(value)
    except Exception:
        pass
    return default


def match_issuer(name: str, issuer_rules: list[tuple[str, str, str]]) -> tuple[str, str]:
    text = clean_text(name)
    for key, issuer, mid in issuer_rules:
        if key and key in text:
            return issuer, mid
    return "", ""


def maturity_bucket(maturity, base_date) -> str:
    if pd.isna(maturity) or pd.isna(base_date):
        return "기타"
    years = (pd.Timestamp(maturity) - pd.Timestamp(base_date)).days / 365
    if years <= 0.25:
        return "0.0~0.25"
    if years <= 0.5:
        return "0.25~0.5"
    if years <= 1:
        return "0.5~1"
    if years <= 1.5:
        return "1.0~1.5"
    if years <= 2:
        return "1.5~2"
    if years <= 2.5:
        return "2.0~2.5"
    if years <= 3:
        return "2.5~3"
    return "3+"


def money_uk(value: float) -> float:
    return round(value / 100_000_000, 2)


def pct(value: float) -> float:
    return round(value * 100, 4)


def process_holding_frame(
    holdings: pd.DataFrame,
    fund_by_k: dict,
    issuer_rules: list[tuple[str, str, str]],
) -> tuple[list[dict], object]:
    holdings = holdings.copy()
    holdings["보유일"] = as_date(holdings["보유일"])
    holdings["발행일"] = as_date(holdings["발행일"])
    holdings["만기일"] = as_date(holdings["만기일"])
    holdings["예탁원코드"] = holdings["예탁원코드"].map(clean_text)
    holdings = holdings[holdings["예탁원코드"].isin(fund_by_k.keys())].copy()

    base_date = holdings["보유일"].max()
    holding_rows = []
    for _, row in holdings.iterrows():
        info = fund_by_k.get(clean_text(row["예탁원코드"]), {})
        issue, mid = match_issuer(row.get("종목명"), issuer_rules)
        market = clean_text(row.get("시장구분"))
        if market == "정기예금":
            mid = "정기예금"
        elif market == "CD":
            mid = "CD"
        real = num(row.get("평가금")) * num(info.get("지분율"))
        eval_amt = num(row.get("평가금"))
        fund_eval = num(info.get("평가금액"))
        holding_rows.append(
            {
                "date": str(row["보유일"]) if pd.notna(row["보유일"]) else "",
                "fund": clean_text(info.get("펀드명") or row.get("펀드명")),
                "type": clean_text(info.get("구분")),
                "strategy": clean_text(info.get("전략")),
                "manager": clean_text(info.get("운용사")),
                "asset": clean_text(row.get("자산군")),
                "market": market,
                "code": clean_text(row.get("종목코드")),
                "name": clean_text(row.get("종목명")),
                "issuer": issue,
                "mid": mid,
                "rating": clean_text(row.get("신용등급") or "미분류"),
                "maturity": str(row["만기일"]) if pd.notna(row["만기일"]) else "",
                "duration": round(num(row.get("듀레이션")), 4),
                "ytm": round(num(row.get("YTM")), 4),
                "coupon": round(num(row.get("이표율")), 4),
                "qty": num(row.get("수량")),
                "eval": eval_amt,
                "real": real,
                "book": num(info.get("장부가")),
                "fundEval": fund_eval,
                "weight": real / fund_eval if fund_eval else 0,
                "bucket": maturity_bucket(row["만기일"], base_date),
            }
        )
    return holding_rows, base_date


def process_trade_frame(
    trades: pd.DataFrame,
    fund_by_assoc: dict,
    issuer_rules: list[tuple[str, str, str]],
) -> list[dict]:
    trades = trades.copy()
    trades["기준일"] = as_date(trades["기준일"])
    trades["채권만기일"] = as_date(trades["채권만기일"])
    trades["협회펀드코드"] = trades["협회펀드코드"].map(clean_text)
    keep_assets = {"채권", "어음", "선물옵션파생", "펀드", "기타", "해외상품", "현금성자산"}
    trades = trades[trades["협회펀드코드"].isin(fund_by_assoc.keys()) & trades["자산구분"].isin(keep_assets)].copy()

    trade_rows = []
    for _, row in trades.iterrows():
        info = fund_by_assoc.get(clean_text(row["협회펀드코드"]), {})
        asset = clean_text(row.get("자산구분"))
        issue, mid = match_issuer(row.get("종목명"), issuer_rules)
        if asset == "선물옵션파생":
            issue, mid = "파생", "파생"
        elif clean_text(row.get("시장구분")) in {"정기예금", "CD", "레포"} and not mid:
            mid = clean_text(row.get("시장구분"))
        sign = -1 if clean_text(row.get("거래구분")) == "매도" else 1
        base = num(row.get("결제금액")) if asset == "선물옵션파생" else num(row.get("매매수량"))
        trade_rows.append(
            {
                "date": str(row["기준일"]) if pd.notna(row["기준일"]) else "",
                "fund": clean_text(info.get("펀드명") or row.get("펀드명")),
                "type": clean_text(info.get("구분")),
                "strategy": clean_text(info.get("전략")),
                "manager": clean_text(info.get("운용사")),
                "asset": asset,
                "market": clean_text(row.get("시장구분")),
                "code": clean_text(row.get("종목코드")),
                "name": clean_text(row.get("종목명")),
                "side": clean_text(row.get("거래구분")),
                "qty": num(row.get("매매수량")),
                "settle": num(row.get("결제금액")),
                "real": sign * base * num(info.get("지분율")),
                "duration": round(num(row.get("듀레이션")), 4),
                "ytm": round(num(row.get("매매금리")), 4),
                "maturity": str(row["채권만기일"]) if pd.notna(row["채권만기일"]) else "",
                "issuer": issue,
                "mid": mid,
            }
        )
    return trade_rows


def read_trade_parquet_rows() -> list[dict]:
    if not TRADE_PARQUET_DIR.exists():
        return []
    files = sorted(TRADE_PARQUET_DIR.glob("trades_*.parquet"))
    if not files:
        return []
    frames = [pd.read_parquet(path) for path in files]
    df = pd.concat(frames, ignore_index=True)
    if "snapshot_key" in df.columns:
        df = df.drop(columns=["snapshot_key"])
    return df.drop_duplicates().to_dict("records")


def read_holding_parquet_rows() -> list[dict]:
    if not HOLDING_PARQUET_DIR.exists():
        return []
    files = sorted(HOLDING_PARQUET_DIR.glob("holdings_*.parquet"))
    if not files:
        return []
    frames = [pd.read_parquet(path) for path in files]
    df = pd.concat(frames, ignore_index=True)
    if "snapshot_key" in df.columns:
        df = df.drop(columns=["snapshot_key"])
    return df.drop_duplicates().to_dict("records")


def is_holding_base(row: dict) -> bool:
    return (
        row.get("asset") not in {"해외상품", "선물옵션", "선물옵션파생", "채권차입", "채권매도"}
        and row.get("market") not in {"FX스왑", "FX SWAP", "국채선물", "레포", "해외파생"}
        and "국고채" not in str(row.get("mid") or "")
    )


def is_dy_base(row: dict) -> bool:
    return row.get("asset") in {"어음", "채권", "현금성자산"} and row.get("market") in {
        "CD",
        "기업어음",
        "일반",
        "정기예금",
        "현금 및 예금",
    }


def build_kpi_series(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    df = pd.DataFrame(rows)
    series = []
    for date, daily in df.groupby("date"):
        records = daily.to_dict("records")
        h = [r for r in records if is_holding_base(r)]
        dy = [r for r in records if is_dy_base(r)]
        total = sum(num(r.get("real")) for r in h)
        fund_eval = daily[["fund", "fundEval"]].drop_duplicates()["fundEval"].map(num).sum()
        dy_total = sum(num(r.get("real")) for r in dy)
        duration = sum(num(r.get("real")) * num(r.get("duration")) for r in dy) / dy_total if dy_total else 0
        ytm = sum(num(r.get("real")) * num(r.get("ytm")) for r in dy) / dy_total if dy_total else 0
        delta = total * duration / 10000
        series.append(
            {
                "date": date,
                "total": total,
                "eval": fund_eval,
                "lev": total / fund_eval * 100 if fund_eval else 0,
                "duration": duration,
                "delta": delta,
                "ytm": ytm,
            }
        )
    return sorted(series, key=lambda r: r["date"])


def build_data() -> dict:
    fund = pd.read_excel(ROOT / "펀드정보.xlsx", sheet_name=0)
    fund = fund.dropna(how="all").reset_index(drop=True)
    fund["펀드코드"] = fund["펀드코드"].map(clean_text)
    fund["협회코드"] = fund["협회코드"].map(clean_text)

    issuer = pd.read_excel(ROOT / "발행사.xlsx", sheet_name=0).dropna(how="all")
    issuer_rules = []
    for _, row in issuer.iterrows():
        key = clean_text(row.get("발행사"))
        if key:
            issuer_rules.append((key, clean_text(row.get("발행사(변경후)")), clean_text(row.get("중분류"))))
    issuer_rules.sort(key=lambda x: len(x[0]), reverse=True)

    fund_by_k = fund.set_index("펀드코드").to_dict("index")
    fund_by_assoc = fund.set_index("협회코드").to_dict("index")

    holding_rows, base_date = process_holding_frame(read_raw_xlsx("전체펀드 보유현황.xlsx"), fund_by_k, issuer_rules)

    trade_rows = read_trade_parquet_rows()
    if not trade_rows:
        trade_rows = process_trade_frame(read_raw_xlsx("전체펀드 매매현황.xlsx"), fund_by_assoc, issuer_rules)

    fund_rows = []
    for _, row in fund.iterrows():
        fund_rows.append(
            {
                "type": clean_text(row.get("구분")),
                "strategy": clean_text(row.get("전략")),
                "manager": clean_text(row.get("운용사")),
                "fund": clean_text(row.get("펀드명")),
                "code": clean_text(row.get("펀드코드")),
                "assoc": clean_text(row.get("협회코드")),
                "share": num(row.get("지분율")),
                "book": num(row.get("장부가")),
                "eval": num(row.get("평가금액")),
                "aum": num(row.get("펀드AUM")),
                "seller": clean_text(row.get("판매사")),
                "newDate": str(pd.to_datetime(row.get("신규일"), errors="coerce").date()) if pd.notna(row.get("신규일")) else "",
                "closeDate": str(pd.to_datetime(row.get("결산일"), errors="coerce").date()) if pd.notna(row.get("결산일")) else "",
                "swapDate": str(pd.to_datetime(row.get("스왑만기"), errors="coerce").date()) if pd.notna(row.get("스왑만기")) else "",
                "lp1": clean_text(row.get("LP1")),
                "lp1w": num(row.get("LP1비중")),
                "lp2": clean_text(row.get("LP2")),
                "lp2w": num(row.get("lp2비중")),
                "memo": clean_text(row.get("메모")),
            }
        )

    trade_dates = sorted([r["date"] for r in trade_rows if r.get("date")])
    history_holding_rows = read_holding_parquet_rows()
    kpi_series = build_kpi_series(history_holding_rows or holding_rows)
    kpi_history_rows = [
        {
            "date": r.get("date", ""),
            "fund": r.get("fund", ""),
            "type": r.get("type", ""),
            "strategy": r.get("strategy", ""),
            "manager": r.get("manager", ""),
            "mid": r.get("mid", ""),
            "asset": r.get("asset", ""),
            "market": r.get("market", ""),
            "real": r.get("real", 0),
            "duration": r.get("duration", 0),
            "ytm": r.get("ytm", 0),
            "fundEval": r.get("fundEval", 0),
        }
        for r in (history_holding_rows or holding_rows)
    ]
    kpi_dates = [r["date"] for r in kpi_series if r.get("date")]

    return {
        "asOf": str(base_date),
        "generated": str(pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")),
        "holdings": holding_rows,
        "trades": trade_rows,
        "funds": fund_rows,
        "kpiSeries": kpi_series,
        "kpiHistory": kpi_history_rows,
        "kpiMin": kpi_dates[0] if kpi_dates else "",
        "kpiMax": kpi_dates[-1] if kpi_dates else "",
        "tradeMin": trade_dates[0] if trade_dates else "",
        "tradeMax": trade_dates[-1] if trade_dates else "",
        "summary": {
            "holdingRows": len(holding_rows),
            "tradeRows": len(trade_rows),
            "funds": len(fund_rows),
            "rawHoldingRows": int(len(read_raw_xlsx("전체펀드 보유현황.xlsx"))),
            "rawTradeRows": len(trade_rows),
        },
    }


HTML_TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>채권형수익증권 대시보드</title>
<style>
:root{--ink:#073d35;--deep:#005542;--teal:#1f7569;--mint:#cfe9df;--line:#0b6657;--paper:#fbfdfc;--soft:#eef6f4;--blue:#24639a;--red:#d83b3b;--grid:#d9e4df}
*{box-sizing:border-box}body{margin:0;font-family:"Malgun Gothic","Apple SD Gothic Neo",Arial,sans-serif;background:#f6faf8;color:#102b28;font-size:13px}
.app{display:grid;grid-template-columns:244px 1fr;grid-template-rows:auto 1fr;gap:0 10px;min-height:100vh}.topbar{grid-column:1/-1;display:grid;grid-template-columns:420px auto minmax(620px,780px) max-content;align-items:start;gap:14px;padding:6px 10px 0 0}.pageTitle{border-top:2px solid var(--line);border-bottom:12px solid var(--deep);color:var(--ink);font-size:28px;font-weight:800;letter-spacing:0;padding:7px 0 8px 10px;white-space:nowrap}.tabNav{display:flex;align-items:center;gap:6px;padding-top:14px}.tabBtn{border:1.5px solid var(--line);background:#eef7f4;color:var(--ink);border-radius:5px;padding:8px 18px;font-weight:800;cursor:pointer;min-width:74px}.tabBtn.active{background:var(--deep);color:white;box-shadow:inset 0 0 0 1px #b7d8cf}
.side{grid-column:1;grid-row:2;background:white;border-right:2px solid var(--line);padding:8px 8px 16px;position:sticky;top:0;height:calc(100vh - 76px);overflow:auto}
.asof{display:grid;grid-template-columns:52px 1fr;gap:6px 8px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:7px 2px;font-size:12px}.resetAll{grid-column:1/-1;border:1px solid var(--line);background:#eef7f4;color:var(--ink);border-radius:4px;padding:4px 8px;cursor:pointer;font-weight:700}.filter{border:1.5px solid var(--line);border-radius:5px;padding:6px;margin:8px 0;background:#fcfffe}.filterHead{display:flex;align-items:center;justify-content:space-between;margin:0 0 6px;gap:4px}.filter h3{margin:0;color:var(--ink);font-size:12px;flex:1}.miniAll,.multiBtn{border:1px solid #b6d1ca;background:#e9f2ef;color:var(--ink);border-radius:3px;padding:2px 6px;font-size:10px;cursor:pointer}.multiBtn.active{background:var(--deep);border-color:var(--line);color:white}.chips{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px}.chip{border:0;background:#2a7569;color:white;border-radius:3px;padding:4px 6px;text-align:left;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer}.chip.active{background:#092f2a;color:#fff;box-shadow:inset 0 0 0 2px #9ad0c1}.chip.disabled{background:#d9e1de;color:#7b8f8a;cursor:not-allowed}.main{grid-column:2;grid-row:2;padding:6px 10px 18px;overflow:hidden}.memo,.filterInfo{border:1.5px solid var(--line);background:white;border-radius:0 0 6px 6px;min-height:54px}.filterInfo{padding:7px 9px;font-size:11px;line-height:1.45;width:max-content;max-width:560px}.filterInfo b{display:block;color:var(--ink);font-size:12px;margin-bottom:3px}.filterInfo span{display:block;white-space:nowrap}.memo table{width:100%;border-collapse:collapse;font-size:11px}.memo th{background:var(--deep);color:white;border:1px solid #111;padding:2px 5px}.memo td{border:1px solid #222;height:17px;text-align:center}.memoNote{border-top:1px solid #222;padding:5px 7px;font-size:11px;min-height:24px;text-align:left}
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin:8px 0}.kpi{border:1.5px solid var(--line);border-radius:6px;background:white;padding:9px 12px;min-height:62px}.kpi span{display:block;color:var(--ink);font-weight:800;font-size:12px}.kpi b{display:block;text-align:right;color:#005042;font-size:21px;margin-top:10px}.tradeRange{display:flex;align-items:center;justify-content:flex-end;gap:8px;margin:0 0 8px;font-size:12px;color:var(--ink);font-weight:800}.dateInput{border:1px solid #9abeb6;border-radius:4px;padding:3px 7px;font-size:12px;color:#102b28;background:white}.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;align-items:start}.detailGrid{grid-template-columns:1fr 1fr}.tabPane:not(.active){display:none}.tabPane.active.grid{display:grid}.panel{border:1.5px solid var(--line);border-radius:16px;background:white;padding:10px;min-width:0;overflow:hidden}.panel h2{margin:0 0 7px;color:var(--ink);font-size:13px;display:flex;align-items:center;gap:5px}.panel h2:before{content:"";width:18px;height:12px;background:linear-gradient(90deg,#458c7b,#b7d8cf);border:1px solid var(--line);border-radius:8px;display:inline-block}.wide{grid-column:1 / -1}.tablewrap{overflow:auto;max-height:310px}.topPanel{min-height:468px}.topPanel .tablewrap{overflow-x:auto;overflow-y:visible;max-height:none}.summaryTall{height:331px}.detailPanel{height:calc(100vh - 188px);min-height:720px;display:flex;flex-direction:column}.detailPanel .tablewrap{flex:1;min-height:0;max-height:none}.side .filter:nth-last-child(1) .chips{grid-template-columns:repeat(2,minmax(0,1fr))}
table.data{width:100%;border-collapse:collapse;font-size:11px;white-space:nowrap}.data th{position:sticky;top:0;background:var(--teal);color:white;padding:3px 5px;border-right:1px solid #d8eee8;cursor:pointer;user-select:none}.data th.sortAsc:after{content:" ▲";font-size:9px}.data th.sortDesc:after{content:" ▼";font-size:9px}.data td{padding:2px 5px;border-bottom:1px solid #e6efec}.data tr:nth-child(even){background:#f7fbfa}.num{text-align:right}.neg{color:var(--red)}.tag{background:#064e43;color:white;border-radius:2px;padding:1px 4px}.chart{height:300px}.comboSvg{width:100%;height:360px}.kpiChart{width:100%;height:430px}.analysisPanel{min-height:560px}.analysisControls{display:flex;align-items:center;gap:10px;margin:4px 0 12px;font-weight:800;color:var(--ink)}.analysisControls label{display:flex;align-items:center;gap:6px}.bar{height:18px;margin:6px 0;position:relative}.bar i{display:block;height:100%;background:var(--deep)}.bar b{position:absolute;left:calc(var(--w,0%) + 6px);top:2px;background:transparent;color:var(--deep);font-size:10px;padding:1px 3px;white-space:nowrap}.ratingRow{display:grid;grid-template-columns:42px 1fr;align-items:center;gap:8px;margin:9px 0;font-weight:700}.svgbox{width:100%;height:260px}.sectorPanel .svgbox{height:282px}.controls{display:flex;align-items:center;gap:8px;margin-bottom:6px;position:relative}.search{border:1px solid #9abeb6;border-radius:4px;padding:4px 7px;min-width:220px}.btn{border:1px solid var(--line);background:#eef7f4;color:var(--ink);border-radius:4px;padding:4px 8px;cursor:pointer}.suggestions{position:absolute;top:28px;left:0;right:70px;z-index:5;background:white;border:1px solid var(--line);border-radius:4px;box-shadow:0 4px 10px rgba(0,0,0,.08);max-height:150px;overflow:auto}.suggestion{padding:5px 8px;font-size:11px;cursor:pointer}.suggestion.active,.suggestion:hover{background:var(--deep);color:white}.foot{margin-top:8px;color:#5a706c;font-size:11px;text-align:right}
.panelTitleRow{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:0 0 7px}.panelTitleRow h2{margin:0}.tradeRange.compact{margin:0;justify-content:flex-end;gap:6px;white-space:nowrap}.tradeRange.compact .dateInput{width:122px}.analysisGrid{display:grid;grid-template-columns:1fr 1fr;gap:8px;align-items:start}.analysisPanel{min-height:360px}.analysisPanel .kpiChart{height:310px}.analysisControls{margin:0;gap:6px;white-space:nowrap}.analysisControls .dateInput{width:122px}
@media(max-width:1200px){.app{grid-template-columns:1fr;grid-template-rows:auto auto auto}.topbar{grid-template-columns:1fr}.tabNav{padding:0 0 6px 10px}.side{grid-column:1;grid-row:2;position:relative;height:auto;border-right:0;border-bottom:2px solid var(--line)}.main{grid-column:1;grid-row:3}.grid,.detailGrid{grid-template-columns:1fr}.wide{grid-column:auto;grid-row:auto}.kpis{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body>
<div class="app">
  <header class="topbar">
    <div class="pageTitle">채권형수익증권 대시보드</div>
    <nav class="tabNav" aria-label="화면 선택">
      <button class="tabBtn active" data-tab="summary" type="button">요약</button>
      <button class="tabBtn" data-tab="detail" type="button">상세</button>
      <button class="tabBtn" data-tab="analysis" type="button">시계열분석</button>
    </nav>
    <div class="memo"><table><thead><tr><th>펀드명</th><th>전략</th><th>AUM(억)</th><th>지분율</th><th>신규일</th><th>결산일</th><th>스왑만기</th><th>판매사</th><th>LP1</th><th>LP1비중</th><th>LP2</th><th>LP2비중</th></tr></thead><tbody id="fundMini"></tbody></table><div id="fundMemo" class="memoNote"></div></div>
    <div class="filterInfo"><b>패널별 편입자산 기준</b><span>보유: 해외상품/선물옵션/채권차입/채권매도, FX스왑/국채선물/레포/해외파생, 국고채 제외</span><span>듀레이션·YTM: 어음/채권/현금성자산, CD/기업어음/일반/정기예금/현금 및 예금</span><span>중분류·신용등급·거래내역은 원본 기준별 별도 필터 적용</span></div>
  </header>
  <aside class="side">
    <div class="asof"><b>기준일</b><span id="asOf"></span><button id="resetAll" class="resetAll">전체 초기화</button></div>
    <div id="filters"></div>
  </aside>
  <main class="main">
    <section class="kpis">
      <div class="kpi"><span>총 익스포저</span><b id="kTotal"></b></div>
      <div class="kpi"><span>당행 평가액</span><b id="kEval"></b></div>
      <div class="kpi"><span>레버리지</span><b id="kLev"></b></div>
      <div class="kpi"><span>듀레이션</span><b id="kDur"></b></div>
      <div class="kpi"><span>델타</span><b id="kDelta"></b></div>
      <div class="kpi"><span>YTM</span><b id="kYtm"></b></div>
    </section>
    <section id="summaryTab" class="grid tabPane active">
      <div class="panel topPanel"><h2>주요보유내역(TOP20)</h2><div class="tablewrap"><table class="data" id="topHold"></table></div></div>
      <div class="panel topPanel"><div class="panelTitleRow"><h2>주요매매내역</h2><div class="tradeRange compact"><span>매매기간</span><input class="dateInput tradeStartInput" type="date" /><span>~</span><input class="dateInput tradeEndInput" type="date" /></div></div><div class="tablewrap"><table class="data" id="tradeTbl"></table></div></div>
      <div class="panel sectorPanel summaryTall"><h2>중분류(섹터)</h2><svg id="pie" class="svgbox" viewBox="0 0 360 250"></svg></div>
      <div class="panel summaryTall"><h2>신용등급</h2><div id="rating" class="chart"></div></div>
      <div class="panel"><h2>만기 구조</h2><svg id="maturity" class="comboSvg" viewBox="0 0 820 360"></svg></div>
      <div class="panel"><h2>발행사별 보유현황</h2><div class="controls"><input id="issuerSearch" class="search" placeholder="발행사 검색" autocomplete="off" /><button id="issuerRun" class="btn">검색</button><div id="issuerChoices" class="suggestions"></div></div><div class="tablewrap"><table class="data" id="issuerTbl"></table></div></div>
    </section>
    <section id="detailTab" class="grid detailGrid tabPane">
      <div class="panel detailPanel"><div class="panelTitleRow"><h2>전체매매내역</h2><div class="tradeRange compact"><span>매매기간</span><input class="dateInput tradeStartInput" type="date" /><span>~</span><input class="dateInput tradeEndInput" type="date" /></div></div><div class="tablewrap"><table class="data" id="allTrade"></table></div></div>
      <div class="panel detailPanel"><h2>전체보유내역</h2><div class="controls"><input id="search" class="search" placeholder="검색" /><button id="reset" class="btn">초기화</button></div><div class="tablewrap"><table class="data" id="allHold"></table></div></div>
    </section>
    <section id="analysisTab" class="analysisGrid tabPane">
      <div class="panel analysisPanel" data-metric="total"><div class="panelTitleRow"><h2>총 익스포저</h2><div class="analysisControls"><input class="dateInput kpiStartInput" data-metric="total" type="date" /><span>~</span><input class="dateInput kpiEndInput" data-metric="total" type="date" /></div></div><svg id="kpiChart_total" class="kpiChart" viewBox="0 0 1000 310"></svg></div>
      <div class="panel analysisPanel" data-metric="eval"><div class="panelTitleRow"><h2>당행 평가액</h2><div class="analysisControls"><input class="dateInput kpiStartInput" data-metric="eval" type="date" /><span>~</span><input class="dateInput kpiEndInput" data-metric="eval" type="date" /></div></div><svg id="kpiChart_eval" class="kpiChart" viewBox="0 0 1000 310"></svg></div>
      <div class="panel analysisPanel" data-metric="lev"><div class="panelTitleRow"><h2>레버리지</h2><div class="analysisControls"><input class="dateInput kpiStartInput" data-metric="lev" type="date" /><span>~</span><input class="dateInput kpiEndInput" data-metric="lev" type="date" /></div></div><svg id="kpiChart_lev" class="kpiChart" viewBox="0 0 1000 310"></svg></div>
      <div class="panel analysisPanel" data-metric="duration"><div class="panelTitleRow"><h2>듀레이션</h2><div class="analysisControls"><input class="dateInput kpiStartInput" data-metric="duration" type="date" /><span>~</span><input class="dateInput kpiEndInput" data-metric="duration" type="date" /></div></div><svg id="kpiChart_duration" class="kpiChart" viewBox="0 0 1000 310"></svg></div>
      <div class="panel analysisPanel" data-metric="delta"><div class="panelTitleRow"><h2>델타</h2><div class="analysisControls"><input class="dateInput kpiStartInput" data-metric="delta" type="date" /><span>~</span><input class="dateInput kpiEndInput" data-metric="delta" type="date" /></div></div><svg id="kpiChart_delta" class="kpiChart" viewBox="0 0 1000 310"></svg></div>
      <div class="panel analysisPanel" data-metric="ytm"><div class="panelTitleRow"><h2>YTM</h2><div class="analysisControls"><input class="dateInput kpiStartInput" data-metric="ytm" type="date" /><span>~</span><input class="dateInput kpiEndInput" data-metric="ytm" type="date" /></div></div><svg id="kpiChart_ytm" class="kpiChart" viewBox="0 0 1000 310"></svg></div>
    </section>
    <div class="foot" id="foot"></div>
  </main>
</div>
<script>
const DATA = __DATA__;
const state = {type:[],strategy:[],mid:[],manager:[],fund:[],multi:{type:false,strategy:false,mid:false,manager:false,fund:false},search:"",issuerSearch:"롯데카드",selectedIssuer:"롯데카드",issuerIndex:0,activeTab:"summary",sorts:{}};
function defaultTradeStart(end){
  if(!end) return "";
  const d=new Date(`${end}T00:00:00`);
  d.setMonth(d.getMonth()-1);
  const y=d.getFullYear(), m=String(d.getMonth()+1).padStart(2,"0"), day=String(d.getDate()).padStart(2,"0");
  return `${y}-${m}-${day}`;
}
state.tradeEnd=DATA.tradeMax || DATA.asOf;
state.tradeStart=defaultTradeStart(state.tradeEnd);
const kpiMetrics=["total","eval","lev","duration","delta","ytm"];
state.kpiRanges=Object.fromEntries(kpiMetrics.map(k=>[k,{start:defaultTradeStart(DATA.kpiMax||DATA.asOf),end:DATA.kpiMax||DATA.asOf}]));
const filterDefs = [
  ["type","구분", d=>d.type],
  ["strategy","전략", d=>d.strategy],
  ["mid","중분류", d=>d.mid],
  ["manager","운용사", d=>d.manager],
  ["fund","펀드명", d=>d.fund]
];
const KRW = v => (v/100000000).toLocaleString("ko-KR",{maximumFractionDigits:0});
const KRWLong = v => {
  const uk = Math.round((v||0)/100000000);
  if (Math.abs(uk) >= 10000) {
    const jo = Math.trunc(uk/10000), rest = Math.abs(uk%10000);
    return `${jo.toLocaleString("ko-KR")}조 ${rest.toLocaleString("ko-KR")}억원`;
  }
  return `${uk.toLocaleString("ko-KR")} 억원`;
};
const KRW2 = v => `${((v||0)/100000000).toLocaleString("ko-KR",{minimumFractionDigits:2,maximumFractionDigits:2})} 억원`;
const one = v => Number(v||0).toLocaleString("ko-KR",{maximumFractionDigits:2});
const fmtPct = v => `${Number(v||0).toLocaleString("ko-KR",{maximumFractionDigits:2})}%`;
const chartDefs = {
  total:["총 익스포저",v=>KRWLong(v),v=>KRW(v)],
  eval:["당행 평가액",v=>KRWLong(v),v=>KRW(v)],
  lev:["레버리지",v=>fmtPct(v),v=>fmtPct(v)],
  duration:["듀레이션",v=>`${one(v)} 년`,v=>one(v)],
  delta:["델타",v=>KRW2(v),v=>KRW(v)],
  ytm:["YTM",v=>fmtPct(v),v=>fmtPct(v)]
};
const by = (arr,key) => arr.reduce((m,d)=>((m[key(d)||"미분류"]=(m[key(d)||"미분류"]||0)+d.real),m),{});
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function filtered(arr){
  return arr.filter(d => (!state.type.length||state.type.includes(d.type))&&(!state.strategy.length||state.strategy.includes(d.strategy))&&(!state.mid.length||state.mid.includes(d.mid))&&(!state.manager.length||state.manager.includes(d.manager))&&(!state.fund.length||state.fund.includes(d.fund)));
}
function tradeDateBase(d){
  return (!state.tradeStart || d.date >= state.tradeStart) && (!state.tradeEnd || d.date <= state.tradeEnd);
}
const inSet = (v, items) => items.includes(v);
const hasAny = (v, items) => items.some(x => String(v||"").includes(x));
function holdingBase(d){
  return !inSet(d.asset,["해외상품","선물옵션","선물옵션파생","채권차입","채권매도"]) &&
    !inSet(d.market,["FX스왑","FX SWAP","국채선물","레포","해외파생"]) &&
    !hasAny(d.mid,["국고채"]);
}
function dyBase(d){
  return inSet(d.asset,["어음","채권","현금성자산"]) &&
    inSet(d.market,["CD","기업어음","일반","정기예금","현금 및 예금"]);
}
function sectorBase(d){
  return inSet(d.asset,["어음","채권","현금성자산"]) &&
    inSet(d.market,["기업어음","일반"]) &&
    !hasAny(d.mid,["국고","국고채","통안"]);
}
function ratingBase(d){
  return inSet(d.asset,["어음","채권"]) &&
    inSet(d.market,["CD","기업어음","일반"]);
}
function tradeBase(d){
  return inSet(d.asset,["채권","어음","펀드","기타","해외상품","현금성자산"]) &&
    d.market !== "레포";
}
function matchesExcept(d, skipKey){
  return (skipKey==="type"||!state.type.length||state.type.includes(d.type))&&(skipKey==="strategy"||!state.strategy.length||state.strategy.includes(d.strategy))&&(skipKey==="mid"||!state.mid.length||state.mid.includes(d.mid))&&(skipKey==="manager"||!state.manager.length||state.manager.includes(d.manager))&&(skipKey==="fund"||!state.fund.length||state.fund.includes(d.fund));
}
function toggleFilter(key,value){
  const list=state[key];
  const idx=list.indexOf(value);
  if(state.multi[key]){
    if(idx>=0) list.splice(idx,1); else list.push(value);
  }else{
    state[key]=idx>=0 ? [] : [value];
  }
}
function sortValue(v){
  if(v == null || v === "") return "";
  if(typeof v === "number") return v;
  const s=String(v).replace(/<[^>]*>/g,"").trim();
  const n=Number(s.replace(/[,%억원조\s]/g,""));
  if(s && !Number.isNaN(n) && /[0-9]/.test(s)) return n;
  return s.toLowerCase();
}
function sortedRows(tableId, cols, rows){
  const sort=state.sorts[tableId];
  if(!sort) return rows;
  const col=cols[sort.idx];
  const getter=col[3] || col[1];
  return [...rows].sort((a,b)=>{
    const av=sortValue(getter(a)), bv=sortValue(getter(b));
    let cmp=0;
    if(typeof av==="number" && typeof bv==="number") cmp=av-bv;
    else cmp=String(av).localeCompare(String(bv),"ko",{numeric:true});
    return sort.dir==="asc" ? cmp : -cmp;
  });
}
function table(el, cols, rows){
  const tableId=el.id, sort=state.sorts[tableId], data=sortedRows(tableId,cols,rows);
  el.innerHTML = `<thead><tr>${cols.map((c,i)=>`<th data-col="${i}" class="${sort&&sort.idx===i ? (sort.dir==="asc"?"sortAsc":"sortDesc") : ""}">${c[0]}</th>`).join("")}</tr></thead><tbody>`+
    data.map(r=>`<tr>${cols.map(c=>`<td class="${c[2]||""}">${c[1](r)}</td>`).join("")}</tr>`).join("")+"</tbody>";
  el.querySelectorAll("th").forEach(th=>th.onclick=()=>{
    const idx=Number(th.dataset.col), cur=state.sorts[tableId];
    state.sorts[tableId]={idx,dir:cur&&cur.idx===idx&&cur.dir==="desc"?"asc":"desc"};
    table(el,cols,rows);
  });
}
function renderFilters(){
  const box=document.getElementById("filters");
  box.innerHTML=filterDefs.map(([key,title,fn])=>{
    const enabled=new Set(DATA.holdings.filter(d=>matchesExcept(d,key)).map(fn).filter(Boolean));
    const vals=[...new Set(DATA.holdings.map(fn).filter(Boolean))].sort((a,b)=>{
      if(key==="fund"){
        const ae=enabled.has(a), be=enabled.has(b);
        if(ae!==be) return ae ? -1 : 1;
      }
      return a.localeCompare(b,"ko");
    }).slice(0,120);
    return `<div class="filter"><div class="filterHead"><h3>${title}</h3><button class="multiBtn ${state.multi[key]?"active":""}" data-key="${key}" data-action="multi">중복</button><button class="miniAll" data-key="${key}" data-action="clear">해제</button></div><div class="chips">${vals.map(v=>{const active=state[key].includes(v), disabled=!enabled.has(v)&&!active; return `<button title="${v}" class="chip ${active?"active":""} ${disabled?"disabled":""}" data-key="${key}" data-v="${esc(v)}" ${disabled?"disabled":""}>${esc(v)}</button>`}).join("")}</div></div>`;
  }).join("");
  box.querySelectorAll("button").forEach(b=>b.onclick=()=>{
    if(b.dataset.action==="multi"){
      state.multi[b.dataset.key]=!state.multi[b.dataset.key];
      if(!state.multi[b.dataset.key] && state[b.dataset.key].length>1) state[b.dataset.key]=state[b.dataset.key].slice(0,1);
    }else if(b.dataset.action==="clear"){
      state[b.dataset.key]=[];
      state.multi[b.dataset.key]=false;
    }else if(b.dataset.v){
      toggleFilter(b.dataset.key,b.dataset.v);
    }
    render();
  });
}
function aggregate(){
  const h=filtered(DATA.holdings).filter(holdingBase), dy=filtered(DATA.holdings).filter(dyBase), t=filtered(DATA.trades).filter(tradeBase);
  const total=h.reduce((s,d)=>s+d.real,0), fundEval=[...new Map(filtered(DATA.funds).map(f=>[f.fund,f])).values()].reduce((s,f)=>s+f.eval,0);
  const dyTotal=dy.reduce((s,d)=>s+d.real,0);
  const dur=dyTotal?dy.reduce((s,d)=>s+d.real*d.duration,0)/dyTotal:0, ytm=dyTotal?dy.reduce((s,d)=>s+d.real*d.ytm,0)/dyTotal:0;
  const delta=total*dur/10000;
  document.getElementById("kTotal").textContent=KRWLong(total);
  document.getElementById("kEval").textContent=KRWLong(fundEval);
  document.getElementById("kLev").textContent=fundEval?`${Math.round(total/fundEval*100).toLocaleString("ko-KR")}%`:"-";
  document.getElementById("kDur").textContent=`${Number(dur||0).toLocaleString("ko-KR",{minimumFractionDigits:2,maximumFractionDigits:2})} 년`;
  document.getElementById("kDelta").textContent=KRW2(delta);
  document.getElementById("kYtm").textContent=fmtPct(ytm);
}
function renderTables(){
  const h=filtered(DATA.holdings).filter(holdingBase), t=filtered(DATA.trades).filter(tradeBase).filter(tradeDateBase);
  const top=[...h].sort((a,b)=>(a.maturity||"9999").localeCompare(b.maturity||"9999")).slice(0,20);
  table(document.getElementById("topHold"), [["만기일",d=>d.maturity],["펀드명",d=>d.fund],["자산군",d=>d.asset],["중분류",d=>d.mid],["발행사",d=>d.issuer],["등급",d=>d.rating],["실보유",d=>KRW(d.real),"num"],["펀드보유",d=>KRW(d.fundEval),"num"],["비중",d=>fmtPct(d.weight*100),"num"],["듀레이션",d=>one(d.duration),"num"],["YTM",d=>one(d.ytm),"num"]], top);
  const latestTrade=[...t].sort((a,b)=>b.date.localeCompare(a.date)).slice(0,20);
  table(document.getElementById("tradeTbl"), [["기준일",d=>d.date],["펀드명",d=>d.fund],["자산구분",d=>d.asset],["발행사",d=>d.issuer],["거래",d=>d.side],["만기일",d=>d.maturity],["듀레이션",d=>one(d.duration),"num"],["금리",d=>one(d.ytm),"num"],["금액(실보유)",d=>`<span class="${d.real<0?"neg":""}">${KRW(d.real)}</span>`,"num"],["금액(원본)",d=>KRW(d.settle),"num"]], latestTrade);
  const allTrade=[...t].sort((a,b)=>b.date.localeCompare(a.date)).slice(0,500);
  table(document.getElementById("allTrade"), [["기준일",d=>d.date],["펀드명",d=>d.fund],["자산구분",d=>d.asset],["중분류",d=>d.mid],["발행사",d=>d.issuer],["거래",d=>d.side],["종목명",d=>d.name],["만기일",d=>d.maturity],["듀레이션",d=>one(d.duration),"num"],["금리",d=>one(d.ytm),"num"],["금액(실보유)",d=>`<span class="${d.real<0?"neg":""}">${KRW(d.real)}</span>`,"num"],["금액(원본)",d=>KRW(d.settle),"num"]], allTrade);
  const q=state.search.toLowerCase();
  const all=h.filter(d=>!q||[d.fund,d.name,d.issuer,d.mid,d.rating].join(" ").toLowerCase().includes(q)).slice(0,500);
  table(document.getElementById("allHold"), [["펀드명",d=>d.fund],["자산군",d=>d.asset],["중분류",d=>`<b>${d.mid||""}</b>`],["발행사",d=>d.issuer],["신용등급",d=>d.rating],["만기일",d=>d.maturity],["실보유(억)",d=>KRW(d.real),"num"]], all);
  const selectedFund=state.fund.length===1 ? DATA.funds.find(f=>f.fund===state.fund[0]) : null;
  document.getElementById("fundMini").innerHTML=selectedFund ? `<tr><td>${esc(selectedFund.fund)}</td><td>${esc(selectedFund.strategy)}</td><td class="num">${KRW(selectedFund.aum)}</td><td class="num">${fmtPct(selectedFund.share*100)}</td><td>${selectedFund.newDate}</td><td>${selectedFund.closeDate}</td><td>${selectedFund.swapDate}</td><td>${esc(selectedFund.seller)}</td><td>${esc(selectedFund.lp1)}</td><td class="num">${fmtPct(selectedFund.lp1w*100)}</td><td>${esc(selectedFund.lp2)}</td><td class="num">${selectedFund.lp2w?fmtPct(selectedFund.lp2w*100):""}</td></tr>` : "";
  document.getElementById("fundMemo").textContent=selectedFund ? `특이사항: ${selectedFund.memo || "-"}` : "";
  renderIssuerPanel(h);
}
function renderMaturity(){
  const order=["0.0~0.25","0.25~0.5","0.5~1","1.0~1.5","1.5~2","2.0~2.5","2.5~3","3+"];
  const map=by(filtered(DATA.holdings).filter(holdingBase),d=>d.bucket), total=Object.values(map).reduce((a,b)=>a+b,0)||1, max=Math.max(...Object.values(map),1);
  const values=order.map(k=>map[k]||0), maxAmt=Math.max(...values,1), left=58, right=760, top=30, base=286, w=(right-left)/order.length, maxPct=Math.max(...values.map(v=>v/total),0.01);
  const yAmt=v=>base-(v/maxAmt)*(base-top), yPct=v=>base-((v/total)/maxPct)*(base-top), points=values.map((v,i)=>`${left+w*i+w/2},${yPct(v)}`).join(" ");
  let svg=`<line x1="${left}" y1="${base}" x2="${right}" y2="${base}" stroke="#9fb8b2"/><line x1="${left}" y1="${top}" x2="${left}" y2="${base}" stroke="#9fb8b2"/><line x1="${right}" y1="${top}" x2="${right}" y2="${base}" stroke="#9fb8b2"/>`;
  [0,.25,.5,.75,1].forEach(p=>{const y=base-(base-top)*p, amount=maxAmt*p, ratio=maxPct*p*100; svg+=`<line x1="${left}" y1="${y}" x2="${right}" y2="${y}" stroke="#d7e2df"/><text x="${left-8}" y="${y+4}" text-anchor="end" font-size="11" fill="#6b7d79">${KRW(amount)}</text><text x="${right+8}" y="${y+4}" font-size="11" fill="#6b7d79">${ratio.toFixed(1)}%</text>`});
  values.forEach((v,i)=>{const x=left+w*i+w*.22, bw=w*.36, h=base-yAmt(v), drawH=v>0?Math.max(h,26):0, pct=v/total*100, labelY=base-drawH/2+4; svg+=`<rect x="${x}" y="${base-drawH}" width="${bw}" height="${drawH}" fill="#8bb8ad"/>${v>0?`<rect x="${x+bw/2-24}" y="${labelY-13}" width="48" height="20" fill="#005542"/><text x="${x+bw/2}" y="${labelY+1}" text-anchor="middle" font-size="12" font-weight="700" fill="#fff">${KRW(v)}</text>`:""}<text x="${left+w*i+w/2}" y="326" text-anchor="middle" font-size="12">${order[i]}</text><text x="${left+w*i+w/2}" y="${Math.max(top+12,yPct(v)-15)}" text-anchor="middle" font-size="12" font-weight="700">${pct.toFixed(1)}%</text>`});
  svg+=`<polyline points="${points}" fill="none" stroke="#005542" stroke-width="4"/>`+values.map((v,i)=>`<circle cx="${left+w*i+w/2}" cy="${yPct(v)}" r="5" fill="#005542"/>`).join("");
  svg+=`<text x="${left}" y="18" font-size="12" fill="#6b7d79">금액(억)</text><text x="${right}" y="18" text-anchor="end" font-size="12" fill="#005542">비중</text>`;
  document.getElementById("maturity").innerHTML=svg;
}
function renderRating(){
  const order=["RF","AAA","AA+","AA","AA-","A1","미분류"];
  const map=by(filtered(DATA.holdings).filter(ratingBase),d=>d.rating), total=Object.values(map).reduce((a,b)=>a+b,0)||1, max=Math.max(...order.map(k=>map[k]||0),1);
  document.getElementById("rating").innerHTML=order.map(k=>{const v=map[k]||0, w=v/max*88; return `<div class="ratingRow"><span>${k}</span><div class="bar" style="--w:${w}%"><i style="width:${w}%"></i><b>${(v/total*100).toFixed(1)}%</b></div></div>`}).join("");
}
function renderIssuerPanel(rows){
  const issuers=[...new Set(rows.map(d=>d.issuer).filter(Boolean))].sort((a,b)=>a.localeCompare(b,"ko"));
  const q=state.issuerSearch.toLowerCase();
  const shown=(q && state.selectedIssuer!==state.issuerSearch) ? issuers.filter(v=>v.toLowerCase().includes(q)).slice(0,10) : [];
  if(state.issuerIndex>=shown.length) state.issuerIndex=0;
  document.getElementById("issuerChoices").innerHTML=shown.map((v,i)=>`<div title="${esc(v)}" class="suggestion ${i===state.issuerIndex?"active":""}" data-issuer="${esc(v)}">${esc(v)}</div>`).join("");
  document.querySelectorAll("#issuerChoices .suggestion").forEach(el=>el.onclick=()=>selectIssuer(el.dataset.issuer));
  const selected=state.selectedIssuer && issuers.includes(state.selectedIssuer) ? state.selectedIssuer : null;
  const issuerRows=selected ? rows.filter(d=>d.issuer===selected).sort((a,b)=>(a.maturity||"9999").localeCompare(b.maturity||"9999")).slice(0,20) : [];
  table(document.getElementById("issuerTbl"), [["펀드명",d=>d.fund],["자산군",d=>d.asset],["만기일",d=>d.maturity],["듀레이션",d=>one(d.duration),"num"],["YTM",d=>one(d.ytm),"num"],["실보유",d=>KRW(d.real),"num"],["펀드보유액",d=>KRW(d.fundEval),"num"]], issuerRows);
}
function selectIssuer(name){
  state.selectedIssuer=name;
  state.issuerSearch=name;
  state.issuerIndex=0;
  document.getElementById("issuerSearch").value=name;
  renderTables();
}
function runIssuerSearch(){
  const rows=filtered(DATA.holdings).filter(holdingBase);
  const issuers=[...new Set(rows.map(d=>d.issuer).filter(Boolean))].sort((a,b)=>a.localeCompare(b,"ko"));
  const q=state.issuerSearch.toLowerCase();
  const match=issuers.find(v=>v.toLowerCase()===q) || issuers.find(v=>v.toLowerCase().includes(q));
  if(match) selectIssuer(match);
}
function piePath(cx,cy,r,a0,a1){const x0=cx+r*Math.cos(a0),y0=cy+r*Math.sin(a0),x1=cx+r*Math.cos(a1),y1=cy+r*Math.sin(a1);return `M${cx},${cy} L${x0},${y0} A${r},${r} 0 ${a1-a0>Math.PI?1:0} 1 ${x1},${y1} Z`;}
function renderPie(){
  const map=by(filtered(DATA.holdings).filter(sectorBase),d=>d.mid||"미분류"), entries=Object.entries(map).sort((a,b)=>b[1]-a[1]).slice(0,7), total=entries.reduce((s,d)=>s+d[1],0)||1, colors=["#5d998d","#064f43","#38e0c5","#d8e3e0","#b7ddcf","#d9e9f7","#8bbfb1"];
  let a=-Math.PI/2; let svg="";
  entries.forEach(([k,v],i)=>{const a1=a+v/total*Math.PI*2, share=v/total, mid=(a+a1)/2, outside=share<0.075; const tx=180+(outside?132:82)*Math.cos(mid), ty=125+(outside?112:82)*Math.sin(mid), label=`${k}, ${(share*100).toFixed(1)}%`, w=Math.max(42,label.length*7.2); svg+=`<path d="${piePath(180,125,112,a,a1)}" fill="${colors[i%colors.length]}" stroke="white"/>`; if(outside){const x2=180+116*Math.cos(mid), y2=125+96*Math.sin(mid); svg+=`<line x1="${180+102*Math.cos(mid)}" y1="${125+102*Math.sin(mid)}" x2="${x2}" y2="${y2}" stroke="#005542"/><line x1="${x2}" y1="${y2}" x2="${tx}" y2="${ty}" stroke="#005542"/>`;} svg+=`<rect x="${tx-w/2}" y="${ty-13}" width="${w}" height="20" fill="#005542"/><text x="${tx}" y="${ty+1}" text-anchor="middle" fill="white" font-size="11" font-weight="700">${esc(label)}</text>`; a=a1;});
  document.getElementById("pie").innerHTML=svg;
}
function kpiRowsForMetric(metric){
  const range=state.kpiRanges[metric];
  const rows=filtered(DATA.kpiHistory).filter(d=>(!range.start||d.date>=range.start)&&(!range.end||d.date<=range.end));
  const grouped=new Map();
  rows.forEach(r=>{if(!grouped.has(r.date)) grouped.set(r.date,[]); grouped.get(r.date).push(r);});
  return [...grouped.entries()].sort((a,b)=>a[0].localeCompare(b[0])).map(([date,daily])=>{
    const h=daily.filter(holdingBase), dy=daily.filter(dyBase);
    const total=h.reduce((s,d)=>s+Number(d.real||0),0);
    const fundEval=[...new Map(daily.map(d=>[d.fund,d.fundEval])).values()].reduce((s,v)=>s+Number(v||0),0);
    const dyTotal=dy.reduce((s,d)=>s+Number(d.real||0),0);
    const duration=dyTotal?dy.reduce((s,d)=>s+Number(d.real||0)*Number(d.duration||0),0)/dyTotal:0;
    const ytm=dyTotal?dy.reduce((s,d)=>s+Number(d.real||0)*Number(d.ytm||0),0)/dyTotal:0;
    return {date,total,eval:fundEval,lev:fundEval?total/fundEval*100:0,duration,delta:total*duration/10000,ytm};
  });
}
function renderKpiChart(metric){
  const def=chartDefs[metric], rows=kpiRowsForMetric(metric), svgEl=document.getElementById(`kpiChart_${metric}`);
  if(!rows.length){svgEl.innerHTML=`<text x="500" y="160" text-anchor="middle" fill="#6b7d79" font-size="16">선택한 기간에 데이터가 없습니다.</text>`;return;}
  const values=rows.map(d=>Number(d[metric]||0)), min=Math.min(...values), max=Math.max(...values), pad=(max-min)*.12 || Math.max(Math.abs(max)*.12,1);
  const yMin=min-pad, yMax=max+pad, left=76, right=964, top=28, base=244, w=(right-left)/Math.max(rows.length-1,1);
  const x=i=>left+w*i, y=v=>base-((v-yMin)/(yMax-yMin))*(base-top);
  let svg=`<rect x="0" y="0" width="1000" height="310" fill="#fff"/>`;
  [0,.5,1].forEach(p=>{const yy=base-(base-top)*p, val=yMin+(yMax-yMin)*p; svg+=`<line x1="${left}" y1="${yy}" x2="${right}" y2="${yy}" stroke="#d7e2df"/><text x="${left-10}" y="${yy+4}" text-anchor="end" font-size="11" fill="#6b7d79">${def[2](val)}</text>`});
  const points=rows.map((d,i)=>`${x(i)},${y(Number(d[metric]||0))}`).join(" ");
  svg+=`<line x1="${left}" y1="${base}" x2="${right}" y2="${base}" stroke="#9fb8b2"/><line x1="${left}" y1="${top}" x2="${left}" y2="${base}" stroke="#9fb8b2"/><polyline points="${points}" fill="none" stroke="#005542" stroke-width="4"/>`;
  rows.forEach((d,i)=>{const xx=x(i), yy=y(Number(d[metric]||0)); svg+=`<circle cx="${xx}" cy="${yy}" r="5" fill="#005542"><title>${d.date} ${def[1](d[metric])}</title></circle>`; if(i===0||i===rows.length-1||rows.length<=8||i%Math.ceil(rows.length/5)===0){svg+=`<text x="${xx}" y="278" text-anchor="middle" font-size="11" fill="#334b47">${d.date.slice(5)}</text>`;}});
  const last=rows[rows.length-1]; svg+=`<rect x="${right-162}" y="14" width="150" height="28" rx="4" fill="#eef7f4" stroke="#0b6657"/><text x="${right-87}" y="33" text-anchor="middle" font-size="12" font-weight="800" fill="#005542">${def[1](last[metric])}</text>`;
  svgEl.innerHTML=svg;
}
function renderKpiCharts(){
  kpiMetrics.forEach(renderKpiChart);
}
function render(){
  renderFilters(); aggregate(); renderTables(); renderMaturity(); renderRating(); renderPie(); renderKpiCharts();
  document.getElementById("foot").textContent=`보유 ${DATA.summary.holdingRows.toLocaleString()}건 / 매매 ${DATA.summary.tradeRows.toLocaleString()}건 / 펀드 ${DATA.summary.funds.toLocaleString()}개 · 생성 ${DATA.generated}`;
}
function setTab(name){
  state.activeTab=name;
  document.querySelectorAll(".tabBtn").forEach(btn=>btn.classList.toggle("active",btn.dataset.tab===name));
  document.getElementById("summaryTab").classList.toggle("active",name==="summary");
  document.getElementById("detailTab").classList.toggle("active",name==="detail");
  document.getElementById("analysisTab").classList.toggle("active",name==="analysis");
}
document.getElementById("asOf").textContent=DATA.asOf;
document.getElementById("issuerSearch").value=state.issuerSearch;
function syncTradeInputs(){
  document.querySelectorAll(".tradeStartInput").forEach(el=>{el.min=DATA.tradeMin||"";el.max=DATA.tradeMax||"";el.value=state.tradeStart;});
  document.querySelectorAll(".tradeEndInput").forEach(el=>{el.min=DATA.tradeMin||"";el.max=DATA.tradeMax||"";el.value=state.tradeEnd;});
}
syncTradeInputs();
document.querySelectorAll(".kpiStartInput").forEach(el=>{const m=el.dataset.metric;el.min=DATA.kpiMin||"";el.max=DATA.kpiMax||"";el.value=state.kpiRanges[m].start;});
document.querySelectorAll(".kpiEndInput").forEach(el=>{const m=el.dataset.metric;el.min=DATA.kpiMin||"";el.max=DATA.kpiMax||"";el.value=state.kpiRanges[m].end;});
document.querySelectorAll(".tabBtn").forEach(btn=>btn.onclick=()=>setTab(btn.dataset.tab));
document.querySelectorAll(".tradeStartInput").forEach(el=>el.onchange=e=>{state.tradeStart=e.target.value;syncTradeInputs();renderTables();});
document.querySelectorAll(".tradeEndInput").forEach(el=>el.onchange=e=>{state.tradeEnd=e.target.value;syncTradeInputs();renderTables();});
document.querySelectorAll(".kpiStartInput").forEach(el=>el.onchange=e=>{const m=e.target.dataset.metric;state.kpiRanges[m].start=e.target.value;renderKpiChart(m);});
document.querySelectorAll(".kpiEndInput").forEach(el=>el.onchange=e=>{const m=e.target.dataset.metric;state.kpiRanges[m].end=e.target.value;renderKpiChart(m);});
document.getElementById("search").oninput=e=>{state.search=e.target.value;renderTables();};
document.getElementById("reset").onclick=()=>{state.search="";document.getElementById("search").value="";renderTables();};
document.getElementById("issuerSearch").oninput=e=>{state.issuerSearch=e.target.value;state.selectedIssuer=null;state.issuerIndex=0;renderTables();};
document.getElementById("issuerSearch").onkeydown=e=>{
  const count=document.querySelectorAll("#issuerChoices .suggestion").length;
  if(e.key==="ArrowDown"&&count){e.preventDefault();state.issuerIndex=(state.issuerIndex+1)%count;renderTables();}
  if(e.key==="ArrowUp"&&count){e.preventDefault();state.issuerIndex=(state.issuerIndex-1+count)%count;renderTables();}
  if(e.key==="Enter"){e.preventDefault();const item=document.querySelectorAll("#issuerChoices .suggestion")[state.issuerIndex]; if(item) selectIssuer(item.dataset.issuer); else runIssuerSearch();}
};
document.getElementById("issuerRun").onclick=runIssuerSearch;
document.getElementById("resetAll").onclick=()=>{state.type=[];state.strategy=[];state.mid=[];state.manager=[];state.fund=[];state.multi={type:false,strategy:false,mid:false,manager:false,fund:false};state.search="";state.tradeEnd=DATA.tradeMax||DATA.asOf;state.tradeStart=defaultTradeStart(state.tradeEnd);state.kpiRanges=Object.fromEntries(kpiMetrics.map(k=>[k,{start:defaultTradeStart(DATA.kpiMax||DATA.asOf),end:DATA.kpiMax||DATA.asOf}]));state.issuerSearch="롯데카드";state.selectedIssuer="롯데카드";state.issuerIndex=0;document.getElementById("search").value="";syncTradeInputs();document.querySelectorAll(".kpiStartInput").forEach(el=>{const m=el.dataset.metric;el.value=state.kpiRanges[m].start;});document.querySelectorAll(".kpiEndInput").forEach(el=>{const m=el.dataset.metric;el.value=state.kpiRanges[m].end;});document.getElementById("issuerSearch").value=state.issuerSearch;render();};
async function hydrateManualData(){
  const client=window.parent!==window&&window.parent.dashboardSupabase;if(!client)return;
  const load=async key=>{let out=[];for(let start=0;;start+=1000){const {data,error}=await client.from("manual_file_rows").select("payload").eq("domain","bond").eq("file_key",key).order("row_no").range(start,start+999);if(error)throw error;out.push(...data.map(x=>x.payload));if(data.length<1000)return out;}};
  try{
    const [fundRows,issuerRows]=await Promise.all([load("fund_info"),load("issuer")]);
    if(fundRows.length){const oldFunds=[...DATA.funds],next=fundRows.map(x=>({type:x["구분"]||"",strategy:x["전략"]||"",manager:x["운용사"]||"",fund:x["펀드명"]||"",code:String(x["펀드코드"]||""),assoc:String(x["협회코드"]||""),share:Number(x["지분율"]||0),book:Number(x["장부가"]||0),eval:Number(x["평가금액"]||0),aum:Number(x["펀드AUM"]||0),seller:x["판매사"]||"",newDate:String(x["신규일"]||"").slice(0,10),closeDate:String(x["결산일"]||"").slice(0,10),swapDate:String(x["스왑만기"]||"").slice(0,10),lp1:x["LP1"]||"",lp1w:Number(x["LP1비중"]||0),lp2:x["LP2"]||"",lp2w:Number(x["lp2비중"]||0),memo:x["메모"]||""}));for(const nf of next){const old=oldFunds.find(x=>x.code===nf.code)||oldFunds.find(x=>x.assoc===nf.assoc);if(!old)continue;for(const h of DATA.holdings.filter(x=>x.fund===old.fund)){Object.assign(h,{fund:nf.fund,type:nf.type,strategy:nf.strategy,manager:nf.manager,book:nf.book,fundEval:nf.eval,real:h.eval*nf.share,weight:nf.eval?h.eval*nf.share/nf.eval:0});}for(const t of DATA.trades.filter(x=>x.fund===old.fund))Object.assign(t,{fund:nf.fund,type:nf.type,strategy:nf.strategy,manager:nf.manager});}DATA.funds=next;DATA.summary.funds=next.length;}
    if(issuerRows.length){const rules=issuerRows.map(x=>[String(x["발행사"]||""),x["발행사(변경후)"]||"",x["중분류"]||""]).filter(x=>x[0]).sort((a,b)=>b[0].length-a[0].length);for(const row of [...DATA.holdings,...DATA.trades]){const rule=rules.find(x=>String(row.name||"").includes(x[0]));if(rule){row.issuer=rule[1];row.mid=rule[2];}}}
    render();
  }catch(error){console.warn("채권 수기정보 실시간 동기화 실패",error.message)}
}
let manualRealtimeTimer;
(async()=>{const client=window.parent!==window&&window.parent.dashboardSupabase;if(!client)return;client.channel(`bond-dashboard-${crypto.randomUUID()}`).on("postgres_changes",{event:"*",schema:"public",table:"manual_file_rows",filter:"domain=eq.bond"},()=>{clearTimeout(manualRealtimeTimer);manualRealtimeTimer=setTimeout(hydrateManualData,350)}).subscribe();await hydrateManualData();})();
render();
</script>
</body>
</html>
"""


def main() -> None:
    data = build_data()
    html = HTML_TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    out = ROOT / "채권형수익증권_대시보드.html"
    out.write_text(html, encoding="utf-8")
    print(out)
    print(json.dumps(data["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

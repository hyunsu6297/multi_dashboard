# -*- coding: utf-8 -*-
from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
INPUTS = {
    "fund_info": BASE_DIR / "펀드 정보.xlsx",
    "trades": BASE_DIR / "전체펀드 매매현황.xlsx",
    "holdings": BASE_DIR / "전체펀드 보유현황.xlsx",
    "direct_stocks": BASE_DIR / "주식보유현황.xlsx",
    "industry": BASE_DIR / "업종.xlsx",
}
QUOTE_CANDIDATES = [
    BASE_DIR / "kiwoom_quotes.json",
    BASE_DIR / "kiwoom_realtime_quotes.json",
    BASE_DIR / "realtime_quotes.json",
    BASE_DIR / "change_rates.json",
]
OUTPUT = BASE_DIR / "fund_dashboard.html"
FUND_CODE_ALIAS_CANDIDATES = {
    # KFR holdings currently report this fund under the source code below,
    # while the manually maintained fund list has used different dashboard codes.
    "K554D4EN6070": ["K554D4E97861", "K554D4DM3483"],
}


def esc(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return html.escape(str(value), quote=True)


def clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip().replace(",", "")
    if text.endswith(".0"):
        text = text[:-2]
    return text


def normalize_code(value: object) -> str:
    text = clean_text(value)
    if not text or text.lower() == "nan":
        return ""
    if len(text) >= 9 and text.startswith("KR7") and text[3:9].isdigit():
        return text[3:9]
    return text.zfill(6) if text.isdigit() else text


def parse_float(value: object, default: float | None = 0.0) -> float | None:
    text = clean_text(value).replace("+", "")
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def fmt_money(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    value = float(value)
    sign = "-" if value < 0 else ""
    return f"{sign}{abs(value) / 100_000_000:,.2f}억"


def fmt_price(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.0f}"


def fmt_pct(value: float | int | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value) * 100:.{digits}f}%"


def fmt_rate_percent(value: float | int | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.{digits}f}%"


def rate_bar(value: float | int | None, limit: float) -> str:
    if value is None or pd.isna(value):
        return "<td>-</td>"
    rate = float(value)
    pct = max(min(rate / limit, 1), -1)
    width = abs(pct) * 50
    if rate >= 0:
        bar = f"<span class='bar-pos' style='left:50%;width:{width:.1f}%'></span>"
    else:
        bar = f"<span class='bar-neg' style='left:{50 - width:.1f}%;width:{width:.1f}%'></span>"
    return f"<td><div class='rate-bar'><span class='bar-zero'></span>{bar}<em>{fmt_rate_percent(rate)}</em></div></td>"


def pnl_cell(value: float | int | None) -> str:
    cls = "profit-cell" if (value or 0) >= 0 else "loss-cell"
    return f"<td class='{cls}'>{fmt_money(value)}</td>"


def hana_color(i: int) -> str:
    palette = ["#008485", "#00a69c", "#003b5c", "#7a5c2e", "#e7663f", "#546a7b", "#0f766e", "#b45309", "#4f46e5", "#be123c"]
    return palette[i % len(palette)]


def read_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    funds = (
        pd.read_excel(INPUTS["fund_info"], header=3)
        .dropna(axis=1, how="all")
        .dropna(how="all")
    )[["펀드코드", "펀드명", "지분율", "유형", "평가액"]].copy()
    trades = (
        pd.read_excel(INPUTS["trades"], sheet_name="Data", header=1)
        .drop(columns=["Unnamed: 0"], errors="ignore")
        .dropna(how="all")
    )
    holdings = (
        pd.read_excel(INPUTS["holdings"], sheet_name="Data", header=1)
        .drop(columns=["Unnamed: 0"], errors="ignore")
        .dropna(how="all")
    )

    funds["펀드코드"] = funds["펀드코드"].map(normalize_code)
    funds["펀드명"] = funds["펀드명"].astype(str).str.strip()
    funds["유형"] = funds["유형"].fillna("기타").astype(str).str.strip()
    funds["지분율"] = pd.to_numeric(funds["지분율"], errors="coerce").fillna(1)
    funds.loc[funds["지분율"] > 1, "지분율"] = funds.loc[funds["지분율"] > 1, "지분율"] / 100
    funds["평가액"] = pd.to_numeric(funds["평가액"], errors="coerce")
    funds["평가액원"] = funds["평가액"] * 1_000_000

    for df in (trades, holdings):
        for col in [c for c, dtype in df.dtypes.items() if str(dtype) in {"object", "string"}]:
            df[col] = df[col].astype(str).str.strip()

    for col in ["매매수량", "매매가격", "결제금액", "듀레이션", "매매금리"]:
        trades[col] = pd.to_numeric(trades[col], errors="coerce")
    for col in ["수량", "평가가격", "평가금", "취득가액", "듀레이션", "YTM", "이표율", "순자산"]:
        holdings[col] = pd.to_numeric(holdings[col], errors="coerce")

    trades["기준일"] = pd.to_datetime(trades["기준일"], errors="coerce")
    holdings["보유일"] = pd.to_datetime(holdings["보유일"], errors="coerce")
    trades["협회펀드코드"] = trades["협회펀드코드"].map(normalize_code)
    holdings["협회펀드코드"] = holdings["협회펀드코드"].map(normalize_code)
    fund_codes = set(funds["펀드코드"])
    fund_code_aliases = {
        source: next((target for target in targets if target in fund_codes), targets[0])
        for source, targets in FUND_CODE_ALIAS_CANDIDATES.items()
    }
    trades["협회펀드코드"] = trades["협회펀드코드"].replace(fund_code_aliases)
    holdings["협회펀드코드"] = holdings["협회펀드코드"].replace(fund_code_aliases)
    trades["종목코드정규"] = trades["종목코드"].map(normalize_code)
    holdings["종목코드정규"] = holdings["종목코드"].map(normalize_code)
    return funds, trades, holdings


def read_industry_map() -> tuple[dict[str, str], dict[str, str]]:
    if not INPUTS["industry"].exists():
        return {}, {}
    industry = pd.read_excel(INPUTS["industry"]).dropna(how="all")
    if industry.empty:
        return {}, {}
    code_col = "코드" if "코드" in industry.columns else "Code" if "Code" in industry.columns else None
    large_col = "업종(대)" if "업종(대)" in industry.columns else "대분류" if "대분류" in industry.columns else None
    mid_col = "업종(중)" if "업종(중)" in industry.columns else "중분류" if "중분류" in industry.columns else None
    if not code_col:
        return {}, {}
    industry["종목코드정규"] = industry[code_col].map(normalize_code)
    industry = industry[industry["종목코드정규"].ne("")]
    large = industry[large_col].fillna("미분류").astype(str).str.strip() if large_col else pd.Series("미분류", index=industry.index)
    mid = industry[mid_col].fillna("미분류").astype(str).str.strip() if mid_col else large
    industry["업종대분류"] = large.mask(large.eq(""), "미분류")
    industry["업종중분류"] = mid.mask(mid.eq(""), "미분류")
    deduped = industry.drop_duplicates("종목코드정규")
    return (
        deduped.set_index("종목코드정규")["업종대분류"].to_dict(),
        deduped.set_index("종목코드정규")["업종중분류"].to_dict(),
    )


def load_quote_cache() -> tuple[dict[str, dict[str, float | None]], str]:
    quote_path = next((path for path in QUOTE_CANDIDATES if path.exists()), None)
    if not quote_path:
        return {}, "시세 캐시 파일 없음"
    try:
        data = json.loads(quote_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, f"시세 캐시 읽기 실패: {exc}"

    raw_stocks = data.get("stocks", data) if isinstance(data, dict) else {}
    quotes: dict[str, dict[str, float | None]] = {}
    if isinstance(raw_stocks, dict):
        for code, item in raw_stocks.items():
            norm = normalize_code(code)
            if not norm:
                continue
            if isinstance(item, dict):
                price = parse_float(item.get("price", item.get("cur_prc")), None)
                rate = parse_float(item.get("change_rate", item.get("flu_rt")), None)
            else:
                price = None
                rate = parse_float(item, None)
            quotes[norm] = {
                "price": abs(price) if price is not None else None,
                "change_rate": rate,
                "industry": item.get("industry") or item.get("upName") or "",
                "market": item.get("market") or item.get("marketName") or "",
            }
    return quotes, quote_path.name


def quote_for(row: pd.Series, quotes: dict[str, dict[str, float | None]]) -> pd.Series:
    quote = quotes.get(row.get("종목코드정규", ""), {})
    return pd.Series({"현재가": quote.get("price"), "등락율": quote.get("change_rate"), "키움업종": quote.get("industry")})


def is_equity_related(df: pd.DataFrame, asset_col: str) -> pd.Series:
    asset = df[asset_col].fillna("").astype(str)
    market = df["시장구분"].fillna("").astype(str)
    sector = df.get("업종", df.get("섹터", pd.Series("", index=df.index))).fillna("").astype(str)
    return (
        asset.eq("주식")
        | market.str.contains("주식|주가지수|코스닥|거래소상장|개별주식선물|해외파생", regex=True)
        | sector.str.contains("해외주식", regex=True)
    )


def kpi(label: str, value: str, sub: str = "") -> str:
    return f"<div class='kpi'><span>{esc(label)}</span><strong>{esc(value)}</strong><small>{esc(sub)}</small></div>"


def empty(message: str = "표시할 데이터가 없습니다.") -> str:
    return f"<div class='empty'>{esc(message)}</div>"


def pie_svg(rows: list[tuple[object, float]], size: int = 360, max_rows: int = 8) -> str:
    rows = [(str(k) if str(k) != "nan" else "미분류", float(v or 0)) for k, v in rows if pd.notna(v) and float(v or 0) > 0]
    rows = rows[: max_rows - 1] + [("기타 합계", sum(v for _, v in rows[max_rows - 1 :]))] if len(rows) > max_rows else rows
    total = sum(v for _, v in rows)
    if total <= 0:
        return empty()
    import math

    cx = cy = size / 2
    r = size / 2 - 8
    start = 0.0
    paths, legend = [], []
    for i, (label, value) in enumerate(rows):
        angle = value / total * 2 * math.pi
        end = start + angle
        x1, y1 = cx + r * math.cos(start), cy + r * math.sin(start)
        x2, y2 = cx + r * math.cos(end), cy + r * math.sin(end)
        large = 1 if angle > math.pi else 0
        color = hana_color(i)
        tooltip = esc(f"{label}: {fmt_pct(value / total)} / {fmt_money(value)}")
        paths.append(f'<path d="M {cx:.1f} {cy:.1f} L {x1:.1f} {y1:.1f} A {r:.1f} {r:.1f} 0 {large} 1 {x2:.1f} {y2:.1f} Z" fill="{color}"><title>{tooltip}</title></path>')
        mid = start + angle / 2
        lx, ly = cx + (r * 0.62) * math.cos(mid), cy + (r * 0.62) * math.sin(mid)
        if value / total >= 0.055:
            paths.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" class="pie-label">{esc(label[:8])}</text>')
        legend.append(f'<li><span style="background:{color}"></span><b>{esc(label)}</b><em>{fmt_pct(value / total)}</em><small>{fmt_money(value)}</small></li>')
        start = end
    return f"<div class='pie-wrap'><svg viewBox='0 0 {size} {size}' class='pie'>{''.join(paths)}<circle cx='{cx}' cy='{cy}' r='{r * .46:.1f}' fill='#fff'></circle></svg><ul class='legend'>{''.join(legend)}</ul></div>"


def sector_large_pie_svg(rows: list[tuple[object, float]], size: int = 500, max_rows: int = 9) -> str:
    rows = [(str(k) if str(k) != "nan" else "미분류", float(v or 0)) for k, v in rows if pd.notna(v) and float(v or 0) > 0]
    rows = sorted(rows, key=lambda x: x[1], reverse=True)
    rows = rows[: max_rows - 1] + [("기타", sum(v for _, v in rows[max_rows - 1 :]))] if len(rows) > max_rows else rows
    total = sum(v for _, v in rows)
    if total <= 0:
        return empty()
    import math

    cx = cy = size / 2
    r = size / 2 - 18
    start = -math.pi / 2
    parts = [f'<svg viewBox="0 0 {size} {size}" class="sector-pie">']
    legend = []
    callouts = []
    for i, (label, value) in enumerate(rows):
        angle = value / total * 2 * math.pi
        end = start + angle
        x1, y1 = cx + r * math.cos(start), cy + r * math.sin(start)
        x2, y2 = cx + r * math.cos(end), cy + r * math.sin(end)
        large = 1 if angle > math.pi else 0
        color = hana_color(i)
        tooltip = esc(f"{label}: {fmt_pct(value / total, 0)} / {fmt_money(value)}")
        parts.append(f'<path d="M {cx:.1f} {cy:.1f} L {x1:.1f} {y1:.1f} A {r:.1f} {r:.1f} 0 {large} 1 {x2:.1f} {y2:.1f} Z" fill="{color}" stroke="#fff" stroke-width="2"><title>{tooltip}</title></path>')
        mid = start + angle / 2
        pct = value / total
        if pct >= 0.055:
            lx, ly = cx + (r * 0.62) * math.cos(mid), cy + (r * 0.62) * math.sin(mid)
            text = esc(f"{label[:7]}, {fmt_pct(pct, 0)}")
            parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" class="slice-tag">{text}</text>')
        else:
            side = 1 if math.cos(mid) >= 0 else -1
            callouts.append({
                "label": label,
                "pct": pct,
                "side": side,
                "anchor_x": cx + (r * 0.98) * math.cos(mid),
                "anchor_y": cy + (r * 0.98) * math.sin(mid),
                "target_y": cy + (r * 1.02) * math.sin(mid),
            })
        legend.append(f'<li><span style="background:{color}"></span><b>{esc(label)}</b><em>{fmt_pct(pct, 0)}</em><small>{fmt_money(value)}</small></li>')
        start = end
    for side in (-1, 1):
        side_callouts = sorted([item for item in callouts if item["side"] == side], key=lambda item: item["target_y"])
        if not side_callouts:
            continue
        min_y, max_y, gap = 34, size - 34, 22
        for idx, item in enumerate(side_callouts):
            item["label_y"] = min(max(item["target_y"], min_y + idx * gap), max_y)
        for idx in range(1, len(side_callouts)):
            prev = side_callouts[idx - 1]
            item = side_callouts[idx]
            item["label_y"] = max(item["label_y"], prev["label_y"] + gap)
        overflow = side_callouts[-1]["label_y"] - max_y
        if overflow > 0:
            for item in side_callouts:
                item["label_y"] -= overflow
        for idx in range(len(side_callouts) - 2, -1, -1):
            item = side_callouts[idx]
            nxt = side_callouts[idx + 1]
            item["label_y"] = min(item["label_y"], nxt["label_y"] - gap)
        for item in side_callouts:
            text_x = size - 86 if side > 0 else 86
            elbow_x = cx + side * (r + 8)
            anchor = "start" if side > 0 else "end"
            line_end_x = text_x - 46 if side > 0 else text_x + 46
            text = esc(f"{str(item['label'])[:7]}, {fmt_pct(item['pct'], 0)}")
            parts.append(f'<path d="M {item["anchor_x"]:.1f} {item["anchor_y"]:.1f} L {elbow_x:.1f} {item["label_y"]:.1f} L {line_end_x:.1f} {item["label_y"]:.1f}" class="callout"></path>')
            parts.append(f'<text x="{text_x:.1f}" y="{item["label_y"] + 3:.1f}" text-anchor="{anchor}" class="slice-callout">{text}</text>')
    parts.append("</svg>")
    return "".join(parts) + f"<ul class='sector-legend'>{''.join(legend)}</ul>"


def sector_mid_bar_svg(rows: list[tuple[object, float]], all_labels: list[str], width: int = 620, max_rows: int = 24) -> str:
    values = {str(k) if str(k) != "nan" else "미분류": float(v or 0) for k, v in rows if pd.notna(k)}
    if all_labels:
        rows = sorted(((label, values.get(label, 0.0)) for label in all_labels), key=lambda x: x[1], reverse=True)[:max_rows]
    else:
        rows = sorted(values.items(), key=lambda x: x[1], reverse=True)[:max_rows]
    total = sum(values.values())
    if total <= 0:
        total = 1
    left, right, top, bottom = 178, 54, 14, 34
    row_h = 29
    height = top + bottom + row_h * len(rows)
    plot_w = width - left - right
    max_pct = max([v / total for _, v in rows] + [0.01])
    grid_max = max(0.05, (int(max_pct * 20) + 1) / 20)
    parts = [f'<svg viewBox="0 0 {width} {height}" class="sector-bar" preserveAspectRatio="none">']
    for tick in range(0, int(grid_max * 100) + 1, 5):
        x = left + plot_w * (tick / 100) / grid_max
        parts.append(f'<line x1="{x:.1f}" y1="{top - 4}" x2="{x:.1f}" y2="{height - bottom}" class="bar-grid"></line>')
        parts.append(f'<text x="{x:.1f}" y="{height - 8}" text-anchor="middle" class="bar-axis">{tick}%</text>')
    for i, (label, value) in enumerate(rows):
        pct = value / total
        y = top + i * row_h
        w = plot_w * pct / grid_max if pct > 0 else 0
        parts.append(f'<text x="{left - 11}" y="{y + 19}" text-anchor="end" class="bar-label">{esc(label[:15])}</text>')
        if w:
            parts.append(f'<rect x="{left}" y="{y + 7}" width="{w:.1f}" height="14" fill="#00483a"></rect>')
        parts.append(f'<text x="{left + w + 9:.1f}" y="{y + 19}" class="bar-value">{fmt_pct(pct, 0)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def diverging_bar_svg(rows: list[tuple[object, float]], width: int = 1120, max_rows: int = 12) -> str:
    rows = [(str(k) if str(k) != "nan" else "미분류", float(v or 0)) for k, v in rows if pd.notna(v) and float(v or 0) != 0]
    rows = sorted(rows, key=lambda x: abs(x[1]), reverse=True)[:max_rows]
    if not rows:
        return empty()
    left, right, top, bottom = 158, 122, 16, 24
    height = 520
    available_h = height - top - bottom
    gap = 10
    bar_h = max(24, min(32, (available_h / max(len(rows), 1)) - gap))
    plot_w = width - left - right
    zero_x = left + plot_w / 2
    scale = (plot_w / 2) / (max(abs(v) for _, v in rows) or 1)
    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart">']
    parts.append(f'<line x1="{zero_x:.1f}" y1="4" x2="{zero_x:.1f}" y2="{height - bottom + 4}" class="zero"></line>')
    for i, (label, value) in enumerate(rows):
        y = top + i * (bar_h + gap)
        w = max(3, abs(value) * scale)
        x = zero_x if value >= 0 else zero_x - w
        fill = "#008485" if value >= 0 else "#e7663f"
        parts.append(f'<text x="0" y="{y + 18}" class="axis big-axis">{esc(label[:18])}</text>')
        parts.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="3" fill="{fill}"></rect>')
        tx = x + w + 7 if value >= 0 else x - 7
        anchor = "start" if value >= 0 else "end"
        parts.append(f'<text x="{tx:.1f}" y="{y + 18}" text-anchor="{anchor}" class="value big-axis">{fmt_money(value)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def daily_trade_svg(df: pd.DataFrame, width: int = 1120, height: int = 520) -> str:
    if df.empty:
        return empty("매매 데이터가 없습니다.")
    pivot = df.pivot_table(index="기준일", columns="거래구분", values="우리결제금액", aggfunc="sum", fill_value=0).sort_index()
    dates = list(pivot.index)
    buys = pivot["매수"] if "매수" in pivot else pd.Series(0, index=pivot.index)
    sells = pivot["매도"] if "매도" in pivot else pd.Series(0, index=pivot.index)
    max_v = max((buys + sells).max(), 1)
    left, right, top, bottom = 74, 24, 30, 54
    plot_w, plot_h = width - left - right, height - top - bottom
    bar_w = min(86, plot_w / max(len(dates), 1) * 0.62)
    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart">']
    for tick in range(3):
        y = top + plot_h * tick / 2
        val = max_v * (1 - tick / 2)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" class="gridline"></line>')
        parts.append(f'<text x="2" y="{y + 4:.1f}" class="axis daily-axis">{fmt_money(val)}</text>')
    for i, date in enumerate(dates):
        x = left + (i + 0.5) * plot_w / len(dates) - bar_w / 2
        buy_h = plot_h * buys.loc[date] / max_v
        sell_h = plot_h * sells.loc[date] / max_v
        parts.append(f'<rect x="{x:.1f}" y="{top + plot_h - buy_h:.1f}" width="{bar_w:.1f}" height="{buy_h:.1f}" rx="3" fill="#008485"></rect>')
        parts.append(f'<rect x="{x:.1f}" y="{top + plot_h - buy_h - sell_h:.1f}" width="{bar_w:.1f}" height="{sell_h:.1f}" rx="3" fill="#e7663f"></rect>')
        parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{height - 14}" text-anchor="middle" class="axis daily-axis">{date.strftime("%m-%d")}</text>')
    parts.append("</svg>")
    return "".join(parts)


def trade_category_svg(rows: list[tuple[object, float]], all_labels: list[str] | None = None, width: int = 1180, height: int = 390, max_rows: int = 28) -> str:
    values = {str(k) if str(k) != "nan" else "미분류": float(v or 0) for k, v in rows if pd.notna(k)}
    if all_labels:
        rows = sorted(((label, values.get(label, 0.0)) for label in all_labels), key=lambda x: x[1], reverse=True)[:max_rows]
    else:
        rows = sorted(values.items(), key=lambda x: x[1], reverse=True)[:max_rows]
    if not rows:
        return empty("업종별 매매 데이터가 없습니다.")
    left, right, top, bottom = 54, 32, 26, 76
    plot_w, plot_h = width - left - right, height - top - bottom
    max_abs = max(abs(v) for _, v in rows) or 1
    zero_y = top + plot_h / 2
    scale = (plot_h / 2 - 10) / max_abs
    step = plot_w / max(len(rows), 1)
    bar_w = max(12, min(36, step * 0.52))
    tick_count = 4
    parts = [f'<svg viewBox="0 0 {width} {height}" class="trade-category-chart">']
    for i in range(-tick_count, tick_count + 1):
        value = max_abs * i / tick_count
        y = zero_y - value * scale
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" class="gridline"></line>')
        if i != 0:
            parts.append(f'<text x="6" y="{y + 4:.1f}" class="axis trade-axis">{fmt_money(value)}</text>')
    parts.append(f'<line x1="{left}" y1="{zero_y:.1f}" x2="{width - right}" y2="{zero_y:.1f}" class="zero"></line>')
    for i, (label, value) in enumerate(rows):
        cx = left + step * (i + 0.5)
        h = max(1.0, abs(value) * scale) if value else 0.0
        y = zero_y - h if value >= 0 else zero_y
        parts.append(f'<rect x="{cx - bar_w / 2:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="#005344"></rect>')
        label_text = esc(label[:12])
        label_y = height - 58
        parts.append(f'<text x="{cx:.1f}" y="{label_y}" text-anchor="end" transform="rotate(-42 {cx:.1f} {label_y})" class="trade-label">{label_text}</text>')
    parts.append("</svg>")
    return "".join(parts)


def table_html(headers: list[str], rows: list[list[str]], css_class: str = "table-wrap") -> str:
    if not rows:
        return empty()
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(cell for cell in row) + "</tr>" for row in rows)
    return f"<div class='{css_class}'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def signed_position(row: pd.Series) -> float:
    return -1.0 if row.get("포지션") == "매도" else 1.0


def safe_sum(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.sum())


def holding_breakdowns(df: pd.DataFrame, amount_col: str) -> dict[str, str]:
    breakdowns = {}
    for key, rows in df.groupby(["종목코드정규", "종목명", "포지션"], dropna=False):
        total = rows[amount_col].sum()
        lines = []
        for fund, amount in rows.groupby("보유펀드명")[amount_col].sum().sort_values(ascending=False).items():
            lines.append(f"{fund}: {fmt_money(amount)} ({fmt_pct(amount / total if total else 0)})")
        breakdowns["|".join(map(str, key))] = "\n".join(lines)
    return breakdowns


def net_trade_breakdowns(df: pd.DataFrame) -> dict[str, str]:
    breakdowns = {}
    for key, rows in df.groupby(["종목코드정규", "종목명"], dropna=False):
        signed = rows.assign(순매수금액=rows["우리결제금액"] * rows["거래구분"].map({"매수": 1, "매도": -1}).fillna(0))
        by_fund = signed.groupby("보유펀드명")["순매수금액"].sum()
        total_abs = by_fund.abs().sum()
        lines = []
        for fund, amount in by_fund.sort_values(key=lambda s: s.abs(), ascending=False).items():
            if amount:
                lines.append(f"{fund}: {fmt_money(amount)} ({fmt_pct(abs(amount) / total_abs if total_abs else 0)})")
        breakdowns["|".join(map(str, key))] = "\n".join(lines)
    return breakdowns


def holding_table(df: pd.DataFrame, position: str, denominator: float, limit: int = 20) -> str:
    rows = df[df["포지션"] == position].copy()
    if rows.empty:
        return empty(f"{position} 포지션 보유내역이 없습니다.")
    tips = holding_breakdowns(rows, "우리평가금")
    summary = (
        rows.groupby(["종목코드정규", "종목명", "업종", "포지션"], dropna=False)
        .agg(평가금=("우리평가금", "sum"), 취득가액=("우리취득가액", "sum"), 시장PL=("시장PL", "sum"), PL=("PL", "sum"), 보유펀드수=("보유펀드명", "nunique"))
        .reset_index()
    )
    summary["평가손익"] = summary["PL"]
    summary["수익률"] = summary["평가손익"] / summary["평가금"].replace({0: pd.NA})
    summary["등락율"] = summary["시장PL"] / summary["평가금"].replace({0: pd.NA})
    summary["비중"] = summary["평가금"] / denominator if denominator else pd.NA
    summary = summary.sort_values("평가금", ascending=False).head(limit)
    body = []
    for _, row in summary.iterrows():
        key = "|".join(map(str, [row["종목코드정규"], row["종목명"], row["포지션"]]))
        body.append([
            f"<td class='name-cell has-tip' title='{esc(tips.get(key, ''))}'>{esc(row['종목명'])}</td>",
            f"<td>{fmt_pct(row['비중'])}</td>",
            f"<td>{esc(row['업종'])}</td>",
            f"<td>{int(row['보유펀드수']):,}</td>",
            f"<td>{fmt_money(row['평가금'])}</td>",
            rate_bar(row["등락율"] * 100 if pd.notna(row["등락율"]) else None, 5),
            f"<td>{fmt_money(row['평가손익'])}</td>",
            f"<td>{fmt_pct(row['수익률'])}</td>",
        ])
    return table_html(["종목명", "비중", "업종", "펀드", "평가금", "등락율", "손익", "수익률"], body)


def trade_table(df: pd.DataFrame, limit: int = 24) -> str:
    rows = df[df["우리결제금액"].abs() >= 50_000_000].copy()
    if rows.empty:
        return empty("주식/주식관련 매매내역이 없습니다.")
    rows = rows.sort_values(["기준일", "우리결제금액"], ascending=[False, False]).head(limit)
    body = []
    for _, row in rows.iterrows():
        side_class = "profit-cell" if row["거래구분"] == "매수" else "loss-cell" if row["거래구분"] == "매도" else ""
        body.append([
            f"<td>{esc(row['기준일'])}</td>",
            f"<td>{esc(row['보유펀드명'])}</td>",
            f"<td class='name-cell'>{esc(row['종목명'])}</td>",
            f"<td>{esc(row['업종'])}</td>",
            f"<td class='{side_class}'>{esc(row['거래구분'])}</td>",
            f"<td class='{side_class}'>{fmt_money(row['우리결제금액'])}</td>",
        ])
    return table_html(["기준일", "펀드명", "종목명", "업종", "구분", "결제금액"], body, "table-wrap tall")


def net_trade_table(df: pd.DataFrame, direction: str, limit: int = 24) -> str:
    if df.empty:
        return empty()
    tips = net_trade_breakdowns(df)
    signed = df.assign(순매수금액=df["우리결제금액"] * df["거래구분"].map({"매수": 1, "매도": -1}).fillna(0))
    summary = (
        signed.groupby(["종목코드정규", "종목명", "업종"], dropna=False)
        .agg(순매수금액=("순매수금액", "sum"), 펀드수=("보유펀드명", "nunique"))
        .reset_index()
    )
    if direction == "buy":
        summary = summary[summary["순매수금액"] > 0].sort_values("순매수금액", ascending=False)
    else:
        summary = summary[summary["순매수금액"] < 0].sort_values("순매수금액")
    summary = summary.head(limit)
    if summary.empty:
        return empty("해당 순매매 종목이 없습니다.")
    body = []
    for _, row in summary.iterrows():
        key = "|".join(map(str, [row["종목코드정규"], row["종목명"]]))
        body.append([
            f"<td class='name-cell has-tip' title='{esc(tips.get(key, ''))}'>{esc(row['종목명'])}</td>",
            f"<td>{esc(row['업종'])}</td>",
            f"<td>{int(row['펀드수']):,}</td>",
            f"<td>{fmt_money(row['순매수금액'])}</td>",
        ])
    return table_html(["종목명", "업종", "펀드", "순매수금액"], body)


def direct_stock_table(df: pd.DataFrame, title: str, panel_class: str = "") -> str:
    if df.empty:
        return empty(f"{title} 데이터가 없습니다.")
    rows = df.sort_values("평가액", ascending=False, na_position="last")
    body = []
    for _, row in rows.iterrows():
        body.append([
            f"<td class='name-cell'>{esc(row['종목명'])}</td>",
            f"<td>{esc(row['종목코드정규'])}</td>",
            f"<td>{fmt_price(row['보유수량'])}</td>",
            f"<td>{fmt_price(row.get('현재가'))}</td>",
            f"<td>{fmt_money(row.get('평가액'))}</td>",
            rate_bar(row.get("등락율"), 10),
            pnl_cell(row.get("PL")),
        ])
    for _ in range(max(0, 8 - len(body))):
        body.append(["<td>&nbsp;</td>", "<td></td>", "<td></td>", "<td></td>", "<td></td>", "<td></td>", "<td></td>"])
    total_eval = safe_sum(rows["평가액"])
    total_pl = safe_sum(rows["PL"])
    body.append([
        "<td class='total-label'>합계</td>",
        "<td></td>",
        f"<td>{fmt_price(safe_sum(rows['보유수량']))}</td>",
        "<td></td>",
        f"<td>{fmt_money(total_eval)}</td>",
        "<td></td>",
        pnl_cell(total_pl),
    ])
    cls = f"panel {panel_class}".strip()
    return f"<article class='{cls}'><div class='panel-title'><h4>{esc(title)}</h4><span>8행 슬롯 + 합계</span></div>" + table_html(["종목명", "코드", "수량", "주가", "평가액", "등락율", "PL"], body, "table-wrap direct") + "</article>"


def fund_pl_table(
    df: pd.DataFrame,
    all_holdings: pd.DataFrame,
    fund_catalog: pd.DataFrame | None = None,
    highlight_fund: str | None = None,
) -> str:
    if (df.empty or "PL" not in df) and (fund_catalog is None or fund_catalog.empty):
        return empty("시세 캐시가 없어 펀드별 PL을 계산할 수 없습니다.")

    if fund_catalog is not None and not fund_catalog.empty:
        summary = (
            fund_catalog[["펀드명", "평가액원"]]
            .rename(columns={"펀드명": "보유펀드명", "평가액원": "펀드평가액원"})
            .dropna(subset=["보유펀드명"])
            .drop_duplicates(subset=["보유펀드명"], keep="first")
            .copy()
        )
        summary["Exposure"] = 0.0
        summary["PL"] = 0.0
        summary["종목수"] = 0
    else:
        summary = pd.DataFrame(columns=["보유펀드명", "펀드평가액원", "Exposure", "PL", "종목수"])

    if not df.empty and "PL" in df:
        stock_summary = (
            df.groupby("보유펀드명", dropna=False)
            .agg(Exposure=("우리평가금", "sum"), PL=("PL", "sum"), 종목수=("종목코드정규", "nunique"))
            .reset_index()
        )
        fund_value_denominator = (
            df.groupby("보유펀드명", dropna=False)["펀드평가액원"].first()
            if "펀드평가액원" in df
            else pd.Series(dtype=float)
        )
        stock_summary["펀드평가액원"] = stock_summary["보유펀드명"].map(fund_value_denominator).fillna(stock_summary["Exposure"])
        if summary.empty:
            summary = stock_summary
        else:
            summary = summary.merge(stock_summary, on="보유펀드명", how="outer", suffixes=("", "_stock"))
            for column in ("Exposure", "PL", "종목수"):
                summary[column] = summary[f"{column}_stock"].fillna(summary[column]).fillna(0)
                summary.drop(columns=[f"{column}_stock"], inplace=True)
            summary["펀드평가액원"] = summary["펀드평가액원"].fillna(summary["펀드평가액원_stock"]).fillna(summary["Exposure"])
            summary.drop(columns=["펀드평가액원_stock"], inplace=True)

    summary["등락율"] = summary["PL"] / summary["펀드평가액원"].replace({0: pd.NA})
    summary = summary.sort_values("등락율", ascending=False, na_position="last")
    body = []
    for _, row in summary.iterrows():
        tr_class = " class='highlight-row'" if highlight_fund and row["보유펀드명"] == highlight_fund else ""
        body.append([
            f"<td{tr_class}>{esc(row['보유펀드명'])}</td>",
            f"<td>{int(row['종목수']):,}</td>",
            f"<td>{fmt_money(row['Exposure'])}</td>",
            rate_bar(row["등락율"] * 100 if pd.notna(row["등락율"]) else None, 5),
            pnl_cell(row["PL"]),
        ])
    total_exposure = summary["Exposure"].sum()
    total_pl = summary["PL"].sum()
    total_fund_value = summary["펀드평가액원"].sum() if "펀드평가액원" in summary else total_exposure
    total_rate = total_pl / total_fund_value if total_fund_value else pd.NA
    body.append([
        "<td class='total-label'>합계</td>",
        f"<td>{int(summary['종목수'].sum()):,}</td>",
        f"<td>{fmt_money(total_exposure)}</td>",
        rate_bar(total_rate * 100 if pd.notna(total_rate) else None, 5),
        pnl_cell(total_pl),
    ])
    return table_html(["펀드명", "종목", "주식Exposure", "등락율", "주식PL"], body, "table-wrap fund-pl")


def prepare_direct_stock_sheet(sheet_name: str, quotes: dict[str, dict[str, float | None]]) -> pd.DataFrame:
    if not INPUTS["direct_stocks"].exists():
        return pd.DataFrame(columns=["종목명", "종목코드정규", "보유수량", "현재가", "평가액", "등락율", "PL"])
    df = pd.read_excel(INPUTS["direct_stocks"], sheet_name=sheet_name).dropna(how="all")
    df["종목명"] = df["종목명"].astype(str).str.strip()
    df["종목코드정규"] = df["종목코드"].map(normalize_code)
    df["보유수량"] = pd.to_numeric(df["보유수량"], errors="coerce").fillna(0)
    quote_values = df.apply(lambda row: quote_for(row, quotes), axis=1)
    df = pd.concat([df, quote_values], axis=1)
    df["평가액"] = df["보유수량"] * df["현재가"]
    df["PL"] = df["평가액"] * df["등락율"] / 100.0
    return df


def make_view(
    label: str,
    all_holdings: pd.DataFrame,
    stock_holdings: pd.DataFrame,
    all_stock_holdings_for_pl: pd.DataFrame,
    stock_trades: pd.DataFrame,
    fund_catalog: pd.DataFrame,
    global_pl: dict[str, float | None],
    investment_table_html: str,
    product_table_html: str,
    sector_large_labels: list[str],
    sector_mid_labels: list[str],
) -> str:
    total_fund_amount = all_holdings["우리평가금"].sum()
    long_amount = stock_holdings.loc[stock_holdings["포지션"] == "매수", "우리평가금"].sum()
    short_amount = stock_holdings.loc[stock_holdings["포지션"] == "매도", "우리평가금"].sum()
    net_exposure = long_amount - short_amount
    investment_exposure = global_pl.get("투자주식Exposure")
    product_exposure = global_pl.get("상품주식Exposure")
    total_exposure = (net_exposure or 0) + (investment_exposure or 0) + (product_exposure or 0)
    buy_amount = stock_trades.loc[stock_trades["거래구분"] == "매수", "우리결제금액"].sum()
    sell_amount = stock_trades.loc[stock_trades["거래구분"] == "매도", "우리결제금액"].sum()
    trade_dates = stock_trades["기준일"].dropna()
    period = "-" if trade_dates.empty else f"{trade_dates.min():%Y-%m-%d} ~ {trade_dates.max():%Y-%m-%d}"
    fund_meta = ""
    count_meta = ""
    if not all_holdings.empty:
        rate = all_holdings["지분율"].dropna()
        count_meta = f"지분율 {fmt_pct(rate.iloc[0])} · 보유 {len(stock_holdings):,}건 · 매매 {len(stock_trades):,}건" if label != "전체 펀드 통합" and not rate.empty else f"펀드 {all_holdings['보유펀드명'].nunique():,}개 · 보유 {len(stock_holdings):,}건 · 매매 {len(stock_trades):,}건"
    sector_large_hold = stock_holdings.groupby("업종대분류")["우리평가금"].sum().sort_values(ascending=False).reset_index()
    sector_mid_hold = stock_holdings.groupby("업종중분류")["우리평가금"].sum().sort_values(ascending=False).reset_index()
    sector_trade_large = (
        stock_trades.assign(순매수금액=stock_trades["우리결제금액"] * stock_trades["거래구분"].map({"매수": 1, "매도": -1}).fillna(0))
        .groupby("업종대분류")["순매수금액"].sum().reset_index()
    )
    sector_trade_mid = (
        stock_trades.assign(순매수금액=stock_trades["우리결제금액"] * stock_trades["거래구분"].map({"매수": 1, "매도": -1}).fillna(0))
        .groupby("업종중분류")["순매수금액"].sum().reset_index()
    )
    sector_large_rank = stock_holdings.groupby("업종대분류")["우리평가금"].sum().to_dict() if not stock_holdings.empty else {}
    sector_large_view_labels = sorted(sector_large_labels, key=lambda label: sector_large_rank.get(label, 0.0), reverse=True)
    sector_mid_rank = stock_holdings.groupby("업종중분류")["우리평가금"].sum().to_dict() if not stock_holdings.empty else {}
    sector_mid_view_labels = sorted(sector_mid_labels, key=lambda label: sector_mid_rank.get(label, 0.0), reverse=True)
    return f"""
      <div class="summary-strip">
        <span class="period-data" data-period="{esc(period)}"></span>
        <div class="selected-block"><span class="eyebrow">선택 펀드</span><h2>{esc(label)}</h2><small>{esc(count_meta)}</small></div>
        <div class="metric-groups">
          <div class="metric-group pl-group">
            {kpi("전체 PL", fmt_money(global_pl.get("전체PL")), "합산")}
            {kpi("수익증권 PL", fmt_money(global_pl.get("수익증권PL")), "펀드")}
            {kpi("투자주식 PL", fmt_money(global_pl.get("투자주식PL")), "직접")}
            {kpi("상품주식 PL", fmt_money(global_pl.get("상품주식PL")), "직접")}
          </div>
          <div class="metric-group exposure-group">
            {kpi("전체 Exposure", fmt_money(total_exposure), "합산")}
            {kpi("수익증권 Net", fmt_money(net_exposure), f"전체 중 {fmt_pct(net_exposure / total_fund_amount if total_fund_amount else pd.NA)}")}
            {kpi("투자주식 Exposure", fmt_money(investment_exposure), "직접")}
            {kpi("상품주식 Exposure", fmt_money(product_exposure), "직접")}
          </div>
        </div>
      </div>
      <section id="holdingSection" class="section-block">
        <div class="section-title"><h3>보유분석</h3></div>
        <div class="hold-grid">
          {investment_table_html}
          <article class="panel fund-pl-panel"><div class="panel-title"><h4>펀드별 등락율/손익</h4><span>등락율 내림차순</span></div>{fund_pl_table(all_stock_holdings_for_pl, all_holdings, fund_catalog, None if label == "전체 펀드 통합" else label)}</article>
          <article class="panel long-panel"><div class="panel-title"><h4>Long 보유내역</h4><span>hover: 펀드별 금액/비율</span></div>{holding_table(stock_holdings, "매수", total_fund_amount)}</article>
          {product_table_html}
          <article class="panel sector-large-panel"><div class="mini-title"><span class="mini-icon"></span>업종별(대)</div>{sector_large_pie_svg(list(zip(sector_large_hold["업종대분류"], sector_large_hold["우리평가금"])))}</article>
          <article class="panel sector-mid-panel"><div class="mini-title"><span class="mini-icon"></span>업종별(중)</div>{sector_mid_bar_svg(list(zip(sector_mid_hold["업종중분류"], sector_mid_hold["우리평가금"])), sector_mid_view_labels)}</article>
          <article class="panel short-panel"><div class="panel-title"><h4>Short 보유내역</h4><span>hover: 펀드별 금액/비율</span></div>{holding_table(stock_holdings, "매도", total_fund_amount)}</article>
        </div>
      </section>
      <section id="tradeSection" class="section-block">
        <div class="section-title"><h3>매매분석</h3><span>현금성자산 제외, 주식/주식관련 포지션만 표시</span></div>
        <div class="kpis compact">
          {kpi("총 매수", fmt_money(buy_amount), f"{int((stock_trades['거래구분'] == '매수').sum()):,}건")}
          {kpi("총 매도", fmt_money(sell_amount), f"{int((stock_trades['거래구분'] == '매도').sum()):,}건")}
          {kpi("순매수", fmt_money(buy_amount - sell_amount), "전체 기간")}
          {kpi("매매 종목", f"{stock_trades['종목코드정규'].nunique():,}개", f"거래 {len(stock_trades):,}건")}
        </div>
        <div class="trade-grid">
          <article class="panel"><div class="panel-title"><h4>상위 순매수</h4><span>hover: 펀드별 순금액/비율</span></div>{net_trade_table(stock_trades, "buy")}</article>
          <article class="panel"><div class="panel-title"><h4>상위 순매도</h4><span>hover: 펀드별 순금액/비율</span></div>{net_trade_table(stock_trades, "sell")}</article>
          <article class="panel trade-recent"><div class="panel-title trade-title"><h4>매매내역</h4><div class="trade-range"><input class="trade-date" id="tradeStart" type="date" aria-label="매매 시작일"><span>~</span><input class="trade-date" id="tradeEnd" type="date" aria-label="매매 종료일"></div></div><div class="table-wrap"><table id="stockTradeTable"></table></div></article>
          <article class="panel trade-sector-panel"><div class="panel-title"><h4>업종별 매매내역(대)</h4><span>매수 + / 매도 -</span></div>{trade_category_svg(list(zip(sector_trade_large["업종대분류"], sector_trade_large["순매수금액"])), sector_large_view_labels)}</article>
          <article class="panel trade-sector-panel"><div class="panel-title"><h4>업종별 매매내역(중)</h4><span>매수 + / 매도 -</span></div>{trade_category_svg(list(zip(sector_trade_mid["업종중분류"], sector_trade_mid["순매수금액"])), sector_mid_view_labels)}</article>
        </div>
      </section>
    """


def build_dashboard() -> Path:
    funds, trades_raw, holdings_raw = read_inputs()
    quotes, quote_source = load_quote_cache()
    industry_large_by_code, industry_mid_by_code = read_industry_map()
    codes = set(funds["펀드코드"])
    info = funds.set_index("펀드코드")

    holdings = holdings_raw[holdings_raw["협회펀드코드"].isin(codes)].copy()
    trades = trades_raw[trades_raw["협회펀드코드"].isin(codes)].copy()
    for df in (holdings, trades):
        df["보유펀드명"] = df["협회펀드코드"].map(info["펀드명"]).fillna(df["펀드명"])
        df["지분율"] = df["협회펀드코드"].map(info["지분율"]).fillna(1)
        df["펀드평가액원"] = df["협회펀드코드"].map(info["평가액원"])

    holdings["우리평가금"] = holdings["평가금"].fillna(0) * holdings["지분율"]
    holdings["우리취득가액"] = holdings["취득가액"].fillna(0) * holdings["지분율"]
    trades["우리결제금액"] = trades["결제금액"].fillna(0) * trades["지분율"]

    quote_values = holdings.apply(lambda row: quote_for(row, quotes), axis=1)
    holdings = pd.concat([holdings, quote_values], axis=1)
    holdings["업종대분류"] = holdings["종목코드정규"].map(industry_large_by_code).fillna("미분류")
    holdings["업종중분류"] = holdings["종목코드정규"].map(industry_mid_by_code).fillna("미분류")
    holdings["업종"] = holdings["업종중분류"]
    holdings["포지션부호"] = holdings.apply(signed_position, axis=1)
    holdings["시장PL"] = holdings["우리평가금"] * holdings["등락율"] / 100.0
    holdings["PL"] = holdings["우리평가금"] * holdings["포지션부호"] * holdings["등락율"] / 100.0

    trades["업종대분류"] = trades["종목코드정규"].map(industry_large_by_code).fillna("미분류")
    trades["업종중분류"] = trades["종목코드정규"].map(industry_mid_by_code).fillna("미분류")
    trades["업종"] = trades["업종중분류"]

    stock_holdings = holdings[is_equity_related(holdings, "자산군")].copy()
    stock_trades = trades[is_equity_related(trades, "자산구분") & trades["거래구분"].isin(["매수", "매도"])].copy()
    stock_trade_history = stock_trades.copy()
    if not stock_trades.empty and stock_trades["기준일"].notna().any():
        default_trade_end = stock_trades["기준일"].max()
        stock_trades = stock_trades[stock_trades["기준일"] >= default_trade_end - pd.DateOffset(months=1)].copy()
    trade_history = [
        {
            "date": row["기준일"].strftime("%Y-%m-%d") if pd.notna(row["기준일"]) else "",
            "fundCode": str(row["협회펀드코드"]),
            "fund": str(row["보유펀드명"]),
            "name": str(row["종목명"]),
            "side": str(row["거래구분"]),
            "amount": float(row["우리결제금액"]) if pd.notna(row["우리결제금액"]) else 0.0,
        }
        for _, row in stock_trade_history.iterrows()
    ]

    investment_stocks = prepare_direct_stock_sheet("투자주식", quotes)
    product_stocks = prepare_direct_stock_sheet("상품주식", quotes)
    fund_pl = safe_sum(stock_holdings["PL"])
    investment_pl = safe_sum(investment_stocks["PL"])
    product_pl = safe_sum(product_stocks["PL"])
    investment_exposure = safe_sum(investment_stocks["평가액"])
    product_exposure = safe_sum(product_stocks["평가액"])
    total_pl = None if all(v is None for v in [fund_pl, investment_pl, product_pl]) else sum(v or 0 for v in [fund_pl, investment_pl, product_pl])
    global_pl = {
        "전체PL": total_pl,
        "수익증권PL": fund_pl,
        "투자주식PL": investment_pl,
        "상품주식PL": product_pl,
        "투자주식Exposure": investment_exposure,
        "상품주식Exposure": product_exposure,
    }
    investment_table = direct_stock_table(investment_stocks, "투자주식", "investment-panel")
    product_table = direct_stock_table(product_stocks, "상품주식", "product-panel")
    sector_mid_labels = (
        stock_holdings.groupby("업종중분류")["우리평가금"].sum().sort_values(ascending=False).index.astype(str).tolist()
    )
    sector_large_labels = (
        stock_holdings.groupby("업종대분류")["우리평가금"].sum().sort_values(ascending=False).index.astype(str).tolist()
    )

    views = {"ALL": make_view("전체 펀드 통합", holdings, stock_holdings, stock_holdings, stock_trades, funds, global_pl, investment_table, product_table, sector_large_labels, sector_mid_labels)}
    fund_buttons = [{
        "key": "ALL",
        "name": "전체 펀드",
        "code": "ALL",
        "type": "전체",
        "meta": "",
    }]
    type_order = {"주식": 0, "멀티": 1, "롱숏": 2, "혼합": 3, "IPO": 4}
    funds_sorted = funds.assign(_type_order=funds["유형"].map(type_order).fillna(99)).sort_values(["_type_order", "펀드명"])
    for _, fund in funds_sorted.iterrows():
        code = fund["펀드코드"]
        h_all = holdings[holdings["협회펀드코드"] == code].copy()
        h_stock = stock_holdings[stock_holdings["협회펀드코드"] == code].copy()
        t_stock = stock_trades[stock_trades["협회펀드코드"] == code].copy()
        views[code] = make_view(fund["펀드명"], h_all, h_stock, stock_holdings, t_stock, funds, global_pl, investment_table, product_table, sector_large_labels, sector_mid_labels)
        fund_buttons.append({
            "key": code,
            "name": fund["펀드명"],
            "code": code,
            "type": fund["유형"],
            "meta": "",
        })

    source_note = {
        "input_dir": str(BASE_DIR),
        "fund_count": int(len(funds)),
        "holding_stock_related_rows": int(len(stock_holdings)),
        "trade_stock_related_rows": int(len(stock_trades)),
        "quote_source": quote_source,
        "quote_count": len(quotes),
        "direct_stock_file": INPUTS["direct_stocks"].name if INPUTS["direct_stocks"].exists() else "없음",
        "amount_basis": "원본 금액 x 펀드정보 지분율",
    }

    html_text = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>주식 & 수익증권 대시보드</title>
  <style>
    :root {{ --hana:#00483a; --hana-light:#00a88e; --navy:#12372d; --ink:#16251f; --muted:#697872; --line:#dfe8e4; --bg:#f5f7f4; --panel:#fff; --soft:#edf5f1; --danger:#e7663f; }}
    * {{ box-sizing:border-box; }}
    html {{ scroll-behavior:smooth; }}
    body {{ margin:0; background:var(--bg); color:var(--ink); font-family:"Segoe UI","Malgun Gothic",Arial,sans-serif; }}
    .topbar {{ height:52px; background:linear-gradient(90deg,#f8fbf9 0%,#fff 44%,#edf7f3 100%); border-bottom:1px solid var(--line); display:flex; align-items:center; justify-content:space-between; padding:0 22px; position:sticky; top:0; z-index:20; }}
    .brand {{ display:flex; align-items:center; gap:12px; font-weight:900; color:var(--hana); letter-spacing:-.3px; font-size:28px; }}
    .refresh-button {{ border:1px solid var(--hana); background:#fff; color:var(--hana); border-radius:7px; padding:6px 10px; font-size:12px; font-weight:900; cursor:pointer; }}
    .refresh-button:hover {{ background:#e8f6f5; }}
    .caption {{ color:var(--muted); font-size:12px; text-align:right; display:grid; gap:2px; }}
    .caption small {{ font-size:11px; color:var(--hana); font-weight:800; }}
    .layout {{ display:grid; grid-template-columns:330px minmax(0,1fr); min-height:calc(100vh - 52px); }}
    aside {{ background:#fff; border-right:1px solid var(--line); padding:12px 14px; position:sticky; top:52px; height:calc(100vh - 52px); overflow:hidden; display:flex; flex-direction:column; }}
    aside h1 {{ margin:0 8px 8px; font-size:18px; color:var(--navy); }}
    .quick-nav {{ display:grid; grid-template-columns:1fr 1fr; gap:7px; margin:0 8px 12px; position:sticky; top:0; background:#fff; z-index:3; }}
    .quick-nav button {{ border:1px solid var(--hana); background:#fff; color:var(--hana); border-radius:8px; padding:8px; font-weight:800; cursor:pointer; }}
    .quick-nav button:hover {{ background:#e8f6f5; }}
    .fund-list {{ display:block; overflow:auto; padding:0 4px 8px; }}
    .fund-group {{ margin:0 0 8px; }}
    .fund-group-title {{ display:flex; align-items:center; gap:7px; margin:6px 4px 5px; font-size:12px; font-weight:900; color:var(--hana); }}
    .fund-group-title:after {{ content:""; height:1px; flex:1; background:var(--line); }}
    .fund-group-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:6px; }}
    .fund-button {{ width:100%; border:1px solid transparent; background:#fff; color:var(--ink); border-radius:7px; padding:7px 8px; text-align:left; cursor:pointer; min-width:0; }}
    .fund-button:hover {{ border-color:#b8dedd; background:#f3fbfa; }}
    .fund-button.active {{ background:#e8f6f1; border-color:var(--hana); box-shadow:inset 3px 0 0 var(--hana); }}
    .fund-button strong {{ display:block; font-size:12px; margin-bottom:2px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .fund-button small {{ display:none; }}
    main {{ padding:6px 18px 34px; overflow:auto; }}
    .summary-strip {{ display:flex; align-items:stretch; gap:12px; width:100%; margin-bottom:4px; }}
    .eyebrow {{ color:var(--hana); font-weight:800; font-size:12px; }}
    h2 {{ margin:3px 0 0; font-size:24px; color:var(--navy); }}
    .selected-block {{ flex:0 0 220px; min-width:0; }}
    .selected-block small {{ display:block; color:var(--muted); font-size:11px; font-weight:800; margin-top:3px; }}
    .metric-groups {{ flex:1 1 auto; display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:10px; min-width:0; }}
    .metric-group {{ display:grid; grid-template-columns:1.12fr 1fr 1fr 1fr; gap:7px; padding:7px; border:1px solid var(--line); border-radius:8px; background:rgba(255,255,255,.72); min-width:0; }}
    .metric-group .kpi:first-child {{ border-color:var(--hana); background:#eaf5f0; box-shadow:inset 4px 0 0 var(--hana); }}
    .period {{ color:var(--muted); font-size:12px; }}
    .section-block {{ scroll-margin-top:74px; margin-bottom:18px; }}
    .section-title {{ display:flex; justify-content:space-between; align-items:baseline; margin:2px 0 6px; }}
    .section-title h3 {{ margin:0; font-size:20px; color:var(--navy); }}
    .section-title span {{ color:var(--muted); font-size:12px; }}
    .kpis {{ display:grid; grid-template-columns:repeat(4,minmax(120px,1fr)); gap:10px; margin-bottom:12px; }}
    .kpi {{ background:#fff; border:1px solid var(--line); border-radius:6px; padding:7px 8px; min-height:58px; min-width:0; box-shadow:0 1px 0 rgba(0,72,58,.04); }}
    .kpi span {{ display:block; color:var(--muted); font-size:10.5px; margin-bottom:4px; }}
    .kpi strong {{ display:block; color:var(--navy); font-size:15px; line-height:1.1; white-space:nowrap; letter-spacing:0; }}
    .kpi small {{ display:block; color:var(--muted); font-size:10px; margin-top:4px; white-space:nowrap; }}
    .hold-grid {{ display:grid; grid-template-columns:1.22fr 1.05fr 1.31fr; gap:10px; align-items:start; }}
    .trade-grid {{ display:grid; grid-template-columns:1.55fr 1.55fr .75fr .75fr .75fr .75fr; gap:12px; align-items:start; }}
    .panel {{ background:var(--panel); border:1px solid var(--line); border-radius:6px; padding:12px; min-width:0; overflow:hidden; box-shadow:0 2px 8px rgba(18,55,45,.04); }}
    .investment-panel {{ grid-column:1; grid-row:1; }}
    .product-panel {{ grid-column:1; grid-row:2; }}
    .fund-pl-panel {{ grid-column:2; grid-row:1 / span 2; }}
    .long-panel {{ grid-column:3; grid-row:1 / span 2; }}
    .sector-large-panel {{ grid-column:1; grid-row:3; }}
    .sector-mid-panel {{ grid-column:2; grid-row:3; }}
    .short-panel {{ grid-column:3; grid-row:3; }}
    .sector-large-panel,.sector-mid-panel,.short-panel {{ height:760px; }}
    .trade-recent {{ grid-column:span 4; }}
    .chart-panel {{ grid-column:span 3; }}
    .trade-sector-panel {{ grid-column:1 / -1; }}
    .panel-title {{ display:flex; align-items:baseline; justify-content:space-between; gap:10px; margin-bottom:9px; }}
    h4 {{ margin:0; font-size:15px; color:var(--ink); }}
    .panel-title span {{ color:var(--muted); font-size:11px; text-align:right; }}
    .chart {{ width:100%; height:auto; display:block; }}
    .axis {{ fill:#687381; font-size:12px; }}
    .big-axis {{ font-size:14px; font-weight:700; }}
    .daily-axis {{ font-size:19px; font-weight:800; }}
    .value {{ fill:#263847; font-size:12px; font-weight:700; }}
    .gridline {{ stroke:#e7ecef; stroke-width:1; }}
    .zero {{ stroke:#98a2b3; stroke-width:1; stroke-dasharray:3 3; }}
    .pie-wrap {{ display:grid; grid-template-columns:minmax(320px,430px) minmax(0,1fr); gap:16px; align-items:center; justify-items:center; }}
    .pie {{ width:min(420px,100%); height:auto; }}
    .mini-title {{ display:flex; align-items:center; gap:7px; margin:0 0 8px; color:var(--hana); font-size:15px; font-weight:900; }}
    .mini-icon {{ width:12px; height:14px; display:inline-block; border-left:2px solid var(--hana); border-bottom:2px solid var(--hana); background:linear-gradient(90deg,transparent 0 2px,#007c70 2px 4px,transparent 4px 6px,#00a88e 6px 8px,transparent 8px); }}
    .sector-pie {{ width:min(540px,100%); height:auto; display:block; margin:-2px auto 6px; overflow:visible; }}
    .slice-tag {{ fill:#fff; font-size:13px; font-weight:900; paint-order:stroke; stroke:#00483a; stroke-width:4px; stroke-linejoin:round; }}
    .callout {{ stroke:#7d8f88; stroke-width:1; fill:none; }}
    .slice-callout {{ fill:#153c35; font-size:11px; font-weight:900; paint-order:stroke; stroke:#fff; stroke-width:3px; stroke-linejoin:round; }}
    .sector-bar {{ width:100%; height:720px; display:block; }}
    .bar-grid {{ stroke:#e1e9e5; stroke-width:1; }}
    .bar-axis {{ fill:#52615d; font-size:14px; }}
    .bar-label {{ fill:#3b4845; font-size:18px; font-weight:900; }}
    .bar-value {{ fill:#13221d; font-size:17px; font-weight:900; }}
    .trade-category-chart {{ width:100%; height:400px; display:block; overflow:visible; }}
    .trade-axis {{ font-size:12px; fill:#5f6b67; }}
    .trade-label {{ fill:#3e4b47; font-size:13px; font-weight:800; }}
    .sector-legend {{ list-style:none; margin:4px auto 0; padding:0; display:grid; grid-template-columns:repeat(2, max-content); justify-content:center; gap:7px 36px; max-height:230px; overflow:auto; }}
    .sector-legend li {{ display:grid; grid-template-columns:11px max-content max-content; align-items:center; gap:7px; font-size:14px; }}
    .sector-legend span {{ width:9px; height:9px; border-radius:50%; }}
    .sector-legend b {{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:130px; font-weight:700; }}
    .sector-legend em {{ font-style:normal; color:var(--hana); font-weight:900; text-align:right; }}
    .sector-legend small {{ display:none; }}
    .legend {{ list-style:none; margin:0; padding:0; display:grid; gap:6px; width:100%; }}
    .legend li {{ display:grid; grid-template-columns:10px minmax(90px,1fr) 50px 76px; align-items:center; gap:6px; font-size:11px; }}
    .legend span {{ width:9px; height:9px; border-radius:50%; }}
    .legend em {{ font-style:normal; color:var(--hana); font-weight:800; text-align:right; }}
    .legend small {{ color:var(--muted); text-align:right; }}
    .table-wrap {{ overflow:auto; border:1px solid var(--line); border-radius:8px; max-height:660px; }}
    .table-wrap.tall {{ max-height:660px; }}
    .table-wrap.direct {{ max-height:360px; }}
    .table-wrap.fund-pl {{ max-height:760px; }}
    .short-panel .table-wrap {{ max-height:700px; }}
    table {{ width:100%; border-collapse:collapse; font-size:10.5px; background:#fff; table-layout:auto; }}
    th,td {{ padding:6px 6px; border-bottom:1px solid var(--line); text-align:right; white-space:nowrap; }}
    th:first-child,td:first-child,th:nth-child(2),td:nth-child(2),th:nth-child(3),td:nth-child(3) {{ text-align:left; }}
    th {{ background:#eef5f1; color:#40515d; font-weight:800; position:sticky; top:0; z-index:1; }}
    .total-label {{ font-weight:800; color:var(--navy); }}
    tbody tr:last-child td {{ background:#f8fafc; font-weight:800; }}
    .highlight-row {{ background:#fff7d6 !important; color:var(--navy); font-weight:900; }}
    .name-cell {{ max-width:82px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .fund-pl table {{ table-layout:fixed; }}
    .fund-pl th,.fund-pl td {{ padding-left:5px; padding-right:5px; }}
    .fund-pl th:first-child,.fund-pl td:first-child {{ width:68px; max-width:68px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .fund-pl th:nth-child(2),.fund-pl td:nth-child(2) {{ width:34px; }}
    .fund-pl th:nth-child(3),.fund-pl td:nth-child(3) {{ width:62px; }}
    .fund-pl th:nth-child(4),.fund-pl td:nth-child(4) {{ width:62px; }}
    .fund-pl th:nth-child(5),.fund-pl td:nth-child(5) {{ width:58px; }}
    .fund-pl .rate-bar {{ width:52px; max-width:52px; }}
    .investment-panel .name-cell,.product-panel .name-cell {{ max-width:82px; }}
    .investment-panel th:nth-child(2),.investment-panel td:nth-child(2),.product-panel th:nth-child(2),.product-panel td:nth-child(2) {{ max-width:48px; overflow:hidden; text-overflow:ellipsis; }}
    .investment-panel th:nth-child(3),.investment-panel td:nth-child(3),.product-panel th:nth-child(3),.product-panel td:nth-child(3) {{ max-width:54px; }}
    .long-panel .name-cell {{ max-width:122px; }}
    .short-panel .name-cell {{ max-width:82px; }}
    .long-panel th:nth-child(3),.long-panel td:nth-child(3),.short-panel th:nth-child(3),.short-panel td:nth-child(3) {{ max-width:54px; overflow:hidden; text-overflow:ellipsis; }}
    .long-panel th,.long-panel td,.short-panel th,.short-panel td {{ padding-left:5px; padding-right:5px; }}
    .trade-recent th:nth-child(2),.trade-recent td:nth-child(2) {{ max-width:66px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .trade-recent th:nth-child(3),.trade-recent td:nth-child(3) {{ max-width:82px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .profit-cell {{ color:#e7663f; font-weight:800; }}
    .loss-cell {{ color:#2563eb; font-weight:800; }}
    .buy-cell {{ color:#e7663f; font-weight:800; }}
    .sell-cell {{ color:#2563eb; font-weight:800; }}
    .rate-bar {{ position:relative; height:18px; width:64px; max-width:64px; background:#f1f5f9; border-radius:4px; overflow:hidden; margin-left:auto; }}
    .rate-bar span {{ position:absolute; top:0; bottom:0; opacity:.72; }}
    .rate-bar .bar-zero {{ left:50%; width:1px; background:#667085; opacity:.8; }}
    .rate-bar .bar-pos {{ background:#f59e9e; }}
    .rate-bar .bar-neg {{ background:#93c5fd; }}
    .rate-bar em {{ position:relative; z-index:2; display:block; text-align:center; font-style:normal; font-weight:800; color:#172033; line-height:18px; font-size:10px; }}
    .has-tip {{ cursor:help; }}
    .has-tip:hover {{ background:#f3fbfa; }}
    .empty {{ padding:24px; color:var(--muted); text-align:center; border:1px dashed var(--line); border-radius:8px; }}
    .audit {{ color:var(--muted); font-size:11px; margin-top:14px; }}
    .trade-title {{ flex-wrap:wrap; }}.trade-range {{ margin-left:auto;display:flex;align-items:center;gap:5px }}.trade-date {{ width:122px;border:1px solid #9abeb6;border-radius:4px;padding:4px 7px }}
    @media (max-width:1280px) {{ .hold-grid,.trade-grid {{ grid-template-columns:1fr 1fr; }} .investment-panel,.product-panel,.fund-pl-panel,.long-panel,.short-panel,.sector-large-panel,.sector-mid-panel,.trade-recent,.chart-panel {{ grid-column:1 / -1; grid-row:auto; }} }}
    @media (max-width:980px) {{ .topbar {{ height:auto;min-height:52px;padding:8px 10px;align-items:flex-start;gap:6px;flex-wrap:wrap }}.brand {{ font-size:20px }}.layout {{ grid-template-columns:1fr; }} aside {{ position:static; height:auto; border-right:0; border-bottom:1px solid var(--line);padding:8px }} .fund-list {{ max-height:220px; }} .fund-group-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)) }} main {{ padding:8px }}.kpis,.hold-grid,.trade-grid,.pie-wrap {{ grid-template-columns:1fr; }} .trade-recent {{ grid-column:auto; }}.metric-groups {{ grid-template-columns:1fr }}.summary-strip {{ align-items:flex-start;flex-wrap:wrap }}.trade-range {{ width:100%;margin-left:0 }}.trade-date {{ width:calc(50% - 12px) }}.panel {{ padding:8px }} }}
  </style>
</head>
<body>
  <div class="topbar">
    <div class="brand"><span>주식 & 수익증권 대시보드</span><button type="button" id="refreshPage" class="refresh-button">새로고침</button></div>
    <div class="caption"><span>작업 폴더 raw 데이터 · 지분율 반영 · 주식/주식관련 분석</span><small id="periodCaption"></small></div>
  </div>
  <div class="layout">
    <aside>
      <h1>펀드 목록</h1>
      <div class="quick-nav">
        <button type="button" data-target="holdingSection">보유분석</button>
        <button type="button" data-target="tradeSection">매매분석</button>
      </div>
      <div id="fundList" class="fund-list"></div>
    </aside>
    <main>
      <div id="dashboard"></div>
      <div class="audit">검증 메모: {esc(json.dumps(source_note, ensure_ascii=False))}</div>
    </main>
  </div>
  <script>
    const views = {json.dumps(views, ensure_ascii=False)};
    const funds = {json.dumps(fund_buttons, ensure_ascii=False)};
    const tradeHistory = {json.dumps(trade_history, ensure_ascii=False)};
    const tradeDates = tradeHistory.map(row => row.date).filter(Boolean).sort();
    const tradeMax = tradeDates.at(-1) || "";
    const tradeMin = tradeDates[0] || "";
    const defaultTradeStart = tradeMax ? (() => {{ const d=new Date(`${{tradeMax}}T00:00:00`); d.setMonth(d.getMonth()-1); return d.toISOString().slice(0,10); }})() : "";
    let tradeStart = defaultTradeStart, tradeEnd = tradeMax;
    const fundList = document.getElementById("fundList");
    const dashboard = document.getElementById("dashboard");
    let currentKey = "ALL";
    function renderTradeHistory() {{
      const table = document.getElementById("stockTradeTable");
      if (!table) return;
      const rows = tradeHistory.filter(row => (currentKey === "ALL" || row.fundCode === currentKey) && (!tradeStart || row.date >= tradeStart) && (!tradeEnd || row.date <= tradeEnd)).sort((a,b)=>b.date.localeCompare(a.date)).slice(0,500);
      table.innerHTML = `<thead><tr><th>기준일</th><th>펀드명</th><th>종목명</th><th>거래</th><th>금액(실보유)</th></tr></thead><tbody>${{rows.map(row=>`<tr><td>${{row.date}}</td><td>${{row.fund}}</td><td>${{row.name}}</td><td>${{row.side}}</td><td class="num">${{Math.round(row.amount).toLocaleString("ko-KR")}}</td></tr>`).join("")}}</tbody>`;
      for (const [id,value] of [["tradeStart",tradeStart],["tradeEnd",tradeEnd]]) {{ const input=document.getElementById(id); if(!input)continue; input.min=tradeMin;input.max=tradeMax;input.value=value;input.onchange=e=>{{if(id==="tradeStart")tradeStart=e.target.value;else tradeEnd=e.target.value;renderTradeHistory();}}; }}
    }}
    function render(key) {{
      currentKey = key;
      dashboard.innerHTML = views[key];
      const period = dashboard.querySelector(".period-data")?.dataset.period || "";
      document.getElementById("periodCaption").textContent = period ? `매매기간 ${{period}}` : "";
      renderTradeHistory();
      document.querySelectorAll(".fund-button").forEach((button) => button.classList.toggle("active", button.dataset.key === key));
    }}
    function drawList(term = "") {{
      const normalized = "";
      fundList.innerHTML = "";
      const order = ["전체", "주식", "멀티", "롱숏", "혼합", "IPO"];
      const filtered = funds.filter((fund) => !normalized || `${{fund.name}} ${{fund.code}} ${{fund.type}}`.toLowerCase().includes(normalized));
      order.concat([...new Set(filtered.map((fund) => fund.type).filter((type) => !order.includes(type)))]).forEach((type) => {{
        const groupFunds = filtered.filter((fund) => fund.type === type);
        if (!groupFunds.length) return;
        const group = document.createElement("div");
        group.className = "fund-group";
        group.innerHTML = `<div class="fund-group-title">${{type}}</div><div class="fund-group-grid"></div>`;
        const grid = group.querySelector(".fund-group-grid");
        groupFunds.forEach((fund) => {{
          const button = document.createElement("button");
          button.className = "fund-button";
          button.dataset.key = fund.key;
          button.innerHTML = `<strong>${{fund.name}}</strong>`;
          button.addEventListener("click", () => render(fund.key));
          grid.appendChild(button);
        }});
        fundList.appendChild(group);
      }});
      document.querySelectorAll(".fund-button").forEach((button) => button.classList.toggle("active", button.dataset.key === currentKey));
    }}
    document.querySelectorAll(".quick-nav button").forEach((button) => {{
      button.addEventListener("click", () => document.getElementById(button.dataset.target)?.scrollIntoView({{ behavior:"smooth", block:"start" }}));
    }});
    document.getElementById("refreshPage")?.addEventListener("click", () => location.reload());
    drawList();
    render("ALL");
  </script>
</body>
</html>
"""
    OUTPUT.write_text(html_text, encoding="utf-8")
    return OUTPUT


if __name__ == "__main__":
    print(build_dashboard())

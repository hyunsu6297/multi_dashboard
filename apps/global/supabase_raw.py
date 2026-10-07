"""KFR Partner API snapshots, matching the stock dashboard's DB contract."""
from __future__ import annotations
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import pandas as pd

COMMON = {"fund_kr_code": "협회펀드코드", "item_code": "종목코드", "item_k_name": "종목명", "asset_s_class_k_name": "시장구분"}
MAPS = {
    "fund_holdings": {**COMMON, "buy_day": "보유일", "fund_k_name": "펀드명", "asset_b_class_k_name": "자산군", "qty": "수량", "price": "평가가격", "eval_amt": "평가금", "invest_amt": "원천투자금", "nav_amt": "순자산", "share_ratio": "지분율", "flag": "포지션"},
    "fund_trades": {**COMMON, "trade_day": "기준일", "fund_kr_full_name": "펀드명", "asset_b_class_k_name": "자산구분", "trade_qty": "매매수량", "trade_price": "매매가격", "settle_amt": "결제금액", "trade_type": "거래구분"},
}

class SupabaseRaw:
    def __init__(self):
        key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY") or "").strip()
        if not key:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY 환경변수가 필요합니다.")
        self.base = os.getenv("SUPABASE_URL", "https://esqakvzvchcunhzjlyry.supabase.co").rstrip("/") + "/rest/v1/"
        self.headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    def get(self, table, params):
        request = Request(self.base + table + "?" + urlencode(params, safe=".,()"), headers=self.headers)
        try:
            with urlopen(request, timeout=120) as response:
                result = json.load(response)
        except HTTPError as exc:
            raise RuntimeError(f"Supabase {table} 조회 실패 (HTTP {exc.code})") from exc
        if not isinstance(result, list):
            raise RuntimeError(f"Supabase {table}: 잘못된 응답 형식")
        return result

    def pages(self, table, params):
        offset = 0
        while True:
            batch = self.get(table, {**params, "limit": "1000", "offset": str(offset)})
            if not batch:
                break
            yield from batch
            offset += len(batch)

    def snapshots(self, source, latest=False, start=None, end=None):
        params = {"select": "id,business_date,row_count,file_name,downloaded_at", "source_key": f"eq.{source}", "source_format": "eq.kfr_partner_api_json", "order": "business_date.desc,downloaded_at.desc,id.desc"}
        dates = []
        if start:
            dates.append(f"business_date.gte.{start}")
        if end:
            dates.append(f"business_date.lte.{end}")
        if dates:
            params["and"] = "(" + ",".join(dates) + ")"
        if latest:
            return self.get("kfr_source_snapshots", {**params, "limit": "1"})
        by_date = {}
        for row in self.pages("kfr_source_snapshots", params):
            by_date.setdefault(str(row["business_date"]), row)
        return [by_date[day] for day in sorted(by_date)]

    def frame(self, source, snapshots, codes):
        rows = []
        if not all(re.fullmatch(r"[A-Za-z0-9]+", code) for code in codes):
            raise ValueError("펀드코드는 영문·숫자로 입력해야 합니다.")
        for snapshot in snapshots if codes else []:
            params = {"select": "row_no,payload", "snapshot_id": f"eq.{snapshot['id']}", "order": "row_no.asc", "payload->>fund_kr_code": "in.(" + ",".join(codes) + ")"}
            for item in self.pages("kfr_source_rows", params):
                payload = item.get("payload") or {}
                required = {"fund_kr_code", "item_code", "eval_amt", "nav_amt", "share_ratio"} if source == "fund_holdings" else {"fund_kr_code", "item_code", "settle_amt", "trade_type"}
                if not required.issubset(payload):
                    raise RuntimeError(f"{source}: KFR API 필수 필드 누락")
                row = {label: payload.get(field) for field, label in MAPS[source].items()}
                row["스냅샷일"] = snapshot["business_date"]
                rows.append(row)
        return pd.DataFrame(rows, columns=[*MAPS[source].values(), "스냅샷일"]).drop_duplicates()

    def daily_nav_frame(self, snapshots, codes):
        """Fetch only the position-level NAV and ownership fields needed on trade dates."""
        if not all(re.fullmatch(r"[A-Za-z0-9]+", code) for code in codes):
            raise ValueError("펀드코드는 영문·숫자로 입력해야 합니다.")
        rows = []
        for snapshot in snapshots if codes else []:
            params = {"select": "row_no,payload->>fund_kr_code,payload->>nav_amt,payload->>share_ratio",
                      "snapshot_id": f"eq.{snapshot['id']}", "order": "row_no.asc",
                      "payload->>fund_kr_code": "in.(" + ",".join(codes) + ")"}
            for item in self.pages("kfr_source_rows", params):
                rows.append({"기준일": snapshot["business_date"], "협회펀드코드": item.get("fund_kr_code"),
                             "순자산": item.get("nav_amt"), "지분율": item.get("share_ratio")})
        return pd.DataFrame(rows, columns=["기준일", "협회펀드코드", "순자산", "지분율"])

def load_raw(codes, start=None, end=None, *, allow_empty=False):
    for value in (start, end):
        if value and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("조회일은 YYYY-MM-DD 형식이어야 합니다.")
    client = SupabaseRaw()
    hs = client.snapshots("fund_holdings", latest=True, end=end)
    if not hs:
        raise RuntimeError("Supabase에 보유현황 API 스냅샷이 없습니다.")
    ts = client.snapshots("fund_trades", start=start, end=end)
    trade_dates = {snapshot["business_date"] for snapshot in ts}
    nav_snapshots = [snapshot for snapshot in client.snapshots("fund_holdings", start=min(trade_dates), end=max(trade_dates))
                     if snapshot["business_date"] in trade_dates] if trade_dates else []
    with ThreadPoolExecutor(max_workers=3) as pool:
        h = pool.submit(client.frame, "fund_holdings", hs, codes)
        t = pool.submit(client.frame, "fund_trades", ts, codes)
        n = pool.submit(client.daily_nav_frame, nav_snapshots, codes)
        holdings, trades, daily_nav = h.result(), t.result(), n.result()
    if holdings.empty and not allow_empty:
        raise RuntimeError("최신 보유현황에 관리 대상 펀드가 없습니다. 펀드코드를 확인하세요.")
    return holdings, trades, daily_nav, {"provider": "supabase", "holdingsDate": hs[0]["business_date"], "tradeDates": [s["business_date"] for s in ts], "holdings": "Supabase / fund_holdings", "trades": "Supabase / fund_trades"}

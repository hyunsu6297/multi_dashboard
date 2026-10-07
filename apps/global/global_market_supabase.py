"""Supabase transport shared by the Bloomberg-only global receiver."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

DEFAULT_SUPABASE_URL = "https://esqakvzvchcunhzjlyry.supabase.co"
REQUEST_TABLE = "global_market_refresh_requests"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} environment variable is required.")
    return value


class SupabaseRest:
    def __init__(self, url: str, secret_key: str) -> None:
        self.base_url = f"{url.rstrip('/')}/rest/v1"
        self.headers = {"apikey": secret_key, "Authorization": f"Bearer {secret_key}",
                        "Content-Type": "application/json"}

    def request(self, path: str, *, method: str = "GET", body: Any = None,
                headers: dict[str, str] | None = None) -> bytes:
        payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(f"{self.base_url}/{path}", data=payload, method=method,
                                     headers={**self.headers, **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Supabase HTTP {exc.code}: {detail[:500]}") from exc

    def get_all(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode(params, safe=".,()")
        return json.loads(self.request(f"{table}?{query}") or b"[]")

    def upsert_rows(self, table: str, rows: list[dict[str, Any]], conflict: str) -> None:
        if not rows:
            return
        path = f"{table}?on_conflict={urllib.parse.quote(conflict)}"
        for start in range(0, len(rows), 500):
            self.request(path, method="POST", body=rows[start:start + 500],
                         headers={"Prefer": "resolution=merge-duplicates,return=minimal"})

    def update_rows(self, table: str, filters: dict[str, str], payload: dict[str, Any]) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode(filters, safe=".,()")
        return json.loads(self.request(f"{table}?{query}", method="PATCH", body=payload,
                                       headers={"Prefer": "return=representation"}) or b"[]")


def normalize_security_list(values: Any) -> list[str]:
    if not isinstance(values, list) or len(values) > 1000:
        raise ValueError("Invalid security list")
    out = []
    for value in values:
        if not isinstance(value, str) or len(value) > 180:
            raise ValueError("Invalid security identifier")
        security = " ".join(value.split())
        if security:
            out.append(security)
    return list(dict.fromkeys(out))


def load_market_snapshot(client: SupabaseRest) -> tuple[dict[str, Any], str | None]:
    rows = client.get_all("manual_file_rows", {
        "select": "payload,created_by", "domain": "eq.global", "file_key": "eq.market_data", "limit": "1"})
    if not rows:
        return {"securities": {}, "errors": {}}, None
    return rows[0].get("payload") or {}, rows[0].get("created_by")


def publish_market_snapshot(client: SupabaseRest, market: dict[str, Any], created_by: str | None) -> None:
    record: dict[str, Any] = {"domain": "global", "file_key": "market_data",
                              "file_label": "Market data", "sheet_name": "Data", "row_no": 1,
                              "payload": market, "updated_at": utc_now()}
    if created_by:
        record["created_by"] = created_by
    client.upsert_rows("manual_file_rows", [record], "domain,file_key,sheet_name,row_no")


def publish_quotes(client: SupabaseRest, market: dict[str, Any]) -> None:
    now = utc_now()
    rows = [{"security": security, "payload": payload, "fx": market.get("fx"),
             "source": "bloomberg-pc-receiver", "as_of": market.get("asOf"),
             "updated_at": now, "error": None}
            for security, payload in (market.get("securities") or {}).items()]
    rows.extend({"security": security, "payload": {}, "fx": market.get("fx"),
                 "source": "bloomberg-pc-receiver", "as_of": market.get("asOf"),
                 "updated_at": now, "error": str(error)}
                for security, error in (market.get("errors") or {}).items()
                if security not in (market.get("securities") or {}))
    client.upsert_rows("global_market_quotes", rows, "security")


def complete_request(client: SupabaseRest, request_id: str, *, status: str,
                     result: dict[str, Any] | None = None, error: str | None = None) -> None:
    client.update_rows(REQUEST_TABLE, {"id": f"eq.{request_id}"},
                       {"status": status, "completed_at": utc_now(),
                        "result": result or {}, "error": error})

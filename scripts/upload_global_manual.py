"""Upload initial global dashboard manual data to Supabase.

Run this manually when the global dashboard domain is first added to a
Supabase project. It intentionally is not part of the daily workflow because
daily uploads would overwrite user edits made in the web UI.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANUAL_DIR = ROOT / "web" / "data" / "manual"
GLOBAL_FILES = [
    "global_etf_db.json",
    "global_fund_info.json",
    "global_emp_info.json",
    "global_emp_portfolios.json",
    "global_market_data.json",
]


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value.rstrip("/")


def request(method: str, url: str, key: str, body: Any | None = None, prefer: str | None = None) -> Any:
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            payload = res.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase HTTP {exc.code}: {detail[:1000]}") from exc
    return json.loads(payload) if payload else None


def main() -> None:
    base_url = f"{required_env('SUPABASE_URL')}/rest/v1/manual_file_rows"
    service_key = required_env("SUPABASE_SERVICE_ROLE_KEY")
    for file_name in GLOBAL_FILES:
        payload = json.loads((MANUAL_DIR / file_name).read_text(encoding="utf-8"))
        records = []
        for sheet in payload["sheets"]:
            for index, row in enumerate(sheet["rows"], start=1):
                records.append({
                    "domain": payload["domain"],
                    "file_key": payload["file_key"],
                    "file_label": payload["file_label"],
                    "sheet_name": sheet["name"],
                    "row_no": index,
                    "payload": row,
                })
        for start in range(0, len(records), 500):
            request(
                "POST",
                f"{base_url}?on_conflict=domain,file_key,sheet_name,row_no",
                service_key,
                records[start:start + 500],
                prefer="resolution=merge-duplicates,return=minimal",
            )
        print(f"uploaded {payload['domain']}/{payload['file_key']}: rows={len(records)}")


if __name__ == "__main__":
    main()

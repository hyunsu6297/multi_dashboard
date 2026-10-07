"""One-time, global-only migration of the local Edge dashboard cache to Supabase.

Requires dfindexeddb and SUPABASE_SERVICE_ROLE_KEY. A timestamped backup of the
existing global rows is written before any database mutation.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dfindexeddb.leveldb import ldb


URL = "https://esqakvzvchcunhzjlyry.supabase.co/rest/v1/manual_file_rows"
ORIGIN = b"_http://127.0.0.1:8766\x00\x01globalDashboard."
KEYS = {"etfs": ("etf_db", "ETF DB"), "funds": ("fund_info", "Fund DB"),
        "market": ("market_data", "Market data")}


def read_cache(leveldb_dir: Path) -> dict:
    latest = {}
    for filename in glob.glob(str(leveldb_dir / "*.ldb")):
        for record in ldb.FileReader(filename).GetKeyValueRecords():
            if not record.key.startswith(ORIGIN):
                continue
            key = record.key[len(ORIGIN):].decode("ascii", errors="ignore")
            if key not in KEYS or (key in latest and latest[key][0] > record.sequence_number):
                continue
            value = record.value
            if not value or value[0] not in (0, 1):
                continue
            decoded = value[1:].decode("utf-16-le" if value[0] == 0 else "utf-8")
            latest[key] = (record.sequence_number, json.loads(decoded))
    return {key: value for key, (_, value) in latest.items()}


def request(key: str, path: str, *, method: str = "GET", body=None, prefer=""):
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if prefer:
        headers["Prefer"] = prefer
    req = urllib.request.Request(URL + path,
                                 data=None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as response:
        raw = response.read()
    return json.loads(raw) if raw else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--leveldb-dir", type=Path,
                        default=Path.home() / "AppData/Local/Microsoft/Edge/User Data/Default/Local Storage/leveldb")
    parser.add_argument("--backup-dir", type=Path, default=Path.home() / "Documents/Codex/global-db-backups")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not key:
        raise SystemExit("SUPABASE_SERVICE_ROLE_KEY is required")
    cache = read_cache(args.leveldb_dir)
    if not isinstance(cache.get("etfs"), list) or not cache["etfs"]:
        raise SystemExit("Local ETF cache missing; refusing to replace database rows")
    query = "?" + urllib.parse.urlencode({"select": "*", "domain": "eq.global", "order": "file_key.asc,row_no.asc"})
    existing = request(key, query) or []
    args.backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = args.backup_dir / f"global_manual_before_cache_migration_{stamp}.json"
    backup.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Backup: {backup}")
    print("Local cache:", {name: len(value) if isinstance(value, list) else len(value)
                            for name, value in cache.items()})
    print("Existing DB:", {name: sum(row["file_key"] == file_key for row in existing)
                            for name, (file_key, _) in KEYS.items()})
    if not args.apply:
        print("Dry run; no DB rows changed")
        return
    for name, (file_key, label) in KEYS.items():
        value = cache.get(name)
        if value is None:
            continue
        rows = value if isinstance(value, list) else [value]
        if not rows or not all(isinstance(row, dict) for row in rows):
            raise RuntimeError(f"Invalid cache rows: {name}")
        records = [{"domain": "global", "file_key": file_key, "file_label": label,
                    "sheet_name": "Data", "row_no": index + 1, "payload": row}
                   for index, row in enumerate(rows)]
        for start in range(0, len(records), 500):
            request(key, "?on_conflict=domain,file_key,sheet_name,row_no", method="POST",
                    body=records[start:start + 500], prefer="resolution=merge-duplicates,return=minimal")
        # Only remove obsolete trailing rows for this global file key.
        filters = "?" + urllib.parse.urlencode({"domain": "eq.global", "file_key": f"eq.{file_key}",
                                                "sheet_name": "eq.Data", "row_no": f"gt.{len(rows)}"})
        request(key, filters, method="DELETE")
        print(f"Migrated global/{file_key}: {len(rows)} rows")


if __name__ == "__main__":
    main()

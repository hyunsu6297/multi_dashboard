"""Restore dashboard build inputs from the latest Supabase snapshots."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

from openpyxl import Workbook


KFR_TARGETS = {
    "fund_trades": "전체펀드 매매현황.xlsx",
    "fund_holdings": "전체펀드 보유현황.xlsx",
    "mezzanine_price": "메자닌 기준가.xlsx",
}

MANUAL_TARGETS = {
    ("stock", "fund_info"): ("펀드 정보.xlsx", 4),
    ("stock", "sector"): ("업종.xlsx", 1),
    ("stock", "stock_holding"): ("주식보유현황.xlsx", 1),
    ("bond", "fund_info"): ("펀드정보.xlsx", 1),
    ("bond", "issuer"): ("발행사.xlsx", 1),
}


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


class SupabaseRest:
    def __init__(self, url: str, secret_key: str) -> None:
        self.base_url = f"{url.rstrip('/')}/rest/v1"
        self.headers = {"apikey": secret_key, "Content-Type": "application/json"}
        if secret_key.count(".") == 2:
            self.headers["Authorization"] = f"Bearer {secret_key}"

    def get_all(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode(params, safe=".,()")
        loaded: list[dict[str, Any]] = []
        for start in range(0, 1_000_000, 1000):
            headers = {**self.headers, "Range": f"{start}-{start + 999}"}
            request = urllib.request.Request(
                f"{self.base_url}/{table}?{query}", headers=headers, method="GET"
            )
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    page = json.loads(response.read())
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Supabase HTTP {exc.code}: {detail[:1000]}") from exc
            loaded.extend(page)
            if len(page) < 1000:
                return loaded
        raise RuntimeError(f"Pagination limit exceeded for {table}")


def write_workbook(
    path: Path,
    sheets: dict[str, list[dict[str, Any]]],
    header_row: int,
) -> None:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for sheet_name, rows in sheets.items():
        sheet = workbook.create_sheet(str(sheet_name)[:31] or "Data")
        columns: list[str] = []
        for row in rows:
            for column in row["payload"]:
                if column not in columns:
                    columns.append(column)
        for column_index, column in enumerate(columns, start=1):
            sheet.cell(row=header_row, column=column_index, value=column)
        for output_row, row in enumerate(rows, start=header_row + 1):
            for column_index, column in enumerate(columns, start=1):
                sheet.cell(row=output_row, column=column_index, value=row["payload"].get(column))
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def restore_kfr(client: SupabaseRest, stock_dir: Path, bond_dir: Path, mezzanine_dir: Path) -> None:
    snapshots = client.get_all(
        "kfr_source_snapshots",
        {"select": "id,source_key,business_date,downloaded_at", "order": "business_date.desc,downloaded_at.desc"},
    )
    latest: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        latest.setdefault(snapshot["source_key"], snapshot)

    for source_key, file_name in KFR_TARGETS.items():
        snapshot = latest.get(source_key)
        if not snapshot:
            raise RuntimeError(f"No KFR snapshot found for {source_key}")
        rows = client.get_all(
            "kfr_source_rows",
            {
                "select": "sheet_name,row_no,payload",
                "snapshot_id": f"eq.{snapshot['id']}",
                "order": "sheet_name.asc,row_no.asc",
            },
        )
        sheets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            sheets[row["sheet_name"]].append(row)
        for target_dir in (stock_dir, bond_dir, mezzanine_dir):
            write_workbook(target_dir / file_name, sheets, header_row=2)
        print(f"restored {source_key}: snapshot={snapshot['id']}, rows={len(rows)}")


def restore_manual(client: SupabaseRest, stock_dir: Path, bond_dir: Path) -> None:
    for (domain, file_key), (file_name, header_row) in MANUAL_TARGETS.items():
        rows = client.get_all(
            "manual_file_rows",
            {
                "select": "sheet_name,row_no,payload",
                "domain": f"eq.{domain}",
                "file_key": f"eq.{file_key}",
                "order": "sheet_name.asc,row_no.asc",
            },
        )
        if not rows:
            raise RuntimeError(f"No manual rows found for {domain}/{file_key}")
        sheets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            sheets[row["sheet_name"]].append(row)
        target_dir = stock_dir if domain == "stock" else bond_dir
        write_workbook(target_dir / file_name, sheets, header_row=header_row)
        print(f"restored {domain}/{file_key}: rows={len(rows)}")


def restore_mezzanine_manual(client: SupabaseRest, mezzanine_dir: Path) -> None:
    mezzanine_dir.mkdir(parents=True, exist_ok=True)
    rows = client.get_all("manual_file_rows", {
        "select": "sheet_name,row_no,payload", "domain": "eq.mezzanine",
        "file_key": "eq.instrument_info", "order": "row_no.asc",
    })
    if not rows:
        raise RuntimeError("No manual rows found for mezzanine/instrument_info")
    write_workbook(mezzanine_dir / "종목정보.xlsx", {"Sheet1": rows}, header_row=1)
    fund_rows = client.get_all("manual_file_rows", {
        "select": "sheet_name,row_no,payload", "domain": "eq.mezzanine",
        "file_key": "eq.fund_info", "order": "row_no.asc",
    })
    if not fund_rows:
        raise RuntimeError("No manual rows found for mezzanine/fund_info")
    write_workbook(mezzanine_dir / "펀드정보.xlsx", {"Sheet1": fund_rows}, header_row=1)

    additions = client.get_all("manual_file_rows", {
        "select": "row_no,payload", "domain": "eq.mezzanine",
        "file_key": "eq.instrument_additions", "order": "row_no.asc",
    })
    addition_payload = []
    for row in additions:
        payload = dict(row["payload"])
        addition_payload.append({
            "addition_id": payload.pop("addition_id", ""),
            "linked_instrument_id": payload.pop("linked_instrument_id", ""),
            "fields": payload,
        })
    (mezzanine_dir / "instrument_additions.json").write_text(
        json.dumps(addition_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    overrides = client.get_all("manual_file_rows", {
        "select": "row_no,payload", "domain": "eq.mezzanine",
        "file_key": "eq.instrument_overrides", "order": "row_no.asc",
    })
    override_payload = {}
    for row in overrides:
        payload = dict(row["payload"])
        instrument_id = str(payload.pop("instrument_id", ""))
        if instrument_id:
            override_payload[instrument_id] = payload
    (mezzanine_dir / "instrument_overrides.json").write_text(
        json.dumps(override_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    delta_rows = client.get_all("mezzanine_delta_history", {
        "select": "business_date,security_code,security_name,fund_name,nav,nav_return,underlying_change_rate,daily_delta,is_valid,source",
        "order": "business_date.asc,security_code.asc,fund_name.asc",
    })
    (mezzanine_dir / "delta_history.json").write_text(
        json.dumps(delta_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"restored mezzanine manual data: instruments={len(rows)}, additions={len(addition_payload)}, overrides={len(override_payload)}, delta_history={len(delta_rows)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-dir", default="apps/stock")
    parser.add_argument("--bond-dir", default="apps/bond")
    parser.add_argument("--mezzanine-dir", default="apps/mezzanine")
    args = parser.parse_args()
    client = SupabaseRest(required_env("SUPABASE_URL"), required_env("SUPABASE_SERVICE_ROLE_KEY"))
    restore_kfr(client, Path(args.stock_dir), Path(args.bond_dir), Path(args.mezzanine_dir))
    restore_manual(client, Path(args.stock_dir), Path(args.bond_dir))
    restore_mezzanine_manual(client, Path(args.mezzanine_dir))


if __name__ == "__main__":
    main()



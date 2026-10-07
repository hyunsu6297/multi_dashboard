from __future__ import annotations

import sqlite3
from pathlib import Path


DEFAULT_HISTORY_PATH = Path(__file__).resolve().parent / "data" / "period_ai_history.sqlite3"


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("""
        CREATE TABLE IF NOT EXISTS period_ai_history (
            id INTEGER PRIMARY KEY,
            fund_scope TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            model TEXT NOT NULL,
            snapshot_count INTEGER NOT NULL,
            analysis TEXT NOT NULL
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS period_ai_history_lookup
        ON period_ai_history (fund_scope, start_date, end_date, fingerprint, id DESC)
    """)
    return connection


def _entry(row: sqlite3.Row, include_analysis: bool = False) -> dict:
    result = {
        "id": row["id"],
        "source": "local",
        "fundScope": row["fund_scope"],
        "startDate": row["start_date"],
        "endDate": row["end_date"],
        "analysisFingerprint": row["fingerprint"],
        "generatedAt": row["generated_at"],
        "model": row["model"],
        "snapshotCount": row["snapshot_count"],
    }
    if include_analysis:
        result["analysis"] = row["analysis"]
    return result


def list_history(path: Path = DEFAULT_HISTORY_PATH, limit: int = 200) -> list[dict]:
    connection = _connect(path)
    try:
        rows = connection.execute(
            "SELECT * FROM period_ai_history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_entry(row) for row in rows]
    finally:
        connection.close()


def get_history(history_id: int, path: Path = DEFAULT_HISTORY_PATH) -> dict | None:
    connection = _connect(path)
    try:
        row = connection.execute(
            "SELECT * FROM period_ai_history WHERE id = ?", (history_id,)
        ).fetchone()
        return _entry(row, True) if row else None
    finally:
        connection.close()


def find_matching_history(
    fund_scope: str, start_date: str, end_date: str, fingerprint: str,
    path: Path = DEFAULT_HISTORY_PATH,
) -> dict | None:
    connection = _connect(path)
    try:
        row = connection.execute("""
            SELECT * FROM period_ai_history
            WHERE fund_scope = ? AND start_date = ? AND end_date = ? AND fingerprint = ?
            ORDER BY id DESC LIMIT 1
        """, (fund_scope, start_date, end_date, fingerprint)).fetchone()
        return _entry(row, True) if row else None
    finally:
        connection.close()


def save_history(
    fund_scope: str, start_date: str, end_date: str, fingerprint: str,
    generated_at: str, model: str, snapshot_count: int, analysis: str,
    path: Path = DEFAULT_HISTORY_PATH,
) -> dict:
    connection = _connect(path)
    try:
        with connection:
            cursor = connection.execute("""
                INSERT INTO period_ai_history
                (fund_scope, start_date, end_date, fingerprint, generated_at, model, snapshot_count, analysis)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fund_scope, start_date, end_date, fingerprint, generated_at,
                model, snapshot_count, analysis,
            ))
        return get_history(cursor.lastrowid, path)
    finally:
        connection.close()

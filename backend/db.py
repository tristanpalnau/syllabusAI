"""
db.py — SQLite persistence for session structured data.

Uses stdlib sqlite3 only — no new dependencies.
ChromaDB handles vector chunk persistence separately; this handles SyllabusStructure.
"""

import dataclasses
import json
import sqlite3
from pathlib import Path

from models import SyllabusStructure

_DB_PATH = Path(__file__).parent / "sessions.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id     TEXT PRIMARY KEY,
                filename       TEXT,
                structure_json TEXT NOT NULL,
                created_at     TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)


def save_session(session_id: str, filename: str, structure: SyllabusStructure) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO sessions (session_id, filename, structure_json, created_at)
            VALUES (?, ?, ?, datetime('now'))
            """,
            (session_id, filename, json.dumps(dataclasses.asdict(structure))),
        )


def load_session(session_id: str) -> SyllabusStructure | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT structure_json FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    if row is None:
        return None
    return _from_dict(json.loads(row["structure_json"]))


def delete_session(session_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM sessions WHERE session_id = ?", (session_id,)
        )
    return cur.rowcount > 0


def _from_dict(d: dict) -> SyllabusStructure:
    return SyllabusStructure(
        course_name=d.get("course_name"),
        instructor=d.get("instructor"),
        exam_dates=d.get("exam_dates") or [],
        assignment_deadlines=d.get("assignment_deadlines") or [],
        grade_weights=d.get("grade_weights") or {},
        late_policy=d.get("late_policy"),
        attendance_policy=d.get("attendance_policy"),
        office_hours=d.get("office_hours") or [],
    )

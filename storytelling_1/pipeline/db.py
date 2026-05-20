from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Set


SCHEMA = """
CREATE TABLE IF NOT EXISTS stories (
    request_id TEXT PRIMARY KEY,
    study_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_id TEXT NOT NULL,
    prompt_group TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    replicate INTEGER NOT NULL,
    status TEXT NOT NULL,
    response_text TEXT,
    created_at_utc TEXT NOT NULL,
    elapsed_seconds REAL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    finish_reason TEXT,
    provider_response_id TEXT,
    response_sha256 TEXT,
    error_type TEXT,
    error_message TEXT,
    provider_meta_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_stories_status ON stories(status);
CREATE INDEX IF NOT EXISTS idx_stories_provider_prompt ON stories(provider, prompt_id);
CREATE INDEX IF NOT EXISTS idx_stories_prompt ON stories(prompt_id);
"""


def connect(sqlite_path: str | Path) -> sqlite3.Connection:
    path = Path(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript(SCHEMA)
    return conn


def completed_request_ids(conn: sqlite3.Connection) -> Set[str]:
    rows = conn.execute("SELECT request_id FROM stories WHERE status = 'ok'").fetchall()
    return {row[0] for row in rows}


def upsert_story(conn: sqlite3.Connection, row: dict) -> None:
    columns = [
        "request_id", "study_id", "provider", "model", "prompt_id", "prompt_group", "prompt_text",
        "replicate", "status", "response_text", "created_at_utc", "elapsed_seconds", "input_tokens",
        "output_tokens", "total_tokens", "finish_reason", "provider_response_id", "response_sha256",
        "error_type", "error_message", "provider_meta_json"
    ]
    placeholders = ", ".join([":" + c for c in columns])
    assignments = ", ".join([f"{c}=excluded.{c}" for c in columns if c != "request_id"])
    sql = f"""
    INSERT INTO stories ({', '.join(columns)})
    VALUES ({placeholders})
    ON CONFLICT(request_id) DO UPDATE SET {assignments}
    """
    conn.execute(sql, {c: row.get(c) for c in columns})
    conn.commit()

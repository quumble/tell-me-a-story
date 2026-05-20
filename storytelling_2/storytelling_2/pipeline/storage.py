\
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable


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

CREATE TABLE IF NOT EXISTS motif_scores (
    request_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_id TEXT NOT NULL,
    prompt_group TEXT NOT NULL,
    replicate INTEGER NOT NULL,
    status TEXT NOT NULL,
    scored_prefix_chars INTEGER NOT NULL,
    title TEXT,
    has_lighthouse INTEGER NOT NULL,
    has_keeper INTEGER NOT NULL,
    has_lantern INTEGER NOT NULL,
    has_lamp INTEGER NOT NULL,
    has_light INTEGER NOT NULL,
    has_sea_ocean_water INTEGER NOT NULL,
    has_ship_boat INTEGER NOT NULL,
    has_storm_fog INTEGER NOT NULL,
    has_old_caretaker INTEGER NOT NULL,
    has_clockmaker INTEGER NOT NULL,
    has_collecting INTEGER NOT NULL,
    lighthouse_attractor INTEGER NOT NULL,
    suppression_violation INTEGER,
    response_chars INTEGER,
    output_tokens INTEGER,
    finish_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_stories_status ON stories(status);
CREATE INDEX IF NOT EXISTS idx_stories_provider_prompt ON stories(provider, prompt_id);
CREATE INDEX IF NOT EXISTS idx_stories_prompt ON stories(prompt_id);
CREATE INDEX IF NOT EXISTS idx_scores_provider_prompt ON motif_scores(provider, prompt_id);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=WAL;")
    con.executescript(SCHEMA)
    return con


def upsert_story(con: sqlite3.Connection, row: dict[str, Any]) -> None:
    cols = [
        "request_id", "study_id", "provider", "model", "prompt_id", "prompt_group",
        "prompt_text", "replicate", "status", "response_text", "created_at_utc",
        "elapsed_seconds", "input_tokens", "output_tokens", "total_tokens",
        "finish_reason", "provider_response_id", "response_sha256", "error_type",
        "error_message", "provider_meta_json"
    ]
    values = [row.get(c) for c in cols]
    placeholders = ",".join(["?"] * len(cols))
    updates = ",".join([f"{c}=excluded.{c}" for c in cols if c != "request_id"])
    con.execute(
        f"INSERT INTO stories ({','.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT(request_id) DO UPDATE SET {updates}",
        values,
    )
    con.commit()


def story_statuses(con: sqlite3.Connection) -> dict[str, str]:
    return {rid: status for rid, status in con.execute("SELECT request_id, status FROM stories")}

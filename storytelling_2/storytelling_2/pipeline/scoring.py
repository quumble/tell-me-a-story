\
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from .storage import connect


PATTERNS = {
    "has_lighthouse": r"\blighthouse\b",
    "has_keeper": r"\bkeeper\b",
    "has_lantern": r"\blantern\b",
    "has_lamp": r"\blamp\b",
    "has_light": r"\blight(?:s|ing)?\b",
    "has_sea_ocean_water": r"\bsea\b|\bocean\b|\bwater\b|\bshore\b|\bcoast\b",
    "has_ship_boat": r"\bship\b|\bships\b|\bboat\b|\bboats\b|\bsailor\b|\bsailors\b|\bfishing\b|\bvessel\b|\bharbor\b",
    "has_storm_fog": r"\bstorm\b|\bstormy\b|\bfog\b|\bfoggy\b|\brain\b|\bwind\b|\bwaves?\b",
    "has_old_caretaker": r"\bold\b.{0,80}\b(?:man|woman|keeper|caretaker|lamplighter)\b|\b(?:man|woman|keeper|caretaker|lamplighter)\b.{0,80}\bold\b",
    "has_clockmaker": r"\bclockmaker\b|\bclock\b|\bclocks\b|\bgear\b|\bgears\b|\btick\b|\btock\b",
    "has_collecting": r"\bcollect(?:s|ed|ing|or)?\b",
}

SUPPRESSION_BANNED = re.compile(
    r"\blighthouse\b|\blamp\b|\blantern\b|\bsea\b|\bocean\b|\bships?\b|\bboats?\b|"
    r"\bstorms?\b|\bfog\b|\bislands?\b|\bcliffs?\b|\bkeeper\b|\bcaretakers?\b|\bold\b",
    re.I,
)


def extract_title(text: str) -> str | None:
    if not text:
        return None
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None
    first = lines[0]
    first = re.sub(r"^#+\s*", "", first)
    if len(first) <= 120 and not first.lower().startswith(("here ", "sure", "of course", "once upon")):
        return first.strip("*_ ")
    # try next line if first is intro
    if len(lines) > 1:
        second = re.sub(r"^#+\s*", "", lines[1]).strip("*_ ")
        if len(second) <= 120:
            return second
    return None


def score_db(db_path: str | Path, prefix_chars: int = 1800) -> int:
    con = connect(db_path)
    rows = con.execute("""
        SELECT request_id, provider, model, prompt_id, prompt_group, replicate, status,
               response_text, output_tokens, finish_reason
        FROM stories
        WHERE status='ok'
    """).fetchall()
    scored = 0

    for row in rows:
        (request_id, provider, model, prompt_id, prompt_group, replicate, status,
         response_text, output_tokens, finish_reason) = row
        text = response_text or ""
        prefix = text[:prefix_chars]
        flags = {name: int(bool(re.search(pattern, prefix, re.I | re.S))) for name, pattern in PATTERNS.items()}

        lighthouse_attractor = int(
            flags["has_lighthouse"] or
            (flags["has_keeper"] and flags["has_light"] and flags["has_sea_ocean_water"])
        )

        suppression_violation = None
        if prompt_id == "P08_suppression":
            suppression_violation = int(bool(SUPPRESSION_BANNED.search(prefix)))

        values = {
            "request_id": request_id,
            "provider": provider,
            "model": model,
            "prompt_id": prompt_id,
            "prompt_group": prompt_group,
            "replicate": replicate,
            "status": status,
            "scored_prefix_chars": prefix_chars,
            "title": extract_title(text),
            **flags,
            "lighthouse_attractor": lighthouse_attractor,
            "suppression_violation": suppression_violation,
            "response_chars": len(text),
            "output_tokens": output_tokens,
            "finish_reason": finish_reason,
        }

        cols = list(values.keys())
        placeholders = ",".join(["?"] * len(cols))
        updates = ",".join([f"{c}=excluded.{c}" for c in cols if c != "request_id"])
        con.execute(
            f"INSERT INTO motif_scores ({','.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT(request_id) DO UPDATE SET {updates}",
            [values[c] for c in cols],
        )
        scored += 1

    con.commit()
    con.close()
    return scored

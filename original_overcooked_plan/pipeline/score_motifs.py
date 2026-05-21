from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import pandas as pd


PATTERNS = {
    "has_lighthouse": r"\blight\s*house\b|\blighthouse\b",
    "has_keeper": r"\bkeeper\b|\bcaretaker\b|\blamplighter\b",
    "has_lamp_lantern_light": r"\blamp\b|\blantern\b|\bbeacon\b|\blight\b|\blit\b",
    "has_sea_coast": r"\bsea\b|\bocean\b|\bshore\b|\bcoast\b|\bharbo[u]?r\b|\breef\b|\bcliff\b|\bisland\b|\brocky\b",
    "has_ship_boat": r"\bship\b|\bboat\b|\bvessel\b|\bfisherm[ae]n\b|\bsailor\b|\bsailboat\b",
    "has_storm_fog": r"\bstorm\b|\bstormy\b|\bfog\b|\bfoggy\b|\brain\b|\blightning\b|\bthunder\b",
    "has_old_person": r"\bold\b|\belderly\b|\baged\b",
    "has_forty_years": r"\bforty\b|\bforty-one\b|\bforty-three\b|\b40\b|\b41\b|\b43\b",
    "has_spiral_stairs": r"\bspiral stairs\b|\bspiral stair\b|\bstairs\b|\bsteps\b",
    "has_rocky_spit_phrase": r"rocky spit of land|spit of rock",
    "has_sea_arguing_phrase": r"sea (?:was |never quite stopped )?arguing with the shore|sea never quite stopped arguing",
    "has_great_lamp_phrase": r"great lamp",
    "has_want_another_followup": r"want another|would you like another|hope you enjoyed|i hope you enjoyed",
}


def extract_title(text: str) -> Optional[str]:
    if not isinstance(text, str) or not text.strip():
        return None
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None
    intro_patterns = [
        r"^here(?:'s| is)\b",
        r"^i'd be happy",
        r"^once upon a time",
        r"^the old ",
        r"^once, ",
    ]
    # Prefer a short title-looking line after a generic intro.
    for idx, line in enumerate(lines[:6]):
        if len(line) > 80:
            continue
        lower = line.lower()
        if any(re.search(p, lower) for p in intro_patterns):
            continue
        if line.endswith(('.', '!', '?')):
            continue
        if len(line.split()) <= 8:
            return line
    return None


def score_text(text: str) -> Dict[str, Any]:
    text = text or ""
    scored: Dict[str, Any] = {}
    for name, pattern in PATTERNS.items():
        scored[name] = bool(re.search(pattern, text, flags=re.IGNORECASE))
        scored[name.replace("has_", "count_")] = len(re.findall(pattern, text, flags=re.IGNORECASE))
    scored["title_guess"] = extract_title(text)
    scored["char_count"] = len(text)
    scored["word_count"] = len(re.findall(r"\b\w+\b", text))
    scored["has_lighthouse_keeper_combo"] = scored["has_lighthouse"] and scored["has_keeper"]
    scored["has_lighthouse_parable_cluster"] = (
        scored["has_lighthouse"]
        and scored["has_lamp_lantern_light"]
        and scored["has_sea_coast"]
        and (scored["has_ship_boat"] or scored["has_storm_fog"])
    )
    return scored


def score_motifs(*, base_dir: str, config: Dict[str, Any]) -> None:
    db_path = Path(base_dir) / config["storage"]["sqlite_path"]
    results_dir = Path(base_dir) / config["storage"].get("results_dir", "results")
    results_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM stories WHERE status = 'ok'", conn)
    if df.empty:
        print("No OK stories to score yet.")
        return

    score_rows = [score_text(text) for text in df["response_text"].fillna("")]
    score_df = pd.concat([df.reset_index(drop=True), pd.DataFrame(score_rows)], axis=1)
    score_path = results_dir / "motif_scores.csv"
    score_df.to_csv(score_path, index=False)

    bool_cols = [c for c in score_df.columns if c.startswith("has_")]
    summary = (
        score_df.groupby(["provider", "model", "prompt_id", "prompt_group"], dropna=False)[bool_cols + ["word_count"]]
        .agg({**{c: ["sum", "mean"] for c in bool_cols}, "word_count": ["mean", "median"]})
        .reset_index()
    )
    summary.columns = ["_".join([str(x) for x in col if x]) for col in summary.columns.to_flat_index()]
    summary_path = results_dir / "prompt_provider_summary.csv"
    summary.to_csv(summary_path, index=False)

    title_counts = (
        score_df["title_guess"]
        .fillna("(no title guessed)")
        .value_counts()
        .rename_axis("title_guess")
        .reset_index(name="count")
    )
    title_counts.to_csv(results_dir / "title_counts.csv", index=False)

    print(f"Wrote {score_path}")
    print(f"Wrote {summary_path}")

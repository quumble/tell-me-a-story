\
from __future__ import annotations

from pathlib import Path
import gzip
import json
import sqlite3
import pandas as pd

from .storage import connect


def export_all(db_path: str | Path, export_dir: str | Path, shard_max_rows: int = 500) -> dict:
    export_dir = Path(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    con = connect(db_path)

    stories = pd.read_sql_query("SELECT * FROM stories ORDER BY replicate, prompt_id, provider", con)
    scores = pd.read_sql_query("SELECT * FROM motif_scores ORDER BY replicate, prompt_id, provider", con)

    paths = []
    stories_csv = export_dir / "stories.csv.gz"
    stories.to_csv(stories_csv, index=False, compression="gzip")
    paths.append(str(stories_csv))

    if not scores.empty:
        scores_csv = export_dir / "motif_scores.csv.gz"
        scores.to_csv(scores_csv, index=False, compression="gzip")
        paths.append(str(scores_csv))

    # JSONL shards for uploadability.
    if not stories.empty:
        records = stories.to_dict(orient="records")
        shard_idx = 1
        for start in range(0, len(records), shard_max_rows):
            shard = records[start:start+shard_max_rows]
            p = export_dir / f"stories_shard_{shard_idx:04d}.jsonl.gz"
            with gzip.open(p, "wt", encoding="utf-8") as f:
                for rec in shard:
                    f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            paths.append(str(p))
            shard_idx += 1

    manifest = {
        "stories_rows": int(len(stories)),
        "motif_score_rows": int(len(scores)),
        "shard_max_rows": int(shard_max_rows),
        "files": paths,
    }
    manifest_path = export_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    paths.append(str(manifest_path))
    return manifest

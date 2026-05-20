from __future__ import annotations

import csv
import gzip
import json
import math
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable


def rows_as_dicts(conn: sqlite3.Connection):
    conn.row_factory = sqlite3.Row
    for row in conn.execute("SELECT * FROM stories ORDER BY replicate, prompt_id, provider"):
        yield dict(row)


def export_data(*, base_dir: str, config: Dict[str, Any]) -> None:
    db_path = Path(base_dir) / config["storage"]["sqlite_path"]
    export_dir = Path(base_dir) / config["storage"].get("export_dir", "data/exports")
    export_dir.mkdir(parents=True, exist_ok=True)
    shard_rows = int(config["storage"].get("shard_rows", 250))

    conn = sqlite3.connect(db_path)
    all_rows = list(rows_as_dicts(conn))

    # Compact CSV for spreadsheet/analysis use.
    csv_path = export_dir / "stories.csv.gz"
    if all_rows:
        with gzip.open(csv_path, "wt", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
            writer.writeheader()
            writer.writerows(all_rows)

    # Sharded JSONL.GZ avoids enormous single files.
    for old in export_dir.glob("stories_shard_*.jsonl.gz"):
        old.unlink()
    for shard_idx in range(math.ceil(len(all_rows) / shard_rows)):
        shard = all_rows[shard_idx * shard_rows : (shard_idx + 1) * shard_rows]
        path = export_dir / f"stories_shard_{shard_idx + 1:04d}.jsonl.gz"
        with gzip.open(path, "wt", encoding="utf-8") as f:
            for row in shard:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    manifest = {
        "sqlite_path": str(db_path),
        "row_count": len(all_rows),
        "csv_gz": str(csv_path),
        "jsonl_gz_shard_rows": shard_rows,
        "jsonl_gz_shard_count": math.ceil(len(all_rows) / shard_rows) if all_rows else 0,
    }
    with open(export_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(json.dumps(manifest, indent=2))

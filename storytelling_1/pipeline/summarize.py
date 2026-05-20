from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict

import pandas as pd


def summarize(*, base_dir: str, config: Dict[str, Any]) -> None:
    db_path = Path(base_dir) / config["storage"]["sqlite_path"]
    results_dir = Path(base_dir) / config["storage"].get("results_dir", "results")
    results_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM stories", conn)
    if df.empty:
        print("No rows yet.")
        return

    status_summary = (
        df.groupby(["provider", "model", "prompt_id", "status"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["provider", "prompt_id", "status"])
    )
    status_summary.to_csv(results_dir / "run_status_summary.csv", index=False)

    token_cols = [c for c in ["input_tokens", "output_tokens", "total_tokens", "elapsed_seconds"] if c in df.columns]
    if token_cols:
        token_summary = (
            df[df["status"] == "ok"]
            .groupby(["provider", "model"], dropna=False)[token_cols]
            .agg(["count", "mean", "sum"])
            .reset_index()
        )
        token_summary.columns = ["_".join([str(x) for x in col if x]) for col in token_summary.columns.to_flat_index()]
        token_summary.to_csv(results_dir / "token_usage_summary.csv", index=False)

    # Lightweight markdown status report.
    md_path = results_dir / "run_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Storytelling 1 Run Report\n\n")
        f.write("## Status by provider, model, prompt, status\n\n")
        f.write(status_summary.to_markdown(index=False))
        f.write("\n")
    print(f"Wrote {results_dir / 'run_status_summary.csv'}")
    print(f"Wrote {md_path}")

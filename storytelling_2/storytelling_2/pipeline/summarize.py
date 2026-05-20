\
from __future__ import annotations

from pathlib import Path
import sqlite3
import pandas as pd

from .storage import connect


def _md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    return df.to_markdown(index=False)


def summarize(db_path: str | Path, out_dir: str | Path = "results", truncation_warning_rate: float = 0.25) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    con = connect(db_path)

    stories = pd.read_sql_query("SELECT * FROM stories", con)
    scores = pd.read_sql_query("SELECT * FROM motif_scores", con)

    lines = ["# storytelling_2 summary", ""]
    if stories.empty:
        lines.append("No story rows found yet.")
        (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")
        return {"rows": 0}

    lines.append("## Run status")
    status = stories.groupby(["provider", "status"]).size().reset_index(name="n")
    lines.append(_md_table(status))
    lines.append("")

    token_latency = stories.groupby("provider").agg(
        n=("request_id", "count"),
        avg_elapsed_seconds=("elapsed_seconds", "mean"),
        avg_output_tokens=("output_tokens", "mean"),
        max_output_tokens_seen=("output_tokens", "max"),
    ).reset_index()
    for col in ["avg_elapsed_seconds", "avg_output_tokens"]:
        token_latency[col] = token_latency[col].round(2)
    lines.append("## Latency and token usage")
    lines.append(_md_table(token_latency))
    lines.append("")

    # Truncation warnings.
    finish = stories.copy()
    finish["truncated_like"] = finish["finish_reason"].fillna("").str.contains("max_tokens|MAX_TOKENS|incomplete|length", case=False, regex=True)
    trunc = finish.groupby("provider").agg(n=("request_id","count"), truncated=("truncated_like","sum")).reset_index()
    trunc["truncation_rate"] = (trunc["truncated"] / trunc["n"]).round(3)
    warnings = trunc[trunc["truncation_rate"] >= truncation_warning_rate]
    lines.append("## Truncation check")
    lines.append(_md_table(trunc))
    if not warnings.empty:
        lines.append("")
        lines.append("⚠️ Truncation warning: at least one provider is frequently ending due to a max-token/length condition. Check provider-specific max-output configuration before scaling.")
    lines.append("")

    if not scores.empty:
        attractor = scores.groupby(["provider", "prompt_id"]).agg(
            n=("request_id","count"),
            lighthouse_attractor_rate=("lighthouse_attractor","mean"),
            suppression_violation_rate=("suppression_violation","mean"),
            avg_output_tokens=("output_tokens","mean"),
        ).reset_index()
        for col in ["lighthouse_attractor_rate", "suppression_violation_rate", "avg_output_tokens"]:
            attractor[col] = attractor[col].round(3)
        lines.append("## Motif rates by provider × prompt")
        lines.append(_md_table(attractor))
        lines.append("")

        by_provider = scores.groupby("provider").agg(
            n=("request_id","count"),
            lighthouse_attractor_rate=("lighthouse_attractor","mean"),
            has_lighthouse_rate=("has_lighthouse","mean"),
            has_sea_ocean_water_rate=("has_sea_ocean_water","mean"),
            has_clockmaker_rate=("has_clockmaker","mean"),
        ).reset_index()
        for col in by_provider.columns:
            if col.endswith("_rate"):
                by_provider[col] = by_provider[col].round(3)
        lines.append("## Motif rates by provider")
        lines.append(_md_table(by_provider))
        lines.append("")

        title_counts = scores["title"].dropna().value_counts().head(30).reset_index()
        title_counts.columns = ["title", "n"]
        title_counts.to_csv(out_dir / "title_counts.csv", index=False)
        lines.append("## Top extracted titles")
        lines.append(_md_table(title_counts.head(15)))
        lines.append("")

        attractor.to_csv(out_dir / "prompt_provider_motif_rates.csv", index=False)
        by_provider.to_csv(out_dir / "provider_motif_rates.csv", index=False)
    else:
        lines.append("No motif scores found yet. Run `python run.py score` first.")

    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    return {"rows": len(stories), "scored_rows": len(scores)}

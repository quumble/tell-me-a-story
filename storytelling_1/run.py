from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

from pipeline.config import load_config
from pipeline.export import export_data
from pipeline.plan import make_balanced_plan, write_plan_csv
from pipeline.run_study import run_study
from pipeline.score_motifs import score_motifs
from pipeline.summarize import summarize


def parse_provider_arg(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    return [x.strip() for x in value.split(",") if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the storytelling_1 LLM story-attractor study.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("plan", help="Write the balanced request plan CSV without calling APIs.")

    run_p = sub.add_parser("run", help="Run API calls and save rows incrementally to SQLite.")
    run_p.add_argument("--provider", help="Comma-separated subset: openai,anthropic,gemini")
    run_p.add_argument("--max-requests", type=int, default=None, help="Stop after this many new API calls.")
    run_p.add_argument("--retry-errors", action="store_true", help="Retry rows currently marked status=error.")

    sub.add_parser("score", help="Score motifs from saved OK stories.")
    sub.add_parser("summarize", help="Write status and token summaries.")
    sub.add_parser("export", help="Export SQLite rows to compressed CSV and sharded JSONL.GZ.")

    all_p = sub.add_parser("all", help="Run, then score, summarize, and export.")
    all_p.add_argument("--provider", help="Comma-separated subset: openai,anthropic,gemini")
    all_p.add_argument("--max-requests", type=int, default=None)
    all_p.add_argument("--retry-errors", action="store_true")

    args = parser.parse_args()
    base_dir = Path(__file__).resolve().parent
    load_dotenv(base_dir / ".env")
    config, prompts = load_config(base_dir)

    if args.command == "plan":
        plan = make_balanced_plan(config, prompts)
        write_plan_csv(plan, base_dir / config["storage"]["request_plan_csv"])
        print(f"Wrote {len(plan)} planned requests to {base_dir / config['storage']['request_plan_csv']}")
        return

    if args.command == "run":
        run_study(
            base_dir=str(base_dir),
            config=config,
            prompts=prompts,
            only_providers=parse_provider_arg(args.provider),
            max_requests=args.max_requests,
            retry_errors=args.retry_errors,
        )
        return

    if args.command == "score":
        score_motifs(base_dir=str(base_dir), config=config)
        return

    if args.command == "summarize":
        summarize(base_dir=str(base_dir), config=config)
        return

    if args.command == "export":
        export_data(base_dir=str(base_dir), config=config)
        return

    if args.command == "all":
        run_study(
            base_dir=str(base_dir),
            config=config,
            prompts=prompts,
            only_providers=parse_provider_arg(args.provider),
            max_requests=args.max_requests,
            retry_errors=args.retry_errors,
        )
        score_motifs(base_dir=str(base_dir), config=config)
        summarize(base_dir=str(base_dir), config=config)
        export_data(base_dir=str(base_dir), config=config)
        return


if __name__ == "__main__":
    main()

\
from __future__ import annotations

import argparse
import asyncio
import csv
import datetime as dt
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from pipeline.config import load_yaml, load_dotenv, enabled_providers, load_prompts
from pipeline.plan import build_plan, write_plan, read_plan
from pipeline.storage import connect, upsert_story, story_statuses
from pipeline.scoring import score_db
from pipeline.summarize import summarize
from pipeline.export import export_all

from providers.openai_provider import OpenAIProvider
from providers.anthropic_provider import AnthropicProvider
from providers.gemini_provider import GeminiProvider


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "study_config.yaml"
PROMPTS_PATH = ROOT / "prompts.yaml"


PROVIDER_CLASSES = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def rel(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def load_all() -> tuple[dict, list[dict], dict]:
    load_dotenv(ROOT / ".env")
    cfg = load_yaml(CONFIG_PATH)
    prompts = load_prompts(PROMPTS_PATH)
    providers = enabled_providers(cfg)
    return cfg, prompts, providers


def cmd_plan(args: argparse.Namespace) -> None:
    cfg, prompts, providers = load_all()
    study = cfg["study"]
    n = args.n or int(study["n_per_provider_prompt"])
    rows = build_plan(
        study_id=study["study_id"],
        prompts=prompts,
        providers=providers,
        n=n,
        seed=int(study.get("random_seed", 508)),
    )
    plan_path = rel(cfg["storage"]["request_plan_path"])
    write_plan(rows, plan_path)
    con = connect(rel(cfg["storage"]["sqlite_path"]))
    print(f"Wrote {len(rows)} planned requests to {plan_path}")
    print(f"SQLite ready at {rel(cfg['storage']['sqlite_path'])}")


def provider_instance(provider_name: str, cfg: dict):
    pconf = cfg["providers"][provider_name]
    key = os.environ.get(pconf.get("api_key_env", ""))
    if not key:
        raise RuntimeError(f"Missing API key env var: {pconf.get('api_key_env')}")
    return PROVIDER_CLASSES[provider_name](api_key=key)


def call_one(provider_name: str, row: dict[str, Any], cfg: dict) -> dict[str, Any]:
    study = cfg["study"]
    pconf = cfg["providers"][provider_name]
    provider = provider_instance(provider_name, cfg)
    max_output_tokens = int(study["max_output_tokens"])
    timeout_seconds = int(study.get("request_timeout_seconds", 90))
    retry_attempts = int(study.get("retry_attempts_per_request", 2))
    backoff = float(study.get("retry_backoff_seconds", 5))

    last_exc = None
    started = time.perf_counter()
    for attempt in range(retry_attempts + 1):
        try:
            result = provider.complete(
                model=row["model"],
                prompt=row["prompt_text"],
                max_output_tokens=max_output_tokens,
                timeout_seconds=timeout_seconds,
                extra_request=pconf.get("extra_request", {}),
            )
            elapsed = time.perf_counter() - started
            return {
                **row,
                "replicate": int(row["replicate"]),
                "status": "ok",
                "response_text": result.response_text,
                "created_at_utc": now_utc(),
                "elapsed_seconds": elapsed,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "total_tokens": result.total_tokens,
                "finish_reason": result.finish_reason,
                "provider_response_id": result.provider_response_id,
                "response_sha256": result.response_sha256,
                "error_type": None,
                "error_message": None,
                "provider_meta_json": result.meta_json(),
            }
        except Exception as exc:
            last_exc = exc
            if attempt < retry_attempts:
                time.sleep(backoff * (attempt + 1))

    elapsed = time.perf_counter() - started
    return {
        **row,
        "replicate": int(row["replicate"]),
        "status": "error",
        "response_text": None,
        "created_at_utc": now_utc(),
        "elapsed_seconds": elapsed,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "finish_reason": None,
        "provider_response_id": None,
        "response_sha256": None,
        "error_type": type(last_exc).__name__ if last_exc else "UnknownError",
        "error_message": str(last_exc) if last_exc else "Unknown error",
        "provider_meta_json": None,
    }


async def cmd_run_async(args: argparse.Namespace) -> None:
    cfg, prompts, providers = load_all()
    db_path = rel(cfg["storage"]["sqlite_path"])
    plan_path = rel(cfg["storage"]["request_plan_path"])
    if not plan_path.exists():
        print("No request plan found; creating one first.")
        cmd_plan(argparse.Namespace(n=None))

    plan = read_plan(plan_path)

    if args.provider:
        keep = set(args.provider)
        plan = [r for r in plan if r["provider"] in keep]
    if args.prompt_id:
        keep = set(args.prompt_id)
        plan = [r for r in plan if r["prompt_id"] in keep]

    con = connect(db_path)
    statuses = story_statuses(con)

    pending = []
    for r in plan:
        prior = statuses.get(r["request_id"])
        if prior is None:
            pending.append(r)
        elif args.retry_errors and prior == "error":
            pending.append(r)

    if args.max_requests:
        pending = pending[:args.max_requests]

    if not pending:
        print("No pending requests.")
        return

    concurrency = args.concurrency or int(cfg["study"].get("default_concurrency", 1))
    launch_delay = float(args.launch_delay or 0.0)
    print(f"Running {len(pending)} requests with concurrency={concurrency}")

    sem = asyncio.Semaphore(concurrency)
    write_lock = asyncio.Lock()
    completed = 0

    async def worker(row: dict[str, Any]):
        nonlocal completed
        async with sem:
            if launch_delay:
                await asyncio.sleep(launch_delay)
            result = await asyncio.to_thread(call_one, row["provider"], row, cfg)
            async with write_lock:
                con2 = connect(db_path)
                upsert_story(con2, result)
                con2.close()
                completed += 1
                status = result["status"]
                tokens = result.get("output_tokens")
                fr = result.get("finish_reason")
                print(f"[{completed}/{len(pending)}] {status:5s} {row['provider']:9s} {row['prompt_id']} rep={row['replicate']} out={tokens} finish={fr}")

    await asyncio.gather(*(worker(r) for r in pending))


def cmd_run(args: argparse.Namespace) -> None:
    asyncio.run(cmd_run_async(args))


def cmd_score(args: argparse.Namespace) -> None:
    cfg, prompts, providers = load_all()
    n = score_db(
        rel(cfg["storage"]["sqlite_path"]),
        prefix_chars=int(cfg["study"].get("response_prefix_chars_for_scoring", 1800)),
    )
    print(f"Scored {n} ok story rows.")


def cmd_summarize(args: argparse.Namespace) -> None:
    cfg, prompts, providers = load_all()
    result = summarize(
        rel(cfg["storage"]["sqlite_path"]),
        out_dir=ROOT / "results",
        truncation_warning_rate=float(cfg["study"].get("truncation_warning_rate", 0.25)),
    )
    print(f"Wrote results/summary.md ({result})")


def cmd_export(args: argparse.Namespace) -> None:
    cfg, prompts, providers = load_all()
    manifest = export_all(
        rel(cfg["storage"]["sqlite_path"]),
        rel(cfg["storage"]["export_dir"]),
        shard_max_rows=int(cfg["storage"].get("jsonl_shard_max_rows", 500)),
    )
    print(f"Exported {manifest['stories_rows']} rows to {rel(cfg['storage']['export_dir'])}")


def cmd_status(args: argparse.Namespace) -> None:
    cfg, prompts, providers = load_all()
    import pandas as pd
    con = connect(rel(cfg["storage"]["sqlite_path"]))
    try:
        rows = pd.read_sql_query("""
            SELECT provider, prompt_id, status, COUNT(*) AS n,
                   ROUND(AVG(elapsed_seconds), 2) AS avg_elapsed,
                   ROUND(AVG(output_tokens), 1) AS avg_output_tokens
            FROM stories
            GROUP BY provider, prompt_id, status
            ORDER BY prompt_id, provider, status
        """, con)
        if rows.empty:
            print("No story rows yet.")
        else:
            print(rows.to_string(index=False))
    finally:
        con.close()


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="storytelling_2 runner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="create balanced request plan")
    p.add_argument("--n", type=int, help="override n_per_provider_prompt")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("run", help="run pending requests")
    p.add_argument("--max-requests", type=int)
    p.add_argument("--concurrency", type=int)
    p.add_argument("--retry-errors", action="store_true")
    p.add_argument("--provider", action="append", choices=list(PROVIDER_CLASSES.keys()))
    p.add_argument("--prompt-id", action="append")
    p.add_argument("--launch-delay", type=float, default=0.0, help="seconds to wait before launching each request")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("score", help="score motif flags")
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("summarize", help="write summary markdown and csvs")
    p.set_defaults(func=cmd_summarize)

    p = sub.add_parser("export", help="export compressed csv/jsonl shards")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("status", help="show current run status")
    p.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

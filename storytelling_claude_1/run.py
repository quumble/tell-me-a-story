#!/usr/bin/env python3
"""
run.py — generate stories and append each one to a flat CSV.

Usage:
    python run.py                      # run everything still missing
    python run.py --limit 24           # smoke test: stop after 24 new calls
    python run.py --provider anthropic # one provider only
    python run.py --retry-errors       # re-attempt rows previously saved as errors

Design notes:
  * One CSV (data/stories.csv) is the entire database. Each finished call is
    flushed immediately, so an interrupted run loses nothing.
  * Resuming = skip any request_id already saved with status "ok" (and skip
    "error" rows too, unless --retry-errors).
  * Calls are ordered "by replicate": replicate 1 across every provider/prompt,
    then replicate 2, and so on — so a partial run is still balanced.
"""
from __future__ import annotations

import argparse
import csv
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parent

# Columns in the output CSV, in order.
FIELDS = [
    "request_id", "provider", "model", "prompt_id", "prompt_text",
    "replicate", "status", "story_text",
    "input_tokens", "output_tokens", "elapsed_sec", "created_utc", "error",
]


# --------------------------------------------------------------------------- #
# Provider calls. One small function each. Each returns:
#   (story_text, input_tokens, output_tokens)
# and raises on failure (the caller records the error and moves on).
# --------------------------------------------------------------------------- #
def call_openai(prompt, model, max_tokens):
    from openai import OpenAI
    client = OpenAI(api_key=_key("OPENAI_API_KEY"))
    r = client.responses.create(model=model, input=prompt, max_output_tokens=max_tokens)
    text = getattr(r, "output_text", "") or ""
    usage = getattr(r, "usage", None)
    return text.strip(), _u(usage, "input_tokens"), _u(usage, "output_tokens")


def call_anthropic(prompt, model, max_tokens):
    from anthropic import Anthropic
    client = Anthropic(api_key=_key("ANTHROPIC_API_KEY"))
    r = client.messages.create(
        model=model, max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
    usage = getattr(r, "usage", None)
    return text.strip(), _u(usage, "input_tokens"), _u(usage, "output_tokens")


def call_gemini(prompt, model, max_tokens):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=_key("GEMINI_API_KEY"))
    r = client.models.generate_content(
        model=model, contents=prompt,
        config=types.GenerateContentConfig(max_output_tokens=max_tokens),
    )
    usage = getattr(r, "usage_metadata", None)
    return ((getattr(r, "text", "") or "").strip(),
            _u(usage, "prompt_token_count"), _u(usage, "candidates_token_count"))


CALLERS = {"openai": call_openai, "anthropic": call_anthropic, "gemini": call_gemini}


def _key(env_name):
    val = os.getenv(env_name)
    if not val:
        raise RuntimeError(f"Missing environment variable {env_name} (set it in .env)")
    return val


def _u(usage, name):
    """Pull a token count off a usage object/dict, tolerating missing fields."""
    if usage is None:
        return None
    if isinstance(usage, dict):
        return usage.get(name)
    return getattr(usage, name, None)


# --------------------------------------------------------------------------- #
# Plan + CSV helpers
# --------------------------------------------------------------------------- #
def load_config():
    with open(BASE / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_plan(cfg, only_provider=None):
    """Balanced-by-replicate list of every request the study needs."""
    active = {
        name: p for name, p in cfg["providers"].items()
        if p.get("enabled", True) and (only_provider in (None, name))
    }
    plan = []
    global_cap = int(cfg["max_output_tokens"])
    for rep in range(1, int(cfg["n_per_cell"]) + 1):
        for prompt in cfg["prompts"]:
            for name, p in active.items():
                # A provider may override the global token cap (e.g. Gemini,
                # which self-limits and breaks under a tight cap).
                cap = int(p.get("max_output_tokens", global_cap))
                plan.append({
                    "request_id": f"{name}|{prompt['id']}|r{rep:04d}",
                    "provider": name,
                    "model": p["model"],
                    "prompt_id": prompt["id"],
                    "prompt_text": prompt["text"],
                    "replicate": rep,
                    "max_tokens": cap,
                })
    return plan


def read_existing(csv_path):
    """Return {request_id: status} for rows already in the CSV."""
    seen = {}
    if csv_path.exists():
        with open(csv_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                seen[row["request_id"]] = row["status"]
    return seen


def append_row(csv_path, row):
    """Append one row, writing a header first if the file is new."""
    new_file = not csv_path.exists()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in FIELDS})


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Run the storytelling_claude_1 study.")
    ap.add_argument("--provider", choices=list(CALLERS), help="run a single provider")
    ap.add_argument("--limit", type=int, help="stop after this many new calls")
    ap.add_argument("--retry-errors", action="store_true", help="re-attempt error rows")
    args = ap.parse_args()

    # Load .env if python-dotenv is around (optional convenience).
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE / ".env")
    except ImportError:
        pass

    cfg = load_config()
    csv_path = BASE / cfg["output_csv"]
    plan = build_plan(cfg, only_provider=args.provider)
    seen = read_existing(csv_path)

    def skip(req_id):
        status = seen.get(req_id)
        if status == "ok":
            return True
        if status == "error" and not args.retry_errors:
            return True
        return False

    todo = [item for item in plan if not skip(item["request_id"])]
    print(f"Plan: {len(plan)} total | already done: {len(plan) - len(todo)} | "
          f"to run now: {len(todo)}")

    sleep_s = float(cfg.get("sleep_between_calls", 0))
    done_now = ok = err = 0

    for item in todo:
        if args.limit is not None and done_now >= args.limit:
            print(f"Hit --limit {args.limit}; stopping.")
            break

        print(f"  {item['provider']:<9} {item['prompt_id']:<20} rep={item['replicate']}")
        started = time.time()
        row = dict(item)
        row["created_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            text, in_tok, out_tok = CALLERS[item["provider"]](
                item["prompt_text"], item["model"], item["max_tokens"])
            row.update(status="ok", story_text=text,
                       input_tokens=in_tok, output_tokens=out_tok,
                       elapsed_sec=round(time.time() - started, 2), error="")
            ok += 1
        except KeyboardInterrupt:
            print("Interrupted — everything saved so far is in the CSV.")
            raise
        except Exception as exc:  # record and continue; the study is long-running
            row.update(status="error", story_text="",
                       input_tokens="", output_tokens="",
                       elapsed_sec=round(time.time() - started, 2),
                       error=f"{type(exc).__name__}: {exc}")
            err += 1
            print(f"    ERROR: {row['error']}")

        append_row(csv_path, row)
        seen[item["request_id"]] = row["status"]
        done_now += 1
        if sleep_s:
            time.sleep(sleep_s)

    print(f"\nDone. New calls: {done_now} (ok={ok}, error={err}). CSV: {csv_path}")


if __name__ == "__main__":
    main()

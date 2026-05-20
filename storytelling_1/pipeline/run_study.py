from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .db import completed_request_ids, connect, upsert_story
from .plan import make_balanced_plan, write_plan_csv
from .provider_factory import make_provider


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_study(
    *,
    base_dir: str,
    config: Dict[str, Any],
    prompts: List[Dict[str, Any]],
    only_providers: Optional[List[str]] = None,
    max_requests: Optional[int] = None,
    retry_errors: bool = False,
) -> None:
    sqlite_path = f"{base_dir}/{config['storage']['sqlite_path']}"
    conn = connect(sqlite_path)
    plan = make_balanced_plan(config, prompts, only_providers=only_providers)
    write_plan_csv(plan, f"{base_dir}/{config['storage']['request_plan_csv']}")

    done = completed_request_ids(conn)
    provider_clients: Dict[str, Any] = {}
    completed_this_run = 0
    max_output_tokens = int(config["study"].get("max_output_tokens", 1200))
    stop_on_error = bool(config["study"].get("stop_on_error", True))
    sleep_s = float(config["study"].get("sleep_seconds_between_requests", 0.0))

    existing_error_ids = set()
    if not retry_errors:
        existing_error_ids = {
            row[0]
            for row in conn.execute("SELECT request_id FROM stories WHERE status = 'error'").fetchall()
        }

    provider_cfgs = config["providers"]

    for i, item in enumerate(plan, start=1):
        request_id = item["request_id"]
        if request_id in done or request_id in existing_error_ids:
            continue
        if max_requests is not None and completed_this_run >= max_requests:
            print(f"Reached --max-requests={max_requests}; stopping.")
            break

        provider_name = item["provider"]
        provider_cfg = provider_cfgs[provider_name]
        model = provider_cfg["model"]
        extra = provider_cfg.get("extra") or {}
        prompt_text = item["prompt_text"]

        print(
            f"[{i}/{len(plan)}] {provider_name} {model} {item['prompt_id']} "
            f"rep={item['replicate']}"
        )

        started = time.time()
        try:
            if provider_name not in provider_clients:
                provider_clients[provider_name] = make_provider(provider_name, provider_cfg)
            result = provider_clients[provider_name].generate(
                prompt_text,
                model=model,
                max_output_tokens=max_output_tokens,
                extra=extra,
            )
            elapsed = time.time() - started
            row = {
                **item,
                "status": "ok",
                "response_text": result.text,
                "created_at_utc": utc_now_iso(),
                "elapsed_seconds": elapsed,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "total_tokens": result.total_tokens,
                "finish_reason": result.finish_reason,
                "provider_response_id": result.provider_response_id,
                "response_sha256": sha256_text(result.text),
                "error_type": None,
                "error_message": None,
                "provider_meta_json": json.dumps(result.provider_meta, ensure_ascii=False, sort_keys=True),
            }
            upsert_story(conn, row)
            completed_this_run += 1
            done.add(request_id)

        except KeyboardInterrupt:
            print("Interrupted by user. Completed rows are already saved in SQLite.")
            raise
        except Exception as exc:  # noqa: BLE001 - this is a long-running data collection script
            elapsed = time.time() - started
            error_type = type(exc).__name__
            error_message = str(exc)
            row = {
                **item,
                "status": "error",
                "response_text": None,
                "created_at_utc": utc_now_iso(),
                "elapsed_seconds": elapsed,
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
                "finish_reason": None,
                "provider_response_id": None,
                "response_sha256": None,
                "error_type": error_type,
                "error_message": error_message,
                "provider_meta_json": json.dumps({}, ensure_ascii=False),
            }
            upsert_story(conn, row)
            print(f"ERROR for {request_id}: {error_type}: {error_message}")
            if stop_on_error:
                print("stop_on_error=true; stopping. Re-run with --retry-errors after fixing quota/keys/model IDs.")
                break

        if sleep_s > 0:
            time.sleep(sleep_s)

    ok_count = conn.execute("SELECT COUNT(*) FROM stories WHERE status = 'ok'").fetchone()[0]
    err_count = conn.execute("SELECT COUNT(*) FROM stories WHERE status = 'error'").fetchone()[0]
    print(f"Saved OK rows: {ok_count}; error rows: {err_count}; database: {sqlite_path}")

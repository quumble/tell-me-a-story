from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def enabled_providers(config: Dict[str, Any], only: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    providers = []
    only_set = set(only or [])
    for name, cfg in config["providers"].items():
        if not cfg.get("enabled", True):
            continue
        if only_set and name not in only_set:
            continue
        providers.append({"name": name, **cfg})
    return providers


def make_balanced_plan(config: Dict[str, Any], prompts: List[Dict[str, Any]], only_providers: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    study_id = config["study"]["id"]
    n = int(config["study"]["n_per_cell"])
    providers = enabled_providers(config, only_providers)
    plan = []
    for replicate in range(1, n + 1):
        for prompt in prompts:
            for provider in providers:
                request_id = f"{study_id}:{provider['name']}:{prompt['id']}:r{replicate:04d}"
                plan.append(
                    {
                        "request_id": request_id,
                        "study_id": study_id,
                        "provider": provider["name"],
                        "model": provider["model"],
                        "prompt_id": prompt["id"],
                        "prompt_group": prompt.get("group", ""),
                        "prompt_text": prompt["text"],
                        "replicate": replicate,
                    }
                )
    return plan


def write_plan_csv(plan: List[Dict[str, Any]], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not plan:
        return
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(plan[0].keys()))
        writer.writeheader()
        writer.writerows(plan)

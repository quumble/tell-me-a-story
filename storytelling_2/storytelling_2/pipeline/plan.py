\
from __future__ import annotations

from pathlib import Path
import csv
import random


def build_plan(*, study_id: str, prompts: list[dict], providers: dict, n: int, seed: int = 508) -> list[dict]:
    rng = random.Random(seed)
    provider_names = list(providers.keys())
    rows = []

    # Balanced by replicate: if interrupted, every early prefix contains all providers/prompts.
    for rep in range(1, n + 1):
        prompt_order = list(prompts)
        # Keep P01 early, but rotate remaining prompts lightly by replicate to avoid strong temporal ordering.
        if len(prompt_order) > 1:
            first = prompt_order[0]
            rest = prompt_order[1:]
            rng.shuffle(rest)
            prompt_order = [first] + rest

        for prompt in prompt_order:
            pnames = list(provider_names)
            rng.shuffle(pnames)
            for provider in pnames:
                model = providers[provider]["model"]
                request_id = f"{study_id}:{provider}:{prompt['prompt_id']}:r{rep:04d}"
                rows.append({
                    "request_id": request_id,
                    "study_id": study_id,
                    "provider": provider,
                    "model": model,
                    "prompt_id": prompt["prompt_id"],
                    "prompt_group": prompt["prompt_group"],
                    "prompt_text": prompt["prompt_text"],
                    "replicate": rep,
                })
    return rows


def write_plan(rows: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["request_id","study_id","provider","model","prompt_id","prompt_group","prompt_text","replicate"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def read_plan(path: str | Path) -> list[dict]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

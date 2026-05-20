from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml


def load_yaml(path: str | Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config(base_dir: str | Path) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    base = Path(base_dir)
    config = load_yaml(base / "study_config.yaml")
    prompts_doc = load_yaml(base / "prompts.yaml")
    prompts = prompts_doc["prompts"]
    return config, prompts

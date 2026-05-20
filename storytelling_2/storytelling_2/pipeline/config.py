\
from __future__ import annotations

from pathlib import Path
import os
import yaml


def load_yaml(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_dotenv(path: str | Path = ".env") -> None:
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def enabled_providers(config: dict) -> dict:
    return {
        name: pconf
        for name, pconf in config.get("providers", {}).items()
        if pconf.get("enabled", False)
    }


def load_prompts(path: str | Path) -> list[dict]:
    data = load_yaml(path)
    return data["prompts"]

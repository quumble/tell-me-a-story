from __future__ import annotations

import os
from typing import Any, Dict, Optional

from .base import GenerationResult, ProviderClient


def _get_usage_value(usage: Any, name: str) -> Optional[int]:
    if usage is None:
        return None
    if isinstance(usage, dict):
        return usage.get(name)
    return getattr(usage, name, None)


class AnthropicProvider(ProviderClient):
    provider_name = "anthropic"

    def __init__(self, api_key_env: str = "ANTHROPIC_API_KEY") -> None:
        from anthropic import Anthropic

        api_key = os.getenv(api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing {api_key_env}")
        self.client = Anthropic(api_key=api_key)

    def generate(self, prompt: str, *, model: str, max_output_tokens: int, extra: Dict[str, Any]) -> GenerationResult:
        # Do not set temperature/top_p/top_k for the main study.
        response = self.client.messages.create(
            model=model,
            max_tokens=max_output_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", ""))
        usage = getattr(response, "usage", None)
        input_tokens = _get_usage_value(usage, "input_tokens")
        output_tokens = _get_usage_value(usage, "output_tokens")
        total_tokens = None
        if input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens

        return GenerationResult(
            provider=self.provider_name,
            model=model,
            text="\n".join(parts).strip(),
            finish_reason=getattr(response, "stop_reason", None),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            provider_response_id=getattr(response, "id", None),
            provider_meta={"stop_sequence": getattr(response, "stop_sequence", None)},
        )

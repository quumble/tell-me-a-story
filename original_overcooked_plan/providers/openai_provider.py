from __future__ import annotations

import os
from typing import Any, Dict, Optional

from .base import GenerationResult, ProviderClient


def _extract_output_text(response: Any) -> str:
    """Best-effort extraction across OpenAI SDK response shapes."""
    text = getattr(response, "output_text", None)
    if text:
        return text

    chunks = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            content_text = getattr(content, "text", None)
            if content_text:
                chunks.append(content_text)
    return "\n".join(chunks).strip()


def _get_usage_value(usage: Any, name: str) -> Optional[int]:
    if usage is None:
        return None
    if isinstance(usage, dict):
        return usage.get(name)
    return getattr(usage, name, None)


class OpenAIProvider(ProviderClient):
    provider_name = "openai"

    def __init__(self, api_key_env: str = "OPENAI_API_KEY") -> None:
        from openai import OpenAI

        api_key = os.getenv(api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing {api_key_env}")
        self.client = OpenAI(api_key=api_key)

    def generate(self, prompt: str, *, model: str, max_output_tokens: int, extra: Dict[str, Any]) -> GenerationResult:
        kwargs: Dict[str, Any] = {
            "model": model,
            "input": prompt,
            "max_output_tokens": max_output_tokens,
        }

        # For GPT-5-family models, a reasoning effort can be supplied when desired.
        # Leave sampling parameters unset for the main study.
        reasoning_effort = extra.get("reasoning_effort")
        if reasoning_effort:
            kwargs["reasoning"] = {"effort": reasoning_effort}

        response = self.client.responses.create(**kwargs)
        usage = getattr(response, "usage", None)
        input_tokens = _get_usage_value(usage, "input_tokens")
        output_tokens = _get_usage_value(usage, "output_tokens")
        total_tokens = _get_usage_value(usage, "total_tokens")
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens

        return GenerationResult(
            provider=self.provider_name,
            model=model,
            text=_extract_output_text(response),
            finish_reason=getattr(response, "status", None),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            provider_response_id=getattr(response, "id", None),
            provider_meta={"status": getattr(response, "status", None)},
        )

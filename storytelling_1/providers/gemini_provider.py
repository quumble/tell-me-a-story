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


class GeminiProvider(ProviderClient):
    provider_name = "gemini"

    def __init__(self, api_key_env: str = "GEMINI_API_KEY") -> None:
        from google import genai

        api_key = os.getenv(api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing {api_key_env}")
        self.client = genai.Client(api_key=api_key)

    def generate(self, prompt: str, *, model: str, max_output_tokens: int, extra: Dict[str, Any]) -> GenerationResult:
        from google.genai import types

        # Do not set temperature/top_p for the main study.
        response = self.client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=max_output_tokens),
        )

        usage = getattr(response, "usage_metadata", None)
        input_tokens = _get_usage_value(usage, "prompt_token_count")
        output_tokens = _get_usage_value(usage, "candidates_token_count")
        total_tokens = _get_usage_value(usage, "total_token_count")

        finish_reason = None
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            finish_reason = str(getattr(candidates[0], "finish_reason", "")) or None

        return GenerationResult(
            provider=self.provider_name,
            model=model,
            text=(getattr(response, "text", None) or "").strip(),
            finish_reason=finish_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            provider_response_id=None,
            provider_meta={},
        )

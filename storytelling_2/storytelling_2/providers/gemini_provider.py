\
from __future__ import annotations

from typing import Any
from .common import ProviderResult


def _get_attr(obj: Any, name: str, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str | None = None):
        from google import genai
        self.genai = genai
        self.client = genai.Client(api_key=api_key)

    def complete(self, *, model: str, prompt: str, max_output_tokens: int, timeout_seconds: int = 90, extra_request: dict | None = None) -> ProviderResult:
        from google.genai import types

        config_kwargs = {"max_output_tokens": max_output_tokens}
        for k, v in (extra_request or {}).items():
            if v is not None:
                config_kwargs[k] = v
        config = types.GenerateContentConfig(**config_kwargs)

        # google-genai does not consistently expose per-request timeout in the same way
        # as the other SDKs, so timeout_seconds is currently recorded but not forced here.
        resp = self.client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )

        text = getattr(resp, "text", None) or ""
        finish_reason = None
        if getattr(resp, "candidates", None):
            finish_reason = str(_get_attr(resp.candidates[0], "finish_reason", None))

        usage = _get_attr(resp, "usage_metadata", None)
        input_tokens = _get_attr(usage, "prompt_token_count", None)
        output_tokens = _get_attr(usage, "candidates_token_count", None)
        total_tokens = _get_attr(usage, "total_token_count", None)

        return ProviderResult(
            response_text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            finish_reason=finish_reason,
            provider_response_id=None,
            provider_meta={},
        )

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


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str | None = None):
        from anthropic import Anthropic
        self.client = Anthropic(api_key=api_key)

    def complete(self, *, model: str, prompt: str, max_output_tokens: int, timeout_seconds: int = 90, extra_request: dict | None = None) -> ProviderResult:
        kwargs = dict(
            model=model,
            max_tokens=max_output_tokens,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout_seconds,
        )
        for k, v in (extra_request or {}).items():
            if v is not None:
                kwargs[k] = v

        resp = self.client.messages.create(**kwargs)

        parts = []
        for block in getattr(resp, "content", []) or []:
            txt = getattr(block, "text", None)
            if txt:
                parts.append(txt)
        text = "\n".join(parts)

        usage = _get_attr(resp, "usage", None)
        input_tokens = _get_attr(usage, "input_tokens", None)
        output_tokens = _get_attr(usage, "output_tokens", None)
        total_tokens = None
        if input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens

        return ProviderResult(
            response_text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            finish_reason=_get_attr(resp, "stop_reason", None),
            provider_response_id=_get_attr(resp, "id", None),
            provider_meta={"stop_sequence": _get_attr(resp, "stop_sequence", None)},
        )

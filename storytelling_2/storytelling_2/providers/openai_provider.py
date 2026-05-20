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


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str | None = None):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)

    def complete(self, *, model: str, prompt: str, max_output_tokens: int, timeout_seconds: int = 90, extra_request: dict | None = None) -> ProviderResult:
        kwargs = dict(
            model=model,
            input=prompt,
            max_output_tokens=max_output_tokens,
            timeout=timeout_seconds,
        )
        for k, v in (extra_request or {}).items():
            if v is not None:
                kwargs[k] = v

        resp = self.client.responses.create(**kwargs)

        text = getattr(resp, "output_text", None)
        if text is None:
            # Fallback for SDK/model variants.
            parts = []
            for item in getattr(resp, "output", []) or []:
                for content in getattr(item, "content", []) or []:
                    t = getattr(content, "text", None)
                    if t:
                        parts.append(t)
            text = "\n".join(parts)

        usage = _get_attr(resp, "usage", None)
        input_tokens = _get_attr(usage, "input_tokens", None)
        output_tokens = _get_attr(usage, "output_tokens", None)
        total_tokens = _get_attr(usage, "total_tokens", None)
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens

        status = _get_attr(resp, "status", None)
        incomplete_details = _get_attr(resp, "incomplete_details", None)
        reason = status
        if incomplete_details:
            reason = f"{status}:{_get_attr(incomplete_details, 'reason', incomplete_details)}"

        return ProviderResult(
            response_text=text or "",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            finish_reason=reason,
            provider_response_id=_get_attr(resp, "id", None),
            provider_meta={"status": status},
        )

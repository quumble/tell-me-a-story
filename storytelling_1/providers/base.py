from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class GenerationResult:
    provider: str
    model: str
    text: str
    finish_reason: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    provider_response_id: Optional[str] = None
    provider_meta: Dict[str, Any] = field(default_factory=dict)


class ProviderClient:
    provider_name: str

    def generate(self, prompt: str, *, model: str, max_output_tokens: int, extra: Dict[str, Any]) -> GenerationResult:
        raise NotImplementedError

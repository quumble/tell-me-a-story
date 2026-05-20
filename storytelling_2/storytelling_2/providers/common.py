\
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import hashlib
import json


@dataclass
class ProviderResult:
    response_text: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    finish_reason: Optional[str] = None
    provider_response_id: Optional[str] = None
    provider_meta: Optional[dict[str, Any]] = None

    @property
    def response_sha256(self) -> str:
        return hashlib.sha256((self.response_text or "").encode("utf-8")).hexdigest()

    def meta_json(self) -> str:
        return json.dumps(self.provider_meta or {}, ensure_ascii=False, sort_keys=True)

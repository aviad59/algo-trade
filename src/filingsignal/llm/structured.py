"""The provider-uniform backstop: call an adapter, parse JSON, validate with a
pydantic model, and retry once (feeding the error back) on failure. This is what
makes both a schema-native provider (Claude) and a JSON-mode one (Kimi) reliable.
"""

from __future__ import annotations

import json
import re
from typing import Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from .base import LLMClient, LLMResult, StopReason

T = TypeVar("T", bound=BaseModel)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


class LLMError(RuntimeError):
    pass


class LLMRefusal(LLMError):
    pass


def _extract_json(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t[:4].lower() == "json":
            t = t[4:]
    m = _JSON_RE.search(t)
    return m.group(0) if m else t


def complete_structured(
    client: LLMClient,
    *,
    system: str,
    user: str,
    schema: Optional[dict],
    model_cls: Type[T],
    max_tokens: int = 8000,
    effort: Optional[str] = None,
    retries: int = 1,
) -> tuple[T, LLMResult]:
    attempt_user = user
    last_err: Exception | None = None
    for _ in range(retries + 1):
        result = client.complete(
            system=system, user=attempt_user, schema=schema,
            max_tokens=max_tokens, effort=effort,
        )
        if result.stop_reason is StopReason.refusal:
            raise LLMRefusal(result.text or "model refused to respond")
        if result.stop_reason is StopReason.context_overflow:
            raise LLMError("input exceeded the model context window (split sections upstream)")
        try:
            data = json.loads(_extract_json(result.text))
            return model_cls.model_validate(data), result
        except (json.JSONDecodeError, ValidationError) as exc:
            last_err = exc
            attempt_user = (
                user
                + f"\n\nYour previous reply was not valid ({type(exc).__name__}): {exc}\n"
                "Return ONLY a single JSON object matching the required schema."
            )
    raise LLMError(f"structured output failed after {retries + 1} attempts: {last_err}")

"""Provider-neutral LLM interface.

Both agents (extractor, rating) call an ``LLMClient`` and never touch a vendor
SDK directly. Concrete adapters live in ``claude.py`` and ``openai_compat.py``;
``structured.py`` adds the validate-and-retry backstop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable

from ..models import Usage


class StopReason(str, Enum):
    complete = "complete"
    max_tokens = "max_tokens"
    refusal = "refusal"
    context_overflow = "context_overflow"
    other = "other"


@dataclass(frozen=True)
class Capabilities:
    """What an adapter/model can do — replaces the predecessor's
    ``supports_adaptive_thinking`` string-matching hack."""

    native_schema: bool = False   # provider enforces the JSON schema server-side
    prompt_cache: bool = False    # supports caching a stable system prefix
    thinking: bool = False        # supports adaptive/extended thinking


@dataclass
class LLMResult:
    text: str
    stop_reason: StopReason = StopReason.complete
    usage: Usage = field(default_factory=Usage)
    raw: Any = None


@runtime_checkable
class LLMClient(Protocol):
    """The single call the pipeline depends on. ``schema`` is a JSON Schema an
    adapter may enforce natively (Claude) or ignore in favor of the prompt +
    the pydantic backstop (OpenAI-compatible)."""

    model: str
    capabilities: Capabilities

    def complete(
        self,
        *,
        system: str,
        user: str,
        schema: Optional[dict] = None,
        max_tokens: int = 4096,
        effort: Optional[str] = None,
    ) -> LLMResult: ...

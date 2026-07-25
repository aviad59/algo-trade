"""Provider-agnostic LLM layer (Claude or Kimi/OpenAI-compatible)."""

from .base import Capabilities, LLMClient, LLMResult, StopReason
from .claude import ClaudeClient
from .factory import make_llm_client, resolve_model
from .openai_compat import OpenAICompatClient
from .structured import LLMError, LLMRefusal, complete_structured

__all__ = [
    "Capabilities",
    "LLMClient",
    "LLMResult",
    "StopReason",
    "ClaudeClient",
    "OpenAICompatClient",
    "make_llm_client",
    "resolve_model",
    "complete_structured",
    "LLMError",
    "LLMRefusal",
]

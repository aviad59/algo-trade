"""Build an ``LLMClient`` from env/config. Provider swap lives here.

  FILINGSIGNAL_LLM_PROVIDER = claude | kimi | openai        (default claude)
  FILINGSIGNAL_LLM_MODEL    = shared model override
  FILINGSIGNAL_<AGENT>_MODEL= per-agent override (EXTRACTOR / RATING)
  FILINGSIGNAL_LLM_BASE_URL = OpenAI-compatible base url (Kimi/GPT)
  ANTHROPIC_API_KEY / MOONSHOT_API_KEY / OPENAI_API_KEY
"""

from __future__ import annotations

from typing import Optional

from ..env import env_optional_str, env_str
from .base import LLMClient
from .claude import ClaudeClient
from .openai_compat import OpenAICompatClient

_DEFAULT_MODEL = {
    "claude": "claude-sonnet-5",
    "kimi": "kimi-k2-0711-preview",
    "openai": "gpt-4.1",
}
_MOONSHOT_BASE = "https://api.moonshot.ai/v1"


def resolve_model(agent: str, *, provider: str, override: Optional[str] = None) -> str:
    if override:
        return override
    per_agent = env_optional_str(f"FILINGSIGNAL_{agent.upper()}_MODEL")
    if per_agent:
        return per_agent
    shared = env_optional_str("FILINGSIGNAL_LLM_MODEL")
    if shared:
        return shared
    return _DEFAULT_MODEL.get(provider, _DEFAULT_MODEL["claude"])


def make_llm_client(
    agent: str = "extractor",
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    client: Optional[LLMClient] = None,
) -> LLMClient:
    if client is not None:  # test injection / preconstructed
        return client
    provider = (provider or env_str("FILINGSIGNAL_LLM_PROVIDER", "claude")).lower()
    model = resolve_model(agent, provider=provider, override=model)

    if provider == "claude":
        return ClaudeClient(model=model, api_key=env_optional_str("ANTHROPIC_API_KEY"))
    if provider in ("kimi", "moonshot"):
        return OpenAICompatClient(
            model=model,
            api_key=env_optional_str("MOONSHOT_API_KEY"),
            base_url=env_str("FILINGSIGNAL_LLM_BASE_URL", _MOONSHOT_BASE),
        )
    if provider == "openai":
        return OpenAICompatClient(
            model=model,
            api_key=env_optional_str("OPENAI_API_KEY"),
            base_url=env_optional_str("FILINGSIGNAL_LLM_BASE_URL"),
        )
    raise ValueError(f"unknown LLM provider {provider!r} (use claude|kimi|openai)")

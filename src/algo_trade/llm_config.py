"""Centralized LLM model resolution for pipeline agents.

Model choice is never hardcoded at call sites. Resolution order:

1. Explicit ``override`` (constructor / function argument)
2. Per-agent env: ``ALGO_TRADE_EXTRACTOR_MODEL`` or ``ALGO_TRADE_RECOMMENDER_MODEL``
3. Shared env: ``ALGO_TRADE_LLM_MODEL``
4. Default from ``.env`` / ``ALGO_TRADE_DEFAULT_*_MODEL``
"""

from __future__ import annotations

from typing import Literal

from .env import env_str

AgentName = Literal["extractor", "recommender"]

DEFAULT_EXTRACTOR_MODEL = env_str(
    "ALGO_TRADE_DEFAULT_EXTRACTOR_MODEL", "claude-opus-4-7"
)
DEFAULT_RECOMMENDER_MODEL = env_str(
    "ALGO_TRADE_DEFAULT_RECOMMENDER_MODEL", "claude-opus-4-7"
)

_AGENT_DEFAULTS: dict[AgentName, str] = {
    "extractor": DEFAULT_EXTRACTOR_MODEL,
    "recommender": DEFAULT_RECOMMENDER_MODEL,
}

_AGENT_ENV: dict[AgentName, str] = {
    "extractor": "ALGO_TRADE_EXTRACTOR_MODEL",
    "recommender": "ALGO_TRADE_RECOMMENDER_MODEL",
}


def resolve_model(agent: AgentName, *, override: str | None = None) -> str:
    """Return the model id to use for *agent*."""
    if override:
        return override

    agent_env = env_str(_AGENT_ENV[agent], "")
    if agent_env:
        return agent_env

    shared = env_str("ALGO_TRADE_LLM_MODEL", "")
    if shared:
        return shared

    return _AGENT_DEFAULTS[agent]

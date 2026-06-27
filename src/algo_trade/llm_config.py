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

# Default to Sonnet 4.6 for both agents: ~40% cheaper than Opus 4.7 on
# both input and output tokens, still strong on structured reasoning and
# instruction following. Override via ALGO_TRADE_*_MODEL env vars (see
# resolve_model below) to switch to Opus 4.7 for harder reasoning or
# Haiku 4.5 for cost-only backfills.
DEFAULT_EXTRACTOR_MODEL = env_str(
    "ALGO_TRADE_DEFAULT_EXTRACTOR_MODEL", "claude-sonnet-4-6"
)
DEFAULT_RECOMMENDER_MODEL = env_str(
    "ALGO_TRADE_DEFAULT_RECOMMENDER_MODEL", "claude-sonnet-4-6"
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

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

# Default to Haiku 4.5 for both agents -- cheapest tier ($1 / $5 per 1M
# tokens). User-chosen tradeoff: extraction quality on hedged language
# is weaker than Sonnet/Opus, so expect more false positives in the
# buffer. Override via ALGO_TRADE_*_MODEL env vars to switch to
# claude-sonnet-4-6 (balanced) or claude-opus-4-7 (highest quality).
DEFAULT_EXTRACTOR_MODEL = env_str(
    "ALGO_TRADE_DEFAULT_EXTRACTOR_MODEL", "claude-haiku-4-5"
)
DEFAULT_RECOMMENDER_MODEL = env_str(
    "ALGO_TRADE_DEFAULT_RECOMMENDER_MODEL", "claude-haiku-4-5"
)

_AGENT_DEFAULTS: dict[AgentName, str] = {
    "extractor": DEFAULT_EXTRACTOR_MODEL,
    "recommender": DEFAULT_RECOMMENDER_MODEL,
}

_AGENT_ENV: dict[AgentName, str] = {
    "extractor": "ALGO_TRADE_EXTRACTOR_MODEL",
    "recommender": "ALGO_TRADE_RECOMMENDER_MODEL",
}


# Adaptive thinking and output_config effort exist on Claude 4.6+ models
# only; older tiers — including the default claude-haiku-4-5 — reject them
# with a 400 (`adaptive thinking is not supported on this model`). Written
# as a block-list of known-old generations so unknown/future model ids get
# the modern request shape by default.
_PRE_ADAPTIVE_MARKERS = ("claude-3", "-3-", "-4-0", "-4-1", "-4-5")


def supports_adaptive_thinking(model: str) -> bool:
    """True when *model* accepts ``thinking={"type": "adaptive"}`` + effort."""
    return not any(marker in model for marker in _PRE_ADAPTIVE_MARKERS)


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

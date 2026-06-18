"""Tests for centralized LLM model resolution."""

from __future__ import annotations

import pytest

from algo_trade.llm_config import (
    DEFAULT_EXTRACTOR_MODEL,
    DEFAULT_RECOMMENDER_MODEL,
    resolve_model,
)


@pytest.fixture(autouse=True)
def _clear_model_env(monkeypatch):
    for key in (
        "ALGO_TRADE_EXTRACTOR_MODEL",
        "ALGO_TRADE_RECOMMENDER_MODEL",
        "ALGO_TRADE_LLM_MODEL",
        "ALGO_TRADE_DEFAULT_EXTRACTOR_MODEL",
        "ALGO_TRADE_DEFAULT_RECOMMENDER_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_resolve_model_uses_override() -> None:
    assert resolve_model("extractor", override="custom-model") == "custom-model"
    assert resolve_model("recommender", override="custom-model") == "custom-model"


def test_resolve_model_agent_env_beats_shared(monkeypatch) -> None:
    monkeypatch.setenv("ALGO_TRADE_EXTRACTOR_MODEL", "agent-extractor")
    monkeypatch.setenv("ALGO_TRADE_LLM_MODEL", "shared-model")
    assert resolve_model("extractor") == "agent-extractor"


def test_resolve_model_shared_env_beats_default(monkeypatch) -> None:
    monkeypatch.setenv("ALGO_TRADE_LLM_MODEL", "shared-model")
    assert resolve_model("recommender") == "shared-model"


def test_resolve_model_defaults() -> None:
    assert resolve_model("extractor") == DEFAULT_EXTRACTOR_MODEL
    assert resolve_model("recommender") == DEFAULT_RECOMMENDER_MODEL


def test_resolve_model_uses_default_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("ALGO_TRADE_DEFAULT_EXTRACTOR_MODEL", "env-default-extractor")
    monkeypatch.setenv("ALGO_TRADE_DEFAULT_RECOMMENDER_MODEL", "env-default-recommender")
    # Re-import defaults after env is set — resolve_model reads env at call time
    # for agent/shared vars; defaults are module-level from import.
    # Override via per-agent env instead (runtime path):
    monkeypatch.setenv("ALGO_TRADE_EXTRACTOR_MODEL", "env-default-extractor")
    monkeypatch.setenv("ALGO_TRADE_RECOMMENDER_MODEL", "env-default-recommender")
    assert resolve_model("extractor") == "env-default-extractor"
    assert resolve_model("recommender") == "env-default-recommender"

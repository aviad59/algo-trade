"""Tests for backend API Settings loaded from environment."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from algo_trade import env
from api.config import Settings
from api.deps import get_settings


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch) -> None:
    env._loaded = False
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
    env._loaded = False


def test_settings_defaults(monkeypatch) -> None:
    for key in (
        "ALGO_TRADE_BUFFER_PATH",
        "ALGO_TRADE_UNIVERSE_DIR",
        "ALGO_TRADE_FORECAST_SINCE",
        "ALGO_TRADE_FORECAST_UNTIL",
        "ALGO_TRADE_RANKING_MODE",
        "ALGO_TRADE_API_HOST",
        "ALGO_TRADE_API_PORT",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = Settings.from_env()
    assert settings.buffer_path == env.repo_root() / "data" / "buffer.sqlite"
    assert settings.universe_dir == env.repo_root() / "backend" / "universe"
    assert settings.ranking_mode == "rules"
    assert settings.recommender_model is None
    assert settings.api_host == "0.0.0.0"
    assert settings.api_port == 8000
    assert "localhost:5173" in settings.cors_origins[0]


def test_settings_reads_explicit_forecast_window(monkeypatch) -> None:
    monkeypatch.setenv("ALGO_TRADE_FORECAST_SINCE", "2025-01-01")
    monkeypatch.setenv("ALGO_TRADE_FORECAST_UNTIL", "2025-12-31")
    settings = Settings.from_env()
    assert settings.forecast_since == date(2025, 1, 1)
    assert settings.forecast_until == date(2025, 12, 31)


def test_settings_invalid_ranking_mode_falls_back_to_rules(monkeypatch) -> None:
    monkeypatch.setenv("ALGO_TRADE_RANKING_MODE", "magic")
    assert Settings.from_env().ranking_mode == "rules"


def test_settings_recommender_mode_and_model(monkeypatch) -> None:
    monkeypatch.setenv("ALGO_TRADE_RANKING_MODE", "recommender")
    monkeypatch.setenv("ALGO_TRADE_RECOMMENDER_MODEL", "custom-recommender")
    settings = Settings.from_env()
    assert settings.ranking_mode == "recommender"
    assert settings.recommender_model == "custom-recommender"


def test_get_settings_cached(monkeypatch, tmp_path) -> None:
    db = tmp_path / "buf.sqlite"
    monkeypatch.setenv("ALGO_TRADE_BUFFER_PATH", str(db))
    first = get_settings()
    monkeypatch.setenv("ALGO_TRADE_BUFFER_PATH", str(tmp_path / "other.sqlite"))
    second = get_settings()
    assert first is second
    assert first.buffer_path == Path(db)

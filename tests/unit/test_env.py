"""Tests for repo-root ``.env`` loading."""

from __future__ import annotations

import pytest

from algo_trade import env


@pytest.fixture(autouse=True)
def _reset_env_loader() -> None:
    env._loaded = False
    yield
    env._loaded = False


def test_env_path_resolves_relative_to_repo_root(monkeypatch) -> None:
    monkeypatch.setenv("ALGO_TRADE_BUFFER_PATH", "data/custom.sqlite")
    path = env.env_path("ALGO_TRADE_BUFFER_PATH", "data/buffer.sqlite")
    assert path == env.repo_root() / "data" / "custom.sqlite"


def test_load_env_reads_repo_dotenv(tmp_path, monkeypatch) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("ALGO_TRADE_RANKING_MODE=recommender\n", encoding="utf-8")
    monkeypatch.setattr(env, "repo_root", lambda: tmp_path)
    monkeypatch.delenv("ALGO_TRADE_RANKING_MODE", raising=False)

    env.load_env()
    assert env.env_str("ALGO_TRADE_RANKING_MODE", "rules") == "recommender"


def test_shell_env_beats_dotenv_file(tmp_path, monkeypatch) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("ALGO_TRADE_RANKING_MODE=recommender\n", encoding="utf-8")
    monkeypatch.setattr(env, "repo_root", lambda: tmp_path)
    monkeypatch.setenv("ALGO_TRADE_RANKING_MODE", "rules")

    env.load_env()
    assert env.env_str("ALGO_TRADE_RANKING_MODE", "") == "rules"


def test_env_int_and_float_defaults(monkeypatch) -> None:
    monkeypatch.delenv("ALGO_TRADE_API_PORT", raising=False)
    monkeypatch.delenv("ALGO_TRADE_TIMER_BUY_THRESHOLD", raising=False)
    assert env.env_int("ALGO_TRADE_API_PORT", 8000) == 8000
    assert env.env_float("ALGO_TRADE_TIMER_BUY_THRESHOLD", 0.0) == 0.0


def test_env_int_and_float_from_env(monkeypatch) -> None:
    monkeypatch.setenv("ALGO_TRADE_API_PORT", "9001")
    monkeypatch.setenv("ALGO_TRADE_TIMER_BUY_THRESHOLD", "0.25")
    assert env.env_int("ALGO_TRADE_API_PORT", 8000) == 9001
    assert env.env_float("ALGO_TRADE_TIMER_BUY_THRESHOLD", 0.0) == pytest.approx(0.25)


def test_env_optional_str(monkeypatch) -> None:
    monkeypatch.delenv("ALGO_TRADE_RECOMMENDER_MODEL", raising=False)
    assert env.env_optional_str("ALGO_TRADE_RECOMMENDER_MODEL") is None
    monkeypatch.setenv("ALGO_TRADE_RECOMMENDER_MODEL", "custom-model")
    assert env.env_optional_str("ALGO_TRADE_RECOMMENDER_MODEL") == "custom-model"

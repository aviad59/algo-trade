"""Tests for algo-trade-extract CLI defaults from .env."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from algo_trade import env
from algo_trade.extract_cli import _cli


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch) -> None:
    env._loaded = False
    yield
    env._loaded = False


def test_extract_cli_errors_without_identity(monkeypatch) -> None:
    monkeypatch.delenv("ALGO_TRADE_SEC_IDENTITY", raising=False)
    with pytest.raises(SystemExit):
        _cli(["TSLA"])


def test_extract_cli_uses_identity_from_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ALGO_TRADE_SEC_IDENTITY", "Jane Doe jane@example.com")
    monkeypatch.setenv("ALGO_TRADE_BUFFER_PATH", str(tmp_path / "buf.sqlite"))

    mock_buf = MagicMock()
    mock_fetcher = MagicMock()
    mock_fetcher.fetch.return_value = []

    with (
        patch("algo_trade.fetcher.Fetcher", return_value=mock_fetcher) as fetcher_cls,
        patch("algo_trade.extractor.Extractor", return_value=MagicMock()),
        patch("algo_trade.buffer.Buffer", return_value=mock_buf),
    ):
        mock_buf.__enter__.return_value = mock_buf
        code = _cli(["TSLA"])

    assert code == 0
    fetcher_cls.assert_called_once_with(identity="Jane Doe jane@example.com")
    mock_fetcher.fetch.assert_called_once()

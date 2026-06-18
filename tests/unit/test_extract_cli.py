"""Tests for algo-trade-extract CLI defaults from .env."""

from __future__ import annotations

from datetime import date
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
        patch("algo_trade.extract_cli.Fetcher", return_value=mock_fetcher) as fetcher_cls,
        patch("algo_trade.extract_cli.Extractor", return_value=MagicMock()),
        patch("algo_trade.extract_cli.Buffer", return_value=mock_buf),
    ):
        mock_buf.__enter__.return_value = mock_buf
        code = _cli(["TSLA", "--no-progress"])

    assert code == 0
    fetcher_cls.assert_called_once_with(identity="Jane Doe jane@example.com")
    mock_fetcher.fetch.assert_called_once()


def test_extract_cli_prints_progress_for_filing(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("ALGO_TRADE_SEC_IDENTITY", "Jane Doe jane@example.com")
    monkeypatch.setenv("ALGO_TRADE_BUFFER_PATH", str(tmp_path / "buf.sqlite"))

    fetched = MagicMock()
    fetched.form = "10-Q"
    fetched.filing_date = date(2026, 4, 30)
    fetched.accession_number = "ACC-001"
    fetched.company_name = "Tesla, Inc."

    extracted = MagicMock()
    extracted.dated_effects = [MagicMock(), MagicMock()]
    extracted.extractor_confidence = 0.91

    mock_buf = MagicMock()
    mock_fetcher = MagicMock()
    mock_fetcher.fetch.return_value = [fetched]
    mock_extractor = MagicMock()
    mock_extractor.extract.return_value = extracted

    with (
        patch("algo_trade.extract_cli.Fetcher", return_value=mock_fetcher),
        patch("algo_trade.extract_cli.Extractor", return_value=mock_extractor),
        patch("algo_trade.extract_cli.Buffer", return_value=mock_buf),
    ):
        mock_buf.__enter__.return_value = mock_buf
        code = _cli(["TSLA", "--no-progress"])

    assert code == 0
    err = capsys.readouterr().err
    assert "Plan: 1 ticker(s)" in err
    assert "running extractor" in err
    assert "ok TSLA/ACC-001: 2 dated effect(s)" in err
    assert "Done. Upserted 1 filing(s), 2 dated effect(s)" in err

"""Tests for extract CLI progress reporting."""

from __future__ import annotations

import io
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from algo_trade.extract_progress import ExtractProgress


def test_extract_progress_prints_plan_and_finish() -> None:
    stream = io.StringIO()
    with ExtractProgress(
        tickers=["TSLA", "GM"],
        forms=["10-Q"],
        limit=1,
        db_path="data/buffer.sqlite",
        model="claude-opus-4-7",
        enabled=False,
        stream=stream,
    ) as progress:
        progress.start_ticker("TSLA", 1, 2)
        progress.fetched("TSLA", 1)
        progress.start_extract(
            "TSLA",
            form="10-Q",
            filing_date="2026-04-30",
            accession="ACC-001",
        )
        progress.upserted(
            "TSLA",
            accession="ACC-001",
            n_effects=3,
            confidence=0.82,
        )
        progress.finish(1, 3)

    output = stream.getvalue()
    assert "Plan: 2 ticker(s)" in output
    assert "Buffer: data/buffer.sqlite" in output
    assert "Extractor model: claude-opus-4-7" in output
    assert "TSLA - fetching SEC filings" in output
    assert "running extractor" in output
    assert "ok TSLA/ACC-001: 3 dated effect(s)" in output
    assert "Done. Upserted 1 filing(s), 3 dated effect(s)" in output


def test_extract_progress_reports_fetch_failure() -> None:
    stream = io.StringIO()
    with ExtractProgress(
        tickers=["BAD"],
        forms=["10-K"],
        limit=1,
        db_path="data/buffer.sqlite",
        model="claude-opus-4-7",
        enabled=False,
        stream=stream,
    ) as progress:
        progress.start_ticker("BAD", 1, 1)
        progress.skip("BAD", phase="fetch", detail="ticker not found")
        progress.finish(0, 0)

    assert "FAIL BAD fetch failed: ticker not found" in stream.getvalue()

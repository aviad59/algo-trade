"""Unit tests for the /api/v1/backtest service (walk-forward, cached)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from algo_trade.buffer import Buffer
from algo_trade.models import DatedEffect, Direction, ExtractedFiling, Magnitude
from api.deps import get_settings
from api.services import backtest as svc


def _filing(accession: str, filing_date: str, window: tuple[str, str]) -> ExtractedFiling:
    return ExtractedFiling(
        ticker="FCX",
        cik="0000831259",
        filing_type="10-Q",
        filing_date=date.fromisoformat(filing_date),
        accession_number=accession,
        dated_effects=[
            DatedEffect(
                sector="copper",
                direction=Direction.increase,
                magnitude=Magnitude.large,
                window_start=date.fromisoformat(window[0]),
                window_end=date.fromisoformat(window[1]),
                rationale="ramp",
                source_span="Item 7, MD&A",
            )
        ],
        flagged_risks=[],
        extractor_confidence=0.9,
        extractor_model="test-model",
        extracted_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )


def _write_prices(directory, instrument: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    start = date(2025, 1, 1)
    rows = ["date,close"]
    day = start
    price = 100.0
    while day <= date.today() + timedelta(days=1):
        if day.weekday() < 5:
            rows.append(f"{day.isoformat()},{price:.2f}")
            price += 0.1
        day += timedelta(days=1)
    (directory / f"{instrument}.csv").write_text("\n".join(rows), encoding="utf-8")


@pytest.fixture()
def env(tmp_path, monkeypatch):
    universe = tmp_path / "universe"
    universe.mkdir()
    (universe / "material-to-index.json").write_text(
        '{"indexes": {"copper": {"etfs": ["COPX"]}}}', encoding="utf-8"
    )
    (universe / "materials.json").write_text('{"materials": []}', encoding="utf-8")
    _write_prices(tmp_path / "prices", "COPX")
    monkeypatch.setenv("ALGO_TRADE_UNIVERSE_DIR", str(universe))
    monkeypatch.setenv("ALGO_TRADE_PRICES_DIR", str(tmp_path / "prices"))
    monkeypatch.setenv("ALGO_TRADE_BACKTEST_SINCE", "2025-07-01")
    monkeypatch.delenv("ALGO_TRADE_FORECAST_UNTIL", raising=False)
    get_settings.cache_clear()
    svc._backtest_cache.clear()
    yield tmp_path
    get_settings.cache_clear()
    svc._backtest_cache.clear()


@pytest.fixture()
def buf() -> Buffer:
    with Buffer(":memory:") as b:
        yield b


def test_backtest_reports_walkforward_trades(env, buf) -> None:
    # Filed Sep 2025 forecasting a 2026 ramp: tradable in real time.
    buf.upsert(_filing("ACC-1", "2025-09-15", ("2026-01-01", "2026-06-30")),
               company_name="Freeport")

    result = svc.build_backtest(buf)

    assert result["available"] is True
    assert result["mode"] == "walk-forward"
    copper = next(r for r in result["results"] if r["sector"] == "copper")
    assert copper["instrument"] == "COPX"
    assert copper["trades"], "expected at least one trade from an in-time filing"
    first = copper["trades"][0]
    # walk-forward: nothing can happen before the filing existed
    assert first["entry_date"] >= "2025-10-01"
    assert result["overall"]["trades_closed"] + result["overall"]["open_positions"] >= 1


def test_backtest_without_prices_is_available_false(env, buf, monkeypatch) -> None:
    monkeypatch.setenv("ALGO_TRADE_PRICES_DIR", str(env / "nonexistent"))
    get_settings.cache_clear()
    buf.upsert(_filing("ACC-1", "2025-09-15", ("2026-01-01", "2026-06-30")),
               company_name="Freeport")

    result = svc.build_backtest(buf)

    assert result["available"] is False
    assert "prices" in result["reason"].lower()
    assert result["results"] == []


def test_backtest_empty_buffer_is_available_false(env, buf) -> None:
    result = svc.build_backtest(buf)
    assert result["available"] is False
    assert result["results"] == []


def test_backtest_is_cached_until_buffer_changes(env, buf, monkeypatch) -> None:
    buf.upsert(_filing("ACC-1", "2025-09-15", ("2026-01-01", "2026-06-30")),
               company_name="Freeport")

    calls = {"n": 0}
    real_compute = svc._compute_backtest

    def counting(*args, **kwargs):
        calls["n"] += 1
        return real_compute(*args, **kwargs)

    monkeypatch.setattr(svc, "_compute_backtest", counting)

    first = svc.build_backtest(buf)
    second = svc.build_backtest(buf)
    assert calls["n"] == 1, "unchanged buffer must serve the cached backtest"
    assert second == first

    buf.upsert(_filing("ACC-2", "2025-12-15", ("2026-02-01", "2026-08-31")),
               company_name="Freeport")
    svc.build_backtest(buf)
    assert calls["n"] == 2, "new extraction must invalidate the cached backtest"

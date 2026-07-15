"""Hermetic tests for the point-in-time (walk-forward) backtest mode.

The scenario that motivates walk-forward: dated effects routinely carry
windows that begin BEFORE their filing date ("spending is elevated this
year", filed in April, window January-December). Full-buffer mode lets
that April filing move an October-of-last-year decision; walk-forward
must not.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd
import pytest

from algo_trade.backtest import backtest_buffer, walkforward_actions
from algo_trade.buffer import Buffer
from algo_trade.models import (
    DatedEffect,
    Direction,
    ExtractedFiling,
    Magnitude,
    TimerAction,
)
from algo_trade.timer import TimerConfig, detect_actions
from algo_trade.timeline import build_curve


def _effect(window_start: str, window_end: str, sector: str = "copper") -> DatedEffect:
    return DatedEffect(
        sector=sector,
        direction=Direction.increase,
        magnitude=Magnitude.large,
        window_start=date.fromisoformat(window_start),
        window_end=date.fromisoformat(window_end),
        rationale="test",
        source_span="Item 7, MD&A",
    )


def _filing(
    accession: str,
    filing_date: str,
    effects: list[DatedEffect],
    *,
    ticker: str = "FCX",
) -> ExtractedFiling:
    return ExtractedFiling(
        ticker=ticker,
        cik="0000831259",
        filing_type="10-Q",
        filing_date=date.fromisoformat(filing_date),
        accession_number=accession,
        dated_effects=effects,
        flagged_risks=[],
        extractor_confidence=0.9,
        extractor_model="test-model",
        extracted_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )


@pytest.fixture()
def buf() -> Buffer:
    with Buffer(":memory:") as b:
        yield b


CFG = TimerConfig(lookahead_months=3, buy_threshold=0.0)
SINCE = date(2025, 7, 1)
UNTIL = date(2026, 7, 1)


def test_walkforward_never_acts_before_the_filing_exists(buf):
    # Window reaches back to January; the filing only appears April 20.
    buf.upsert(
        _filing("ACC-1", "2026-04-20", [_effect("2026-01-01", "2026-12-31")]),
        company_name="Freeport",
    )

    # Full-buffer mode back-dates the knowledge: BUY fires long before April.
    naive = detect_actions(build_curve(buf, "copper", SINCE, UNTIL), config=CFG)
    assert naive and naive[0].action is TimerAction.BUY
    assert naive[0].date < date(2026, 4, 20)

    # Walk-forward: nothing tradeable can happen before the filing date.
    honest = walkforward_actions(buf, "copper", since=SINCE, until=UNTIL, config=CFG)
    for signal in honest:
        assert signal.date >= date(2026, 5, 1), (
            f"{signal.action} on {signal.date} predates the filing (2026-04-20)"
        )


def test_walkforward_still_fires_on_filings_known_in_time(buf):
    # Filed in September 2025, forecasting a Jan-Jun 2026 ramp: a trader
    # could genuinely have acted on this. Walk-forward should BUY.
    buf.upsert(
        _filing("ACC-1", "2025-09-15", [_effect("2026-01-01", "2026-06-30")]),
        company_name="Freeport",
    )

    actions = walkforward_actions(buf, "copper", since=SINCE, until=UNTIL, config=CFG)

    assert actions, "expected a BUY from a filing known well in advance"
    assert actions[0].action is TimerAction.BUY
    assert actions[0].date >= date(2025, 10, 1)  # after the filing existed


def test_walkforward_empty_sector_returns_no_actions(buf):
    assert walkforward_actions(buf, "copper", since=SINCE, until=UNTIL, config=CFG) == []


def test_backtest_buffer_walkforward_flag_changes_trades(buf, tmp_path):
    # Same look-ahead scenario as above; prices rise all year, so entry
    # timing shows up directly in entry_date.
    buf.upsert(
        _filing("ACC-1", "2026-04-20", [_effect("2026-01-01", "2026-12-31")]),
        company_name="Freeport",
    )
    idx = pd.date_range("2025-07-01", "2026-07-01", freq="B")
    from algo_trade.backtest import PriceSeries

    prices = {"COPX": PriceSeries(
        pd.Series([100.0 + 0.1 * i for i in range(len(idx))], index=idx),
        instrument="COPX",
    )}
    universe = tmp_path / "universe"
    universe.mkdir()
    (universe / "material-to-index.json").write_text(
        '{"indexes": {"copper": {"etfs": ["COPX"]}}}', encoding="utf-8"
    )

    naive = backtest_buffer(
        buf, since=SINCE, until=UNTIL, prices=prices,
        timer_config=CFG, universe_dir=universe,
    )
    honest = backtest_buffer(
        buf, since=SINCE, until=UNTIL, prices=prices,
        timer_config=CFG, universe_dir=universe, walkforward=True,
    )

    assert naive.results and naive.results[0].trades
    naive_entry = naive.results[0].trades[0].entry_date
    assert naive_entry < date(2026, 4, 20)  # the bias, demonstrated

    if honest.results:  # walk-forward may or may not trade, but never early
        for trade in honest.results[0].trades:
            assert trade.entry_date >= date(2026, 5, 1)

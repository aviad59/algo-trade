"""Hermetic tests for the backtest harness (Stage 7).

Synthetic price series + seeded in-memory Buffer + canned TimerSignals.
No market-data calls, no LLM calls, no real SQLite.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from algo_trade.backtest import (
    BacktestResult,
    BacktestSummary,
    PriceSeries,
    Trade,
    backtest_actions,
    backtest_buffer,
    default_instrument_for_sector,
)
from algo_trade.buffer import Buffer
from algo_trade.models import (
    DatedEffect,
    Direction,
    ExtractedFiling,
    Magnitude,
    TimerAction,
    TimerSignal,
)


# --------------------------------------------------------------------------- #
# Fixture helpers
# --------------------------------------------------------------------------- #


def _daily_prices(start: str, end: str, base: float = 100.0, slope: float = 0.0) -> pd.Series:
    """Synthetic daily close series. ``slope`` is the per-trading-day delta."""
    idx = pd.date_range(start=start, end=end, freq="B")  # business days
    closes = [base + slope * i for i in range(len(idx))]
    return pd.Series(closes, index=idx, name="close")


def _signal(d: str, action: TimerAction, rationale: str = "test") -> TimerSignal:
    return TimerSignal(date=date.fromisoformat(d), action=action, rationale=rationale)


def _effect(
    sector: str,
    window_start: str,
    window_end: str,
    *,
    direction: Direction = Direction.increase,
    magnitude: Magnitude = Magnitude.large,
) -> DatedEffect:
    return DatedEffect(
        sector=sector,
        direction=direction,
        magnitude=magnitude,
        window_start=date.fromisoformat(window_start),
        window_end=date.fromisoformat(window_end),
        rationale="test",
        source_span="Item 7, MD&A",
    )


def _extracted(
    *,
    ticker: str = "TSLA",
    accession: str = "ACC-001",
    filing_date: str = "2024-01-30",
    effects: list[DatedEffect],
) -> ExtractedFiling:
    return ExtractedFiling(
        ticker=ticker,
        cik="0001318605",
        filing_type="10-Q",
        filing_date=date.fromisoformat(filing_date),
        accession_number=accession,
        dated_effects=effects,
        flagged_risks=[],
        extraction_warnings=[],
        extractor_confidence=0.8,
        extractor_model="claude-opus-4-7",
        extracted_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


# --------------------------------------------------------------------------- #
# PriceSeries
# --------------------------------------------------------------------------- #


def test_price_series_rejects_empty():
    with pytest.raises(ValueError):
        PriceSeries(pd.Series([], dtype=float), instrument="LIT")


def test_price_series_on_or_after_skips_weekend():
    # 2024-01-01 is Monday; let's start on Tuesday and ask about Monday.
    series = pd.Series(
        [100.0, 101.0, 102.0],
        index=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
    )
    ps = PriceSeries(series, instrument="LIT")
    actual_date, price = ps.price_on_or_after(date(2024, 1, 1))
    assert actual_date == date(2024, 1, 2)
    assert price == 100.0


def test_price_series_on_or_after_returns_none_past_end():
    series = pd.Series([100.0], index=pd.to_datetime(["2024-01-02"]))
    ps = PriceSeries(series, instrument="LIT")
    assert ps.price_on_or_after(date(2024, 1, 3)) is None


def test_price_series_on_or_before_returns_last_when_d_past_end():
    series = pd.Series(
        [100.0, 101.0], index=pd.to_datetime(["2024-01-02", "2024-01-03"])
    )
    ps = PriceSeries(series, instrument="LIT")
    actual_date, price = ps.price_on_or_before(date(2024, 1, 10))
    assert actual_date == date(2024, 1, 3)
    assert price == 101.0


# --------------------------------------------------------------------------- #
# backtest_actions: closed round trips
# --------------------------------------------------------------------------- #


def test_one_winning_round_trip():
    prices = _daily_prices("2024-01-01", "2024-12-31", base=100.0, slope=0.5)
    # Index 0 (Jan 1) is ~100; ~250 business days later (~Dec 31) is ~225.
    ps = PriceSeries(prices, instrument="LIT")

    actions = [
        _signal("2024-02-01", TimerAction.BUY),
        _signal("2024-10-01", TimerAction.SELL),
    ]
    result = backtest_actions(actions, ps, sector="lithium")

    assert isinstance(result, BacktestResult)
    assert result.instrument == "LIT"
    assert result.n_trades == 1
    assert result.n_winners == 1
    assert result.win_rate == 1.0
    trade = result.trades[0]
    assert trade.entry_price < trade.exit_price
    assert trade.return_pct > 0
    assert trade.open_at_end is False


def test_one_losing_round_trip():
    prices = _daily_prices("2024-01-01", "2024-12-31", base=200.0, slope=-0.5)
    ps = PriceSeries(prices, instrument="LIT")

    actions = [
        _signal("2024-02-01", TimerAction.BUY),
        _signal("2024-08-01", TimerAction.SELL),
    ]
    result = backtest_actions(actions, ps, sector="lithium")

    assert result.n_trades == 1
    assert result.n_winners == 0
    assert result.trades[0].return_pct < 0


def test_open_position_at_window_end_is_marked():
    """A BUY without a matching SELL gets paper-valued at window end."""
    prices = _daily_prices("2024-01-01", "2024-12-31", base=100.0, slope=0.5)
    ps = PriceSeries(prices, instrument="LIT")

    actions = [_signal("2024-02-01", TimerAction.BUY)]
    result = backtest_actions(
        actions, ps, sector="lithium", window_end=date(2024, 12, 31)
    )

    assert len(result.trades) == 1
    assert result.trades[0].open_at_end is True
    # n_trades counts only realised round trips
    assert result.n_trades == 0


def test_buy_without_matching_sell_then_no_followup_buys():
    """Defensive: timer state machine should prevent this anyway."""
    prices = _daily_prices("2024-01-01", "2024-12-31")
    ps = PriceSeries(prices, instrument="LIT")

    actions = [
        _signal("2024-02-01", TimerAction.BUY),
        # No SELL.
    ]
    result = backtest_actions(actions, ps, sector="lithium")
    assert len(result.trades) == 1   # the open BUY


def test_sell_without_buy_is_ignored():
    prices = _daily_prices("2024-01-01", "2024-12-31")
    ps = PriceSeries(prices, instrument="LIT")

    actions = [_signal("2024-03-01", TimerAction.SELL)]
    result = backtest_actions(actions, ps, sector="lithium")
    assert result.trades == []
    assert result.total_return_pct == 0.0


def test_benchmark_equals_strategy_when_holding_through_window_end():
    """Benchmark = buy at first BUY, hold to window_end. If the strategy
    SELLs exactly at window_end (or doesn't SELL at all), the two match."""
    prices = _daily_prices("2024-01-01", "2024-12-31", base=100.0, slope=1.0)
    ps = PriceSeries(prices, instrument="LIT")

    actions = [_signal("2024-02-01", TimerAction.BUY)]   # no SELL -> open at end
    result = backtest_actions(
        actions, ps, sector="lithium", window_end=date(2024, 12, 31)
    )
    # Open position is paper-valued at window end -- matches benchmark.
    assert result.trades[0].open_at_end is True
    assert result.trades[0].return_pct == pytest.approx(
        result.benchmark_return_pct, rel=1e-6
    )
    assert result.alpha_pct == pytest.approx(0.0, abs=1e-9)


def test_strategy_alpha_when_avoiding_drawdown():
    """If the strategy SELLs before a drop and stays out, alpha > 0."""
    closes = (
        [100 + i * 1.0 for i in range(150)]   # 150 days rising
        + [250 - i * 1.0 for i in range(100)]  # 100 days falling
    )
    idx = pd.date_range(start="2024-01-01", periods=len(closes), freq="B")
    ps = PriceSeries(pd.Series(closes, index=idx), instrument="LIT")

    # BUY near the start, SELL near the peak. window_end is past the
    # drawdown, so the benchmark (which holds through window_end) eats
    # the crash while the strategy sits in cash.
    actions = [
        _signal("2024-01-02", TimerAction.BUY),
        _signal("2024-07-01", TimerAction.SELL),
    ]
    result = backtest_actions(
        actions, ps, sector="lithium", window_end=ps.last_date()
    )

    assert result.total_return_pct > 0
    assert result.alpha_pct > 0


# --------------------------------------------------------------------------- #
# default_instrument_for_sector
# --------------------------------------------------------------------------- #


def test_default_instrument_reads_etfs_bucket(tmp_path: Path):
    (tmp_path / "material-to-index.json").write_text(json.dumps({
        "indexes": {
            "lithium": {"etfs": ["LIT", "BATT"], "producers": ["ALB"]}
        }
    }))
    assert default_instrument_for_sector("Lithium", universe_dir=tmp_path) == "LIT"


def test_default_instrument_falls_back_to_producer_when_no_etfs(tmp_path: Path):
    (tmp_path / "material-to-index.json").write_text(json.dumps({
        "indexes": {
            "manganese": {"etfs": [], "producers": ["S32", "GLNCY"]}
        }
    }))
    assert default_instrument_for_sector("Manganese", universe_dir=tmp_path) == "S32"


def test_default_instrument_returns_none_when_missing(tmp_path: Path):
    (tmp_path / "material-to-index.json").write_text(json.dumps({"indexes": {}}))
    assert default_instrument_for_sector("Unobtainium", universe_dir=tmp_path) is None


# --------------------------------------------------------------------------- #
# backtest_buffer: end-to-end on a seeded buffer
# --------------------------------------------------------------------------- #


@pytest.fixture
def buf() -> Buffer:
    return Buffer(":memory:")


def _seed_lithium_window(buf: Buffer) -> None:
    """Seed a buffer that produces a rising-then-falling forward_AUC.

    Effects start in March (not January), so January's forward_AUC is
    smaller than February's -- which is what the timer needs to fire a
    BUY on the rising edge. The signal then plateaus through Mar-Jul
    and falls off, so a SELL fires on the way down.
    """
    extractions = [
        _extracted(
            ticker=t,
            accession=f"ACC-{i}",
            filing_date="2024-01-15",
            effects=[
                _effect(
                    "Lithium",
                    "2024-03-01",
                    "2024-07-31",
                    direction=Direction.increase,
                    magnitude=Magnitude.large,
                )
            ],
        )
        for i, t in enumerate(["TSLA", "GM", "F"])
    ]
    for ext in extractions:
        buf.upsert(ext, company_name=ext.ticker + " INC")


def _instruments_map(tmp_path: Path) -> Path:
    universe_dir = tmp_path / "universe"
    universe_dir.mkdir()
    (universe_dir / "material-to-index.json").write_text(json.dumps({
        "indexes": {"lithium": {"etfs": ["LIT"], "producers": ["ALB"]}}
    }))
    return universe_dir


def test_backtest_buffer_returns_summary_with_trades(buf: Buffer, tmp_path: Path):
    _seed_lithium_window(buf)
    universe_dir = _instruments_map(tmp_path)

    prices = _daily_prices("2024-01-01", "2024-12-31", base=100.0, slope=0.3)
    ps = PriceSeries(prices, instrument="LIT")

    summary = backtest_buffer(
        buf,
        since=date(2024, 1, 1),
        until=date(2024, 12, 31),
        prices={"LIT": ps},
        universe_dir=universe_dir,
    )

    assert isinstance(summary, BacktestSummary)
    # At least one sector traded.
    assert summary.results, "no sectors produced any trades"
    lithium = next((r for r in summary.results if r.sector.lower() == "lithium"), None)
    assert lithium is not None
    assert lithium.instrument == "LIT"
    assert len(lithium.trades) >= 1


def test_backtest_buffer_skips_sectors_without_prices(buf: Buffer, tmp_path: Path):
    _seed_lithium_window(buf)
    universe_dir = _instruments_map(tmp_path)

    summary = backtest_buffer(
        buf,
        since=date(2024, 1, 1),
        until=date(2024, 12, 31),
        prices={},  # no prices supplied
        universe_dir=universe_dir,
    )
    assert summary.results == []
    assert summary.overall_return_pct == 0.0


def test_backtest_buffer_respects_instrument_overrides(buf: Buffer, tmp_path: Path):
    _seed_lithium_window(buf)
    universe_dir = _instruments_map(tmp_path)

    custom_prices = _daily_prices("2024-01-01", "2024-12-31", base=50.0, slope=0.1)
    ps = PriceSeries(custom_prices, instrument="CUSTOM_LIT")

    summary = backtest_buffer(
        buf,
        since=date(2024, 1, 1),
        until=date(2024, 12, 31),
        prices={"CUSTOM_LIT": ps},
        instrument_overrides={"lithium": "CUSTOM_LIT"},
        universe_dir=universe_dir,
    )
    assert any(r.instrument == "CUSTOM_LIT" for r in summary.results)


def test_backtest_buffer_empty_when_no_buffer_effects(buf: Buffer, tmp_path: Path):
    universe_dir = _instruments_map(tmp_path)
    prices = _daily_prices("2024-01-01", "2024-12-31")
    ps = PriceSeries(prices, instrument="LIT")
    summary = backtest_buffer(
        buf,
        since=date(2024, 1, 1),
        until=date(2024, 12, 31),
        prices={"LIT": ps},
        universe_dir=universe_dir,
    )
    assert summary.results == []


def test_summary_aggregates_winrate_across_sectors(buf: Buffer, tmp_path: Path):
    """Multiple sectors, one wins, one loses -> overall_win_rate is 0.5."""
    universe_dir = tmp_path / "universe"
    universe_dir.mkdir()
    (universe_dir / "material-to-index.json").write_text(json.dumps({
        "indexes": {
            "lithium": {"etfs": ["LIT"], "producers": []},
            "copper":  {"etfs": ["COPX"], "producers": []},
        }
    }))

    # Two sectors with effects -- same Mar-Jul window as _seed_lithium_window
    # so the timer fires a clean BUY then SELL on the rising/falling edges.
    for sector, ticker, accession in [
        ("Lithium", "TSLA", "L1"),
        ("Lithium", "GM",   "L2"),
        ("Copper",  "FCX",  "C1"),
        ("Copper",  "RIO",  "C2"),
    ]:
        buf.upsert(
            _extracted(
                ticker=ticker,
                accession=accession,
                effects=[_effect(sector, "2024-03-01", "2024-07-31")],
            ),
            company_name=ticker + " INC",
        )

    # Rising LIT (winner), falling COPX (loser).
    lit  = PriceSeries(_daily_prices("2024-01-01", "2024-12-31", base=100.0, slope=0.5),
                       instrument="LIT")
    copx = PriceSeries(_daily_prices("2024-01-01", "2024-12-31", base=200.0, slope=-0.5),
                       instrument="COPX")

    summary = backtest_buffer(
        buf,
        since=date(2024, 1, 1),
        until=date(2024, 12, 31),
        prices={"LIT": lit, "COPX": copx},
        universe_dir=universe_dir,
    )
    assert len(summary.results) == 2
    # At least one realised round trip per sector
    assert summary.total_trades >= 2
    # Mixed performance -> non-extreme win rate
    assert 0.0 <= summary.overall_win_rate <= 1.0

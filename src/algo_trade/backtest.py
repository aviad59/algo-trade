"""Stage 7 -- Backtest harness.

Closes the loop. The whole project is built on the assertion that
narrated demand (what companies say they will do) is a useful signal
for sector returns. The backtest harness is what lets us *measure*
that, instead of asserting it.

Inputs
------
- A :class:`~algo_trade.buffer.Buffer` populated by Agent #1 over a
  historical date range, so the timeline aggregator + timer have
  something to fire on.
- A price series per instrument (sector ETF or producer basket). This
  module deliberately does NOT integrate with any specific data
  provider -- you bring your own ``date -> close`` mapping. Loading from
  Yahoo Finance / AlphaVantage / a CSV file is the caller's concern.

Algorithm
---------
For each sector with non-empty actions in ``[since, until]``:

  1. Build the timeline curve, run the timer, get ``[BUY, SELL]`` pairs.
  2. Look up the instrument that represents the sector (uses
     ``backend/universe/material-to-index.json``'s ETF bucket by default).
  3. For each BUY/SELL pair, simulate a long position:
       entry  = next price on/after BUY date
       exit   = next price on/after SELL date
       return = (exit / entry) - 1
  4. Open BUY without a matching SELL is paper-valued at the last
     available price in the window.

Output
------
A :class:`BacktestResult` per sector with the trade list, total return,
benchmark (buy-and-hold same instrument over the window) return, and
the resulting alpha. The harness does NOT make trading recommendations
-- it answers the empirical question "did the timer beat hold?"

Hermetic by design
------------------
All tests pass in synthetic ``pd.Series`` price data and a seeded
in-memory buffer. No tests hit a market data provider; the harness
never does either. That's the caller's choice and isolates this code
from data-vendor flakiness.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Mapping, Optional

import pandas as pd

from .buffer import Buffer
from .models import TimerAction, TimerSignal
from .timer import TimerConfig, detect_actions
from .timeline import build_curve

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Types
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Trade:
    """One closed BUY-SELL round trip (or an open BUY paper-valued at window end)."""

    sector: str
    instrument: str
    entry_date: date
    entry_price: float
    exit_date: date
    exit_price: float
    return_pct: float
    open_at_end: bool   # True when the BUY had no matching SELL in window


@dataclass
class BacktestResult:
    """Per-sector backtest output."""

    sector: str
    instrument: str
    trades: list[Trade] = field(default_factory=list)

    # Sum of trade returns (simple accumulation, not compounded). Use
    # `equity_curve` when you want compounding.
    total_return_pct: float = 0.0

    # Buy-and-hold the same instrument from the first BUY date (or window
    # start if no actions) to the last action's date (or window end).
    benchmark_return_pct: float = 0.0

    @property
    def alpha_pct(self) -> float:
        return self.total_return_pct - self.benchmark_return_pct

    @property
    def n_trades(self) -> int:
        return sum(1 for t in self.trades if not t.open_at_end)

    @property
    def n_winners(self) -> int:
        return sum(1 for t in self.trades if not t.open_at_end and t.return_pct > 0)

    @property
    def win_rate(self) -> float:
        n = self.n_trades
        return (self.n_winners / n) if n else 0.0


@dataclass
class BacktestSummary:
    """Aggregate across many sectors."""

    results: list[BacktestResult] = field(default_factory=list)

    @property
    def overall_return_pct(self) -> float:
        """Equal-weighted average of per-sector returns."""
        if not self.results:
            return 0.0
        return sum(r.total_return_pct for r in self.results) / len(self.results)

    @property
    def overall_benchmark_pct(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.benchmark_return_pct for r in self.results) / len(self.results)

    @property
    def overall_alpha_pct(self) -> float:
        return self.overall_return_pct - self.overall_benchmark_pct

    @property
    def total_trades(self) -> int:
        return sum(r.n_trades for r in self.results)

    @property
    def total_winners(self) -> int:
        return sum(r.n_winners for r in self.results)

    @property
    def overall_win_rate(self) -> float:
        n = self.total_trades
        return (self.total_winners / n) if n else 0.0


# --------------------------------------------------------------------------- #
# Price lookup
# --------------------------------------------------------------------------- #


class PriceSeries:
    """Thin wrapper around a date-indexed pandas Series.

    The wrapper exists for one reason: the backtest needs to look up the
    price on the next trading day at or after a given date (because BUY
    actions land on the first of the month, which may be a weekend).
    Putting that logic in one place keeps the harness readable.
    """

    def __init__(self, series: pd.Series, *, instrument: str) -> None:
        if not isinstance(series, pd.Series):
            raise TypeError("PriceSeries needs a pandas Series of closes")
        if series.empty:
            raise ValueError(f"empty price series for {instrument!r}")
        normalized = series.copy()
        normalized.index = pd.to_datetime(normalized.index)
        normalized = normalized.sort_index()
        self._series = normalized
        self.instrument = instrument

    def __len__(self) -> int:
        return len(self._series)

    def first_date(self) -> date:
        return self._series.index[0].date()

    def last_date(self) -> date:
        return self._series.index[-1].date()

    def price_on_or_after(self, d: date) -> Optional[tuple[date, float]]:
        """Return (actual_date, close) for the first trading day at or
        after ``d``. None if no such date exists in the series."""
        ts = pd.Timestamp(d)
        idx = self._series.index.searchsorted(ts, side="left")
        if idx >= len(self._series):
            return None
        actual_ts = self._series.index[idx]
        return actual_ts.date(), float(self._series.iloc[idx])

    def price_on_or_before(self, d: date) -> Optional[tuple[date, float]]:
        """Return (actual_date, close) for the most recent trading day at
        or before ``d``. None if ``d`` predates the series."""
        ts = pd.Timestamp(d)
        idx = self._series.index.searchsorted(ts, side="right") - 1
        if idx < 0:
            return None
        actual_ts = self._series.index[idx]
        return actual_ts.date(), float(self._series.iloc[idx])


# --------------------------------------------------------------------------- #
# Sector -> instrument resolution
# --------------------------------------------------------------------------- #


def default_instrument_for_sector(
    sector: str, *, universe_dir: Path | None = None
) -> Optional[str]:
    """Pick the first ETF from ``material-to-index.json`` for the sector.

    Returns None if the sector has no instrument map or no ETFs. Callers
    can override by passing ``instrument_overrides`` to ``backtest_buffer``.
    """
    if universe_dir is None:
        # Repo-relative fallback. Same path as backend.api.routes.universe.
        universe_dir = Path(__file__).resolve().parents[2] / "backend" / "universe"

    path = universe_dir / "material-to-index.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    bucket = data.get("indexes", {}).get(sector.lower())
    if bucket is None:
        return None
    etfs = bucket.get("etfs") or []
    if etfs:
        return str(etfs[0])
    producers = bucket.get("producers") or []
    if producers:
        return str(producers[0])
    return None


# --------------------------------------------------------------------------- #
# Per-sector backtest
# --------------------------------------------------------------------------- #


def backtest_actions(
    actions: list[TimerSignal],
    prices: PriceSeries,
    *,
    sector: str,
    window_end: Optional[date] = None,
) -> BacktestResult:
    """Replay a sequence of BUY/SELL actions against a price series.

    A BUY without a matching SELL is paper-valued at ``window_end`` (or at
    the last available price if ``window_end`` is None). The open trade
    is included in ``trades`` with ``open_at_end=True`` so callers can
    distinguish it from realised round trips.
    """
    instrument = prices.instrument
    result = BacktestResult(sector=sector, instrument=instrument)

    pending_buy: Optional[tuple[date, float]] = None

    for sig in actions:
        if sig.action is TimerAction.BUY:
            entry = prices.price_on_or_after(sig.date)
            if entry is None:
                logger.warning(
                    "no price on/after %s for %s; skipping BUY",
                    sig.date.isoformat(),
                    instrument,
                )
                continue
            pending_buy = entry
            continue

        # SELL
        if pending_buy is None:
            # Timer's state machine shouldn't emit SELL without a prior BUY,
            # but defend against it.
            continue
        exit_pt = prices.price_on_or_after(sig.date)
        if exit_pt is None:
            # Out of price data. Stop here; the open BUY is handled below.
            break
        entry_date, entry_price = pending_buy
        exit_date, exit_price = exit_pt
        ret = (exit_price / entry_price) - 1.0 if entry_price else 0.0
        result.trades.append(
            Trade(
                sector=sector,
                instrument=instrument,
                entry_date=entry_date,
                entry_price=entry_price,
                exit_date=exit_date,
                exit_price=exit_price,
                return_pct=ret,
                open_at_end=False,
            )
        )
        pending_buy = None

    # Handle an open BUY at end-of-window.
    if pending_buy is not None:
        end = window_end or prices.last_date()
        marked = prices.price_on_or_before(end)
        if marked is not None:
            entry_date, entry_price = pending_buy
            mark_date, mark_price = marked
            ret = (mark_price / entry_price) - 1.0 if entry_price else 0.0
            result.trades.append(
                Trade(
                    sector=sector,
                    instrument=instrument,
                    entry_date=entry_date,
                    entry_price=entry_price,
                    exit_date=mark_date,
                    exit_price=mark_price,
                    return_pct=ret,
                    open_at_end=True,
                )
            )

    result.total_return_pct = sum(t.return_pct for t in result.trades)

    # Benchmark: buy-and-hold from the first BUY's entry date through the
    # END OF THE WINDOW (not the last SELL). This is the meaningful
    # comparison -- the strategy may sit in cash for parts of the window
    # while the benchmark stays invested through whatever happens next.
    # If the strategy's SELL was timely, alpha > 0; if it sold into a
    # rally, alpha < 0.
    if result.trades:
        bench_start = prices.price_on_or_after(result.trades[0].entry_date)
        bench_end_date = window_end or prices.last_date()
        bench_end = prices.price_on_or_before(bench_end_date)
        if bench_start and bench_end and bench_start[1]:
            result.benchmark_return_pct = (bench_end[1] / bench_start[1]) - 1.0

    return result


# --------------------------------------------------------------------------- #
# Buffer-wide backtest
# --------------------------------------------------------------------------- #


def backtest_buffer(
    buf: Buffer,
    *,
    since: date,
    until: date,
    prices: Mapping[str, PriceSeries],
    sectors: Optional[list[str]] = None,
    timer_config: Optional[TimerConfig] = None,
    extractor_model: Optional[str] = None,
    instrument_overrides: Optional[Mapping[str, str]] = None,
    universe_dir: Optional[Path] = None,
) -> BacktestSummary:
    """Run the timer over every sector with effects in ``[since, until]``
    and backtest each against the supplied price series.

    Args:
        buf: A populated buffer. The harness will not write to it.
        since / until: window for the timeline aggregator. Should cover
            both the period where extractions exist AND the price data.
        prices: ``{instrument_ticker: PriceSeries}``. Sectors whose
            instrument isn't in this dict are skipped (with a warning).
        sectors: Optional whitelist. Defaults to "all sectors that
            produced at least one TimerAction in the window."
        timer_config: Override TimerConfig (lookahead, buy_threshold).
        extractor_model: Restrict to extractions from one model.
        instrument_overrides: ``{sector_id: ticker}`` to override the
            default ETF lookup (e.g. {"lithium": "LIT"}).
        universe_dir: Path to ``backend/universe/`` for the default
            instrument lookup. Tests pass a temp dir.
    """
    overrides = {k.lower(): v for k, v in (instrument_overrides or {}).items()}

    if sectors is None:
        # All sectors present in the buffer for the window.
        all_effects = buf.all_effects(since, until, extractor_model=extractor_model)
        sectors = sorted({eff.sector for eff in all_effects})

    summary = BacktestSummary()

    for sector in sectors:
        instrument = overrides.get(sector.lower())
        if instrument is None:
            instrument = default_instrument_for_sector(
                sector, universe_dir=universe_dir
            )
        if instrument is None:
            logger.info("no instrument mapped for sector %r; skipping", sector)
            continue

        price_series = prices.get(instrument)
        if price_series is None:
            logger.info(
                "no price series provided for %s (sector %s); skipping",
                instrument, sector,
            )
            continue

        curve = build_curve(buf, sector, since, until, extractor_model=extractor_model)
        if curve.empty:
            continue
        actions = detect_actions(curve, config=timer_config)
        if not actions:
            continue

        result = backtest_actions(
            actions, price_series, sector=sector, window_end=until
        )
        if result.trades:
            summary.results.append(result)

    return summary

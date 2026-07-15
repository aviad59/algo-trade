"""Backtest API builder — the honest (walk-forward) replay, served read-only.

Mirrors what `algo-trade-backtest --walkforward` prints, as JSON: per-sector
strategy-vs-hold returns, exposure, the trade blotter, and any position still
open at the window end. Decisions replay point-in-time — each month only sees
filings already published — so the numbers quoted here carry no look-ahead
bias.

Prices come from offline CSVs (``ALGO_TRADE_PRICES_DIR``, default
``data/prices``). No prices on disk is a first-class state, not an error:
the endpoint answers ``available: false`` and the UI explains how to cache
prices. Like the ranking, results are cached on the buffer version — a
backtest over 8 sectors takes a few seconds of pandas work, which is too
slow to repeat per page load but changes only when new extractions land.
"""

from __future__ import annotations

import logging
import threading
from datetime import date

from algo_trade.buffer import Buffer

from ..deps import get_settings

logger = logging.getLogger(__name__)

_backtest_cache: dict[tuple, dict] = {}
_backtest_lock = threading.Lock()


def _exposure_pct(result, since: date, until: date) -> float:
    """Fraction of the window the strategy was in the market (vs cash)."""
    window_days = max((until - since).days, 1)
    in_market = sum((t.exit_date - t.entry_date).days for t in result.trades)
    return min(in_market / window_days, 1.0)


def _trade_to_api(trade) -> dict:
    return {
        "entry_date": trade.entry_date.isoformat(),
        "entry_price": round(trade.entry_price, 2),
        "exit_date": trade.exit_date.isoformat(),
        "exit_price": round(trade.exit_price, 2),
        "return_pct": round(trade.return_pct, 4),
        "open_at_end": trade.open_at_end,
    }


def _result_to_api(result, since: date, until: date) -> dict:
    open_trades = [t for t in result.trades if t.open_at_end]
    open_position = None
    if open_trades:
        t = open_trades[0]
        open_position = {
            "entry_date": t.entry_date.isoformat(),
            "entry_price": round(t.entry_price, 2),
            # for an open trade the backtester marks to the last trading day
            "current_price": round(t.exit_price, 2),
            "return_pct": round(t.return_pct, 4),
        }
    return {
        "sector": result.sector,
        "instrument": result.instrument,
        "trades_closed": result.n_trades,
        "win_rate": round(result.win_rate, 4),
        "return_pct": round(result.total_return_pct, 4),
        "benchmark_pct": round(result.benchmark_return_pct, 4),
        "alpha_pct": round(result.alpha_pct, 4),
        "exposure_pct": round(_exposure_pct(result, since, until), 4),
        "open_position": open_position,
        "trades": [_trade_to_api(t) for t in result.trades],
    }


def _unavailable(since: date, until: date, reason: str) -> dict:
    return {
        "contract_version": "1.0",
        "available": False,
        "mode": "walk-forward",
        "since": since.isoformat(),
        "until": until.isoformat(),
        "reason": reason,
        "overall": None,
        "results": [],
    }


def _compute_backtest(buf: Buffer, since: date, until: date, settings) -> dict:
    from algo_trade.backtest import backtest_buffer
    from algo_trade.prices import load_prices_dir

    try:
        prices = load_prices_dir(settings.prices_dir)
    except (FileNotFoundError, NotADirectoryError):
        prices = {}
    if not prices:
        return _unavailable(
            since,
            until,
            "No cached prices found. Run algo-trade-backtest --yfinance "
            f"--save-prices {settings.prices_dir} to populate them.",
        )

    effects = buf.all_effects(since, until)
    sectors = sorted({e.sector for e in effects})
    if not sectors:
        return _unavailable(since, until, "No dated effects in the backtest window.")

    summary = backtest_buffer(
        buf,
        since=since,
        until=until,
        prices=prices,
        sectors=sectors,
        instrument_overrides=settings.backtest_overrides,
        universe_dir=settings.universe_dir,
        walkforward=True,
    )
    if not summary.results:
        return _unavailable(
            since, until, "No sector produced both timer actions and priced trades."
        )

    results = [_result_to_api(r, since, until) for r in summary.results]
    exposures = [r["exposure_pct"] for r in results]
    overall = {
        "win_rate": round(summary.overall_win_rate, 4),
        "return_pct": round(summary.overall_return_pct, 4),
        "benchmark_pct": round(summary.overall_benchmark_pct, 4),
        "alpha_pct": round(summary.overall_alpha_pct, 4),
        "exposure_pct": round(sum(exposures) / len(exposures), 4),
        "trades_closed": summary.total_trades,
        "winners": summary.total_winners,
        "open_positions": sum(1 for r in results if r["open_position"]),
    }
    return {
        "contract_version": "1.0",
        "available": True,
        "mode": "walk-forward",
        "since": since.isoformat(),
        "until": until.isoformat(),
        "reason": None,
        "overall": overall,
        "results": results,
    }


def build_backtest(buf: Buffer) -> dict:
    """Cached walk-forward backtest; invalidates when the buffer changes."""
    settings = get_settings()
    since = settings.backtest_since
    until = settings.forecast_until
    key = (
        buf.path,
        buf.max_extracted_at(),
        buf.count_extractions(),
        since,
        until,
        str(settings.prices_dir),
    )
    with _backtest_lock:
        cached = _backtest_cache.get(key)
        if cached is not None:
            return cached
        result = _compute_backtest(buf, since, until, settings)
        _backtest_cache.clear()  # entries for older buffer versions are dead
        _backtest_cache[key] = result
        return result

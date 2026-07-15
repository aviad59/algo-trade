"""algo-trade-backtest — replay the buy/sell timer against real prices.

Answers the project's central empirical question: did the narrated
signal beat buy-and-hold? Runs the timer over every sector with effects
in the window, maps each sector to its ETF (material-to-index.json),
replays BUY/SELL against the supplied prices, and prints a per-sector
table with strategy return, benchmark return, and alpha.

Price sources (checked in order):
  --prices-dir DIR   offline CSVs, one per instrument (date,close)
  --yfinance         fetch from Yahoo Finance (needs `pip install yfinance`)
Add --save-prices with --yfinance to cache the fetch as CSVs so later
runs are offline and reproducible.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta


def _forecast_window() -> tuple[date, date]:
    from .env import env_str, load_env

    load_env()
    today = date.today()
    default_since = today.replace(day=1) - timedelta(days=365)
    since_raw = env_str("ALGO_TRADE_FORECAST_SINCE", "")
    until_raw = env_str("ALGO_TRADE_FORECAST_UNTIL", "")
    since = date.fromisoformat(since_raw) if since_raw else default_since
    until = date.fromisoformat(until_raw) if until_raw else today
    return since, until


def _exposure_pct(result, since: date, until: date) -> float:
    """Fraction of the window the strategy was actually in the market.

    The strategy sits in cash outside BUY->SELL spans, while the hold
    benchmark stays invested throughout — so raw strategy-vs-hold
    conflates timing skill with time in market. Exposure makes the
    comparison honest: +10% earned in 3 months of exposure is a very
    different result from +10% earned across 12.
    """
    window_days = max((until - since).days, 1)
    in_market = sum((t.exit_date - t.entry_date).days for t in result.trades)
    return min(in_market / window_days, 1.0)


def _format_summary(summary, *, since: date | None = None, until: date | None = None) -> str:
    """Render a BacktestSummary as an aligned text table."""
    show_exposure = since is not None and until is not None
    exposure_header = f" {'exposed':>8}" if show_exposure else ""
    header = (
        f"{'sector':<16} {'etf':<6} {'trades':>6} {'win':>5} "
        f"{'strategy':>9} {'hold':>9} {'alpha':>9}{exposure_header}"
    )
    lines = [header, "-" * len(header)]
    exposures = []
    for r in summary.results:
        open_note = "*" if any(t.open_at_end for t in r.trades) else ""
        exposure_cell = ""
        if show_exposure:
            exposure = _exposure_pct(r, since, until)
            exposures.append(exposure)
            exposure_cell = f" {exposure:>8.0%}"
        lines.append(
            f"{r.sector:<16} {r.instrument:<6} {r.n_trades:>5}{open_note:<1} "
            f"{r.win_rate:>4.0%} {r.total_return_pct:>+9.2%} "
            f"{r.benchmark_return_pct:>+9.2%} {r.alpha_pct:>+9.2%}{exposure_cell}"
        )
    lines.append("-" * len(header))
    overall_exposure = ""
    if show_exposure and exposures:
        overall_exposure = f" {sum(exposures) / len(exposures):>8.0%}"
    lines.append(
        f"{'overall (equal-weighted)':<29} "
        f"{summary.overall_win_rate:>4.0%} {summary.overall_return_pct:>+9.2%} "
        f"{summary.overall_benchmark_pct:>+9.2%} {summary.overall_alpha_pct:>+9.2%}"
        f"{overall_exposure}"
    )
    if any(any(t.open_at_end for t in r.trades) for r in summary.results):
        lines.append("* includes a position still open at window end (paper-valued)")
    if show_exposure:
        lines.append(
            "note: strategy holds cash outside BUY->SELL spans; 'hold' stays "
            "invested all window. Compare alpha alongside 'exposed'."
        )
    return "\n".join(lines)


def _cli(argv: list[str] | None = None) -> int:
    from .backtest import backtest_buffer, default_instrument_for_sector
    from .buffer import Buffer
    from .env import env_path, load_env

    load_env()
    default_since, default_until = _forecast_window()
    default_db = str(env_path("ALGO_TRADE_BUFFER_PATH", "data/buffer.sqlite"))

    parser = argparse.ArgumentParser(
        prog="algo-trade-backtest",
        description="Replay the buy/sell timer against real prices and report alpha vs hold.",
    )
    parser.add_argument(
        "sectors",
        nargs="*",
        metavar="SECTOR",
        help="Sectors to test (default: every sector in the buffer window).",
    )
    parser.add_argument("--db", default=default_db, metavar="PATH",
                        help="SQLite buffer path. Default: ALGO_TRADE_BUFFER_PATH.")
    parser.add_argument("--since", default=default_since.isoformat(),
                        help="Window start (ISO date). Default: ALGO_TRADE_FORECAST_SINCE.")
    parser.add_argument("--until", default=default_until.isoformat(),
                        help="Window end (ISO date). Default: ALGO_TRADE_FORECAST_UNTIL.")
    parser.add_argument("--prices-dir", metavar="DIR",
                        help="Directory of per-instrument CSVs (date,close).")
    parser.add_argument("--yfinance", action="store_true",
                        help="Fetch prices from Yahoo Finance (requires yfinance).")
    parser.add_argument("--save-prices", metavar="DIR",
                        help="With --yfinance: cache fetched prices as CSVs here.")
    parser.add_argument("--trades", action="store_true",
                        help="Also print every individual trade.")
    parser.add_argument("--override", action="append", default=[],
                        metavar="SECTOR=TICKER",
                        help="Instrument override, e.g. aluminum=AA. Repeatable.")
    parser.add_argument("--walkforward", action="store_true",
                        help="Point-in-time mode: each month's decision only sees "
                             "filings published on or before it. Without this flag "
                             "the timer sees the whole buffer at once, which "
                             "back-dates knowledge (look-ahead bias) — fine for "
                             "exploring, not for quoting.")
    args = parser.parse_args(argv)

    overrides: dict[str, str] = {}
    for raw in args.override:
        sector_key, _, ticker = raw.partition("=")
        if not ticker:
            parser.error(f"--override needs SECTOR=TICKER, got {raw!r}")
        overrides[sector_key.lower()] = ticker.upper()

    since = date.fromisoformat(args.since)
    until = date.fromisoformat(args.until)

    with Buffer(args.db) as buf:
        sectors = args.sectors or None
        if sectors is None:
            effects = buf.all_effects(since, until)
            sectors = sorted({e.sector for e in effects})
        if not sectors:
            print("no sectors with effects in window; nothing to backtest", file=sys.stderr)
            return 1

        # Resolve instruments up front so we know which prices we need.
        instruments = {}
        for sector in sectors:
            instrument = overrides.get(sector.lower()) or default_instrument_for_sector(sector)
            if instrument:
                instruments[sector] = instrument
        if not instruments:
            print("no sector maps to an instrument; check material-to-index.json",
                  file=sys.stderr)
            return 1

        # Gather prices.
        prices = {}
        if args.prices_dir:
            from .prices import load_prices_dir

            prices = load_prices_dir(args.prices_dir)
        if args.yfinance:
            from .prices import fetch_yfinance_prices, save_csv_prices

            missing = sorted(set(instruments.values()) - set(prices))
            if missing:
                # Fetch a little past `until` so the mark-to-market at window
                # end has a trading day to land on.
                fetched = fetch_yfinance_prices(
                    missing, start=since, end=until + timedelta(days=5)
                )
                if args.save_prices:
                    save_csv_prices(fetched, args.save_prices)
                prices.update(fetched)
        if not prices:
            print("no prices supplied: use --prices-dir DIR and/or --yfinance",
                  file=sys.stderr)
            return 1

        summary = backtest_buffer(
            buf, since=since, until=until, prices=prices, sectors=list(sectors),
            instrument_overrides=overrides, walkforward=args.walkforward,
        )

    if not summary.results:
        print("no sector produced both timer actions and priced trades in window",
              file=sys.stderr)
        return 1

    mode = "walk-forward (point-in-time)" if args.walkforward else \
        "full-buffer (LOOK-AHEAD BIAS: decisions see filings published later)"
    print(f"Backtest {since} -> {until}  (buffer: {args.db})")
    print(f"Mode: {mode}")
    print(_format_summary(summary, since=since, until=until))

    if args.trades:
        print()
        for r in summary.results:
            for t in r.trades:
                mark = " (open, paper-valued)" if t.open_at_end else ""
                print(
                    f"{t.sector:<16} {t.instrument:<6} "
                    f"{t.entry_date} @ {t.entry_price:.2f} -> "
                    f"{t.exit_date} @ {t.exit_price:.2f}  "
                    f"{t.return_pct:+.2%}{mark}"
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())

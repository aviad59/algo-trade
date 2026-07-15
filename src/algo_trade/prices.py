"""Reference price loaders for the backtest harness.

The backtest harness (`backtest.py`) deliberately takes a
``Mapping[instrument, PriceSeries]`` and never talks to a market-data
vendor itself -- tests stay hermetic and no vendor gets locked in. This
module provides the two reference loaders the roadmap promised so a
real backtest is runnable out of the box:

- :func:`load_csv_prices` / :func:`load_prices_dir` -- offline CSVs, the
  hermetic path. One file per instrument, ``date,close`` columns.
- :func:`fetch_yfinance_prices` -- convenience online fetch. Requires the
  optional ``yfinance`` package (``pip install yfinance``); imports lazily
  so nothing else in the pipeline grows a vendor dependency.

Both return the same shape the harness consumes, so they are drop-in:

    prices = load_prices_dir("data/prices")
    summary = backtest_buffer(buf, since=..., until=..., prices=prices)
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Iterable

import pandas as pd

from .backtest import PriceSeries

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# CSV (offline, hermetic)
# --------------------------------------------------------------------------- #


def load_csv_prices(path: str | Path, *, instrument: str | None = None) -> PriceSeries:
    """Load one instrument's closes from a CSV file.

    Expects a header with ``date`` and ``close`` columns (case-insensitive;
    ``Date``/``Close``/``Adj Close`` from common exports all work). The
    instrument name defaults to the uppercased file stem, so
    ``data/prices/LIT.csv`` becomes instrument ``LIT``.
    """
    path = Path(path)
    frame = pd.read_csv(path)
    columns = {c.lower().strip(): c for c in frame.columns}

    date_col = columns.get("date")
    close_col = columns.get("close") or columns.get("adj close")
    if date_col is None or close_col is None:
        raise ValueError(
            f"{path}: need 'date' and 'close' columns, found {list(frame.columns)!r}"
        )

    series = pd.Series(
        frame[close_col].astype(float).to_numpy(),
        index=pd.to_datetime(frame[date_col]),
    ).dropna()
    name = instrument or path.stem.upper()
    return PriceSeries(series, instrument=name)


def load_prices_dir(directory: str | Path) -> dict[str, PriceSeries]:
    """Load every ``*.csv`` in a directory as ``{TICKER: PriceSeries}``."""
    directory = Path(directory)
    prices: dict[str, PriceSeries] = {}
    for csv_path in sorted(directory.glob("*.csv")):
        try:
            series = load_csv_prices(csv_path)
        except (ValueError, OSError) as exc:
            logger.warning("skipping %s: %s", csv_path, exc)
            continue
        prices[series.instrument] = series
    return prices


def save_csv_prices(prices: dict[str, PriceSeries], directory: str | Path) -> None:
    """Write ``{TICKER: PriceSeries}`` back to one CSV per instrument.

    Round-trips through :func:`load_prices_dir`, so an online fetch can be
    cached once and every later run stays offline.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for ticker, series in prices.items():
        frame = series.series.rename("close").rename_axis("date").reset_index()
        frame.to_csv(directory / f"{ticker}.csv", index=False)


# --------------------------------------------------------------------------- #
# Yahoo Finance (online convenience)
# --------------------------------------------------------------------------- #


def fetch_yfinance_prices(
    tickers: Iterable[str], *, start: date, end: date
) -> dict[str, PriceSeries]:
    """Fetch daily closes for *tickers* from Yahoo Finance.

    Lazy-imports ``yfinance`` so the dependency stays optional. Tickers
    that return no data are skipped with a warning rather than failing
    the whole batch (mirrors the fetcher's one-bad-ticker policy).
    """
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError(
            "yfinance is not installed. `pip install yfinance`, or supply "
            "offline CSVs via --prices-dir / load_prices_dir()."
        ) from exc

    tickers = list(dict.fromkeys(tickers))  # dedupe, keep order
    frame = yf.download(
        tickers,
        start=start.isoformat(),
        end=end.isoformat(),
        auto_adjust=True,
        progress=False,
        group_by="column",
    )
    if frame is None or frame.empty:
        raise RuntimeError(f"Yahoo Finance returned no data for {tickers!r}")

    closes = frame["Close"] if "Close" in frame.columns else frame
    if isinstance(closes, pd.Series):  # single ticker comes back flat
        closes = closes.to_frame(name=tickers[0])

    prices: dict[str, PriceSeries] = {}
    for ticker in tickers:
        if ticker not in closes.columns:
            logger.warning("no Yahoo Finance data for %s; skipping", ticker)
            continue
        series = closes[ticker].dropna()
        if series.empty:
            logger.warning("empty Yahoo Finance series for %s; skipping", ticker)
            continue
        prices[ticker] = PriceSeries(series, instrument=ticker)
    return prices

"""Price loaders + quarterly-return helper for the backtest. Caller supplies
prices (CSV or yfinance); dividend/split-adjusted closes. No vendor lock-in.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from .scorer import Quarter, quarter_end, quarter_start


class PriceSeries:
    def __init__(self, series: pd.Series, ticker: str) -> None:
        s = series.copy()
        s.index = pd.to_datetime(s.index)
        self._s = s.sort_index()
        self.ticker = ticker

    def __len__(self) -> int:
        return len(self._s)

    def price_on_or_after(self, d: date) -> Optional[float]:
        i = self._s.index.searchsorted(pd.Timestamp(d), side="left")
        return float(self._s.iloc[i]) if i < len(self._s) else None

    def price_on_or_before(self, d: date) -> Optional[float]:
        i = self._s.index.searchsorted(pd.Timestamp(d), side="right") - 1
        return float(self._s.iloc[i]) if i >= 0 else None


def quarterly_return(ps: PriceSeries, qtr: Quarter) -> Optional[float]:
    """Percent return from the first trading day in the quarter to the last."""
    entry = ps.price_on_or_after(quarter_start(qtr))
    exit_ = ps.price_on_or_before(quarter_end(qtr))
    if entry is None or exit_ is None or entry == 0:
        return None
    return (exit_ / entry - 1.0) * 100.0


def partial_quarter_return(ps: PriceSeries, qtr: Quarter, asof: date) -> Optional[float]:
    """Quarter-to-date return: first trading day of the quarter to the latest
    price on/before ``asof`` (capped at the quarter end). For tracking an
    in-progress quarter."""
    entry = ps.price_on_or_after(quarter_start(qtr))
    end = min(asof, quarter_end(qtr))
    exit_ = ps.price_on_or_before(end)
    if entry is None or exit_ is None or entry == 0:
        return None
    return (exit_ / entry - 1.0) * 100.0


def load_csv_prices(prices_dir: Path) -> dict[str, PriceSeries]:
    """Load ``<TICKER>.csv`` files with columns date,close (adjusted)."""
    out: dict[str, PriceSeries] = {}
    if not prices_dir.is_dir():
        return out
    for path in prices_dir.glob("*.csv"):
        df = pd.read_csv(path)
        cols = {c.lower(): c for c in df.columns}
        dcol = cols.get("date")
        ccol = cols.get("close") or cols.get("adj close") or cols.get("adj_close")
        if not dcol or not ccol:
            continue
        out[path.stem.upper()] = PriceSeries(
            pd.Series(df[ccol].values, index=df[dcol].values), path.stem.upper()
        )
    return out


def load_yfinance_prices(
    tickers: list[str], start: str, end: str, *, save_dir: Optional[Path] = None
) -> dict[str, PriceSeries]:
    """Fetch dividend/split-adjusted closes. Optional cache to CSV for
    offline-reproducible reruns. Requires ``pip install -e '.[backtest]'``."""
    import yfinance as yf

    out: dict[str, PriceSeries] = {}
    for tk in tickers:
        df = yf.download(tk, start=start, end=end, auto_adjust=True, progress=False)
        if df is None or df.empty:
            continue
        close = df["Close"]
        if hasattr(close, "columns"):  # multiindex safety
            close = close.iloc[:, 0]
        out[tk.upper()] = PriceSeries(close, tk.upper())
        if save_dir:
            save_dir.mkdir(parents=True, exist_ok=True)
            pd.DataFrame({"date": close.index.date, "close": close.values}).to_csv(
                save_dir / f"{tk.upper()}.csv", index=False
            )
    return out

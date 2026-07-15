"""Sector timeline aggregator -- monthly signal curves from buffer effects.

Reads :class:`~algo_trade.buffer.store.SectorEffectRow` objects (via
:class:`~algo_trade.buffer.Buffer.all_effects`) and bins them into per-sector
monthly time series suitable for the buy/sell timer and the web forecast API.

Algorithm (see README §"Sector Timeline Aggregator"):
  1. Weight each effect: direction_sign × magnitude_weight
  2. Spread weight uniformly across overlapping calendar months
  3. Sum per (sector, month)
"""

from __future__ import annotations

import calendar
from datetime import date

import pandas as pd

from .buffer.store import Buffer, SectorEffectRow
from .models import Direction, Magnitude

__all__ = [
    "MAGNITUDE_WEIGHTS",
    "build_all_curves",
    "build_curve",
    "effect_weight",
    "months_in_window",
    "spread_effect_to_months",
]

MAGNITUDE_WEIGHTS: dict[Magnitude, float] = {
    Magnitude.small: 0.3,
    Magnitude.moderate: 0.6,
    Magnitude.large: 1.0,
}

_DIRECTION_SIGN: dict[Direction, float] = {
    Direction.increase: 1.0,
    Direction.decrease: -1.0,
}


def effect_weight(direction: Direction, magnitude: Magnitude) -> float:
    """Signed magnitude weight for one dated effect."""
    return _DIRECTION_SIGN[direction] * MAGNITUDE_WEIGHTS[magnitude]


def _month_end(month_start: date) -> date:
    last_day = calendar.monthrange(month_start.year, month_start.month)[1]
    return date(month_start.year, month_start.month, last_day)


def _next_month(month_start: date) -> date:
    if month_start.month == 12:
        return date(month_start.year + 1, 1, 1)
    return date(month_start.year, month_start.month + 1, 1)


def months_in_window(window_start: date, window_end: date) -> list[date]:
    """First day of each calendar month overlapping ``[window_start, window_end]``."""
    months: list[date] = []
    current = date(window_start.year, window_start.month, 1)
    while current <= window_end:
        if _month_end(current) >= window_start:
            months.append(current)
        current = _next_month(current)
    return months


def spread_effect_to_months(effect: SectorEffectRow) -> list[tuple[date, float]]:
    """Return ``[(month_start, contribution), ...]`` for one effect row."""
    months = months_in_window(effect.window_start, effect.window_end)
    if not months:
        return []
    total = effect_weight(effect.direction, effect.magnitude)
    per_month = total / len(months)
    return [(m, per_month) for m in months]


def _month_range(since: date, until: date) -> list[date]:
    """First-of-month dates from *since* through *until* (inclusive)."""
    return months_in_window(since, until)


def _contributions_dataframe(
    effects: list[SectorEffectRow],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for effect in effects:
        for month, contribution in spread_effect_to_months(effect):
            rows.append(
                {
                    "month": pd.Timestamp(month),
                    "sector": effect.sector,
                    "signal": contribution,
                }
            )
    if not rows:
        return pd.DataFrame(columns=["month", "sector", "signal"])
    return pd.DataFrame(rows)


def _dense_curve(
    aggregated: pd.DataFrame,
    sector: str,
    since: date,
    until: date,
) -> pd.DataFrame:
    month_index = [pd.Timestamp(m) for m in _month_range(since, until)]
    if aggregated.empty:
        return pd.DataFrame(
            {"month": month_index, "sector": sector, "signal": 0.0}
        )

    # Case-insensitive to mirror Buffer.all_effects's LOWER(de.sector) filter —
    # buffer rows may carry e.g. "Aluminum" while callers pass the canonical
    # lowercase material id. Group by month in case several case variants of
    # the same sector coexist in the buffer.
    sector_df = aggregated[
        aggregated["sector"].str.lower() == sector.lower()
    ].copy()
    reindexed = (
        sector_df.groupby("month")["signal"]
        .sum()
        .reindex(month_index, fill_value=0.0)
        .reset_index()
        .rename(columns={"index": "month"})
    )
    reindexed["sector"] = sector
    return reindexed[["month", "sector", "signal"]]


def curve_from_effects(
    effects: list[SectorEffectRow],
    sector: str,
    since: date,
    until: date,
) -> pd.DataFrame:
    """Build a dense monthly signal curve for one sector from effect rows.

    Same output shape as :func:`build_curve`, but takes the effects
    directly instead of querying the buffer — callers that need to filter
    effects themselves (e.g. the point-in-time backtest, which admits only
    filings published before each decision date) use this entry point.
    """
    contributions = _contributions_dataframe(effects)
    if contributions.empty:
        return _dense_curve(contributions, sector, since, until)

    aggregated = (
        contributions.groupby(["sector", "month"], as_index=False)["signal"]
        .sum()
    )
    return _dense_curve(aggregated, sector, since, until)


def build_curve(
    buf: Buffer,
    sector: str,
    since: date,
    until: date,
    *,
    extractor_model: str | None = None,
) -> pd.DataFrame:
    """Build a dense monthly signal curve for one sector.

    Returns a DataFrame with columns ``month`` (Timestamp), ``sector`` (str),
    ``signal`` (float).  Every month in ``[since, until]`` is present; months
    with no contributing effects have ``signal=0.0``.
    """
    effects = buf.all_effects(
        since, until, sector=sector, extractor_model=extractor_model
    )
    return curve_from_effects(effects, sector, since, until)


def build_all_curves(
    buf: Buffer,
    since: date,
    until: date,
    *,
    extractor_model: str | None = None,
) -> pd.DataFrame:
    """Build dense monthly curves for every sector present in the window."""
    effects = buf.all_effects(since, until, extractor_model=extractor_model)
    contributions = _contributions_dataframe(effects)
    if contributions.empty:
        return pd.DataFrame(columns=["month", "sector", "signal"])

    aggregated = (
        contributions.groupby(["sector", "month"], as_index=False)["signal"]
        .sum()
    )
    sectors = sorted(aggregated["sector"].unique())
    parts = [_dense_curve(aggregated, s, since, until) for s in sectors]
    return pd.concat(parts, ignore_index=True)

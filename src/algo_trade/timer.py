"""Buy/sell timer -- forward-AUC signals over sector timeline curves.

Reads per-sector monthly signal curves (from :mod:`algo_trade.timeline`) and
emits BUY/SELL actions without an LLM call.  Output shape matches the web
mock contract ``MaterialForecast``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

import pandas as pd

from .buffer import Buffer
from .models import TimerAction, TimerSignal
from .timeline import build_curve

__all__ = [
    "TimerConfig",
    "TimerStrategy",
    "detect_actions",
    "enrich_curve",
    "forward_auc",
    "material_forecast",
]


class TimerStrategy(str, Enum):
    forward_auc = "forward_auc"
    slope = "slope"
    peak = "peak"
    threshold_dwell = "threshold_dwell"


@dataclass(frozen=True)
class TimerConfig:
    lookahead_months: int = 3
    buy_threshold: float = 0.0


def forward_auc(signals: pd.Series, *, window: int = 3) -> pd.Series:
    """Forward-looking area under the curve.

    ``forward_AUC(t) = signal(t+1) + … + signal(t+W)``.  Partial sums at
    the tail use however many future months remain.
    """
    values = signals.tolist()
    n = len(values)
    out: list[float] = []
    for i in range(n):
        out.append(sum(values[i + 1 : i + 1 + window]))
    return pd.Series(out, index=signals.index)


def enrich_curve(
    curve: pd.DataFrame,
    *,
    config: TimerConfig | None = None,
) -> pd.DataFrame:
    """Add a ``forward_auc`` column to a :func:`~algo_trade.timeline.build_curve` result."""
    cfg = config or TimerConfig()
    enriched = curve.copy()
    enriched["forward_auc"] = forward_auc(
        enriched["signal"], window=cfg.lookahead_months
    )
    return enriched


def detect_actions(
    curve: pd.DataFrame,
    *,
    config: TimerConfig | None = None,
    strategy: TimerStrategy | str = TimerStrategy.forward_auc,
) -> list[TimerSignal]:
    """Detect BUY/SELL actions on a curve with a ``forward_auc`` column."""
    strat = TimerStrategy(strategy)
    if strat is not TimerStrategy.forward_auc:
        raise NotImplementedError(f"strategy {strat.value!r} is not implemented yet")

    cfg = config or TimerConfig()
    if "forward_auc" not in curve.columns:
        curve = enrich_curve(curve, config=cfg)

    auc = curve["forward_auc"].tolist()
    months = curve["month"].tolist()
    if not auc:
        return []

    actions: list[TimerSignal] = []
    buy_index: int | None = None

    for i in range(1, len(auc)):
        if buy_index is None:
            if auc[i] > cfg.buy_threshold and auc[i] > auc[i - 1]:
                buy_index = i
                actions.append(
                    TimerSignal(
                        date=months[i].date()
                        if hasattr(months[i], "date")
                        else months[i],
                        action=TimerAction.BUY,
                        rationale=(
                            f"forward_AUC rising ({auc[i - 1]:.2f} → {auc[i]:.2f})"
                        ),
                    )
                )
            continue

        prev_auc = auc[i - 1]
        curr_auc = auc[i]
        if curr_auc >= prev_auc:
            continue

        is_peak = True
        if i >= 2 and prev_auc < auc[i - 2]:
            is_peak = False
        if not is_peak:
            continue

        actions.append(
            TimerSignal(
                date=months[i].date() if hasattr(months[i], "date") else months[i],
                action=TimerAction.SELL,
                rationale=(
                    f"forward_AUC peaked at {months[i - 1].strftime('%Y-%m')} "
                    f"({prev_auc:.2f}), declining"
                ),
            )
        )
        break

    return actions


def material_forecast(
    buf: Buffer,
    sector: str,
    since: date,
    until: date,
    *,
    as_of: date | None = None,
    config: TimerConfig | None = None,
    extractor_model: str | None = None,
) -> dict:
    """Build a mock-contract-shaped material forecast dict from the buffer."""
    cfg = config or TimerConfig()
    curve = build_curve(
        buf, sector, since, until, extractor_model=extractor_model
    )
    enriched = enrich_curve(curve, config=cfg)
    actions = detect_actions(enriched, config=cfg)

    effects = buf.all_effects(
        since, until, sector=sector, extractor_model=extractor_model
    )
    tickers = {e.ticker for e in effects}

    curve_points = [
        {
            "month": row.month.strftime("%Y-%m"),
            "signal": round(float(row.signal), 4),
            "forward_AUC": round(float(row.forward_auc), 4),
        }
        for row in enriched.itertuples(index=False)
    ]

    return {
        "contract_version": "1.0",
        "material_id": sector,
        "as_of": (as_of or until).isoformat(),
        "actions": [
            {
                "date": a.date.isoformat(),
                "action": a.action.value,
                "rationale": a.rationale,
            }
            for a in actions
        ],
        "curve": curve_points,
        "contributing_ticker_count": len(tickers),
        "universe_curve": None,
    }

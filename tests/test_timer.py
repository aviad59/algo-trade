"""Hermetic tests for algo_trade.timer."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd
import pytest

from algo_trade.buffer import Buffer
from algo_trade.models import DatedEffect, Direction, ExtractedFiling, Magnitude, TimerAction
from algo_trade.timer import (
    TimerConfig,
    detect_actions,
    enrich_curve,
    forward_auc,
    material_forecast,
)


def _curve_from_signals(signals: list[float], start: str = "2026-01-01") -> pd.DataFrame:
    months = pd.date_range(start=start, periods=len(signals), freq="MS")
    return pd.DataFrame({"month": months, "sector": "Lithium", "signal": signals})


def test_forward_auc_arithmetic() -> None:
    signals = pd.Series([0.1, 0.2, 0.5, 1.0, 0.8, 0.3])
    auc = forward_auc(signals, window=3)
    assert auc.iloc[0] == pytest.approx(0.2 + 0.5 + 1.0)
    assert auc.iloc[3] == pytest.approx(0.8 + 0.3)
    assert auc.iloc[5] == pytest.approx(0.0)


def test_enrich_curve_adds_forward_auc() -> None:
    curve = _curve_from_signals([0.1, 0.2, 0.5])
    enriched = enrich_curve(curve)
    assert "forward_auc" in enriched.columns


def test_detect_actions_rising_then_falling() -> None:
    signals = [0.1, 0.2, 0.5, 1.45, 1.45, 1.2, 0.55, 0.1]
    curve = enrich_curve(_curve_from_signals(signals))
    actions = detect_actions(curve, config=TimerConfig(buy_threshold=0.0))
    assert len(actions) >= 1
    assert actions[0].action == TimerAction.BUY
    if len(actions) > 1:
        assert actions[1].action == TimerAction.SELL


def test_detect_actions_flat_curve_no_actions() -> None:
    curve = enrich_curve(_curve_from_signals([0.0, 0.0, 0.0, 0.0]))
    actions = detect_actions(curve, config=TimerConfig(buy_threshold=0.5))
    assert actions == []


def test_detect_actions_monotonic_rise_emits_buy() -> None:
    signals = [0.1, 0.3, 0.6, 1.0, 1.5, 2.0]
    curve = enrich_curve(_curve_from_signals(signals))
    actions = detect_actions(curve, config=TimerConfig(buy_threshold=0.0))
    assert any(a.action == TimerAction.BUY for a in actions)


def _make_extracted() -> ExtractedFiling:
    return ExtractedFiling(
        ticker="TSLA",
        cik="0001318605",
        filing_type="10-Q",
        filing_date=date(2026, 4, 30),
        accession_number="ACC-001",
        dated_effects=[
            DatedEffect(
                sector="lithium",
                direction=Direction.increase,
                magnitude=Magnitude.large,
                window_start=date(2026, 5, 1),
                window_end=date(2026, 8, 31),
                rationale="ramp",
                source_span="Item 2",
            )
        ],
        flagged_risks=[],
        extraction_warnings=[],
        extractor_confidence=0.8,
        extractor_model="claude-opus-4-7",
        extracted_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )


def test_material_forecast_e2e() -> None:
    buf = Buffer(":memory:")
    buf.upsert(_make_extracted(), company_name="Tesla, Inc.")
    forecast = material_forecast(
        buf,
        "lithium",
        since=date(2026, 1, 1),
        until=date(2026, 12, 31),
        as_of=date(2026, 6, 8),
    )
    assert forecast["material_id"] == "lithium"
    assert forecast["as_of"] == "2026-06-08"
    assert forecast["contributing_ticker_count"] == 1
    assert forecast["universe_curve"] is None
    assert len(forecast["curve"]) == 12
    assert forecast["curve"][0]["month"] == "2026-01"
    assert "forward_AUC" in forecast["curve"][0]
    assert "signal" in forecast["curve"][0]

"""Hermetic tests for algo_trade.timeline."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd
import pytest

from algo_trade.buffer import Buffer
from algo_trade.models import DatedEffect, Direction, ExtractedFiling, Magnitude
from algo_trade.timeline import (
    build_all_curves,
    build_curve,
    effect_weight,
    months_in_window,
    spread_effect_to_months,
)
from algo_trade.buffer.store import SectorEffectRow


def _make_effect(
    sector: str = "Lithium",
    direction: Direction = Direction.increase,
    magnitude: Magnitude = Magnitude.large,
    window_start: str = "2026-05-01",
    window_end: str = "2026-08-31",
) -> DatedEffect:
    return DatedEffect(
        sector=sector,
        direction=direction,
        magnitude=magnitude,
        window_start=date.fromisoformat(window_start),
        window_end=date.fromisoformat(window_end),
        rationale="test",
        source_span="Item 2",
    )


def _make_extracted(
    accession: str = "ACC-001",
    ticker: str = "TSLA",
    effects: list[DatedEffect] | None = None,
    model: str = "claude-opus-4-7",
) -> ExtractedFiling:
    return ExtractedFiling(
        ticker=ticker,
        cik="0001318605",
        filing_type="10-Q",
        filing_date=date(2026, 4, 30),
        accession_number=accession,
        dated_effects=effects if effects is not None else [_make_effect()],
        flagged_risks=[],
        extraction_warnings=[],
        extractor_confidence=0.8,
        extractor_model=model,
        extracted_at=datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def buf() -> Buffer:
    return Buffer(":memory:")


def test_effect_weight_large_increase() -> None:
    assert effect_weight(Direction.increase, Magnitude.large) == pytest.approx(1.0)


def test_effect_weight_moderate_decrease() -> None:
    assert effect_weight(Direction.decrease, Magnitude.moderate) == pytest.approx(-0.6)


def test_months_in_window_full_months() -> None:
    months = months_in_window(date(2026, 5, 1), date(2026, 8, 31))
    assert months == [
        date(2026, 5, 1),
        date(2026, 6, 1),
        date(2026, 7, 1),
        date(2026, 8, 1),
    ]


def test_months_in_window_partial_months() -> None:
    months = months_in_window(date(2026, 5, 15), date(2026, 6, 14))
    assert months == [date(2026, 5, 1), date(2026, 6, 1)]


def test_spread_effect_to_months_large_increase_may_aug() -> None:
    effect = SectorEffectRow(
        sector="Lithium",
        direction=Direction.increase,
        magnitude=Magnitude.large,
        window_start=date(2026, 5, 1),
        window_end=date(2026, 8, 31),
        rationale="r",
        source_span="s",
        ticker="TSLA",
        cik="c",
        filing_type="10-Q",
        filing_date=date(2026, 4, 30),
        accession_number="A",
        company_name=None,
        extractor_model="m",
        extractor_confidence=0.8,
    )
    spread = spread_effect_to_months(effect)
    assert len(spread) == 4
    assert all(v == pytest.approx(0.25) for _, v in spread)


def test_build_curve_single_effect(buf: Buffer) -> None:
    buf.upsert(_make_extracted())
    curve = build_curve(buf, "Lithium", since=date(2026, 1, 1), until=date(2026, 12, 31))
    may = curve[curve["month"] == pd.Timestamp("2026-05-01")]["signal"].iloc[0]
    assert may == pytest.approx(0.25)


def test_build_curve_moderate_decrease(buf: Buffer) -> None:
    buf.upsert(
        _make_extracted(
            effects=[
                _make_effect(
                    direction=Direction.decrease,
                    magnitude=Magnitude.moderate,
                    window_start="2026-01-01",
                    window_end="2026-03-31",
                )
            ]
        )
    )
    curve = build_curve(buf, "Lithium", since=date(2026, 1, 1), until=date(2026, 3, 31))
    assert curve["signal"].iloc[0] == pytest.approx(-0.2)


def test_build_curve_sums_two_companies(buf: Buffer) -> None:
    buf.upsert(_make_extracted(accession="ACC-001", ticker="TSLA"))
    buf.upsert(_make_extracted(accession="ACC-002", ticker="GM"))
    curve = build_curve(buf, "Lithium", since=date(2026, 5, 1), until=date(2026, 5, 31))
    assert curve["signal"].iloc[0] == pytest.approx(0.5)


def test_build_curve_zero_outside_effects(buf: Buffer) -> None:
    buf.upsert(_make_extracted())
    curve = build_curve(buf, "Lithium", since=date(2026, 1, 1), until=date(2026, 3, 31))
    assert curve["signal"].sum() == pytest.approx(0.0)


def test_build_curve_multi_model_dedup(buf: Buffer) -> None:
    early = _make_extracted(model="claude-opus-4-7")
    early.extracted_at = datetime(2026, 5, 1, tzinfo=timezone.utc)
    late = _make_extracted(
        model="claude-sonnet-4-6",
        effects=[
            _make_effect(
                magnitude=Magnitude.small,
                window_start="2026-05-01",
                window_end="2026-05-31",
            )
        ],
    )
    late.extracted_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
    buf.upsert(early)
    buf.upsert(late)
    curve = build_curve(buf, "Lithium", since=date(2026, 5, 1), until=date(2026, 5, 31))
    # small increase over 1 month = 0.3 (sonnet only)
    assert curve["signal"].iloc[0] == pytest.approx(0.3)


def test_build_all_curves_two_sectors(buf: Buffer) -> None:
    buf.upsert(
        _make_extracted(
            effects=[
                _make_effect("Lithium"),
                _make_effect("Copper", window_start="2026-06-01", window_end="2026-06-30"),
            ]
        )
    )
    curves = build_all_curves(buf, since=date(2026, 1, 1), until=date(2026, 12, 31))
    sectors = set(curves["sector"])
    assert sectors == {"Lithium", "Copper"}

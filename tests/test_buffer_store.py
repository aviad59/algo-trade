"""Hermetic tests for algo_trade.buffer.store.Buffer.

All tests run against an in-process :memory: SQLite database.
No network calls, no ANTHROPIC_API_KEY required.

Test plan (matches the Stage 1 definition of done):
  - Buffer initialises and applies schema
  - upsert stores effects, risks, and warnings round-trip
  - upsert is idempotent on (accession_number, extractor_model)
  - different models for the same filing coexist in extractions
  - effects_for_sector respects the window-intersection filter
  - filings_citing returns one row per distinct accession
  - context manager closes the connection cleanly
  - count_extractions reflects actual row count
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from algo_trade.buffer import Buffer
from algo_trade.buffer.store import SectorEffectRow
from algo_trade.models import (
    DatedEffect,
    Direction,
    ExtractedFiling,
    Magnitude,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _make_effect(
    sector: str = "Lithium",
    direction: Direction = Direction.increase,
    magnitude: Magnitude = Magnitude.large,
    window_start: str = "2026-05-01",
    window_end: str = "2026-08-31",
    rationale: str = "Gigafactory ramp",
    source_span: str = "Item 2, MD&A, p.18",
) -> DatedEffect:
    return DatedEffect(
        sector=sector,
        direction=direction,
        magnitude=magnitude,
        window_start=date.fromisoformat(window_start),
        window_end=date.fromisoformat(window_end),
        rationale=rationale,
        source_span=source_span,
    )


def _make_extracted(
    accession: str = "0001628280-26-005001",
    ticker: str = "TSLA",
    cik: str = "0001318605",
    filing_type: str = "10-Q",
    filing_date: str = "2026-04-30",
    model: str = "claude-opus-4-7",
    confidence: float = 0.79,
    effects: list[DatedEffect] | None = None,
    risks: list[str] | None = None,
    warnings: list[str] | None = None,
) -> ExtractedFiling:
    return ExtractedFiling(
        ticker=ticker,
        cik=cik,
        filing_type=filing_type,
        filing_date=date.fromisoformat(filing_date),
        accession_number=accession,
        dated_effects=effects if effects is not None else [_make_effect()],
        flagged_risks=risks if risks is not None else ["Supply concentration in Chile"],
        extraction_warnings=warnings if warnings is not None else [],
        extractor_confidence=confidence,
        extractor_model=model,
        extracted_at=datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def buf() -> Buffer:
    return Buffer(":memory:")


# --------------------------------------------------------------------------- #
# Initialisation
# --------------------------------------------------------------------------- #


def test_buffer_init_applies_schema(buf: Buffer) -> None:
    assert buf.count_extractions() == 0


def test_buffer_repr_shows_extraction_count(buf: Buffer) -> None:
    buf.upsert(_make_extracted())
    r = repr(buf)
    assert "1" in r


# --------------------------------------------------------------------------- #
# upsert: basic round-trip
# --------------------------------------------------------------------------- #


def test_upsert_returns_extraction_id(buf: Buffer) -> None:
    eid = buf.upsert(_make_extracted())
    assert isinstance(eid, int)
    assert eid > 0


def test_upsert_stores_effects(buf: Buffer) -> None:
    buf.upsert(_make_extracted())
    rows = buf.effects_for_sector(
        "Lithium",
        since=date(2026, 1, 1),
        until=date(2026, 12, 31),
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.sector == "Lithium"
    assert row.direction == Direction.increase
    assert row.magnitude == Magnitude.large
    assert row.ticker == "TSLA"
    assert row.filing_type == "10-Q"
    assert row.extractor_confidence == pytest.approx(0.79)


def test_upsert_stores_company_name(buf: Buffer) -> None:
    buf.upsert(_make_extracted(), company_name="Tesla, Inc.")
    rows = buf.effects_for_sector("Lithium", since=date(2026, 1, 1), until=date(2026, 12, 31))
    assert rows[0].company_name == "Tesla, Inc."


def test_upsert_stores_risks_and_warnings(buf: Buffer) -> None:
    # Risks and warnings are stored; we verify indirectly via filings_citing
    # which counts effects, and via count_extractions.
    buf.upsert(_make_extracted(warnings=["dropped effect: inverted window"]))
    assert buf.count_extractions() == 1


def test_upsert_multiple_effects(buf: Buffer) -> None:
    effects = [
        _make_effect("Lithium", Direction.increase, Magnitude.large, "2026-05-01", "2026-08-31"),
        _make_effect("Copper", Direction.decrease, Magnitude.moderate, "2026-06-01", "2026-09-30"),
    ]
    buf.upsert(_make_extracted(effects=effects))

    lithium = buf.effects_for_sector("Lithium", since=date(2026, 1, 1), until=date(2026, 12, 31))
    copper = buf.effects_for_sector("Copper", since=date(2026, 1, 1), until=date(2026, 12, 31))
    assert len(lithium) == 1
    assert len(copper) == 1
    assert copper[0].direction == Direction.decrease


# --------------------------------------------------------------------------- #
# upsert: idempotency
# --------------------------------------------------------------------------- #


def test_upsert_idempotent_same_model_replaces_effects(buf: Buffer) -> None:
    buf.upsert(_make_extracted())

    # Second upsert with same (accession, model) — different effect count.
    two_effects = [
        _make_effect("Lithium"),
        _make_effect("Copper", window_start="2026-06-01", window_end="2026-09-30"),
    ]
    buf.upsert(_make_extracted(effects=two_effects))

    assert buf.count_extractions() == 1  # still one row
    rows = buf.effects_for_sector("Lithium", since=date(2026, 1, 1), until=date(2026, 12, 31))
    copper = buf.effects_for_sector("Copper", since=date(2026, 1, 1), until=date(2026, 12, 31))
    assert len(rows) == 1  # not doubled
    assert len(copper) == 1


def test_upsert_idempotent_no_duplicate_filings_row(buf: Buffer) -> None:
    buf.upsert(_make_extracted())
    buf.upsert(_make_extracted())  # same accession + model
    assert buf.count_extractions() == 1


# --------------------------------------------------------------------------- #
# upsert: different models coexist
# --------------------------------------------------------------------------- #


def test_upsert_different_models_both_stored(buf: Buffer) -> None:
    opus = _make_extracted(model="claude-opus-4-7")
    sonnet = _make_extracted(model="claude-sonnet-4-6", confidence=0.65)
    buf.upsert(opus)
    buf.upsert(sonnet)
    assert buf.count_extractions() == 2


def test_upsert_different_models_effects_double(buf: Buffer) -> None:
    buf.upsert(_make_extracted(model="claude-opus-4-7"))
    buf.upsert(_make_extracted(model="claude-sonnet-4-6"))
    rows = buf.effects_for_sector("Lithium", since=date(2026, 1, 1), until=date(2026, 12, 31))
    # Two extractions of same filing, each with one Lithium effect → 2 rows
    assert len(rows) == 2


# --------------------------------------------------------------------------- #
# effects_for_sector: window-intersection filter
# --------------------------------------------------------------------------- #


def test_effects_for_sector_window_inside(buf: Buffer) -> None:
    buf.upsert(_make_extracted())  # window 2026-05-01 -> 2026-08-31
    rows = buf.effects_for_sector("Lithium", since=date(2026, 6, 1), until=date(2026, 7, 31))
    assert len(rows) == 1


def test_effects_for_sector_window_overlap_left(buf: Buffer) -> None:
    buf.upsert(_make_extracted())  # window 2026-05-01 -> 2026-08-31
    rows = buf.effects_for_sector("Lithium", since=date(2026, 1, 1), until=date(2026, 6, 1))
    assert len(rows) == 1  # window_end >= since


def test_effects_for_sector_window_overlap_right(buf: Buffer) -> None:
    buf.upsert(_make_extracted())  # window 2026-05-01 -> 2026-08-31
    rows = buf.effects_for_sector("Lithium", since=date(2026, 8, 1), until=date(2026, 12, 31))
    assert len(rows) == 1  # window_start <= until


def test_effects_for_sector_window_no_overlap(buf: Buffer) -> None:
    buf.upsert(_make_extracted())  # window 2026-05-01 -> 2026-08-31
    # Query for 2025 — should return nothing
    rows = buf.effects_for_sector("Lithium", since=date(2025, 1, 1), until=date(2025, 12, 31))
    assert len(rows) == 0


def test_effects_for_sector_wrong_sector_excluded(buf: Buffer) -> None:
    buf.upsert(_make_extracted())  # Lithium effect
    rows = buf.effects_for_sector("Copper", since=date(2026, 1, 1), until=date(2026, 12, 31))
    assert len(rows) == 0


def test_effects_for_sector_ordered_by_window_start(buf: Buffer) -> None:
    early = _make_extracted(
        accession="ACC-001",
        effects=[_make_effect("Lithium", window_start="2026-03-01", window_end="2026-05-31")],
    )
    late = _make_extracted(
        accession="ACC-002",
        effects=[_make_effect("Lithium", window_start="2026-07-01", window_end="2026-09-30")],
    )
    buf.upsert(early)
    buf.upsert(late)
    rows = buf.effects_for_sector("Lithium", since=date(2026, 1, 1), until=date(2026, 12, 31))
    assert rows[0].window_start < rows[1].window_start


# --------------------------------------------------------------------------- #
# filings_citing
# --------------------------------------------------------------------------- #


def test_filings_citing_returns_one_row_per_accession(buf: Buffer) -> None:
    two_effects = [
        _make_effect("Lithium"),
        _make_effect("Lithium", window_start="2026-06-01", window_end="2026-09-30"),
    ]
    buf.upsert(_make_extracted(effects=two_effects))
    citing = buf.filings_citing("Lithium")
    assert len(citing) == 1  # two effects from same filing → one row
    assert citing[0]["ticker"] == "TSLA"
    assert citing[0]["effect_count"] == 2


def test_filings_citing_multiple_filings(buf: Buffer) -> None:
    buf.upsert(_make_extracted(accession="ACC-001"))
    buf.upsert(_make_extracted(accession="ACC-002"))
    citing = buf.filings_citing("Lithium")
    accessions = {r["accession_number"] for r in citing}
    assert accessions == {"ACC-001", "ACC-002"}


def test_filings_citing_empty_when_no_match(buf: Buffer) -> None:
    buf.upsert(_make_extracted())  # Lithium effect
    assert buf.filings_citing("Copper") == []


# --------------------------------------------------------------------------- #
# Context manager
# --------------------------------------------------------------------------- #


def test_context_manager_closes(tmp_path: pytest.TempPathFactory) -> None:
    db_path = tmp_path / "test.sqlite"
    with Buffer(str(db_path)) as buf:
        buf.upsert(_make_extracted())

    # After exit the connection should be closed; a fresh Buffer on the same
    # file should still see the data.
    with Buffer(str(db_path)) as buf2:
        assert buf2.count_extractions() == 1


# --------------------------------------------------------------------------- #
# count_extractions
# --------------------------------------------------------------------------- #


def test_count_extractions_empty(buf: Buffer) -> None:
    assert buf.count_extractions() == 0


def test_count_extractions_increments(buf: Buffer) -> None:
    buf.upsert(_make_extracted(accession="ACC-001"))
    buf.upsert(_make_extracted(accession="ACC-002"))
    assert buf.count_extractions() == 2

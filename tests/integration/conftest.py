"""Shared fixtures for integration tests (buffer + FastAPI TestClient)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from algo_trade.buffer import Buffer
from algo_trade.models import DatedEffect, Direction, ExtractedFiling, Magnitude
from api.deps import get_buffer, get_settings
from api.main import app

pytestmark = pytest.mark.integration

FORECAST_SINCE = "2026-01-01"
FORECAST_UNTIL = "2026-12-31"


def effect(
    sector: str,
    *,
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
        rationale=f"{sector} demand shift",
        source_span="Item 2, MD&A, p.18",
    )


def make_extracted(
    accession: str,
    ticker: str,
    effects: list[DatedEffect],
    *,
    filing_date: str = "2026-04-30",
    sector: str | None = None,
) -> ExtractedFiling:
    if sector is not None and not effects:
        effects = [effect(sector)]
    return ExtractedFiling(
        ticker=ticker,
        cik="0001318605",
        filing_type="10-Q",
        filing_date=date.fromisoformat(filing_date),
        accession_number=accession,
        dated_effects=effects,
        flagged_risks=[],
        extraction_warnings=[],
        extractor_confidence=0.8,
        extractor_model="claude-opus-4-7",
        extracted_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )


def assert_required_keys(data: dict, keys: set[str]) -> None:
    missing = keys - data.keys()
    assert not missing, f"missing keys: {missing}"


@pytest.fixture
def simple_buffer(tmp_path) -> tuple[str, int]:
    """Two-ticker buffer (TSLA + GM, lithium only)."""
    db_path = tmp_path / "simple.sqlite"
    buf = Buffer(str(db_path))
    eid = buf.upsert(
        make_extracted("ACC-001", "TSLA", [effect("lithium")]),
        company_name="Tesla, Inc.",
    )
    buf.upsert(
        make_extracted("ACC-002", "GM", [effect("lithium")]),
        company_name="General Motors",
    )
    buf.close()
    return str(db_path), eid


@pytest.fixture
def demo_buffer(tmp_path) -> tuple[str, dict[str, int]]:
    """Three-ticker buffer (TSLA, GM, FCX) with lithium + copper."""
    db_path = tmp_path / "demo.sqlite"
    buf = Buffer(str(db_path))
    ids = {
        "tsla": buf.upsert(
            make_extracted(
                "ACC-TSLA",
                "TSLA",
                [
                    effect("lithium"),
                    effect("copper", window_start="2026-06-01", window_end="2026-09-30"),
                ],
            ),
            company_name="Tesla, Inc.",
        ),
        "gm": buf.upsert(
            make_extracted("ACC-GM", "GM", [effect("lithium")]),
            company_name="General Motors",
        ),
        "fcx": buf.upsert(
            make_extracted(
                "ACC-FCX",
                "FCX",
                [effect("copper")],
                filing_date="2026-03-15",
            ),
            company_name="Freeport-McMoRan",
        ),
    }
    buf.close()
    return str(db_path), ids


@pytest.fixture
def simple_api_client(simple_buffer, monkeypatch):
    db_path, eid = simple_buffer
    monkeypatch.setenv("ALGO_TRADE_BUFFER_PATH", db_path)
    monkeypatch.setenv("ALGO_TRADE_FORECAST_SINCE", FORECAST_SINCE)
    monkeypatch.setenv("ALGO_TRADE_FORECAST_UNTIL", FORECAST_UNTIL)
    get_settings.cache_clear()

    def override_buffer() -> Buffer:
        return Buffer(db_path)

    app.dependency_overrides[get_buffer] = override_buffer
    client = TestClient(app)
    yield client, eid
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture
def demo_api_client(demo_buffer, monkeypatch):
    db_path, ids = demo_buffer
    monkeypatch.setenv("ALGO_TRADE_BUFFER_PATH", db_path)
    monkeypatch.setenv("ALGO_TRADE_FORECAST_SINCE", FORECAST_SINCE)
    monkeypatch.setenv("ALGO_TRADE_FORECAST_UNTIL", FORECAST_UNTIL)
    get_settings.cache_clear()

    def override_buffer() -> Buffer:
        return Buffer(db_path)

    app.dependency_overrides[get_buffer] = override_buffer
    client = TestClient(app)
    yield client, ids
    app.dependency_overrides.clear()
    get_settings.cache_clear()

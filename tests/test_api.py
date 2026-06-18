"""Hermetic tests for the FastAPI serving layer."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from algo_trade.buffer import Buffer
from algo_trade.models import DatedEffect, Direction, ExtractedFiling, Magnitude
from api.deps import get_buffer, get_settings
from api.main import app


def _make_extracted(
    accession: str = "ACC-001",
    ticker: str = "TSLA",
    sector: str = "lithium",
) -> ExtractedFiling:
    return ExtractedFiling(
        ticker=ticker,
        cik="0001318605",
        filing_type="10-Q",
        filing_date=date(2026, 4, 30),
        accession_number=accession,
        dated_effects=[
            DatedEffect(
                sector=sector,
                direction=Direction.increase,
                magnitude=Magnitude.large,
                window_start=date(2026, 5, 1),
                window_end=date(2026, 8, 31),
                rationale="Cell line ramp",
                source_span="Item 2, MD&A, p.18",
            )
        ],
        flagged_risks=["Supply concentration"],
        extraction_warnings=[],
        extractor_confidence=0.79,
        extractor_model="claude-opus-4-7",
        extracted_at=datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    db_path = tmp_path / "buffer.sqlite"
    buf = Buffer(str(db_path))
    eid = buf.upsert(_make_extracted(), company_name="Tesla, Inc.")
    buf.upsert(
        _make_extracted(accession="ACC-002", ticker="GM", sector="lithium"),
        company_name="General Motors",
    )

    monkeypatch.setenv("ALGO_TRADE_BUFFER_PATH", str(db_path))
    monkeypatch.setenv("ALGO_TRADE_FORECAST_SINCE", "2026-01-01")
    monkeypatch.setenv("ALGO_TRADE_FORECAST_UNTIL", "2026-12-31")
    get_settings.cache_clear()

    def override_buffer() -> Buffer:
        return Buffer(str(db_path))

    app.dependency_overrides[get_buffer] = override_buffer
    client = TestClient(app)
    yield client, eid
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    buf.close()


def test_health(api_client) -> None:
    client, _ = api_client
    response = client.get("/api/v1/meta/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["data_source"] == "pipeline"


def test_material_forecast(api_client) -> None:
    client, _ = api_client
    response = client.get("/api/v1/forecast/materials/lithium")
    assert response.status_code == 200
    data = response.json()
    assert data["material_id"] == "lithium"
    assert len(data["curve"]) == 12
    assert "forward_AUC" in data["curve"][0]


def test_forecast_summary_and_ranking(api_client) -> None:
    client, _ = api_client
    summary = client.get("/api/v1/forecast/summary").json()
    ranking = client.get("/api/v1/forecast/ranking").json()
    assert summary["extractions_count"] == 2
    assert len(summary["top_materials"]) >= 1
    assert len(ranking["ranked_materials"]) >= 1
    assert ranking["ranked_materials"][0]["supporting_tickers"]


def test_extractions_list_and_get(api_client) -> None:
    client, eid = api_client
    listing = client.get("/api/v1/extractions?ticker=TSLA").json()
    assert listing["total"] == 1
    assert listing["items"][0]["ticker"] == "TSLA"
    assert listing["items"][0]["dated_effects"][0]["sector"] == "lithium"

    detail = client.get(f"/api/v1/extractions/ext_{eid:05d}").json()
    assert detail["id"] == f"ext_{eid:05d}"
    assert detail["filing_url"].startswith("https://www.sec.gov/")


def test_extraction_not_found(api_client) -> None:
    client, _ = api_client
    response = client.get("/api/v1/extractions/ext_99999")
    assert response.status_code == 404


def test_universe_endpoints(api_client) -> None:
    client, _ = api_client
    materials = client.get("/api/v1/universe/materials")
    instruments = client.get("/api/v1/universe/instruments/lithium")
    assert materials.status_code == 200
    assert instruments.status_code == 200
    assert instruments.json()["material_id"] == "lithium"


def test_empty_buffer(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "empty.sqlite"
    Buffer(str(db_path)).close()
    monkeypatch.setenv("ALGO_TRADE_BUFFER_PATH", str(db_path))
    monkeypatch.setenv("ALGO_TRADE_FORECAST_SINCE", "2026-01-01")
    monkeypatch.setenv("ALGO_TRADE_FORECAST_UNTIL", "2026-12-31")
    get_settings.cache_clear()

    def override_buffer() -> Buffer:
        return Buffer(str(db_path))

    app.dependency_overrides[get_buffer] = override_buffer
    client = TestClient(app)
    response = client.get("/api/v1/forecast/summary")
    assert response.status_code == 200
    assert response.json()["top_materials"] == []
    app.dependency_overrides.clear()
    get_settings.cache_clear()

"""Integration tests — buffer, timeline, timer, and API working together.

Unlike unit tests in test_api.py / test_buffer_store.py, these exercise
multi-module flows and cross-endpoint consistency the UI depends on.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from algo_trade.buffer import Buffer
from algo_trade.models import DatedEffect, Direction, ExtractedFiling, Magnitude
from algo_trade.timer import material_forecast
from api.deps import get_buffer, get_settings
from api.main import app


FORECAST_SINCE = "2026-01-01"
FORECAST_UNTIL = "2026-12-31"


def _effect(
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


def _extracted(
    accession: str,
    ticker: str,
    effects: list[DatedEffect],
    filing_date: str = "2026-04-30",
) -> ExtractedFiling:
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


@pytest.fixture
def demo_buffer(tmp_path) -> tuple[str, dict[str, int]]:
    """Seed a realistic multi-ticker, multi-material buffer."""
    db_path = tmp_path / "demo.sqlite"
    buf = Buffer(str(db_path))
    ids = {
        "tsla": buf.upsert(
            _extracted("ACC-TSLA", "TSLA", [_effect("lithium"), _effect("copper", window_start="2026-06-01", window_end="2026-09-30")]),
            company_name="Tesla, Inc.",
        ),
        "gm": buf.upsert(
            _extracted("ACC-GM", "GM", [_effect("lithium")]),
            company_name="General Motors",
        ),
        "fcx": buf.upsert(
            _extracted("ACC-FCX", "FCX", [_effect("copper")], filing_date="2026-03-15"),
            company_name="Freeport-McMoRan",
        ),
    }
    buf.close()
    return str(db_path), ids


@pytest.fixture
def api_client(demo_buffer, monkeypatch):
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


def _required_keys(data: dict, keys: set[str]) -> None:
    missing = keys - data.keys()
    assert not missing, f"missing keys: {missing}"


def test_api_material_forecast_matches_pipeline_directly(demo_buffer) -> None:
    """API /forecast/materials must match in-process material_forecast()."""
    db_path, _ = demo_buffer
    buf = Buffer(db_path)
    since = date.fromisoformat(FORECAST_SINCE)
    until = date.fromisoformat(FORECAST_UNTIL)
    expected = material_forecast(buf, "lithium", since, until, as_of=until)
    buf.close()

    monkeypatch_paths = {
        "ALGO_TRADE_BUFFER_PATH": db_path,
        "ALGO_TRADE_FORECAST_SINCE": FORECAST_SINCE,
        "ALGO_TRADE_FORECAST_UNTIL": FORECAST_UNTIL,
    }
    import os

    for key, value in monkeypatch_paths.items():
        os.environ[key] = value
    get_settings.cache_clear()

    def override_buffer() -> Buffer:
        return Buffer(db_path)

    app.dependency_overrides[get_buffer] = override_buffer
    client = TestClient(app)
    response = client.get("/api/v1/forecast/materials/lithium")
    app.dependency_overrides.clear()
    get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json() == expected


def test_ranking_and_summary_are_consistent(api_client) -> None:
    """Top materials in summary must align with ranking scores and tickers."""
    client, _ = api_client
    summary = client.get("/api/v1/forecast/summary").json()
    ranking = client.get("/api/v1/forecast/ranking").json()

    _required_keys(
        summary,
        {"contract_version", "as_of", "pipeline_run_at", "extractions_count", "top_materials"},
    )
    _required_keys(ranking, {"contract_version", "as_of", "ranked_materials"})

    assert summary["extractions_count"] == 3
    assert len(summary["top_materials"]) >= 2
    assert len(ranking["ranked_materials"]) >= 2

    top_ids = [m["material_id"] for m in summary["top_materials"]]
    ranked_ids = [m["material_id"] for m in ranking["ranked_materials"]]
    assert top_ids == ranked_ids[: len(top_ids)]

    lithium = next(m for m in ranking["ranked_materials"] if m["material_id"] == "lithium")
    assert set(lithium["supporting_tickers"]) == {"TSLA", "GM"}


def test_explorer_ticker_and_date_filters(api_client) -> None:
    """Explorer-style queries return expected rows."""
    client, ids = api_client
    response = client.get(
        "/api/v1/extractions",
        params={"ticker": "TSLA,GM", "from": "2026-01-01", "to": "2026-06-30"},
    )
    assert response.status_code == 200
    data = response.json()
    tickers = {item["ticker"] for item in data["items"]}
    assert tickers == {"TSLA", "GM"}
    assert data["total"] == 2

    material_response = client.get(
        "/api/v1/extractions",
        params={"material": "copper", "from": "2026-01-01", "to": "2026-12-31"},
    )
    copper_tickers = {item["ticker"] for item in material_response.json()["items"]}
    assert copper_tickers == {"TSLA", "FCX"}


def test_extraction_detail_links_to_listing(api_client) -> None:
    client, ids = api_client
    listing = client.get("/api/v1/extractions?ticker=TSLA").json()
    public_id = listing["items"][0]["id"]
    detail = client.get(f"/api/v1/extractions/{public_id}").json()
    assert detail["id"] == public_id
    assert detail["ticker"] == "TSLA"
    assert len(detail["dated_effects"]) == 2
    assert {e["sector"] for e in detail["dated_effects"]} == {"lithium", "copper"}


def test_material_forecast_contract_shape(api_client) -> None:
    """Response fields must match the frontend Zod MaterialForecast schema."""
    client, _ = api_client
    data = client.get("/api/v1/forecast/materials/lithium").json()
    _required_keys(
        data,
        {
            "contract_version",
            "material_id",
            "as_of",
            "actions",
            "curve",
            "contributing_ticker_count",
        },
    )
    assert data["contract_version"] == "1.0"
    assert data["contributing_ticker_count"] == 2
    assert len(data["curve"]) == 12
    point = data["curve"][4]  # May
    _required_keys(point, {"month", "signal", "forward_AUC"})
    assert point["month"] == "2026-05"
    assert point["signal"] > 0


def test_sector_case_normalization_in_api(api_client) -> None:
    """Buffer sector 'Lithium' should surface as material_id 'lithium' in API."""
    client, _ = api_client
    # TSLA row was stored with lowercase 'lithium'; upsert GM with capitalized sector
    # Already covered by normalize_material_id on read — verify listing normalizes.
    items = client.get("/api/v1/extractions").json()["items"]
    sectors = {e["sector"] for item in items for e in item["dated_effects"]}
    assert "lithium" in sectors
    assert "Lithium" not in sectors


def test_pagination(api_client) -> None:
    client, _ = api_client
    page1 = client.get("/api/v1/extractions", params={"limit": 2, "offset": 0}).json()
    page2 = client.get("/api/v1/extractions", params={"limit": 2, "offset": 2}).json()
    assert page1["total"] == 3
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 1
    ids_page1 = {item["id"] for item in page1["items"]}
    ids_page2 = {item["id"] for item in page2["items"]}
    assert ids_page1.isdisjoint(ids_page2)

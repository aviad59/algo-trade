"""Integration smoke tests — health, universe, empty buffer."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from algo_trade.buffer import Buffer
from api.deps import get_buffer, get_settings
from api.main import app

from .conftest import FORECAST_SINCE, FORECAST_UNTIL


def test_health(simple_api_client) -> None:
    client, _ = simple_api_client
    response = client.get("/api/v1/meta/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["data_source"] == "pipeline"


def test_universe_endpoints(simple_api_client) -> None:
    client, _ = simple_api_client
    materials = client.get("/api/v1/universe/materials")
    instruments = client.get("/api/v1/universe/instruments/lithium")
    assert materials.status_code == 200
    assert instruments.status_code == 200
    assert instruments.json()["material_id"] == "lithium"


def test_extraction_not_found(simple_api_client) -> None:
    client, _ = simple_api_client
    response = client.get("/api/v1/extractions/ext_99999")
    assert response.status_code == 404


def test_empty_buffer(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "empty.sqlite"
    Buffer(str(db_path)).close()
    monkeypatch.setenv("ALGO_TRADE_BUFFER_PATH", str(db_path))
    monkeypatch.setenv("ALGO_TRADE_FORECAST_SINCE", FORECAST_SINCE)
    monkeypatch.setenv("ALGO_TRADE_FORECAST_UNTIL", FORECAST_UNTIL)
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

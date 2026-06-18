"""Tests for user-safe API error handling."""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from algo_trade.buffer import Buffer
from api.deps import get_buffer, get_settings
from api.errors import buffer_http_exception, open_buffer
from api.main import app


def test_buffer_creates_parent_directory(tmp_path) -> None:
    db_path = tmp_path / "nested" / "dir" / "buffer.sqlite"
    buf = Buffer(str(db_path))
    try:
        assert db_path.is_file()
        assert buf.count_extractions() == 0
    finally:
        buf.close()


def test_open_buffer_maps_sqlite_errors() -> None:
    with patch("algo_trade.buffer.Buffer", side_effect=sqlite3.OperationalError("locked")):
        with pytest.raises(HTTPException) as exc_info:
            open_buffer("/tmp/test.sqlite")
    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["error"] == "buffer_unavailable"


def test_http_exception_returns_safe_json(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "api.sqlite"
    Buffer(str(db_path)).close()
    monkeypatch.setenv("ALGO_TRADE_BUFFER_PATH", str(db_path))
    get_settings.cache_clear()

    def failing_buffer() -> Buffer:
        raise buffer_http_exception()

    app.dependency_overrides[get_buffer] = failing_buffer
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/v1/forecast/summary")
    app.dependency_overrides.clear()
    get_settings.cache_clear()

    assert response.status_code == 503
    body = response.json()
    assert body["error"] == "buffer_unavailable"
    assert "algo-trade-extract" in body["message"]
    assert "buffer.sqlite" not in body["message"]


def test_api_works_when_data_directory_missing(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "fresh" / "data" / "buffer.sqlite"
    assert not db_path.parent.exists()
    monkeypatch.setenv("ALGO_TRADE_BUFFER_PATH", str(db_path))
    get_settings.cache_clear()

    def override_buffer() -> Buffer:
        return Buffer(str(db_path))

    app.dependency_overrides[get_buffer] = override_buffer
    client = TestClient(app)
    response = client.get("/api/v1/forecast/summary")
    app.dependency_overrides.clear()
    get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["top_materials"] == []
    assert db_path.is_file()

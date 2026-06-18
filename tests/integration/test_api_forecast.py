"""Integration tests — forecast, ranking, summary, recommender modes."""

from __future__ import annotations

from datetime import date

from algo_trade.buffer import Buffer
from algo_trade.timer import material_forecast
from api.deps import get_buffer, get_settings
from api.main import app
from fastapi.testclient import TestClient

from .conftest import FORECAST_SINCE, FORECAST_UNTIL, assert_required_keys


def test_material_forecast_basic(simple_api_client) -> None:
    client, _ = simple_api_client
    response = client.get("/api/v1/forecast/materials/lithium")
    assert response.status_code == 200
    data = response.json()
    assert data["material_id"] == "lithium"
    assert len(data["curve"]) == 12
    assert "forward_AUC" in data["curve"][0]


def test_forecast_summary_and_ranking_simple_buffer(simple_api_client) -> None:
    client, _ = simple_api_client
    summary = client.get("/api/v1/forecast/summary").json()
    ranking = client.get("/api/v1/forecast/ranking").json()
    assert summary["extractions_count"] == 2
    assert len(summary["top_materials"]) >= 1
    assert len(ranking["ranked_materials"]) >= 1
    assert ranking["ranked_materials"][0]["supporting_tickers"]


def test_api_material_forecast_matches_pipeline_directly(demo_buffer) -> None:
    """API /forecast/materials must match in-process material_forecast()."""
    db_path, _ = demo_buffer
    buf = Buffer(db_path)
    since = date.fromisoformat(FORECAST_SINCE)
    until = date.fromisoformat(FORECAST_UNTIL)
    expected = material_forecast(buf, "lithium", since, until, as_of=until)
    buf.close()

    import os

    for key, value in {
        "ALGO_TRADE_BUFFER_PATH": db_path,
        "ALGO_TRADE_FORECAST_SINCE": FORECAST_SINCE,
        "ALGO_TRADE_FORECAST_UNTIL": FORECAST_UNTIL,
    }.items():
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


def test_ranking_and_summary_are_consistent(demo_api_client) -> None:
    """Top materials in summary must align with ranking scores and tickers."""
    client, _ = demo_api_client
    summary = client.get("/api/v1/forecast/summary").json()
    ranking = client.get("/api/v1/forecast/ranking").json()

    assert_required_keys(
        summary,
        {"contract_version", "as_of", "pipeline_run_at", "extractions_count", "top_materials"},
    )
    assert_required_keys(ranking, {"contract_version", "as_of", "ranked_materials"})

    assert summary["extractions_count"] == 3
    assert len(summary["top_materials"]) >= 2
    assert len(ranking["ranked_materials"]) >= 2

    top_ids = [m["material_id"] for m in summary["top_materials"]]
    ranked_ids = [m["material_id"] for m in ranking["ranked_materials"]]
    assert top_ids == ranked_ids[: len(top_ids)]

    lithium = next(m for m in ranking["ranked_materials"] if m["material_id"] == "lithium")
    assert set(lithium["supporting_tickers"]) == {"TSLA", "GM"}


def test_material_forecast_contract_shape(demo_api_client) -> None:
    """Response fields must match the frontend Zod MaterialForecast schema."""
    client, _ = demo_api_client
    data = client.get("/api/v1/forecast/materials/lithium").json()
    assert_required_keys(
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
    point = data["curve"][4]
    assert_required_keys(point, {"month", "signal", "forward_AUC"})
    assert point["month"] == "2026-05"
    assert point["signal"] > 0


def test_api_recommender_mode_without_key_uses_rules(simple_api_client, monkeypatch) -> None:
    client, _ = simple_api_client
    monkeypatch.setenv("ALGO_TRADE_RANKING_MODE", "recommender")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()

    ranking = client.get("/api/v1/forecast/ranking").json()
    assert "companies cite" in ranking["ranked_materials"][0]["rationale"]


def test_api_recommender_failure_falls_back_to_rules(simple_api_client, monkeypatch) -> None:
    from algo_trade.recommender import Recommender

    client, _ = simple_api_client
    monkeypatch.setenv("ALGO_TRADE_RANKING_MODE", "recommender")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    get_settings.cache_clear()

    def boom(self, *args, **kwargs):
        raise RuntimeError("recommender unavailable")

    monkeypatch.setattr(Recommender, "rank", boom)

    ranking = client.get("/api/v1/forecast/ranking").json()
    lithium = next(m for m in ranking["ranked_materials"] if m["material_id"] == "lithium")
    assert "companies cite" in lithium["rationale"]


def test_api_recommender_mode_uses_agent_ranking(demo_api_client, monkeypatch) -> None:
    from algo_trade.models import RankedMaterials, SectorRanking
    from algo_trade.recommender import Recommender

    client, _ = demo_api_client
    monkeypatch.setenv("ALGO_TRADE_RANKING_MODE", "recommender")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    get_settings.cache_clear()

    def fake_rank(self, buf, since, until, *, as_of=None, universe_dir=None, max_extractions=100):
        return RankedMaterials(
            as_of=as_of or until,
            ranked_materials=[
                SectorRanking(
                    material_id="lithium",
                    name="Lithium",
                    score=0.95,
                    rationale="Mock recommender: TSLA and GM align on lithium.",
                    supporting_tickers=["TSLA", "GM"],
                )
            ],
            recommender_model="test-recommender-model",
        )

    monkeypatch.setattr(Recommender, "rank", fake_rank)

    ranking = client.get("/api/v1/forecast/ranking").json()
    lithium = next(m for m in ranking["ranked_materials"] if m["material_id"] == "lithium")
    assert lithium["score"] == 0.95
    assert lithium["rationale"].startswith("Mock recommender")
    assert set(lithium["supporting_tickers"]) == {"TSLA", "GM"}


def test_summary_reflects_recommender_ranking(demo_api_client, monkeypatch) -> None:
    from algo_trade.models import RankedMaterials, SectorRanking
    from algo_trade.recommender import Recommender

    client, _ = demo_api_client
    monkeypatch.setenv("ALGO_TRADE_RANKING_MODE", "recommender")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    get_settings.cache_clear()

    def fake_rank(self, buf, since, until, *, as_of=None, universe_dir=None, max_extractions=100):
        return RankedMaterials(
            as_of=as_of or until,
            ranked_materials=[
                SectorRanking(
                    material_id="copper",
                    name="Copper",
                    score=0.99,
                    rationale="Mock copper lead.",
                    supporting_tickers=["FCX"],
                ),
                SectorRanking(
                    material_id="lithium",
                    name="Lithium",
                    score=0.5,
                    rationale="Mock lithium trail.",
                    supporting_tickers=["TSLA"],
                ),
            ],
            recommender_model="test-model",
        )

    monkeypatch.setattr(Recommender, "rank", fake_rank)

    summary = client.get("/api/v1/forecast/summary").json()
    top_ids = [m["material_id"] for m in summary["top_materials"]]
    assert top_ids[0] == "copper"
    assert summary["top_materials"][0]["score"] == 0.99

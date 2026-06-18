"""Unit tests for forecast ranking service (rules vs recommender)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from algo_trade.buffer import Buffer
from algo_trade.models import DatedEffect, Direction, ExtractedFiling, Magnitude, RankedMaterials, SectorRanking
from api.deps import get_settings
from api.services.forecast import build_ranking
from tests.paths import universe_dir


def _extracted(accession: str, ticker: str) -> ExtractedFiling:
    return ExtractedFiling(
        ticker=ticker,
        cik="0001318605",
        filing_type="10-Q",
        filing_date=date(2026, 4, 30),
        accession_number=accession,
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


@pytest.fixture
def ranked_buffer(tmp_path) -> Buffer:
    buf = Buffer(str(tmp_path / "forecast.sqlite"))
    buf.upsert(_extracted("ACC-TSLA", "TSLA"), company_name="Tesla")
    buf.upsert(_extracted("ACC-GM", "GM"), company_name="GM")
    return buf


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_build_ranking_rules_mode_by_default(ranked_buffer, monkeypatch) -> None:
    monkeypatch.delenv("ALGO_TRADE_RANKING_MODE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()

    since = date(2026, 1, 1)
    until = date(2026, 12, 31)
    result = build_ranking(ranked_buffer, since, until, until, universe_dir())

    assert result["contract_version"] == "1.0"
    lithium = next(m for m in result["ranked_materials"] if m["material_id"] == "lithium")
    assert set(lithium["supporting_tickers"]) == {"GM", "TSLA"}
    assert "companies cite" in lithium["rationale"]
    ranked_buffer.close()


def test_build_ranking_recommender_mode_without_api_key_uses_rules(
    ranked_buffer, monkeypatch
) -> None:
    monkeypatch.setenv("ALGO_TRADE_RANKING_MODE", "recommender")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()

    result = build_ranking(
        ranked_buffer,
        date(2026, 1, 1),
        date(2026, 12, 31),
        date(2026, 12, 31),
        universe_dir(),
    )
    lithium = result["ranked_materials"][0]
    assert "companies cite" in lithium["rationale"]
    ranked_buffer.close()


def test_build_ranking_recommender_mode_uses_agent(ranked_buffer, monkeypatch) -> None:
    from algo_trade.recommender import Recommender

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
                    score=0.99,
                    rationale="Agent ranking.",
                    supporting_tickers=["TSLA"],
                )
            ],
            recommender_model="unit-test-model",
        )

    monkeypatch.setattr(Recommender, "rank", fake_rank)

    result = build_ranking(
        ranked_buffer,
        date(2026, 1, 1),
        date(2026, 12, 31),
        date(2026, 12, 31),
        universe_dir(),
    )
    assert result["ranked_materials"][0]["score"] == 0.99
    assert result["ranked_materials"][0]["rationale"] == "Agent ranking."
    ranked_buffer.close()


def test_build_ranking_recommender_failure_falls_back_to_rules(
    ranked_buffer, monkeypatch
) -> None:
    from algo_trade.recommender import Recommender

    monkeypatch.setenv("ALGO_TRADE_RANKING_MODE", "recommender")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    get_settings.cache_clear()

    def boom(self, *args, **kwargs):
        raise RuntimeError("recommender down")

    monkeypatch.setattr(Recommender, "rank", boom)

    result = build_ranking(
        ranked_buffer,
        date(2026, 1, 1),
        date(2026, 12, 31),
        date(2026, 12, 31),
        universe_dir(),
    )
    assert "companies cite" in result["ranked_materials"][0]["rationale"]
    ranked_buffer.close()


def test_build_ranking_recommender_empty_result_falls_back_to_rules(
    ranked_buffer, monkeypatch
) -> None:
    from algo_trade.recommender import Recommender

    monkeypatch.setenv("ALGO_TRADE_RANKING_MODE", "recommender")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    get_settings.cache_clear()

    def empty(self, buf, since, until, *, as_of=None, universe_dir=None, max_extractions=100):
        return RankedMaterials(
            as_of=as_of or until,
            ranked_materials=[],
            recommender_model="unit-test-model",
        )

    monkeypatch.setattr(Recommender, "rank", empty)

    result = build_ranking(
        ranked_buffer,
        date(2026, 1, 1),
        date(2026, 12, 31),
        date(2026, 12, 31),
        universe_dir(),
    )
    assert result["ranked_materials"]
    assert "companies cite" in result["ranked_materials"][0]["rationale"]
    ranked_buffer.close()

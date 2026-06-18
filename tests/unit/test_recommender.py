"""Unit tests for Agent #2 (the Recommender)."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from algo_trade.buffer import Buffer
from algo_trade.models import DatedEffect, Direction, ExtractedFiling, Magnitude
from tests.paths import universe_dir as _universe_dir
from algo_trade.recommender import (
    RANKING_JSON_SCHEMA,
    Recommender,
    build_ranking_context,
    _validate_rankings,
    _load_material_catalog,
)


class _FakeTextBlock:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _FakeMessage:
    def __init__(self, *, text: str, stop_reason: str = "end_turn") -> None:
        self.content = [_FakeTextBlock(text)]
        self.stop_reason = stop_reason
        self.usage = SimpleNamespace(
            input_tokens=0,
            output_tokens=0,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        )


class _FakeStream:
    def __init__(self, message: _FakeMessage) -> None:
        self._message = message

    def __enter__(self) -> "_FakeStream":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def get_final_message(self) -> _FakeMessage:
        return self._message


class _FakeMessages:
    def __init__(self, message: _FakeMessage) -> None:
        self._message = message
        self.last_kwargs: dict[str, Any] | None = None

    def stream(self, **kwargs: Any) -> _FakeStream:
        self.last_kwargs = kwargs
        return _FakeStream(self._message)


class _FakeClient:
    def __init__(self, message: _FakeMessage) -> None:
        self.messages = _FakeMessages(message)


def _repo_universe_dir() -> Path:
    return _universe_dir()


def _effect(sector: str, *, ticker_rationale: str = "demand shift") -> DatedEffect:
    return DatedEffect(
        sector=sector,
        direction=Direction.increase,
        magnitude=Magnitude.large,
        window_start=date(2026, 5, 1),
        window_end=date(2026, 8, 31),
        rationale=ticker_rationale,
        source_span="Item 2, MD&A, p.18",
    )


def _extracted(accession: str, ticker: str, effects: list[DatedEffect]) -> ExtractedFiling:
    return ExtractedFiling(
        ticker=ticker,
        cik="0001318605",
        filing_type="10-Q",
        filing_date=date(2026, 4, 30),
        accession_number=accession,
        dated_effects=effects,
        flagged_risks=[],
        extraction_warnings=[],
        extractor_confidence=0.8,
        extractor_model="claude-opus-4-7",
        extracted_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def seeded_buffer(tmp_path) -> tuple[Buffer, Path]:
    universe_dir = _repo_universe_dir()
    db_path = tmp_path / "rec.sqlite"
    buf = Buffer(str(db_path))
    buf.upsert(_extracted("ACC-TSLA", "TSLA", [_effect("lithium")]), company_name="Tesla")
    buf.upsert(_extracted("ACC-GM", "GM", [_effect("lithium")]), company_name="GM")
    return buf, universe_dir


def test_build_ranking_context_digest(seeded_buffer) -> None:
    buf, universe_dir = seeded_buffer
    since = date(2026, 1, 1)
    until = date(2026, 12, 31)
    context = build_ranking_context(buf, since, until, universe_dir=universe_dir)

    assert context["buffer_tickers"] == ["GM", "TSLA"]
    assert len(context["extractions"]) == 2
    assert context["material_vocabulary"]
    lithium_effects = [
        e
        for ext in context["extractions"]
        for e in ext["dated_effects"]
        if e["material_id"] == "lithium"
    ]
    assert len(lithium_effects) == 2
    buf.close()


def test_rank_happy_path(seeded_buffer) -> None:
    buf, universe_dir = seeded_buffer
    payload = {
        "ranked_materials": [
            {
                "material_id": "lithium",
                "score": 0.88,
                "rationale": "TSLA and GM both cite lithium increases.",
                "supporting_tickers": ["TSLA", "GM"],
                "dissenting_evidence": [],
            }
        ]
    }
    client = _FakeClient(_FakeMessage(text=json.dumps(payload)))
    recommender = Recommender(client=client, model="test-recommender-model")

    result = recommender.rank(
        buf,
        date(2026, 1, 1),
        date(2026, 12, 31),
        as_of=date(2026, 12, 31),
        universe_dir=universe_dir,
    )

    assert result.recommender_model == "test-recommender-model"
    assert len(result.ranked_materials) == 1
    ranking = result.ranked_materials[0]
    assert ranking.material_id == "lithium"
    assert ranking.name == "Lithium"
    assert ranking.score == pytest.approx(0.88)
    assert ranking.supporting_tickers == ["GM", "TSLA"]
    assert client.messages.last_kwargs is not None
    assert client.messages.last_kwargs["model"] == "test-recommender-model"
    buf.close()


def test_rank_drops_unknown_material_and_tickers(seeded_buffer) -> None:
    buf, universe_dir = seeded_buffer
    catalog = _load_material_catalog(universe_dir)
    payload = {
        "ranked_materials": [
            {
                "material_id": "unobtanium",
                "score": 0.9,
                "rationale": "Should be dropped.",
                "supporting_tickers": ["TSLA"],
                "dissenting_evidence": [],
            },
            {
                "material_id": "lithium",
                "score": 0.7,
                "rationale": "Only TSLA is valid.",
                "supporting_tickers": ["TSLA", "FAKE"],
                "dissenting_evidence": [],
            },
        ]
    }
    warnings: list[str] = []
    validated = _validate_rankings(
        payload["ranked_materials"],
        catalog=catalog,
        allowed_tickers={"TSLA", "GM"},
        warnings=warnings,
    )
    assert len(validated) == 1
    assert validated[0].material_id == "lithium"
    assert validated[0].supporting_tickers == ["TSLA"]
    assert any("unknown material_id" in w for w in warnings)
    assert any("dropped unknown tickers" in w for w in warnings)
    buf.close()


def test_rank_empty_buffer_returns_empty_ranking(tmp_path) -> None:
    buf = Buffer(str(tmp_path / "empty.sqlite"))
    client = _FakeClient(_FakeMessage(text='{"ranked_materials": []}'))
    recommender = Recommender(client=client, model="test-model")

    result = recommender.rank(
        buf,
        date(2026, 1, 1),
        date(2026, 12, 31),
        universe_dir=_repo_universe_dir(),
    )

    assert result.ranked_materials == []
    assert client.messages.last_kwargs is None
    buf.close()


def test_build_ranking_context_normalizes_sector_aliases(tmp_path) -> None:
    universe_dir = _repo_universe_dir()
    buf = Buffer(str(tmp_path / "alias.sqlite"))
    buf.upsert(
        _extracted("ACC-TSLA", "TSLA", [_effect("Lithium")]),
        company_name="Tesla",
    )
    context = build_ranking_context(
        buf,
        date(2026, 1, 1),
        date(2026, 12, 31),
        universe_dir=universe_dir,
    )
    material_ids = {
        e["material_id"]
        for ext in context["extractions"]
        for e in ext["dated_effects"]
    }
    assert material_ids == {"lithium"}
    buf.close()


def test_rank_sorts_results_by_score_descending(seeded_buffer) -> None:
    buf, universe_dir = seeded_buffer
    payload = {
        "ranked_materials": [
            {
                "material_id": "lithium",
                "score": 0.4,
                "rationale": "Lower score.",
                "supporting_tickers": ["TSLA"],
                "dissenting_evidence": [],
            },
            {
                "material_id": "copper",
                "score": 0.9,
                "rationale": "Higher score.",
                "supporting_tickers": ["TSLA"],
                "dissenting_evidence": [],
            },
        ]
    }
    # Add copper effect so TSLA can support copper ranking
    buf.upsert(
        _extracted("ACC-TSLA-CU", "TSLA", [_effect("copper")]),
        company_name="Tesla",
    )
    client = _FakeClient(_FakeMessage(text=json.dumps(payload)))
    recommender = Recommender(client=client, model="test-model")

    result = recommender.rank(
        buf,
        date(2026, 1, 1),
        date(2026, 12, 31),
        universe_dir=universe_dir,
    )
    scores = [r.score for r in result.ranked_materials]
    assert scores == sorted(scores, reverse=True)
    buf.close()


def test_rank_refusal_raises(seeded_buffer) -> None:
    buf, universe_dir = seeded_buffer
    message = _FakeMessage(text="{}", stop_reason="refusal")
    client = _FakeClient(message)
    recommender = Recommender(client=client, model="test-model")

    with pytest.raises(RuntimeError, match="refusal"):
        recommender.rank(
            buf,
            date(2026, 1, 1),
            date(2026, 12, 31),
            universe_dir=universe_dir,
        )
    buf.close()


def test_validate_rankings_clamps_score_and_drops_bad_rows(seeded_buffer) -> None:
    buf, universe_dir = seeded_buffer
    catalog = _load_material_catalog(universe_dir)
    warnings: list[str] = []
    validated = _validate_rankings(
        [
            {
                "material_id": "lithium",
                "score": 1.5,
                "rationale": "Clamped score.",
                "supporting_tickers": ["TSLA"],
                "dissenting_evidence": [],
            },
            {
                "material_id": "lithium",
                "score": 0.5,
                "rationale": "",
                "supporting_tickers": ["TSLA"],
                "dissenting_evidence": [],
            },
            {
                "material_id": "lithium",
                "score": 0.5,
                "rationale": "No tickers.",
                "supporting_tickers": [],
                "dissenting_evidence": [],
            },
        ],
        catalog=catalog,
        allowed_tickers={"TSLA", "GM"},
        warnings=warnings,
    )
    assert len(validated) == 1
    assert validated[0].score == pytest.approx(1.0)
    assert any("empty rationale" in w for w in warnings)
    assert any("no valid supporting_tickers" in w for w in warnings)
    buf.close()


def test_recommender_uses_json_schema(seeded_buffer) -> None:
    buf, universe_dir = seeded_buffer
    client = _FakeClient(
        _FakeMessage(
            text=json.dumps(
                {
                    "ranked_materials": [
                        {
                            "material_id": "lithium",
                            "score": 0.5,
                            "rationale": "ok",
                            "supporting_tickers": ["TSLA"],
                            "dissenting_evidence": [],
                        }
                    ]
                }
            )
        )
    )
    recommender = Recommender(client=client, model="test-model")
    recommender.rank(buf, date(2026, 1, 1), date(2026, 12, 31), universe_dir=universe_dir)
    assert client.messages.last_kwargs is not None
    schema = client.messages.last_kwargs["output_config"]["format"]["schema"]
    assert schema is RANKING_JSON_SCHEMA
    buf.close()

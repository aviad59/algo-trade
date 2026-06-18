"""Unit tests for Agent #1 (the Extractor).

We never call the Anthropic API here. Each test injects a fake client into
the Extractor; the fake mimics the surface area we actually use:

    client.messages.stream(...)
        -> context manager yielding an object with .get_final_message()
        -> Message with .content, .stop_reason, .usage

The goal is to exercise prompt assembly, response parsing, and the
defensive validation layer (bad date order -> drop with warning, bad
stop_reason -> raise, etc.) without going anywhere near the network.
"""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest

from algo_trade.extractor import (
    EXTRACTION_JSON_SCHEMA,
    Extractor,
    _build_user_prompt,
    _parse_extraction,
)
from algo_trade.models import DatedEffect, Direction, FetchedFiling, Magnitude


# --------------------------------------------------------------------------- #
# Fakes for the Anthropic streaming surface
# --------------------------------------------------------------------------- #


class _FakeTextBlock:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _FakeMessage:
    def __init__(
        self,
        *,
        text: str,
        stop_reason: str = "end_turn",
        usage: Any | None = None,
        stop_details: Any | None = None,
    ) -> None:
        self.content = [_FakeTextBlock(text)]
        self.stop_reason = stop_reason
        self.usage = usage or SimpleNamespace(
            input_tokens=0,
            output_tokens=0,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        )
        self.stop_details = stop_details


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


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _fetched_tsla_10q() -> FetchedFiling:
    return FetchedFiling(
        ticker="TSLA",
        cik="0001318605",
        company_name="TESLA INC",
        form="10-Q",
        filing_date=date(2026, 4, 30),
        accession_number="0001628280-26-005001",
        sections={
            "mda": "We plan to ramp lithium consumption in May for the Nevada cell line.",
            "risk_factors": "Lithium supply is concentrated in Chile and Australia.",
        },
    )


def _valid_llm_payload() -> dict[str, Any]:
    return {
        "dated_effects": [
            {
                "sector": "Lithium",
                "direction": "increase",
                "magnitude": "large",
                "window_start": "2026-05-01",
                "window_end": "2026-08-31",
                "rationale": "Cell line ramp at Nevada gigafactory begins May.",
                "source_span": "Item 2, MD&A, p.18",
            },
            {
                "sector": "Gold",
                "direction": "decrease",
                "magnitude": "moderate",
                "window_start": "2026-03-01",
                "window_end": "2026-06-30",
                "rationale": "Phasing out gold-plated connector SKU.",
                "source_span": "Item 1A, Risk Factors, p.42",
            },
        ],
        "flagged_risks": ["Lithium supply concentration in Chile/Australia"],
        "extractor_confidence": 0.79,
    }


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #


def test_extract_happy_path_returns_extracted_filing():
    fetched = _fetched_tsla_10q()
    payload = _valid_llm_payload()

    message = _FakeMessage(
        text=json.dumps(payload),
        usage=SimpleNamespace(
            input_tokens=1000,
            output_tokens=500,
            cache_read_input_tokens=4096,
            cache_creation_input_tokens=0,
        ),
    )
    client = _FakeClient(message)

    extractor = Extractor(client=client, model="claude-opus-4-7")
    result = extractor.extract(fetched)

    # Metadata copied from the FetchedFiling
    assert result.ticker == "TSLA"
    assert result.cik == "0001318605"
    assert result.filing_type == "10-Q"
    assert result.filing_date == date(2026, 4, 30)
    assert result.accession_number == "0001628280-26-005001"
    assert result.extractor_model == "claude-opus-4-7"

    # LLM output flowed through validation
    assert len(result.dated_effects) == 2
    lithium = result.dated_effects[0]
    assert lithium.sector == "Lithium"
    assert lithium.direction is Direction.increase
    assert lithium.magnitude is Magnitude.large
    assert lithium.window_start == date(2026, 5, 1)
    assert lithium.window_end == date(2026, 8, 31)
    assert "Nevada" in lithium.rationale
    assert lithium.source_span.startswith("Item 2")

    assert result.flagged_risks == ["Lithium supply concentration in Chile/Australia"]
    assert result.extractor_confidence == pytest.approx(0.79)
    assert result.extraction_warnings == []

    # Cache counters surfaced
    assert result.cache_read_input_tokens == 4096
    assert result.cache_creation_input_tokens == 0


def test_extract_passes_correct_args_to_client():
    fetched = _fetched_tsla_10q()
    message = _FakeMessage(text=json.dumps(_valid_llm_payload()))
    client = _FakeClient(message)

    Extractor(client=client).extract(fetched)

    kwargs = client.messages.last_kwargs
    assert kwargs is not None

    # Default model is Opus 4.7 per the API skill's mandatory default.
    assert kwargs["model"] == "claude-opus-4-7"

    # Adaptive thinking + effort=high for intelligence-sensitive work.
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["output_config"]["effort"] == "high"

    # Structured outputs schema is exactly the one we exported.
    assert kwargs["output_config"]["format"]["type"] == "json_schema"
    assert kwargs["output_config"]["format"]["schema"] is EXTRACTION_JSON_SCHEMA

    # System prompt is cached for cross-filing reuse.
    system = kwargs["system"]
    assert isinstance(system, list) and len(system) == 1
    assert system[0]["cache_control"] == {"type": "ephemeral"}

    # User content carries the filing date as anchor + the section text.
    user_text = kwargs["messages"][0]["content"]
    assert "2026-04-30" in user_text
    assert "TSLA" in user_text
    assert "Nevada cell line" in user_text
    assert "Chile" in user_text


# --------------------------------------------------------------------------- #
# Validation: bad effects are dropped, not raised
# --------------------------------------------------------------------------- #


def test_effect_with_inverted_window_is_dropped_with_warning():
    fetched = _fetched_tsla_10q()
    payload = _valid_llm_payload()
    payload["dated_effects"].append(
        {
            "sector": "Copper",
            "direction": "increase",
            "magnitude": "small",
            "window_start": "2026-07-01",
            "window_end": "2026-06-01",  # inverted
            "rationale": "Copper demand uptick.",
            "source_span": "Item 7, MD&A, p.51",
        }
    )

    client = _FakeClient(_FakeMessage(text=json.dumps(payload)))
    result = Extractor(client=client).extract(fetched)

    sectors = [e.sector for e in result.dated_effects]
    assert "Copper" not in sectors
    assert len(result.dated_effects) == 2
    assert any("Copper" in w or "dated_effects[2]" in w for w in result.extraction_warnings)


def test_effect_with_invalid_enum_is_dropped_with_warning():
    fetched = _fetched_tsla_10q()
    payload = _valid_llm_payload()
    payload["dated_effects"].append(
        {
            "sector": "Tin",
            "direction": "stable",  # not in enum
            "magnitude": "moderate",
            "window_start": "2026-08-01",
            "window_end": "2026-12-01",
            "rationale": "Tin demand holds steady.",
            "source_span": "Item 7, MD&A, p.60",
        }
    )

    client = _FakeClient(_FakeMessage(text=json.dumps(payload)))
    result = Extractor(client=client).extract(fetched)

    assert "Tin" not in [e.sector for e in result.dated_effects]
    assert any("dated_effects[2]" in w or "Tin" in w for w in result.extraction_warnings)


def test_confidence_outside_unit_interval_is_clamped():
    payload = {
        "dated_effects": [],
        "flagged_risks": [],
        "extractor_confidence": 1.7,
    }
    result = _parse_extraction(json.dumps(payload), warnings=[])
    assert result.extractor_confidence == 1.0


def test_non_numeric_confidence_is_coerced_to_zero_with_warning():
    warnings: list[str] = []
    payload = {
        "dated_effects": [],
        "flagged_risks": [],
        "extractor_confidence": "high",
    }
    result = _parse_extraction(json.dumps(payload), warnings=warnings)
    assert result.extractor_confidence == 0.0
    assert any("extractor_confidence" in w for w in warnings)


def test_flagged_risks_non_list_is_coerced_with_warning():
    warnings: list[str] = []
    payload = {
        "dated_effects": [],
        "flagged_risks": "this should have been an array",
        "extractor_confidence": 0.5,
    }
    result = _parse_extraction(json.dumps(payload), warnings=warnings)
    assert result.flagged_risks == []
    assert any("flagged_risks" in w for w in warnings)


# --------------------------------------------------------------------------- #
# Stop-reason handling (Claude 4.5+ can emit these)
# --------------------------------------------------------------------------- #


def test_refusal_raises():
    fetched = _fetched_tsla_10q()
    message = _FakeMessage(
        text=json.dumps(_valid_llm_payload()),
        stop_reason="refusal",
        stop_details=SimpleNamespace(explanation="policy"),
    )
    client = _FakeClient(message)

    with pytest.raises(RuntimeError, match="refused"):
        Extractor(client=client).extract(fetched)


def test_context_window_exceeded_raises():
    fetched = _fetched_tsla_10q()
    message = _FakeMessage(
        text=json.dumps(_valid_llm_payload()),
        stop_reason="model_context_window_exceeded",
    )
    client = _FakeClient(message)

    with pytest.raises(RuntimeError, match="context window"):
        Extractor(client=client).extract(fetched)


def test_max_tokens_records_warning_but_does_not_raise():
    fetched = _fetched_tsla_10q()
    message = _FakeMessage(
        text=json.dumps(_valid_llm_payload()),
        stop_reason="max_tokens",
    )
    client = _FakeClient(message)

    result = Extractor(client=client).extract(fetched)
    assert any("max_tokens" in w for w in result.extraction_warnings)


# --------------------------------------------------------------------------- #
# Prompt assembly
# --------------------------------------------------------------------------- #


def test_user_prompt_includes_mda_and_risk_factors_when_present():
    fetched = _fetched_tsla_10q()
    prompt = _build_user_prompt(fetched)
    assert "MD&A" in prompt
    assert "Risk Factors" in prompt
    assert "Full filing text" not in prompt


def test_user_prompt_falls_back_to_full_text_when_typed_sections_missing():
    fetched = FetchedFiling(
        ticker="NVDA",
        cik="0001045810",
        company_name="NVIDIA CORP",
        form="8-K",
        filing_date=date(2026, 1, 15),
        accession_number="0000950170-26-000001",
        sections={"full_text": "8-K body about a new data center deal."},
    )
    prompt = _build_user_prompt(fetched)
    assert "Full filing text" in prompt
    assert "MD&A" not in prompt
    assert "Risk Factors" not in prompt
    assert "data center deal" in prompt


def test_user_prompt_raises_when_no_sections_present():
    fetched = FetchedFiling(
        ticker="NVDA",
        cik="0001045810",
        company_name="NVIDIA CORP",
        form="10-K",
        filing_date=date(2026, 2, 21),
        accession_number="0000950170-26-001234",
        sections={},  # nothing extracted upstream
    )
    with pytest.raises(ValueError, match="no extractable sections"):
        _build_user_prompt(fetched)


# --------------------------------------------------------------------------- #
# Round-trip serialization
# --------------------------------------------------------------------------- #


def test_extracted_filing_round_trips_through_json():
    fetched = _fetched_tsla_10q()
    payload = _valid_llm_payload()
    client = _FakeClient(_FakeMessage(text=json.dumps(payload)))

    result = Extractor(client=client).extract(fetched)
    raw = result.model_dump_json()

    from algo_trade.models import ExtractedFiling
    restored = ExtractedFiling.model_validate_json(raw)
    assert restored.ticker == result.ticker
    assert len(restored.dated_effects) == len(result.dated_effects)
    assert restored.dated_effects[0].direction is Direction.increase


def test_extractor_reads_model_and_tuning_from_env(monkeypatch):
    fetched = _fetched_tsla_10q()
    message = _FakeMessage(text=json.dumps(_valid_llm_payload()))
    client = _FakeClient(message)

    monkeypatch.setenv("ALGO_TRADE_EXTRACTOR_MODEL", "env-extractor-model")
    monkeypatch.setenv("ALGO_TRADE_EXTRACTOR_MAX_TOKENS", "12000")
    monkeypatch.setenv("ALGO_TRADE_EXTRACTOR_EFFORT", "medium")

    extractor = Extractor(client=client)
    extractor.extract(fetched)

    kwargs = client.messages.last_kwargs
    assert kwargs is not None
    assert kwargs["model"] == "env-extractor-model"
    assert kwargs["max_tokens"] == 12000
    assert kwargs["output_config"]["effort"] == "medium"

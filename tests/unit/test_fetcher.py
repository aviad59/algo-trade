"""Unit tests for the EDGAR fetcher.

We never hit EDGAR here. Every test feeds the section-extraction helpers a
fake Filing object that mimics the surface area we use from edgartools:
  .form, .filing_date, .accession_number, .cik, .company
  .obj() -> typed object with .mda / .risk_factors
  .text() -> full-text fallback
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from algo_trade.fetcher import Fetcher, _attr_text, _to_date, _to_fetched
from algo_trade.models import FetchedFiling


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #


class _MdaWithText:
    """Mimics an edgartools section object whose text is behind .text()."""

    def text(self) -> str:
        return "We plan to ramp lithium consumption in May 2026."


class _FakeTenK:
    mda = _MdaWithText()
    risk_factors = "Supply concentration in Chile and Australia."


class _FakeFiling:
    form = "10-K"
    filing_date = date(2026, 2, 21)
    accession_number = "0000950170-26-001234"
    cik = "1045810"
    company = "NVIDIA CORP"

    def obj(self) -> _FakeTenK:
        return _FakeTenK()

    def text(self) -> str:
        return "FULL TEXT FALLBACK"


# --------------------------------------------------------------------------- #
# _to_fetched
# --------------------------------------------------------------------------- #


def test_extracts_mda_and_risk_factors_from_10k():
    fetched = _to_fetched("nvda", _FakeFiling())

    assert isinstance(fetched, FetchedFiling)
    assert fetched.ticker == "nvda"
    assert fetched.form == "10-K"
    assert fetched.filing_date == date(2026, 2, 21)
    assert fetched.accession_number == "0000950170-26-001234"
    assert fetched.cik == "0000001045810".lstrip("0").zfill(10)
    assert fetched.company_name == "NVIDIA CORP"

    assert "lithium" in fetched.sections["mda"].lower()
    assert "chile" in fetched.sections["risk_factors"].lower()
    assert "full_text" not in fetched.sections
    assert fetched.extraction_warnings == []


def test_falls_back_to_full_text_when_obj_raises():
    class _Broken(_FakeFiling):
        def obj(self):
            raise RuntimeError("typed parse failed")

    fetched = _to_fetched("NVDA", _Broken())

    assert fetched.sections == {"full_text": "FULL TEXT FALLBACK"}
    assert any("obj()" in w for w in fetched.extraction_warnings)


def test_8k_skips_typed_extraction_and_uses_full_text():
    class _EightK(_FakeFiling):
        form = "8-K"

    fetched = _to_fetched("NVDA", _EightK())

    assert fetched.form == "8-K"
    assert fetched.sections == {"full_text": "FULL TEXT FALLBACK"}
    # No warning expected -- we never tried typed extraction.
    assert fetched.extraction_warnings == []


def test_warns_when_individual_sections_are_missing():
    class _TenKNoRisk:
        mda = "MD&A body"
        risk_factors = None  # missing

    class _Filing(_FakeFiling):
        def obj(self):
            return _TenKNoRisk()

    fetched = _to_fetched("NVDA", _Filing())

    assert fetched.sections == {"mda": "MD&A body"}
    assert any("risk_factors" in w for w in fetched.extraction_warnings)


def test_empty_mda_string_is_treated_as_missing():
    class _TenKBlank:
        mda = "   "
        risk_factors = "real risk text"

    class _Filing(_FakeFiling):
        def obj(self):
            return _TenKBlank()

    fetched = _to_fetched("NVDA", _Filing())

    assert "mda" not in fetched.sections
    assert fetched.sections["risk_factors"] == "real risk text"
    assert any("mda" in w for w in fetched.extraction_warnings)


def test_serializes_round_trip_through_json():
    fetched = _to_fetched("NVDA", _FakeFiling())
    raw = fetched.model_dump_json()
    restored = FetchedFiling.model_validate_json(raw)
    assert restored == fetched


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def test_attr_text_handles_string():
    class O:
        x = "hello"
    assert _attr_text(O(), "x") == "hello"


def test_attr_text_handles_object_with_text_method():
    class O:
        class _S:
            def text(self):
                return "body"
        x = _S()
    assert _attr_text(O(), "x") == "body"


def test_attr_text_returns_none_for_missing_attr():
    assert _attr_text(object(), "nope") is None


def test_attr_text_returns_none_for_blank_string():
    class O:
        x = "   "
    assert _attr_text(O(), "x") is None


def test_to_date_accepts_date_datetime_and_iso_string():
    assert _to_date(date(2026, 1, 2)) == date(2026, 1, 2)
    assert _to_date(datetime(2026, 1, 2, 15, 30)) == date(2026, 1, 2)
    assert _to_date("2026-01-02") == date(2026, 1, 2)
    assert _to_date("2026-01-02T00:00:00") == date(2026, 1, 2)


def test_to_date_rejects_unknown_types():
    with pytest.raises(TypeError):
        _to_date(12345)


# --------------------------------------------------------------------------- #
# Fetcher construction
# --------------------------------------------------------------------------- #


def test_identity_validation_rejects_bad_strings(monkeypatch):
    # set_identity should not be called when validation fails -- guard it.
    called = []
    monkeypatch.setattr(
        "algo_trade.fetcher.set_identity",
        lambda s: called.append(s),
    )
    with pytest.raises(ValueError):
        Fetcher(identity="not an email")
    assert called == []


def test_identity_validation_accepts_email_form(monkeypatch):
    seen = []
    monkeypatch.setattr(
        "algo_trade.fetcher.set_identity",
        lambda s: seen.append(s),
    )
    Fetcher(identity="Jane Doe jane@example.com")
    assert seen == ["Jane Doe jane@example.com"]

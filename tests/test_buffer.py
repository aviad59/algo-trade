from datetime import date

from filingsignal.buffer import Buffer
from filingsignal.models import (
    DatedEffect, Direction, ExtractedFiling, Magnitude, Perspective,
)


def _ext(model="m1", conf=0.9):
    return ExtractedFiling(
        ticker="FCX", cik="0000831259", filing_type="8-K", filing_date=date(2026, 6, 23),
        accession_number="acc-1", summary="s",
        dated_effects=[DatedEffect(material="Copper", perspective=Perspective.producer,
                                   direction=Direction.increase, magnitude=Magnitude.large,
                                   window_start=date(2026, 7, 1), window_end=date(2026, 9, 30),
                                   rationale="r", evidence_quote="q")],
        extractor_confidence=conf, extractor_model=model, extraction_warnings=["w1"])


def test_upsert_idempotent_on_accession_model():
    with Buffer(":memory:") as b:
        assert b.has_extraction("acc-1", "m1") is False
        b.upsert(_ext())
        assert b.has_extraction("acc-1", "m1") is True
        b.upsert(_ext())  # same accession+model -> upsert, not duplicate
        assert b.count_extractions() == 1
        assert len(b.effects()) == 1


def test_different_model_kept_side_by_side():
    with Buffer(":memory:") as b:
        b.upsert(_ext(model="m1"))
        b.upsert(_ext(model="m2"))
        assert b.count_extractions() == 2
        # default (model=None) dedupes to latest per accession
        assert len(b.effects()) == 1


def test_effects_and_filings_round_trip():
    with Buffer(":memory:") as b:
        b.upsert(_ext(), company_name="Freeport")
        e = b.effects()[0]
        assert e.material == "Copper" and e.perspective is Perspective.producer
        assert e.confidence == 0.9
        fr = b.get_filing("acc-1")
        assert fr.summary == "s" and fr.warnings == ["w1"] and len(fr.effects) == 1


def test_ratings():
    with Buffer(":memory:") as b:
        b.upsert_rating(material="Copper", quarter="2026 Q3", prose="p",
                        supporting={"t": ["FCX"]}, model="m")
        r = b.get_rating("copper")
        assert r["prose"] == "p" and r["supporting"]["t"] == ["FCX"]

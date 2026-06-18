"""Pydantic models flowing between pipeline stages.

`FetchedFiling` is the unit that flows from the fetcher into Agent #1
(the extractor). `ExtractedFiling` is what Agent #1 emits -- the unit
that flows from the extractor into the buffer, and from the buffer into
the sector timeline aggregator and Agent #2 (the recommender).

Keeping these strict and serializable means we can persist either
stage to JSONL, replay them offline, and unit-test downstream agents
without ever touching EDGAR or calling an LLM.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class FetchedFiling(BaseModel):
    """A single SEC filing after fetch + section extraction."""

    ticker: str
    cik: str
    company_name: str
    form: str
    filing_date: date
    accession_number: str

    # Section name -> clean text. Conventional keys:
    #   "mda"           Management's Discussion & Analysis (Item 7 in 10-K)
    #   "risk_factors"  Risk Factors (Item 1A in 10-K)
    #   "full_text"     Fallback when typed extraction isn't available (8-K,
    #                   or 10-K/10-Q where edgartools couldn't parse sections)
    sections: dict[str, str] = Field(default_factory=dict)

    # Anything we couldn't extract is recorded here so failures stay visible.
    # The extractor agent can decide whether to trust the filing or skip it.
    extraction_warnings: list[str] = Field(default_factory=list)

    def section(self, name: str) -> Optional[str]:
        return self.sections.get(name)

    @property
    def total_text_length(self) -> int:
        return sum(len(v) for v in self.sections.values())


# --------------------------------------------------------------------------- #
# Extractor output -- the dated sector signals Agent #1 emits per filing.
# --------------------------------------------------------------------------- #


class Direction(str, Enum):
    """Whether the company's planned action lifts or reduces sector exposure."""

    increase = "increase"
    decrease = "decrease"


class Magnitude(str, Enum):
    """Qualitative size of the effect.

    We deliberately do not extract dollar amounts. Filings rarely commit
    to precise numbers, and inventing them would corrupt the timeline.
    The aggregator converts these to numeric weights (e.g. 0.3 / 0.6 / 1.0)
    when it builds the per-sector curve.
    """

    small = "small"
    moderate = "moderate"
    large = "large"


class DatedEffect(BaseModel):
    """One time-windowed sector signal extracted from a filing."""

    sector: str
    direction: Direction
    magnitude: Magnitude
    window_start: date
    window_end: date
    rationale: str
    source_span: str

    @model_validator(mode="after")
    def _check_window_order(self) -> "DatedEffect":
        if self.window_end < self.window_start:
            raise ValueError(
                f"window_end ({self.window_end}) precedes window_start "
                f"({self.window_start}) for sector {self.sector!r}"
            )
        return self


class ExtractedFiling(BaseModel):
    """Agent #1's structured output for a single filing.

    Metadata fields (`ticker`, `cik`, `filing_type`, `filing_date`,
    `accession_number`) come from the upstream FetchedFiling and are not
    decided by the LLM. The rest is the LLM's output, schema-enforced.
    """

    ticker: str
    cik: str
    filing_type: str
    filing_date: date
    accession_number: str

    dated_effects: list[DatedEffect] = Field(default_factory=list)
    flagged_risks: list[str] = Field(default_factory=list)
    extractor_confidence: float

    extractor_model: str
    extracted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Anything the extractor dropped (e.g. effects with bad date ranges)
    # is recorded so failures stay visible.
    extraction_warnings: list[str] = Field(default_factory=list)

    # Surface cache hit/write counters so callers can verify prompt
    # caching is working. Zeroed when not available.
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


# --------------------------------------------------------------------------- #
# Timer output -- buy/sell signals and curve points for the web forecast API.
# --------------------------------------------------------------------------- #


class TimerAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class TimerSignal(BaseModel):
    """One BUY or SELL action emitted by the timer."""

    date: date
    action: TimerAction
    rationale: str


class CurvePoint(BaseModel):
    """One month on a material forecast curve (matches mock ISOMonth + signal)."""

    month: str
    signal: float
    forward_auc: float


# --------------------------------------------------------------------------- #
# Recommender output -- ranked materials Agent #2 emits from the buffer.
# --------------------------------------------------------------------------- #


class SectorRanking(BaseModel):
    """One ranked material in Agent #2's output."""

    material_id: str
    name: str
    score: float = Field(ge=0.0, le=1.0)
    rationale: str
    supporting_tickers: list[str]
    dissenting_evidence: list[str] = Field(default_factory=list)


class RankedMaterials(BaseModel):
    """Agent #2's structured ranking over a date-bounded buffer slice."""

    as_of: date
    ranked_materials: list[SectorRanking]
    recommender_model: str
    recommended_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

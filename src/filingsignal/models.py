"""Pydantic contracts flowing between pipeline stages.

`FetchedFiling` (fetcher → filters → extractor) and `ExtractedFiling`
(extractor → buffer → scorer/rating). Extended from the predecessor:
`DatedEffect` now carries `material` (was `sector`), a `perspective` tag, and a
verbatim `evidence_quote`; `ExtractedFiling` carries a human-readable `summary`
and a provider-neutral `usage` block (was Anthropic-specific cache fields).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


# --------------------------------------------------------------------------- #
# Fetcher output
# --------------------------------------------------------------------------- #


class FetchedFiling(BaseModel):
    """A single SEC filing after fetch + section targeting."""

    ticker: str
    cik: str
    company_name: str
    form: str
    filing_date: date
    accession_number: str

    # Section name -> clean text. Conventional keys: "mda", "risk_factors",
    # "exhibit" (8-K/6-K press release), "full_text" (fallback).
    sections: dict[str, str] = Field(default_factory=dict)

    # 8-K / 6-K item numbers (e.g. ["1.01", "8.01"]); empty for periodic forms.
    items: list[str] = Field(default_factory=list)

    # Anything the fetcher couldn't cleanly extract (e.g. a section-isolation
    # fallback). Flows downstream so failures stay visible — never silent.
    extraction_warnings: list[str] = Field(default_factory=list)

    def section(self, name: str) -> Optional[str]:
        return self.sections.get(name)

    @property
    def total_text_length(self) -> int:
        return sum(len(v) for v in self.sections.values())


# --------------------------------------------------------------------------- #
# Extractor output (Agent #1)
# --------------------------------------------------------------------------- #


class Direction(str, Enum):
    increase = "increase"
    decrease = "decrease"


class Magnitude(str, Enum):
    small = "small"
    moderate = "moderate"
    large = "large"


class Perspective(str, Enum):
    """Whether the filing company produces (supply) or consumes (demand) the
    material. Inferred per-effect from context — the same company can produce
    one material and consume another. At the miner-ETF target both an
    ``increase`` from either perspective is bullish, but they are scored
    separately so their predictive value can be measured (ARCHITECTURE §5/§7)."""

    producer = "producer"
    consumer = "consumer"


class DatedEffect(BaseModel):
    """One time-windowed, cited material signal extracted from a filing."""

    material: str
    perspective: Perspective
    direction: Direction
    magnitude: Magnitude
    window_start: date
    window_end: date
    rationale: str          # paraphrase
    evidence_quote: str     # verbatim filing text (non-empty)
    source_span: str = ""   # locator (item/section)

    @model_validator(mode="after")
    def _check(self) -> "DatedEffect":
        if self.window_end < self.window_start:
            raise ValueError(
                f"window_end ({self.window_end}) precedes window_start "
                f"({self.window_start}) for material {self.material!r}"
            )
        if not self.evidence_quote.strip():
            raise ValueError(f"empty evidence_quote for material {self.material!r}")
        return self


class Usage(BaseModel):
    """Provider-neutral token accounting (populated by whichever LLM adapter)."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class ExtractedFiling(BaseModel):
    """Agent #1's structured output for one filing.

    Metadata (`ticker`, `cik`, `filing_type`, `filing_date`, `accession_number`)
    comes from the upstream FetchedFiling; the rest is the LLM's output.
    """

    ticker: str
    cik: str
    filing_type: str
    filing_date: date
    accession_number: str

    summary: str = ""
    dated_effects: list[DatedEffect] = Field(default_factory=list)
    extractor_confidence: float

    extractor_model: str
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    extraction_warnings: list[str] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)

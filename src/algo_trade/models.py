"""Pydantic models for the fetcher's output.

`FetchedFiling` is the unit that flows from the fetcher into Agent #1
(the extractor). Keeping it strict and serializable means we can persist
fetches to JSONL, replay them offline, and unit-test downstream agents
without ever touching EDGAR.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


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

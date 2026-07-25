"""Cheap, pre-LLM filing filters. Run between fetch and extract so no tokens are
spent on routine events or material-irrelevant filings. Composes with the
extractor's incremental DB skip.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..models import FetchedFiling
from ..universe import Universe, load_universe
from .prompts import FormClass, form_class


@dataclass(frozen=True)
class FilterDecision:
    keep: bool
    reason: str


def item_filter(fetched: FetchedFiling, uni: Universe) -> FilterDecision:
    """8-K/6-K item allow/deny. Periodic forms pass through."""
    if form_class(fetched.form) is not FormClass.EVENT:
        return FilterDecision(True, "periodic form")
    items = set(fetched.items)
    if not items:
        return FilterDecision(True, "no item metadata; keep")
    keep, drop = uni.event_items_keep(), uni.event_items_drop()
    if items & keep:
        return FilterDecision(True, f"kept item(s) {sorted(items & keep)}")
    if items <= drop:
        return FilterDecision(False, f"routine items {sorted(items)}")
    return FilterDecision(False, f"no material-relevant item in {sorted(items)}")


def keyword_gate(fetched: FetchedFiling, uni: Universe) -> FilterDecision:
    """Skip filings whose text contains no tracked-material keyword."""
    if not uni.keyword_gate_enabled():
        return FilterDecision(True, "keyword gate disabled")
    text = " ".join(fetched.sections.values()).lower()
    for kw in uni.all_keywords():
        if kw in text:
            return FilterDecision(True, f"keyword '{kw}'")
    return FilterDecision(False, "no tracked-material keyword present")


def should_extract(fetched: FetchedFiling, uni: Optional[Universe] = None) -> FilterDecision:
    uni = uni or load_universe()
    d = item_filter(fetched, uni)
    if not d.keep:
        return d
    return keyword_gate(fetched, uni)

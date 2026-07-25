"""Filing-specific extraction prompts.

One prompt per form class — an 8-K event release is read differently from a
10-Q update or a 40-F annual. A shared CORE carries the invariant rules
(schema, perspective tag, verbatim evidence, canonical vocab, window
discipline); a per-class overlay says *where to look* and *what counts*.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from ..models import FetchedFiling


class FormClass(str, Enum):
    ANNUAL = "annual"      # 10-K, 40-F, 20-F
    INTERIM = "interim"    # 10-Q
    EVENT = "event"        # 8-K, 6-K


_FORM_CLASS = {
    "10-K": FormClass.ANNUAL, "40-F": FormClass.ANNUAL, "20-F": FormClass.ANNUAL,
    "10-Q": FormClass.INTERIM,
    "8-K": FormClass.EVENT, "6-K": FormClass.EVENT,
}


def form_class(form: str) -> FormClass:
    return _FORM_CLASS.get(form.upper().strip(), FormClass.EVENT)


# --------------------------------------------------------------------------- #
# Shared core
# --------------------------------------------------------------------------- #

CORE = """\
You extract time-windowed MATERIAL signals from SEC filings for a materials
sector-rotation model. A signal is a concrete, dated plan or development that
raises or lowers a company's PRODUCTION of (if it mines/refines the material) or
DEMAND for (if it consumes the material) a specific tracked material, over a
specific future window.

For each signal emit a `dated_effect`:
  - material     EXACTLY one canonical material id from the list below.
  - perspective  "producer" if the filer produces/mines/refines the material;
                 "consumer" if the filer uses/buys/consumes it. Decide per
                 effect from the sentence, not from the company in general.
  - direction    "increase" or "decrease" only.
  - magnitude    "small" | "moderate" | "large" (qualitative — never invent $).
  - window_start / window_end   ISO dates. Resolve relative references against
                 the filing date. window_end >= window_start.
  - rationale    one sentence (<200 chars) paraphrasing the plan.
  - evidence_quote  a VERBATIM sentence (or clause) copied from the filing that
                 grounds the effect. Never paraphrase here. Non-empty.
  - source_span  where it came from (item/section), if identifiable.

Also emit:
  - summary      2-3 sentences describing the filing and its material-relevant content.
  - extractor_confidence  0..1, how well-grounded the extraction is.

HARD RULES:
1. Every effect MUST have a verbatim `evidence_quote`. No quote -> drop it.
2. Every effect MUST bound a window. If you cannot bound it to a quarter or a
   few months, DROP it. Do NOT invent a vague full-calendar-year window.
3. `material` MUST be one of the canonical ids. If a mention maps to none, drop it.
4. Only "increase"/"decrease". Status-quo is not a signal.
5. Prefer few high-confidence effects over many speculative ones. Hedged plans
   ("we may", "could", "if conditions allow") are not commitments — drop them.
6. False negatives beat false positives: a missed signal averages out downstream;
   an invented one corrupts the score.

Return ONLY a JSON object with keys: summary, extractor_confidence, dated_effects.
"""

# --------------------------------------------------------------------------- #
# Per-class overlays
# --------------------------------------------------------------------------- #

_OVERLAY = {
    FormClass.ANNUAL: """\
FORM: annual report (10-K / 40-F / 20-F). These are dense and forward-looking.
Read the MD&A, Risk Factors, and business/outlook sections. Multi-quarter
windows are fine (capex programs, mine ramps, multi-year guidance). Emphasize
producer production/capex guidance and any dated consumer procurement plans.
""",
    FormClass.INTERIM: """\
FORM: quarterly report (10-Q). Read the MD&A and Risk Factors. Emphasize CHANGES
versus prior guidance — a raised/lowered outlook, a new near-term development.
Prefer near-term windows (this quarter and the next few). Most 10-Qs yield 0-3
effects; returning none is correct when there is no bounded material plan.
""",
    FormClass.EVENT: """\
FORM: event filing (8-K / 6-K), items: {items}. These report a single material
development. Read the press-release exhibit. Extract the ONE concrete material
event — an offtake/supply agreement, a JV, a project sanction or ramp, a
production/guidance revision. Use tight windows tied to the event. Ignore
boilerplate, financial-statement tables, and governance/administrative content.
""",
}


# --------------------------------------------------------------------------- #
# JSON schema (for schema-native providers; also the shape the prompt describes)
# --------------------------------------------------------------------------- #

EXTRACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "extractor_confidence": {"type": "number"},
        "dated_effects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "material": {"type": "string"},
                    "perspective": {"type": "string", "enum": ["producer", "consumer"]},
                    "direction": {"type": "string", "enum": ["increase", "decrease"]},
                    "magnitude": {"type": "string", "enum": ["small", "moderate", "large"]},
                    "window_start": {"type": "string"},
                    "window_end": {"type": "string"},
                    "rationale": {"type": "string"},
                    "evidence_quote": {"type": "string"},
                    "source_span": {"type": "string"},
                },
                "required": [
                    "material", "perspective", "direction", "magnitude",
                    "window_start", "window_end", "rationale", "evidence_quote",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "extractor_confidence", "dated_effects"],
    "additionalProperties": False,
}


def build_system_prompt(form: str, vocabulary: list[str], *, items: list[str] | None = None) -> str:
    cls = form_class(form)
    overlay = _OVERLAY[cls].format(items=", ".join(items) if items else "(none listed)")
    vocab = "\n".join(f"  - {v}" for v in vocabulary)
    return f"{CORE}\n{overlay}\nCANONICAL MATERIALS (use these ids EXACTLY):\n{vocab}\n"


def build_user_prompt(fetched: FetchedFiling) -> str:
    header = (
        f"Filer: {fetched.ticker} ({fetched.company_name or 'unknown'})\n"
        f"Form: {fetched.form}   Filed: {fetched.filing_date.isoformat()} "
        f"(anchor for relative dates)\n"
        f"Accession: {fetched.accession_number}\n"
    )
    if fetched.items:
        header += f"Items: {', '.join(fetched.items)}\n"

    order = [
        ("mda", "MD&A"),
        ("risk_factors", "Risk Factors"),
        ("exhibit", "Press-release / exhibit"),
        ("full_text", "Full filing text (fallback — section isolation unavailable)"),
    ]
    parts = [header]
    for key, label in order:
        text = fetched.section(key)
        if text:
            parts.append(f"\n--- {label} ---\n{text}")
    if len(parts) == 1:
        raise ValueError(
            f"FetchedFiling {fetched.ticker} {fetched.accession_number} has no sections"
        )
    return "".join(parts)

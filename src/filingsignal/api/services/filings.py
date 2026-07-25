"""FilingRow -> frontend `Filing` shape."""

from __future__ import annotations

from collections import Counter

from ...buffer import Buffer, FilingRow
from ...scorer import quarter_label, quarter_of
from ...universe import Universe

_NEEDS_REVIEW_BELOW = 0.7


def _window_label(ws, we) -> str:
    q1, q2 = quarter_of(ws), quarter_of(we)
    return quarter_label(q1) if q1 == q2 else f"{quarter_label(q1)}–Q{q2[1]}"


def _perspective(fr: FilingRow, uni: Universe) -> str:
    if fr.effects:
        return Counter(e.perspective.value for e in fr.effects).most_common(1)[0][0]
    c = uni.company(fr.ticker)
    if c and c.materials:
        return next(iter(c.materials.values()))
    return "producer"


def _status(fr: FilingRow) -> str:
    return "Needs review" if fr.confidence < _NEEDS_REVIEW_BELOW else "Extracted"


def filing_to_dict(fr: FilingRow, uni: Universe) -> dict:
    return {
        "accession": fr.accession_number,
        "ticker": fr.ticker,
        "company": fr.company_name,
        "form": fr.form,
        "filingDate": fr.filing_date.isoformat(),
        "materials": sorted({e.material for e in fr.effects}),
        "perspective": _perspective(fr, uni),
        "status": _status(fr),
        "confidence": round(fr.confidence, 2),
        "summary": fr.summary,
        "effects": [
            {
                "window": _window_label(e.window_start, e.window_end),
                "material": e.material,
                "perspective": e.perspective.value,
                "direction": e.direction.value,
                "magnitude": e.magnitude.value,
                "text": e.rationale,
                "quote": e.evidence_quote,
            }
            for e in fr.effects
        ],
        "warnings": fr.warnings,
    }


def list_filings(buf: Buffer, uni: Universe, **filters) -> list[dict]:
    rows, _ = buf.list_filings(**filters)
    return [filing_to_dict(r, uni) for r in rows]

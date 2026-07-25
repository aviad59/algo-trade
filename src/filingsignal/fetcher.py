"""Stage 1 — Fetcher. Thin wrapper over ``edgartools``. Salvaged from the
predecessor and extended for foreign forms (40-F/20-F/6-K), 8-K/6-K item
capture, and event-exhibit targeting. Section-isolation fallbacks are recorded
LOUDLY as warnings (the predecessor's silent Tesla full-text fallback is the bug
this fixes).

The module-level ``_to_fetched`` and helpers take a filing-like object so they
can be unit-tested against a fake without touching EDGAR.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any, Iterable, Optional

from .env import env_int
from .extraction.prompts import FormClass, form_class
from .models import FetchedFiling

logger = logging.getLogger(__name__)

ANNUAL_FORMS = {"10-K", "40-F", "20-F"}

# Forward-looking / guidance vocabulary used to score paragraphs when a section
# is too big to send whole. The goal is to keep the outlook + guidance prose and
# drop boilerplate (accounting policies, financial-statement tables, legalese) —
# which cuts token cost ~3-4x AND raises signal density for the extractor.
_GUIDANCE_TERMS = (
    "expect", "guidance", "outlook", "forecast", "anticipat", "project",
    "estimate", "target", "plan", "full year", "full-year", "next quarter",
    "second half", "first half", "increase", "decrease", "higher", "lower",
    "ramp", "capacity", "production", "offtake", "backlog", "per year",
    "run rate", "run-rate", "2026", "2027", "2028",
)


class Fetcher:
    def __init__(self, identity: str, keywords: Iterable[str] = ()) -> None:
        if "@" not in identity:
            raise ValueError("SEC identity must contain a contact email (e.g. 'Name you@x.com')")
        from edgar import set_identity

        set_identity(identity)
        self._identity = identity
        # material name/aliases, used to keep material-relevant paragraphs when a
        # section is condensed; 0 disables condensing (whole section sent).
        self._keywords = tuple(k.lower() for k in keywords)
        self._max_chars = env_int("FILINGSIGNAL_MAX_SECTION_CHARS", 45000)

    def fetch(
        self,
        ticker: str,
        forms: Iterable[str] = ("10-K",),
        limit: int = 1,
    ) -> list[FetchedFiling]:
        """Fetch up to ``limit`` most-recent filings per form. A bad ticker or
        filing is logged and skipped, never raised (batch runs survive it)."""
        from edgar import Company

        ticker = ticker.upper().strip()
        try:
            company = Company(ticker)
        except Exception as exc:  # noqa: BLE001
            logger.warning("could not resolve ticker %s: %s", ticker, exc)
            return []

        out: list[FetchedFiling] = []
        for form in forms:
            try:
                filings = company.get_filings(form=form)
            except Exception as exc:  # noqa: BLE001
                logger.warning("could not list %s for %s: %s", form, ticker, exc)
                continue
            for filing in _take(filings, limit):
                try:
                    out.append(_to_fetched(ticker, filing, keywords=self._keywords, max_chars=self._max_chars))
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "could not extract sections from %s for %s: %s",
                        getattr(filing, "accession_number", "?"), ticker, exc,
                    )
        return out

    def fetch_one(self, ticker: str, form: str, before: Optional[date] = None) -> Optional[FetchedFiling]:
        """The single most-recent filing of ``form`` filed on or before ``before``
        (latest overall if ``before`` is None). For the interactive one-filing
        digest. Returns None if the ticker/form/date yields nothing."""
        from edgar import Company

        ticker = ticker.upper().strip()
        try:
            filings = Company(ticker).get_filings(form=form)
        except Exception as exc:  # noqa: BLE001
            logger.warning("could not list %s for %s: %s", form, ticker, exc)
            return None
        for filing in filings:
            try:
                fd = _to_date(getattr(filing, "filing_date", None))
            except Exception:  # noqa: BLE001
                continue
            if before is not None and fd > before:
                continue
            try:
                return _to_fetched(ticker, filing, keywords=self._keywords, max_chars=self._max_chars)
            except Exception as exc:  # noqa: BLE001
                logger.warning("could not read %s for %s: %s", getattr(filing, "accession_number", "?"), ticker, exc)
                return None
        return None


# --------------------------------------------------------------------------- #
# Internals — module-level for hermetic testing against a fake Filing object
# --------------------------------------------------------------------------- #


def condense_section(text: str, keywords: Iterable[str], max_chars: int) -> tuple[str, bool]:
    """Shrink an over-long section to its guidance-relevant paragraphs.

    Returns ``(text, condensed)``. Paragraphs are scored by material-keyword
    presence + forward-looking vocabulary + whether they carry numbers; the
    highest-scoring ones are kept in reading order up to ``max_chars``. This is
    the cost lever: whole 10-K/10-Q/8-K documents are 70-110k tokens, mostly
    boilerplate and tables — keeping the outlook prose cuts that ~3-4x.
    """
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    kw = tuple(k.lower() for k in keywords)
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paras) <= 1:  # unstructured blob — window around the first keyword hit
        low = text.lower()
        hits = [low.find(k) for k in kw if k in low]
        idx = min(hits) if hits else 0
        start = max(0, idx - max_chars // 4)
        return text[start:start + max_chars], True

    def score(p: str) -> int:
        low = p.lower()
        mat = 3 if any(k in low for k in kw) else 0
        guid = min(sum(1 for t in _GUIDANCE_TERMS if t in low), 4)
        num = 1 if any(ch.isdigit() for ch in low) else 0
        return mat + guid + num

    order = sorted(range(len(paras)), key=lambda i: score(paras[i]), reverse=True)
    keep: set[int] = set()
    total = 0
    for i in order:
        if keep and (score(paras[i]) == 0 or total + len(paras[i]) > max_chars):
            break
        keep.add(i)
        total += len(paras[i])
    return "\n\n".join(paras[i] for i in sorted(keep)), True


def _take(filings: Any, n: int) -> list[Any]:
    taken: list[Any] = []
    for i, f in enumerate(filings):
        if i >= n:
            break
        taken.append(f)
    return taken


def _attr_text(obj: Any, name: str) -> str:
    val = getattr(obj, name, None)
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    text = getattr(val, "text", None)
    if callable(text):
        try:
            return str(text()).strip()
        except Exception:  # noqa: BLE001
            return ""
    return str(val).strip()


def _items(filing: Any) -> list[str]:
    try:
        obj = filing.obj()
        items = getattr(obj, "items", None)
        if items:
            return [str(i).replace("Item ", "").strip() for i in items]
    except Exception:  # noqa: BLE001
        pass
    return []


def _event_exhibit_text(filing: Any) -> str:
    """Pull the EX-99 press-release exhibit(s) of an 8-K/6-K (not the whole dump)."""
    parts: list[str] = []
    for att in getattr(filing, "attachments", []) or []:
        doc = str(getattr(att, "document", "") or "")
        dtype = str(getattr(att, "document_type", "") or getattr(att, "description", "") or "")
        if "99" in doc or "99" in dtype.upper() or "EX-99" in dtype.upper():
            try:
                parts.append(str(att.text() or "").strip())
            except Exception:  # noqa: BLE001
                continue
    return "\n\n".join(p for p in parts if p)


def _to_fetched(
    ticker: str,
    filing: Any,
    *,
    keywords: Iterable[str] = (),
    max_chars: int = 0,
) -> FetchedFiling:
    form = str(getattr(filing, "form", "") or "")
    cls = form_class(form)
    sections: dict[str, str] = {}
    warnings: list[str] = []
    items = _items(filing) if cls is FormClass.EVENT else []

    if cls in (FormClass.ANNUAL, FormClass.INTERIM):
        typed = None
        try:
            typed = filing.obj()
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"obj() failed ({exc}); using full text")
        if typed is not None:
            mda = _attr_text(typed, "management_discussion") or _attr_text(typed, "mda")
            risk = _attr_text(typed, "risk_factors")
            if mda:
                sections["mda"] = mda
            if risk:
                sections["risk_factors"] = risk
        if not sections:
            warnings.append(
                f"section isolation failed for {form}; extractor received full text "
                "(diluted input — flagged, not silent)"
            )
    elif cls is FormClass.EVENT:
        exhibit = _event_exhibit_text(filing)
        if exhibit:
            sections["exhibit"] = exhibit
        else:
            warnings.append(f"no EX-99 exhibit found for {form}; using full text")

    if not sections:
        try:
            sections["full_text"] = str(filing.text() or "").strip()
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"could not read any text for {form} {ticker}: {exc}") from exc

    # Cost/focus lever: keep only guidance-relevant paragraphs of over-long
    # sections. Loud, never silent (consistent with the section-isolation rule).
    if max_chars:
        for name in list(sections):
            condensed, changed = condense_section(sections[name], keywords, max_chars)
            if changed:
                warnings.append(
                    f"section '{name}' condensed {len(sections[name])}->{len(condensed)} chars "
                    "to guidance-relevant paragraphs (cost/focus — flagged, not silent)"
                )
                sections[name] = condensed

    return FetchedFiling(
        ticker=ticker,
        cik=_cik(filing),
        company_name=str(getattr(filing, "company", "") or getattr(filing, "company_name", "") or ""),
        form=form,
        filing_date=_to_date(getattr(filing, "filing_date", None)),
        accession_number=str(getattr(filing, "accession_number", "") or ""),
        sections=sections,
        items=items,
        extraction_warnings=warnings,
    )


def _cik(filing: Any) -> str:
    cik = getattr(filing, "cik", "") or ""
    digits = "".join(ch for ch in str(cik) if ch.isdigit())
    return digits.zfill(10) if digits else ""


def _to_date(v: Any) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if v:
        return date.fromisoformat(str(v)[:10])
    raise ValueError("filing has no filing_date")

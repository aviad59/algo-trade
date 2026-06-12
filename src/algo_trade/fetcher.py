"""EDGAR Fetcher -- thin wrapper around edgartools.

What this does:
  - Resolves a ticker to a Company via edgartools.
  - Pulls the most recent N filings of the requested form types.
  - For 10-K / 10-Q, goes through the typed object and pulls MD&A and
    Risk Factors as separate sections (this is what the extractor agent
    actually needs to read).
  - For 8-K and anything else, falls back to the full filing text.
  - Returns a flat list of FetchedFiling objects, most-recent first.

What this deliberately does NOT do:
  - Call any LLM. This module is pure I/O + parsing.
  - Hit the SEC directly. edgartools owns rate limits, caching, and the
    SEC User-Agent rules; we just set the identity once and let it work.
  - Raise on a single bad ticker. A batch run with 200 tickers should
    survive one broken filing -- failures are logged and skipped.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Iterable, Optional

from edgar import Company, set_identity

from .models import FetchedFiling

logger = logging.getLogger(__name__)


# Forms where we know how to pull typed sections (MD&A, Risk Factors).
# Everything else falls back to .text() of the full filing.
TYPED_FORMS = frozenset({"10-K", "10-Q"})


class Fetcher:
    """Stateful wrapper around edgartools. Construct once per process."""

    def __init__(self, identity: str) -> None:
        """
        Args:
            identity: Contact string passed to edgartools' set_identity().
                SEC requires a contact in the User-Agent for fair access;
                edgartools uses this string. Typical form:
                    "Jane Doe jane@example.com"
        """
        if not identity or "@" not in identity:
            raise ValueError(
                "identity must contain an email, e.g. "
                "'Jane Doe jane@example.com'. SEC requires this in the "
                "User-Agent for fair access."
            )
        set_identity(identity)
        self._identity = identity

    def fetch(
        self,
        ticker: str,
        forms: Iterable[str] = ("10-K",),
        limit: int = 1,
    ) -> list[FetchedFiling]:
        """Fetch up to `limit` most recent filings per form type for `ticker`.

        Returns a flat list across all requested forms, most-recent first
        per form. A failure on a single ticker or filing is logged and
        skipped rather than raised -- the caller is usually iterating over
        many tickers and shouldn't be killed by one bad one.
        """
        ticker = ticker.upper().strip()
        try:
            company = Company(ticker)
        except Exception as exc:
            logger.warning("could not resolve ticker %s: %s", ticker, exc)
            return []

        out: list[FetchedFiling] = []
        for form in forms:
            try:
                filings = company.get_filings(form=form)
            except Exception as exc:
                logger.warning(
                    "could not list %s filings for %s: %s", form, ticker, exc
                )
                continue

            for filing in _take(filings, limit):
                try:
                    fetched = _to_fetched(ticker, filing)
                except Exception as exc:
                    logger.warning(
                        "could not extract sections from %s for %s: %s",
                        getattr(filing, "accession_number", "?"),
                        ticker,
                        exc,
                    )
                    continue
                out.append(fetched)

        return out


# --------------------------------------------------------------------------- #
# Internals -- broken out as module-level functions so they are easy to unit
# test against a fake Filing object without going through edgartools.
# --------------------------------------------------------------------------- #


def _take(filings: Any, n: int) -> list[Any]:
    """Take the first n items from an edgartools Filings collection.

    edgartools' Filings object is iterable in most-recent-first order, so
    plain iteration is the safest cross-version approach.
    """
    taken: list[Any] = []
    for i, f in enumerate(filings):
        if i >= n:
            break
        taken.append(f)
    return taken


def _to_fetched(ticker: str, filing: Any) -> FetchedFiling:
    """Pull metadata + the right sections out of an edgartools Filing."""
    sections: dict[str, str] = {}
    warnings: list[str] = []

    form = getattr(filing, "form", "")

    if form in TYPED_FORMS:
        typed: Any = None
        try:
            typed = filing.obj()
        except Exception as exc:
            warnings.append(f"obj() raised: {exc}; falling back to full text")

        if typed is not None:
            mda = _attr_text(typed, "mda")
            if mda:
                sections["mda"] = mda
            else:
                warnings.append("mda section empty or missing")

            risk = _attr_text(typed, "risk_factors")
            if risk:
                sections["risk_factors"] = risk
            else:
                warnings.append("risk_factors section empty or missing")

    if not sections:
        # Either an 8-K (no typed sections we care about) or typed
        # extraction failed. Fall back to the full filing text so the
        # extractor agent still has something to read.
        sections["full_text"] = filing.text()

    return FetchedFiling(
        ticker=ticker,
        cik=_cik(filing),
        company_name=str(getattr(filing, "company", "") or ""),
        form=form,
        filing_date=_to_date(filing.filing_date),
        accession_number=str(filing.accession_number),
        sections=sections,
        extraction_warnings=warnings,
    )


def _attr_text(obj: Any, name: str) -> Optional[str]:
    """Read a section attribute defensively.

    edgartools sometimes exposes sections as strings, sometimes as objects
    with a `.text()` method. Try both; return None if the section is empty
    or unreadable.
    """
    val = getattr(obj, name, None)
    if val is None:
        return None
    if isinstance(val, str):
        return val.strip() or None
    if hasattr(val, "text") and callable(val.text):
        try:
            return (val.text() or "").strip() or None
        except Exception:
            pass
    s = str(val).strip()
    return s or None


def _cik(filing: Any) -> str:
    raw = getattr(filing, "cik", "")
    if raw == "" or raw is None:
        return ""
    # CIKs are conventionally zero-padded to 10 digits.
    return str(raw).zfill(10)


def _to_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    raise TypeError(f"unrecognized filing_date type: {type(value).__name__}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _cli() -> None:
    """Command-line entry point.

    Example:
        algo-trade-fetch \\
            --identity "Jane Doe jane@example.com" \\
            --ticker NVDA --ticker MSFT \\
            --form 10-K --form 10-Q \\
            --limit 1 \\
            --out fetched.jsonl
    """
    import argparse
    import sys

    p = argparse.ArgumentParser(
        prog="algo-trade-fetch",
        description="Fetch SEC EDGAR filings into a JSONL buffer.",
    )
    p.add_argument(
        "--identity",
        required=True,
        help='SEC contact, e.g. "Jane Doe jane@example.com"',
    )
    p.add_argument(
        "--ticker",
        action="append",
        required=True,
        help="Ticker to fetch (repeatable).",
    )
    p.add_argument(
        "--form",
        action="append",
        default=None,
        help="Form type (repeatable). Default: 10-K.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Most recent N filings to pull per form type. Default: 1.",
    )
    p.add_argument(
        "--out",
        default="-",
        help="JSONL output path, or '-' for stdout. Default: stdout.",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show INFO log lines from edgartools and the fetcher.",
    )
    args = p.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    forms = args.form or ["10-K"]
    fetcher = Fetcher(identity=args.identity)

    sink = sys.stdout if args.out == "-" else open(args.out, "w", encoding="utf-8")
    try:
        n = 0
        for ticker in args.ticker:
            for fetched in fetcher.fetch(ticker=ticker, forms=forms, limit=args.limit):
                sink.write(fetched.model_dump_json() + "\n")
                sink.flush()
                n += 1
        if args.out != "-":
            print(f"wrote {n} filing(s) to {args.out}", file=sys.stderr)
    finally:
        if sink is not sys.stdout:
            sink.close()


if __name__ == "__main__":
    _cli()

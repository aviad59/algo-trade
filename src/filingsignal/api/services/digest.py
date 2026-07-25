"""Interactive one-filing digest for the reviewer demo.

Pick a ticker + form + 'before' date; fetch the single most-recent filing on or
before that date, run it through the same pipeline as the batch job (pre-LLM
filter → Agent #1 extraction), persist it, and return the summary + dated
effects. Auth-gated (spends the baked-in LLM key). Factories are monkeypatchable
so tests inject fakes (no network, no LLM).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from ...buffer import Buffer
from ...extraction import should_extract
from ...refresh import is_auth_error, provider_key_present
from ...universe import load_universe
from ..config import Settings
from .filings import filing_to_dict


def _fetcher_factory(identity: str, keywords):
    from ...fetcher import Fetcher
    return Fetcher(identity, keywords=keywords)


def _extractor_factory():
    from ...extraction import Extractor
    return Extractor()


def digest_one(ticker: str, form: str, before: Optional[date], settings: Settings) -> dict:
    """Returns {status, ...}. status ∈ extracted | cached | filtered | not_found | error."""
    ticker = ticker.upper().strip()
    if not settings.sec_identity:
        return {"status": "error", "reason": "FILINGSIGNAL_SEC_IDENTITY not configured on the server"}
    ok, info = provider_key_present()
    if not ok:
        return {"status": "error", "reason": f"LLM provider not configured: {info}"}

    uni = load_universe(settings.universe_dir / "materials.yaml")
    fetcher = _fetcher_factory(settings.sec_identity, uni.all_keywords())
    fetched = fetcher.fetch_one(ticker, form, before)
    if fetched is None:
        when = f" on or before {before.isoformat()}" if before else ""
        return {"status": "not_found", "reason": f"no {form} found for {ticker}{when}"}

    meta = {
        "ticker": fetched.ticker, "company": fetched.company_name, "form": fetched.form,
        "filingDate": fetched.filing_date.isoformat(), "accession": fetched.accession_number,
        "items": fetched.items,
    }

    buf = Buffer(settings.buffer_path)
    try:
        extractor = _extractor_factory()
        model = extractor.model
        if buf.has_extraction(fetched.accession_number, model):
            fr = buf.get_filing(fetched.accession_number, extractor_model=model)
            return {"status": "cached", "filing": filing_to_dict(fr, uni)}

        decision = should_extract(fetched, uni)
        if not decision.keep:
            return {"status": "filtered", "reason": decision.reason, "meta": meta}

        try:
            ext = extractor.extract(fetched)
        except Exception as exc:  # noqa: BLE001
            if is_auth_error(exc):
                return {"status": "error", "reason": "LLM key invalid or exhausted — extraction refused"}
            return {"status": "error", "reason": f"extraction failed: {type(exc).__name__}: {exc}"[:240]}

        buf.upsert(ext, company_name=fetched.company_name)
        fr = buf.get_filing(fetched.accession_number, extractor_model=model)
        return {"status": "extracted", "filing": filing_to_dict(fr, uni), "model": model}
    finally:
        buf.close()

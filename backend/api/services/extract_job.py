"""Live extraction jobs — demo-token holders pull new tickers via the API.

This is the write path of the demo deployment: fetch a ticker's latest
filings from EDGAR, run Agent #1 on each, upsert into the buffer. Because a
new extraction changes the buffer version, every read-side cache (ranking,
backtest, snapshot staleness) invalidates itself — the whole app re-ranks
after a pull with no extra wiring.

Guard rails, in order:
- The router only calls this for requests carrying the demo token.
- One job at a time (single slot) — a second POST while running is refused.
- A per-boot filings budget (``ALGO_TRADE_DEMO_MAX_FILINGS``, default 20)
  bounds worst-case spend even if the token leaks; on the default
  claude-haiku-4-5 that is well under $1 per container lifetime.
- Requires ANTHROPIC_API_KEY and ALGO_TRADE_SEC_IDENTITY server-side; a
  missing prerequisite fails the job with a readable reason, never a 500.

State is in-process (like the ranking cache): a container restart forgets
running jobs *and* pulled filings together, which is consistent.
"""

from __future__ import annotations

import logging
import re
import threading
from datetime import datetime, timezone

from algo_trade.buffer import Buffer
from algo_trade.env import env_int, env_str

from ..deps import get_settings

logger = logging.getLogger(__name__)

_TICKER_RE = re.compile(r"^[A-Za-z][A-Za-z.\-]{0,9}$")
_ALLOWED_FORMS = {"10-K", "10-Q", "8-K"}
_MAX_LIMIT_PER_REQUEST = 3

_lock = threading.Lock()
_filings_extracted_total = 0
_status: dict = {
    "state": "idle",
    "ticker": None,
    "forms": [],
    "started_at": None,
    "finished_at": None,
    "filings_done": 0,
    "effects_found": 0,
    "events": [],
    "error": None,
}


# Factories are module-level so tests can monkeypatch them with fakes —
# the same injection idea as the repo's fake-client convention.
def _fetcher_factory(identity: str):
    from algo_trade.fetcher import Fetcher

    return Fetcher(identity=identity)


def _extractor_factory():
    from algo_trade.extractor import Extractor

    return Extractor()


def _budget_cap() -> int:
    return env_int("ALGO_TRADE_DEMO_MAX_FILINGS", 20)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event(message: str) -> None:
    with _lock:
        _status["events"].append(message)


def job_status() -> dict:
    with _lock:
        snapshot = dict(_status)
        snapshot["events"] = list(_status["events"])
    snapshot["contract_version"] = "1.0"
    snapshot["budget_used"] = _filings_extracted_total
    snapshot["budget_cap"] = _budget_cap()
    return snapshot


def _fail(message: str) -> None:
    with _lock:
        _status["state"] = "error"
        _status["error"] = message
        _status["finished_at"] = _now()
    _event(message)


def _run(ticker: str, forms: list[str], limit: int, identity: str, db_path: str) -> None:
    global _filings_extracted_total
    try:
        fetcher = _fetcher_factory(identity)
        extractor = _extractor_factory()
        filings = list(fetcher.fetch(ticker=ticker, forms=forms, limit=limit))
        _event(f"EDGAR: found {len(filings)} filing(s) for {ticker}")
        if not filings:
            with _lock:
                _status["state"] = "done"
                _status["finished_at"] = _now()
            return

        with Buffer(db_path) as buf:
            for fetched in filings:
                _event(
                    f"Agent #1 reading {fetched.form} {fetched.accession_number} "
                    f"(filed {fetched.filing_date.isoformat()})…"
                )
                try:
                    extracted = extractor.extract(fetched)
                except Exception as exc:
                    logger.warning("live extract failed for %s: %s", ticker, exc)
                    _event(f"extraction failed for {fetched.accession_number}: {exc}")
                    continue
                buf.upsert(extracted, company_name=fetched.company_name)
                with _lock:
                    _status["filings_done"] += 1
                    _status["effects_found"] += len(extracted.dated_effects)
                    _filings_extracted_total += 1
                _event(
                    f"extracted {len(extracted.dated_effects)} effect(s), "
                    f"confidence {extracted.extractor_confidence:.0%} — saved to buffer"
                )

        with _lock:
            _status["state"] = "done"
            _status["finished_at"] = _now()
        _event("done — dashboard, ranking and backtest now reflect the new filings")
    except Exception as exc:  # network, EDGAR, anything: readable, not a 500
        logger.warning("live extraction job failed", exc_info=True)
        _fail(f"job failed: {exc}")


def start_extraction(ticker: str, forms: list[str] | None, limit: int) -> tuple[str, str]:
    """Try to start a job. Returns (outcome, message) where outcome is
    'started' | 'invalid' | 'busy' | 'budget' | 'unconfigured'."""
    global _status
    ticker = (ticker or "").strip().upper()
    if not _TICKER_RE.match(ticker):
        return "invalid", f"invalid ticker {ticker!r}"
    forms = forms or ["10-Q", "10-K"]
    if not set(forms) <= _ALLOWED_FORMS:
        return "invalid", f"forms must be a subset of {sorted(_ALLOWED_FORMS)}"
    limit = max(1, min(int(limit), _MAX_LIMIT_PER_REQUEST))

    if not env_str("ANTHROPIC_API_KEY", ""):
        return "unconfigured", "server has no ANTHROPIC_API_KEY; live extraction is disabled"
    identity = env_str("ALGO_TRADE_SEC_IDENTITY", "")
    if not identity:
        return "unconfigured", "server has no ALGO_TRADE_SEC_IDENTITY; EDGAR requires one"

    cap = _budget_cap()
    with _lock:
        if _status["state"] == "running":
            return "busy", f"an extraction for {_status['ticker']} is already running"
        if _filings_extracted_total + limit > cap:
            return "budget", (
                f"demo extraction budget reached ({_filings_extracted_total}/{cap} "
                "filings this deployment)"
            )
        _status = {
            "state": "running",
            "ticker": ticker,
            "forms": forms,
            "started_at": _now(),
            "finished_at": None,
            "filings_done": 0,
            "effects_found": 0,
            "events": [
                f"queued: {ticker} — up to {limit} filing(s) per form ({', '.join(forms)})"
            ],
            "error": None,
        }

    settings = get_settings()
    thread = threading.Thread(
        target=_run,
        args=(ticker, forms, limit, identity, str(settings.buffer_path)),
        name=f"extract-{ticker}",
        daemon=True,
    )
    thread.start()
    return "started", f"extraction started for {ticker}"

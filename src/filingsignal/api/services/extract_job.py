"""Background extraction job for the live demo. Single slot, per-boot budget.
Factories are monkeypatchable so tests inject fakes (no network, no LLM)."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from ...buffer import Buffer
from ...extraction import should_extract
from ...universe import load_universe
from ..config import Settings

logger = logging.getLogger(__name__)

_MAX_FILINGS_PER_BOOT = 30
_lock = threading.Lock()
_job: dict = {"status": "idle", "log": [], "processed": 0, "extracted": 0, "budget_used": 0}


def _fetcher_factory(identity: str):
    from ...fetcher import Fetcher
    return Fetcher(identity)


def _extractor_factory():
    from ...extraction import Extractor
    return Extractor()


def job_status() -> dict:
    with _lock:
        return dict(_job, log=list(_job["log"][-30:]))


def _emit(msg: str) -> None:
    with _lock:
        _job["log"].append(f"{datetime.now(timezone.utc).strftime('%H:%M:%S')} {msg}")


def start_job(tickers: list[str], forms: list[str] | None, settings: Settings) -> dict:
    if not settings.sec_identity:
        raise RuntimeError("FILINGSIGNAL_SEC_IDENTITY not set")
    with _lock:
        if _job["status"] == "running":
            raise RuntimeError("a job is already running")
        _job.update(status="running", log=[], processed=0, extracted=0,
                    tickers=[t.upper() for t in tickers])
    threading.Thread(target=_run, args=(tickers, forms, settings), daemon=True).start()
    return job_status()


def _run(tickers: list[str], forms: list[str] | None, settings: Settings) -> None:
    try:
        uni = load_universe(settings.universe_dir / "materials.yaml")
        buf = Buffer(settings.buffer_path)
        fetcher = _fetcher_factory(settings.sec_identity)
        extractor = _extractor_factory()
        for tk in tickers:
            tk = tk.upper()
            use_forms = forms or uni.forms_for_ticker(tk) or ["10-Q", "8-K"]
            for fetched in fetcher.fetch(tk, forms=use_forms, limit=2):
                with _lock:
                    if _job["budget_used"] >= _MAX_FILINGS_PER_BOOT:
                        _emit("per-boot budget reached; stopping")
                        _job["status"] = "done"
                        return
                _job["processed"] = _job.get("processed", 0) + 1
                if buf.has_extraction(fetched.accession_number, extractor.model):
                    _emit(f"skip {tk} {fetched.form} {fetched.accession_number} (already analyzed)")
                    continue
                decision = should_extract(fetched, uni)
                if not decision.keep:
                    _emit(f"filter {tk} {fetched.form}: {decision.reason}")
                    continue
                ext = extractor.extract(fetched)
                buf.upsert(ext, company_name=fetched.company_name)
                with _lock:
                    _job["extracted"] += 1
                    _job["budget_used"] += 1
                _emit(f"extracted {tk} {fetched.form}: {len(ext.dated_effects)} effect(s)")
        buf.close()
        with _lock:
            _job["status"] = "done"
        _emit("done")
    except Exception as exc:  # noqa: BLE001
        logger.exception("extract job failed")
        with _lock:
            _job["status"] = "error"
            _job["error"] = str(exc)
        _emit(f"error: {exc}")

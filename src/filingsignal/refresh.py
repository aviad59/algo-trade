"""The rollover sweep — the piece that makes a new quarter actually pull in new
filings, not just recompute over stale ones.

`sweep()` walks the universe and runs the incremental extractor (Agent #1):
already-digested filings are skipped (``buffer.has_extraction``), irrelevant
ones are filtered pre-LLM, and only genuinely new filings cost a call. The
prediction then recomputes automatically (the scorer is point-in-time), so this
is the only manual/scheduled step a rollover needs.

Guardrail (requested): a bad provider key must not trigger a spend storm.
``provider_key_present()`` is a cheap presence preflight; and if a call fails
with an authentication/permission error mid-sweep (a *wrong* key), the sweep
aborts immediately rather than hammering every ticker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .env import env_optional_str, env_str
from .extraction import Extractor, should_extract
from .llm.structured import LLMRefusal
from .universe import Universe

_KEY_ENV = {
    "claude": "ANTHROPIC_API_KEY",
    "kimi": "MOONSHOT_API_KEY",
    "moonshot": "MOONSHOT_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def provider_key_present(provider: Optional[str] = None) -> tuple[bool, str]:
    """Cheap preflight: is the API key for the chosen provider set at all?
    Returns (ok, message). Does not validate the key against the server — a
    *wrong* key is caught at the first call by the auth-abort in ``sweep``."""
    provider = (provider or env_str("FILINGSIGNAL_LLM_PROVIDER", "claude")).lower()
    key_env = _KEY_ENV.get(provider)
    if key_env is None:
        return False, f"unknown provider {provider!r} (use claude|kimi|openai)"
    if not env_optional_str(key_env):
        return False, f"{key_env} is not set for provider {provider!r}"
    return True, provider


def is_auth_error(exc: BaseException) -> bool:
    """True for a *spend-blocking* provider error — auth/permission failure OR
    an exhausted key (credit balance too low / quota / billing). These mean no
    further call can succeed, so the sweep should abort rather than grind the
    whole list. Detected without importing the vendor SDKs."""
    name = type(exc).__name__.lower()
    if "authentication" in name or "permission" in name:
        return True
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if code in (401, 403, 429, "401", "403", "429"):
        return True
    msg = str(getattr(exc, "message", "") or exc).lower()
    return any(t in msg for t in ("credit balance", "insufficient", "quota", "billing", "too low"))


@dataclass
class RefreshResult:
    fetched: int = 0
    extracted: int = 0
    skipped: int = 0
    filtered: int = 0
    errors: int = 0
    effects: int = 0
    aborted: bool = False
    reason: str = ""


def sweep(
    *,
    buf,
    uni: Universe,
    fetcher,
    extractor: Extractor,
    tickers: Optional[list[str]] = None,
    forms: Optional[list[str]] = None,
    limit: int = 2,
    on_event: Optional[Callable[[str, str, str], None]] = None,
) -> RefreshResult:
    """Incrementally digest new filings across the universe. Idempotent: only
    filings not already in the buffer for this model are extracted. Aborts the
    whole run on a provider auth failure (bad key) instead of retrying per
    ticker."""
    res = RefreshResult()
    emit = on_event or (lambda *_: None)
    for tk in tickers or uni.tickers():
        tk_forms = forms or uni.forms_for_ticker(tk) or ["10-Q", "8-K"]
        for fetched in fetcher.fetch(tk, forms=tk_forms, limit=limit):
            res.fetched += 1
            if buf.has_extraction(fetched.accession_number, extractor.model):
                res.skipped += 1
                emit("skip", tk, fetched.accession_number)
                continue
            decision = should_extract(fetched, uni)
            if not decision.keep:
                res.filtered += 1
                emit("filter", tk, decision.reason)
                continue
            try:
                ext = extractor.extract(fetched)
            except LLMRefusal as e:  # a refusal on one filing — skip, keep going
                res.filtered += 1
                emit("refusal", tk, str(e))
                continue
            except Exception as e:  # noqa: BLE001
                if is_auth_error(e):
                    res.aborted = True
                    res.reason = f"provider spend blocked ({type(e).__name__}: {str(e)[:120]}) — key done/invalid, stopping"
                    emit("abort", tk, res.reason)
                    return res
                res.errors += 1
                emit("error", tk, f"{type(e).__name__}: {e}")
                continue
            buf.upsert(ext, company_name=fetched.company_name)
            res.extracted += 1
            res.effects += len(ext.dated_effects)
            emit("ok", tk, f"{fetched.form} · {len(ext.dated_effects)} effect(s)")
    return res

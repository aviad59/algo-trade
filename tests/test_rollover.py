"""Rollover + sweep: prove the calendar-driven forecast advances deterministically
and the incremental sweep only digests new filings (and refuses to spend on a bad
provider key). The clock seam (FILINGSIGNAL_TODAY) is what makes this testable
without waiting for a real quarter to turn.
"""

from __future__ import annotations

import json
from datetime import date

from filingsignal.models import Direction, FetchedFiling, Magnitude, Perspective

INC = Direction.increase
PRO = Perspective.producer
S, M, L = Magnitude.small, Magnitude.moderate, Magnitude.large

# a valid extraction the FakeLLM returns verbatim (one copper effect)
EXT_JSON = json.dumps({
    "summary": "copper guidance up",
    "extractor_confidence": 0.8,
    "dated_effects": [{
        "material": "Copper", "perspective": "producer", "direction": "increase",
        "magnitude": "moderate", "window_start": "2026-07-01", "window_end": "2026-09-30",
        "rationale": "guidance up", "evidence_quote": "we expect ~750 million pounds of copper",
        "source_span": "Item 2.02",
    }],
})


def _fetched(acc, *, items=("2.02",), text="We expect ~750 million pounds of copper in Q3 2026."):
    return FetchedFiling(
        ticker="FCX", cik="1", company_name="Freeport-McMoRan", form="8-K",
        filing_date=date(2026, 7, 10), accession_number=acc,
        sections={"exhibit": text}, items=list(items),
    )


class FakeFetcher:
    def __init__(self, by_ticker):
        self._by = by_ticker

    def fetch(self, ticker, forms=None, limit=2):
        yield from self._by.get(ticker, [])


# --------------------------------------------------------------------------- #
# clock seam
# --------------------------------------------------------------------------- #

def test_clock_override(monkeypatch):
    from filingsignal.clock import today
    monkeypatch.setenv("FILINGSIGNAL_TODAY", "2030-01-15")
    assert today() == date(2030, 1, 15)
    monkeypatch.setenv("FILINGSIGNAL_TODAY", "not-a-date")  # unparseable → real date
    assert today() == date.today()
    monkeypatch.delenv("FILINGSIGNAL_TODAY", raising=False)
    assert today() == date.today()


def test_target_quarter_rolls_on_boundary(monkeypatch):
    from filingsignal.api.config import Settings
    monkeypatch.delenv("FILINGSIGNAL_FORECAST_QUARTER", raising=False)  # unpin
    monkeypatch.setenv("FILINGSIGNAL_TODAY", "2026-09-30")
    assert Settings.from_env().target_quarter() == (2026, 3)
    monkeypatch.setenv("FILINGSIGNAL_TODAY", "2026-10-01")
    assert Settings.from_env().target_quarter() == (2026, 4)


# --------------------------------------------------------------------------- #
# point-in-time prediction recompute (pure scorer — the "new prediction")
# --------------------------------------------------------------------------- #

def test_forecast_recomputes_and_rolls(uni, make_effect):
    from filingsignal.scorer import score_quarter
    effects = [
        # copper effect targeting Q3, public well before it
        make_effect("FCX", "Copper", PRO, INC, M, "2026-04-15", "2026-07-01", "2026-09-30"),
        # uranium effect targeting Q4, public before both quarters
        make_effect("CCJ", "Uranium", PRO, INC, L, "2026-06-20", "2026-10-01", "2026-12-31"),
        # silver effect filed AFTER Q3 began → must NOT count for Q3 (no look-ahead)
        make_effect("HL", "Silver", PRO, INC, L, "2026-08-01", "2026-07-01", "2026-09-30"),
    ]
    q3 = score_quarter(effects, (2026, 3), uni)
    q4 = score_quarter(effects, (2026, 4), uni)

    assert q3[0].material_name == "Copper"     # Q3 pick
    assert q4[0].material_name == "Uranium"    # rolls to Uranium in Q4 — no code change
    # look-ahead blocked: Silver filed 08-01 contributes nothing to a Q3 (07-01) decision
    silver_q3 = next(r for r in q3 if r.material_name == "Silver")
    assert silver_q3.producer_score == 0.0


# --------------------------------------------------------------------------- #
# incremental sweep
# --------------------------------------------------------------------------- #

def test_sweep_incremental_skips_already_digested(uni, fake_llm):
    from filingsignal.buffer import Buffer
    from filingsignal.extraction import Extractor
    from filingsignal.refresh import sweep

    fetcher = FakeFetcher({"FCX": [_fetched("fcx-a")]})
    ext = Extractor(client=fake_llm(EXT_JSON), universe=uni)
    with Buffer(":memory:") as buf:
        r1 = sweep(buf=buf, uni=uni, fetcher=fetcher, extractor=ext, tickers=["FCX"], forms=["8-K"], limit=1)
        assert r1.extracted == 1 and r1.effects == 1 and not r1.aborted
        r2 = sweep(buf=buf, uni=uni, fetcher=fetcher, extractor=ext, tickers=["FCX"], forms=["8-K"], limit=1)
        assert r2.extracted == 0 and r2.skipped == 1


def test_sweep_filters_routine_filing(uni, fake_llm):
    from filingsignal.buffer import Buffer
    from filingsignal.extraction import Extractor
    from filingsignal.refresh import sweep

    # 8-K Item 5.02 (director change) — dropped by the item allowlist, no LLM call
    routine = _fetched("fcx-502", items=("5.02",), text="Appointment of a new director.")
    fetcher = FakeFetcher({"FCX": [routine]})
    ext = Extractor(client=fake_llm(EXT_JSON), universe=uni)
    with Buffer(":memory:") as buf:
        r = sweep(buf=buf, uni=uni, fetcher=fetcher, extractor=ext, tickers=["FCX"], forms=["8-K"], limit=1)
        assert r.filtered == 1 and r.extracted == 0


# --------------------------------------------------------------------------- #
# provider-key guardrail (the "if the key is invalid, DON'T" requirement)
# --------------------------------------------------------------------------- #

def test_provider_key_preflight(monkeypatch):
    from filingsignal.refresh import provider_key_present
    monkeypatch.setenv("FILINGSIGNAL_LLM_PROVIDER", "claude")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    ok, msg = provider_key_present()
    assert not ok and "ANTHROPIC_API_KEY" in msg
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert provider_key_present()[0]
    monkeypatch.setenv("FILINGSIGNAL_LLM_PROVIDER", "bogus")
    assert not provider_key_present()[0]


class _AuthError(Exception):
    status_code = 401


class _AuthLLM:
    model = "auth-fake"

    def __init__(self):
        from filingsignal.llm.base import Capabilities
        self.capabilities = Capabilities(native_schema=False)

    def complete(self, **kw):
        raise _AuthError("invalid api key")


def test_sweep_aborts_on_auth_error_without_spending(uni):
    from filingsignal.buffer import Buffer
    from filingsignal.extraction import Extractor
    from filingsignal.refresh import sweep

    # two tickers queued; the auth failure on the first must stop the whole run
    fetcher = FakeFetcher({"FCX": [_fetched("fcx-a")], "SCCO": [_fetched("scco-a")]})
    ext = Extractor(client=_AuthLLM(), universe=uni)
    with Buffer(":memory:") as buf:
        r = sweep(buf=buf, uni=uni, fetcher=fetcher, extractor=ext,
                  tickers=["FCX", "SCCO"], forms=["8-K"], limit=1)
        assert r.aborted and r.extracted == 0
        assert r.fetched == 1        # bailed on the first filing, never reached SCCO
        assert buf.count_extractions() == 0

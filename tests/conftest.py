"""Hermetic test fixtures — no network, no API keys. Env is set (and a small
buffer + price CSVs seeded) at import time so the API tests see a ready backend.
"""

from __future__ import annotations

import os
import tempfile
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from filingsignal.env import repo_root

_TMP = Path(tempfile.mkdtemp(prefix="filingsignal-tests-"))
_BUF = _TMP / "buffer.sqlite"
_PRICES = _TMP / "prices"
_PRICES.mkdir(exist_ok=True)

os.environ["FILINGSIGNAL_BUFFER_PATH"] = str(_BUF)
os.environ["FILINGSIGNAL_PRICES_DIR"] = str(_PRICES)
os.environ["FILINGSIGNAL_UNIVERSE_DIR"] = str(repo_root() / "universe")
os.environ["FILINGSIGNAL_API_KEY"] = "test-key"
os.environ["FILINGSIGNAL_FORECAST_QUARTER"] = "2026 Q3"
os.environ["FILINGSIGNAL_BACKTEST_SINCE"] = "2025 Q1"
os.environ.pop("FILINGSIGNAL_SEC_IDENTITY", None)

# Hermetic: never read the developer's real .env (it now holds live API keys and
# a SEC identity that would leak into tests). Mark it loaded so load_env() no-ops.
import filingsignal.env as _env  # noqa: E402
_env._loaded = True

from filingsignal.buffer import Buffer, EffectRow  # noqa: E402
from filingsignal.llm.base import Capabilities, LLMResult, StopReason  # noqa: E402
from filingsignal.models import (  # noqa: E402
    DatedEffect, Direction, ExtractedFiling, FetchedFiling, Magnitude, Perspective,
)
from filingsignal.universe import load_universe  # noqa: E402


def _eff(mat, persp, dirn, mag, ws, we, quote):
    return DatedEffect(material=mat, perspective=persp, direction=dirn, magnitude=mag,
                       window_start=date.fromisoformat(ws), window_end=date.fromisoformat(we),
                       rationale=f"{mat} plan", evidence_quote=quote, source_span="Item")


def _seed():
    seed = [
        ExtractedFiling(ticker="FCX", cik="0000831259", filing_type="8-K", filing_date=date(2026, 6, 23),
                        accession_number="fcx-8k-1", summary="FCX Q2 earnings; copper guidance up.",
                        dated_effects=[_eff("Copper", Perspective.producer, Direction.increase, Magnitude.large,
                                            "2026-07-01", "2026-09-30", '"~750 million pounds of copper"')],
                        extractor_confidence=0.92, extractor_model="fake",
                        extraction_warnings=["exhibit 409K chars"]),
        ExtractedFiling(ticker="ETN", cik="x", filing_type="10-Q", filing_date=date(2026, 5, 30),
                        accession_number="etn-10q-1", summary="Eaton grid-infra backlog strengthens.",
                        dated_effects=[_eff("Copper", Perspective.consumer, Direction.increase, Magnitude.large,
                                            "2026-07-01", "2026-09-30", '"order intake up 31% YoY"')],
                        extractor_confidence=0.81, extractor_model="fake"),
        ExtractedFiling(ticker="MP", cik="x", filing_type="10-Q", filing_date=date(2026, 6, 26),
                        accession_number="mp-10q-1", summary="MP magnet ramp; vague dates.",
                        dated_effects=[_eff("Rare Earths", Perspective.producer, Direction.increase, Magnitude.small,
                                            "2026-10-01", "2026-12-31", '"ramping magnet production"')],
                        extractor_confidence=0.64, extractor_model="fake",
                        extraction_warnings=["2 effects dropped: unbounded window"]),
    ]
    names = {"FCX": "Freeport-McMoRan", "ETN": "Eaton Corp", "MP": "MP Materials"}
    with Buffer(str(_BUF)) as b:
        for s in seed:
            b.upsert(s, company_name=names[s.ticker])
        b.upsert_rating(material="Copper", quarter="2026 Q3",
                        prose="Copper #1: FCX and ETN both point up.",
                        supporting={"tickers": ["FCX", "ETN"]}, model="fake")

    idx = pd.date_range("2024-10-01", "2026-07-15", freq="W")
    rng = np.random.default_rng(3)
    for i, tk in enumerate(["COPX", "GDX", "URNM", "SLX", "SIL", "REMX", "SPY"]):
        close = 100 * np.exp(np.cumsum(rng.normal(0.002 + 0.0004 * i, 0.025, len(idx))))
        pd.DataFrame({"date": idx.date, "close": close}).to_csv(_PRICES / f"{tk}.csv", index=False)


_seed()


class FakeLLM:
    """LLMClient stub: returns queued texts (or one payload repeatedly)."""

    model = "fake"

    def __init__(self, texts, *, native_schema=False):
        self._texts = list(texts) if isinstance(texts, (list, tuple)) else [texts]
        self._i = 0
        self.capabilities = Capabilities(native_schema=native_schema)

    def complete(self, **kw):
        t = self._texts[min(self._i, len(self._texts) - 1)]
        self._i += 1
        if isinstance(t, LLMResult):
            return t
        return LLMResult(text=t, stop_reason=StopReason.complete)


@pytest.fixture
def uni():
    return load_universe(Path(os.environ["FILINGSIGNAL_UNIVERSE_DIR"]) / "materials.yaml")


@pytest.fixture
def buffer_path():
    return str(_BUF)


@pytest.fixture
def fake_llm():
    return FakeLLM


@pytest.fixture
def make_effect():
    def _f(tk, mat, persp, dirn, mag, filed, ws, we, conf=0.8):
        return EffectRow(ticker=tk, company_name=tk, accession_number=tk + filed, form="8-K",
                         filing_date=date.fromisoformat(filed), material=mat, perspective=persp,
                         direction=dirn, magnitude=mag, window_start=date.fromisoformat(ws),
                         window_end=date.fromisoformat(we), rationale="r", evidence_quote="q",
                         source_span="", confidence=conf)
    return _f


@pytest.fixture
def fetched_8k():
    return FetchedFiling(ticker="FCX", cik="0000831259", company_name="Freeport-McMoRan", form="8-K",
                         filing_date=date(2026, 7, 23), accession_number="fcx-8k-new",
                         sections={"exhibit": "We expect ~750 million pounds of copper in Q3 2026."},
                         items=["2.02", "7.01"])

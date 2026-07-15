"""Unit tests for the demo-token-gated live extraction endpoint."""

from __future__ import annotations

import time
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from algo_trade.models import DatedEffect, Direction, ExtractedFiling, Magnitude
from api.deps import get_settings
from api.services import extract_job as svc


class FakeFetched:
    def __init__(self, ticker: str, accession: str) -> None:
        self.ticker = ticker
        self.company_name = f"{ticker} Corp"
        self.form = "10-Q"
        self.filing_date = date(2026, 5, 1)
        self.accession_number = accession


class FakeFetcher:
    def __init__(self, filings: list[FakeFetched]) -> None:
        self._filings = filings

    def fetch(self, *, ticker: str, forms: list[str], limit: int):
        return self._filings[:limit]


class FakeExtractor:
    def extract(self, fetched: FakeFetched) -> ExtractedFiling:
        return ExtractedFiling(
            ticker=fetched.ticker,
            cik="0000000001",
            filing_type=fetched.form,
            filing_date=fetched.filing_date,
            accession_number=fetched.accession_number,
            dated_effects=[
                DatedEffect(
                    sector="copper",
                    direction=Direction.increase,
                    magnitude=Magnitude.large,
                    window_start=date(2026, 6, 1),
                    window_end=date(2026, 12, 31),
                    rationale="fake",
                    source_span="Item 7",
                )
            ],
            flagged_risks=[],
            extractor_confidence=0.8,
            extractor_model="fake-model",
            extracted_at=datetime(2026, 7, 15, tzinfo=timezone.utc),
        )


def _reset_job_state() -> None:
    svc._filings_extracted_total = 0
    svc._status.update(
        state="idle", ticker=None, forms=[], started_at=None, finished_at=None,
        filings_done=0, effects_found=0, events=[], error=None,
    )
    svc._status["events"] = []


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGO_TRADE_DEMO_TOKEN", "tok")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("ALGO_TRADE_SEC_IDENTITY", "Test test@example.com")
    monkeypatch.setenv("ALGO_TRADE_BUFFER_PATH", str(tmp_path / "buf.sqlite"))
    get_settings.cache_clear()
    _reset_job_state()
    monkeypatch.setattr(
        svc, "_fetcher_factory", lambda identity: FakeFetcher([FakeFetched("FCX", "ACC-9")])
    )
    monkeypatch.setattr(svc, "_extractor_factory", lambda: FakeExtractor())

    from api.main import app

    yield TestClient(app)
    get_settings.cache_clear()
    _reset_job_state()


def _wait_done(client: TestClient, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get(
            "/api/v1/extract/status", headers={"X-Demo-Token": "tok"}
        ).json()
        if status["state"] in ("done", "error"):
            return status
        time.sleep(0.05)
    raise AssertionError("job did not finish in time")


def test_extract_requires_token(client) -> None:
    assert client.post("/api/v1/extract", json={"ticker": "FCX"}).status_code == 401
    assert client.get("/api/v1/extract/status").status_code == 401
    wrong = client.post(
        "/api/v1/extract", json={"ticker": "FCX"}, headers={"X-Demo-Token": "nope"}
    )
    assert wrong.status_code == 401


def test_extract_runs_and_upserts(client, tmp_path) -> None:
    response = client.post(
        "/api/v1/extract", json={"ticker": "fcx"}, headers={"X-Demo-Token": "tok"}
    )
    assert response.status_code == 200
    status = _wait_done(client)
    assert status["state"] == "done"
    assert status["filings_done"] == 1
    assert status["effects_found"] == 1
    assert status["budget_used"] == 1

    from algo_trade.buffer import Buffer

    with Buffer(str(tmp_path / "buf.sqlite")) as buf:
        assert buf.count_extractions() == 1


def test_extract_rejects_invalid_ticker(client) -> None:
    response = client.post(
        "/api/v1/extract", json={"ticker": "not a $tik"}, headers={"X-Demo-Token": "tok"}
    )
    assert response.status_code == 422


def test_extract_budget_cap(client, monkeypatch) -> None:
    monkeypatch.setenv("ALGO_TRADE_DEMO_MAX_FILINGS", "1")
    client.post("/api/v1/extract", json={"ticker": "FCX"}, headers={"X-Demo-Token": "tok"})
    _wait_done(client)
    blocked = client.post(
        "/api/v1/extract", json={"ticker": "GM"}, headers={"X-Demo-Token": "tok"}
    )
    assert blocked.status_code == 429
    assert "budget" in blocked.json()["message"].lower()


def test_extract_unconfigured_without_identity(client, monkeypatch) -> None:
    monkeypatch.delenv("ALGO_TRADE_SEC_IDENTITY", raising=False)
    response = client.post(
        "/api/v1/extract", json={"ticker": "FCX"}, headers={"X-Demo-Token": "tok"}
    )
    assert response.status_code == 503

from fastapi.testclient import TestClient

from filingsignal.api.main import app

client = TestClient(app)


def test_meta():
    r = client.get("/api/v1/meta")
    assert r.status_code == 200
    assert r.json()["counts"]["extractions"] == 3


def test_forecast_contract():
    r = client.get("/api/v1/forecast")
    assert r.status_code == 200
    j = r.json()
    assert j["quarter"] == "2026 Q3"
    assert j["materials"][0]["material"] == "Copper"
    assert len(j["trend"]) == 4
    # Agent #2's stored recommendation for the pick+quarter rides along
    assert j["rating"]["material"] == "Copper"
    assert j["rating"]["quarter"] == "2026 Q3"
    assert "point up" in j["rating"]["prose"]
    assert isinstance(j["rating"]["supporting"], list)


def test_filings_and_detail():
    r = client.get("/api/v1/filings")
    assert r.status_code == 200
    filings = r.json()
    assert len(filings) == 3
    by_ticker = {f["ticker"]: f for f in filings}
    assert by_ticker["MP"]["status"] == "Needs review"   # conf 0.64
    assert by_ticker["ETN"]["perspective"] == "consumer"
    assert by_ticker["FCX"]["status"] == "Extracted"
    assert client.get("/api/v1/filings/fcx-8k-1").status_code == 200
    assert client.get("/api/v1/filings/nope").status_code == 404


def test_backtest_available():
    j = client.get("/api/v1/backtest").json()
    assert j["available"] is True and len(j["metrics"]) == 6
    # every quarter report carries the stored recommendation slot (None if unrated)
    assert j["quarterReports"]
    assert all("rating" in qr for qr in j["quarterReports"])


def test_rating():
    j = client.get("/api/v1/rating/copper").json()
    assert j["available"] is True and "point up" in j["prose"]


def test_extract_auth():
    assert client.post("/api/v1/extract", json={"tickers": ["FCX"]}).status_code == 401
    assert client.post("/api/v1/extract", json={"tickers": ["FCX"]},
                       headers={"Authorization": "Bearer wrong"}).status_code == 401
    # valid key but no SEC identity configured -> 503
    r = client.post("/api/v1/extract", json={"tickers": ["FCX"]},
                    headers={"Authorization": "Bearer test-key"})
    assert r.status_code == 503
    assert client.post("/api/v1/extract", json={"tickers": []},
                       headers={"Authorization": "Bearer test-key"}).status_code == 422

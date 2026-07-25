import json

from filingsignal.api.services.analysis import backtest_payload, forecast_payload
from filingsignal.api.config import Settings
from filingsignal.api.deps import get_universe
from filingsignal.buffer import Buffer
from filingsignal.env import env_path


def _settings():
    return Settings.from_env()


def test_backtest_payload_shapes_and_json():
    s = _settings()
    with Buffer(str(s.buffer_path)) as b:
        res = backtest_payload(b, get_universe(), s)
    assert res["available"] is True
    for key in ("quarters", "returns", "rankIC", "decomp", "metrics", "quarterCalls", "hitgrid"):
        assert key in res
    for series in ("strategy", "spy", "eqweight", "random", "hindsight"):
        assert series in res["returns"]
    assert len(res["metrics"]) == 6
    json.dumps(res)  # must be serializable


def test_forecast_payload_shapes():
    s = _settings()
    with Buffer(str(s.buffer_path)) as b:
        res = forecast_payload(b, get_universe(), s)
    assert res["quarter"] == "2026 Q3"
    row = res["materials"][0]
    assert set(row.keys()) == {"material", "etf", "z", "producerScore", "consumerScore", "filings", "rank"}
    assert row["material"] == "Copper"  # top pick from seeded data

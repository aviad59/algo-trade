# Python tests

Tests are split by scope:

| Directory | Scope | Run |
|-----------|--------|-----|
| [`unit/`](unit/) | Single module, hermetic — fakes only, no network | `pytest tests/unit` |
| [`integration/`](integration/) | Multi-module flows — buffer + pipeline + FastAPI | `pytest tests/integration` |

Run everything from the repo root:

```bash
python -m pytest
```

## Unit tests (`tests/unit/`)

One package or service at a time. No live Anthropic calls, no SEC network, no full HTTP stack unless mocking dependencies.

- `test_buffer_*.py` — SQLite schema and `Buffer` store
- `test_env.py`, `test_llm_config.py` — configuration loading
- `test_extractor.py`, `test_recommender.py` — agents with fake Anthropic clients
- `test_fetcher.py`, `test_timeline.py`, `test_timer.py` — pipeline stages
- `test_api_config.py`, `test_forecast_service.py` — API settings and ranking service (direct function calls)
- `test_plot.py` — matplotlib/plotly chart output

## Integration tests (`tests/integration/`)

End-to-end paths the UI depends on: seeded buffer → FastAPI `TestClient` → JSON contract.

| File | Focus |
|------|--------|
| `test_api_smoke.py` | Health, universe, empty buffer, 404 |
| `test_api_forecast.py` | Material forecast, ranking/summary, recommender modes, pipeline parity |
| `test_api_extractions.py` | Explorer filters, detail drill-down, pagination, sector normalization |

Shared fixtures live in [`integration/conftest.py`](integration/conftest.py).

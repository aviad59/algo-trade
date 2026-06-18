# Backend (mock data and API)

This folder supports the **FilingSignal web UI** and the shared JSON contract. The **live Python pipeline** lives in [`src/algo_trade/`](../src/algo_trade/); this folder adds mock snapshots and the read-only HTTP API.

## Layout

```
backend/
  api/                   # FastAPI serving layer (GET /api/v1/*)
  universe/              # Canonical reference data (manufacturers, materials, instrument map)
  mock/v1/               # Demo API snapshots — same shapes as /api/v1
  scripts/
    validate-mock-contract.py
```

| Path | Purpose |
|------|---------|
| [`universe/`](universe/README.md) | Input universe and material vocabulary for agents and validation |
| [`api/`](api/main.py) | FastAPI app — buffer → forecast JSON contract |
| [`mock/v1/`](mock/v1/manifest.json) | Static JSON bundle served to the frontend in mock mode |
| [`scripts/`](scripts/) | CI validation of the mock bundle against [HLD §8](../docs/hld-web-interface.md) |

## Run the live API

```bash
pip install -e ".[dev]"
algo-trade-api
```

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ALGO_TRADE_BUFFER_PATH` | `data/buffer.sqlite` | SQLite buffer file |
| `ALGO_TRADE_FORECAST_SINCE` | 12 months ago | Forecast window start |
| `ALGO_TRADE_FORECAST_UNTIL` | today | Forecast window end / `as_of` |
| `ALGO_TRADE_UNIVERSE_DIR` | `backend/universe` | Universe JSON directory |
| `ALGO_TRADE_CORS_ORIGINS` | `http://localhost:5173,...` | CORS allowlist |

Then point the frontend at the API:

```bash
cd frontend
VITE_API_BASE=/api/v1 VITE_DATA_SOURCE=api npm run dev
```

Vite proxies `/api/v1` → `http://localhost:8000`.

## Validate mock bundle

From repo root:

```bash
py backend/scripts/validate-mock-contract.py
```

## Python pipeline (lives in `src/algo_trade/`)

| Component | Status | Location |
|-----------|--------|----------|
| EDGAR fetcher | Done | [`src/algo_trade/fetcher.py`](../src/algo_trade/fetcher.py) |
| Extractor (Agent #1) | Done | [`src/algo_trade/extractor.py`](../src/algo_trade/extractor.py) |
| Buffer store | Done | [`src/algo_trade/buffer/store.py`](../src/algo_trade/buffer/store.py) |
| Timeline + timer | Done | [`src/algo_trade/timeline.py`](../src/algo_trade/timeline.py), [`timer.py`](../src/algo_trade/timer.py) |
| Recommender (Agent #2) | Planned | [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) |

## Future

- Replace rule-based ranking in the API with Agent #2 output
- Optional export script: buffer / forecast output → `mock/v1/` for offline UI testing

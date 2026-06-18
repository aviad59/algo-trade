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

From the **repository root** (after `pip install -e ".[dev]"`):

```bash
algo-trade-api
```

Serves `GET /api/v1/*` at http://localhost:8000 (host/port from `ALGO_TRADE_API_HOST` / `ALGO_TRADE_API_PORT` in `.env`). Interactive docs: http://localhost:8000/docs

## Run the frontend against the API

Terminal 1 — API:

```bash
algo-trade-api
```

Terminal 2 — UI (set `VITE_API_BASE=/api/v1` and `VITE_DATA_SOURCE=api` in repo-root `.env` first):

```bash
cd frontend
npm run dev
```

Vite proxies `/api/v1` → `http://localhost:8000`.

Copy [`.env.example`](../.env.example) to `.env` at the **repository root** and edit values there. All backend, pipeline, and frontend (`VITE_*`) settings live in that one file.

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | *(empty)* | Required for Extractor / Recommender |
| `ALGO_TRADE_BUFFER_PATH` | `data/buffer.sqlite` | SQLite buffer file |
| `ALGO_TRADE_FORECAST_SINCE` | 12 months ago | Forecast window start |
| `ALGO_TRADE_FORECAST_UNTIL` | today | Forecast window end / `as_of` |
| `ALGO_TRADE_UNIVERSE_DIR` | `backend/universe` | Universe JSON directory |
| `ALGO_TRADE_CORS_ORIGINS` | `http://localhost:5173,...` | CORS allowlist |
| `ALGO_TRADE_RANKING_MODE` | `rules` | `rules` (CI-safe) or `recommender` |
| `ALGO_TRADE_API_HOST` | `0.0.0.0` | API bind host |
| `ALGO_TRADE_API_PORT` | `8000` | API port (Vite proxy uses this too) |
| `ALGO_TRADE_RECOMMENDER_MODEL` | *(via `resolve_model`)* | Override recommender model id |
| `ALGO_TRADE_EXTRACTOR_MODEL` | *(via `resolve_model`)* | Override extractor model id |
| `ALGO_TRADE_LLM_MODEL` | *(via `resolve_model`)* | Shared fallback for both agents |
| `ALGO_TRADE_DEFAULT_EXTRACTOR_MODEL` | `claude-opus-4-7` | Extractor fallback model |
| `ALGO_TRADE_DEFAULT_RECOMMENDER_MODEL` | `claude-opus-4-7` | Recommender fallback model |
| `ALGO_TRADE_EXTRACTOR_MAX_TOKENS` | `16000` | Extractor output ceiling |
| `ALGO_TRADE_EXTRACTOR_EFFORT` | `high` | Extractor effort level |
| `ALGO_TRADE_RECOMMENDER_MAX_TOKENS` | `8000` | Recommender output ceiling |
| `ALGO_TRADE_RECOMMENDER_EFFORT` | `high` | Recommender effort level |
| `ALGO_TRADE_RECOMMENDER_MAX_EXTRACTIONS` | `100` | Max extractions in ranking digest |
| `ALGO_TRADE_TIMER_LOOKAHEAD_MONTHS` | `3` | Forward-AUC window |
| `ALGO_TRADE_TIMER_BUY_THRESHOLD` | `0.0` | BUY signal threshold |
| `ALGO_TRADE_SEC_IDENTITY` | *(empty)* | Default SEC identity for `algo-trade-extract` |
| `ALGO_TRADE_EXTRACT_FORM` | `10-K` | Default form for `algo-trade-extract` |
| `ALGO_TRADE_EXTRACT_LIMIT` | `1` | Default filing limit for `algo-trade-extract` |
| `VITE_API_BASE` | `/mock/v1` | Frontend JSON base path |
| `VITE_DATA_SOURCE` | `mock` | `mock` or `api` |

Shell exports override `.env` (useful in CI).

## Configuration

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
| Recommender (Agent #2) | Done | [`src/algo_trade/recommender.py`](../src/algo_trade/recommender.py) |
| Plot | Done | [`src/algo_trade/plot.py`](../src/algo_trade/plot.py) |

## Future

- Optional export script: buffer / forecast output → `mock/v1/` for offline UI testing

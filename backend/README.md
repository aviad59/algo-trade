# Backend (mock data and contract support)

This folder supports the **FilingSignal web UI** and the shared JSON contract. It does **not** contain the live Python pipeline — that lives in [`src/algo_trade/`](../src/algo_trade/) (fetcher, extractor, buffer schema).

## Layout

```
backend/
  universe/              # Canonical reference data (manufacturers, materials, instrument map)
  mock/v1/               # Demo API snapshots — same shapes as the planned /api/v1 contract
  scripts/
    validate-mock-contract.py
```

| Path | Purpose |
|------|---------|
| [`universe/`](universe/README.md) | Input universe and material vocabulary for agents and validation |
| [`mock/v1/`](mock/v1/manifest.json) | Static JSON bundle served to the frontend in mock mode |
| [`scripts/`](scripts/) | CI validation of the mock bundle against [HLD §8](../docs/hld-web-interface.md) |

## Universe data: two locations (intentional)

| Location | Role |
|----------|------|
| `backend/universe/` | **Source of truth** — full reference files used by the pipeline vocabulary contract and integrity checks |
| `backend/mock/v1/universe/` | **API snapshot** — subset copied into the mock bundle for the web UI (demo manufacturers, materials, instruments) |

These are not duplicates to delete blindly: the mock tree must match what [`frontend/`](../frontend/) fetches under `/mock/v1/`. A future exporter will generate `mock/v1/` from pipeline output; until then both are maintained for the offline demo.

There is **no** tracked `universe/` at the repo root. If you see one locally, it is a leftover from before the web reorganization — use `backend/universe/` instead.

## Validate mock bundle

From repo root:

```bash
py backend/scripts/validate-mock-contract.py
```

## Python pipeline (lives elsewhere)

| Component | Status | Location |
|-----------|--------|----------|
| EDGAR fetcher | Done | [`src/algo_trade/fetcher.py`](../src/algo_trade/fetcher.py) |
| Extractor (Agent #1) | Done | [`src/algo_trade/extractor.py`](../src/algo_trade/extractor.py) |
| Buffer schema | Done | [`src/algo_trade/buffer/schema.sql`](../src/algo_trade/buffer/schema.sql) |
| Buffer store (`upsert`, queries) | Planned | `feature/buffer-store` |
| Timeline aggregator, buy/sell timer, recommender | Planned | [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) |

## Future (this folder)

- HTTP serving layer (`GET /api/v1/*`) exposing pipeline snapshots in the same shapes as `mock/v1/`
- Optional export script: buffer / forecast output → `mock/v1/` for local UI testing

Until then, the frontend stays in mock mode — see [`frontend/README.md`](../frontend/README.md).

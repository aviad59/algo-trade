# FilingSignal — Web UI

Material demand signals from SEC filings. React + TypeScript + Vite demo app: forecast dashboard, material detail, company/filing audit, and Explorer.

## Prerequisites

- Node.js 20+
- npm

## Setup

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

In development, mock JSON is served from `backend/mock/v1` via a Vite middleware (no copy step required). Production builds still sync mock files into `public/mock/v1` via `prebuild`.

## Environment

All frontend and backend settings live in the **repo-root** `.env`. Copy [`.env.example`](../.env.example) to `.env` at the repository root (not inside `frontend/`).

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE` | `/mock/v1` | JSON base path |
| `VITE_DATA_SOURCE` | `mock` | `mock` (static JSON) or `api` (FastAPI backend) |
| `VITE_MOCK_FALLBACK` | `true` | When `api`, use `/mock/v1` if live requests fail |

See [backend/README.md](../backend/README.md) for the full variable list.

### Live API dev

Full pipeline steps (extract → verify → API → UI) are in the main [README — Run the pipeline on live data](../README.md#run-the-pipeline-on-live-data). Short version:

```bash
# Terminal 1 — repo root: populate buffer first (see main README)
algo-trade-extract TSLA GM FCX -v --form 10-Q --limit 1
algo-trade-api

# Terminal 2 — frontend (Vite loads repo-root .env; proxies /api/v1)
cd frontend && npm run dev
```

Set in repo-root `.env`:

```
VITE_API_BASE=/api/v1
VITE_DATA_SOURCE=api
```

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Dev server (port 5173) |
| `npm run build` | Typecheck + production build |
| `npm run preview` | Preview production build |
| `npm run test` | Vitest unit tests |
| `npm run test:e2e` | Playwright E2E (port 5174) |
| `npm run sync-mock` | Copy `backend/mock/v1` → `public/mock/v1` |
| `npm run record-demo` | Record UI walkthrough → `docs/demo/` (gitignored) |
| `npm run lint` | ESLint |

## Routes

| Path | Page |
|------|------|
| `/` | Forecast dashboard |
| `/materials/:materialId` | Material detail + chart |
| `/companies/:ticker` | Company filings |
| `/filings/:extractionId` | Filing audit trail |
| `/explorer` | Ticker + date query |
| `/about` | About + disclaimer |

## Testing

```bash
# Unit tests (contract, filters, URL params)
npm test

# E2E — starts its own dev server on port 5174
npm run test:e2e
```

Validate the mock bundle from the repo root:

```bash
py backend/scripts/validate-mock-contract.py
```

## Docs

- [HLD](../docs/hld-web-interface.md)
- [Implementation plan](../docs/implementation-plan-web.md)
- [Playwright MCP](../docs/playwright-mcp.md)

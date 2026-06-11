# Frontend

Web interface for the algo-trade forecast demo (React + TypeScript + Vite).

## Setup

```bash
cd frontend
npm install
npm run sync-mock   # copy backend/mock/v1 -> public/mock/v1
npm run dev
```

Open http://localhost:5173

## Environment

Copy `.env.example` to `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE` | `/mock/v1` | JSON base path |
| `VITE_DATA_SOURCE` | `mock` | `mock` or `api` |

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Dev server |
| `npm run build` | Production build |
| `npm run preview` | Preview production build |
| `npm run sync-mock` | Refresh mock JSON from `backend/mock/v1` |

## Routes

| Path | Page |
|------|------|
| `/` | Forecast dashboard |
| `/materials/:materialId` | Material detail |
| `/companies/:ticker` | Company detail |
| `/filings/:extractionId` | Filing audit |
| `/explorer` | Ticker + date query |
| `/about` | Disclaimer + about |

See [implementation plan](../docs/implementation-plan-web.md) for phased delivery status.

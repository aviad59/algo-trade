# Deploying FilingSignal

One container serves everything: the React UI, the `/api/v1` JSON API, and the
pre-baked data (SQLite buffer of extracted filings, cached ETF prices, and a
frozen Agent #2 ranking snapshot).

**Cost model — zero public LLM spend, gated live AI:**

- **Public visitors** get the snapshot ranking — real Agent #2 output,
  generated once locally, served as JSON. No API key touched, no per-visitor
  cost, instant loads. (If the snapshot is missing or stale the API falls
  back to rules-based ranking, still free.)
- **Demo-token holders** (e.g. a reviewer given a
  `https://your-space/?demo=SECRET` link) trigger a *live* Agent #2 call.
  The frontend stores the token and sends it as an `X-Demo-Token` header; a
  wrong or absent token silently gets the public view. Results are cached
  per buffer version, so even enthusiastic clicking costs one LLM call per
  container boot. On `claude-haiku-4-5` that call costs ~1–2 cents.

## Prerequisites

The image bundles three gitignored artifacts, so build from a working tree
that has them:

- `data/buffer.sqlite` — populate with `algo-trade-extract` (needs
  `ANTHROPIC_API_KEY` + `ALGO_TRADE_SEC_IDENTITY` at extraction time only)
- `data/prices/*.csv` — populate with
  `algo-trade-backtest --yfinance --save-prices data/prices`
- `data/ranking-snapshot.json` — populate with
  `python backend/scripts/make-ranking-snapshot.py` (one Agent #2 call with
  your local key; re-run after every extraction batch — a stale snapshot is
  ignored, never served)

Never bake `.env` into the image (`.dockerignore` already excludes it).

## Local smoke test

```bash
docker build -t filingsignal .
docker run -p 7860:7860 filingsignal
# open http://localhost:7860  (UI, /api/v1/*, /backtest — all one port)
```

Without Docker (what the Dockerfile does, by hand):

```bash
cd frontend && VITE_DATA_SOURCE=api VITE_API_BASE=/api/v1 npm run build && cd ..
uvicorn api.main:app --host 0.0.0.0 --port 7860
# api.main auto-serves frontend/dist when it exists
```

## HuggingFace Spaces (recommended)

1. Create a Space → SDK: **Docker** → visibility as you like.
2. Push this repo's contents (including `data/buffer.sqlite` and
   `data/prices/` — the Space repo is separate from GitHub, so committing the
   baked data there is fine) with this front-matter in the Space `README.md`:

   ```yaml
   ---
   title: FilingSignal
   emoji: 📈
   sdk: docker
   app_port: 7860
   ---
   ```

3. Optional secrets (Space settings → Variables and secrets) — only needed
   for the gated live-AI demo:
   - `ANTHROPIC_API_KEY` — your key (never in the repo)
   - `ALGO_TRADE_DEMO_TOKEN` — any secret string; hand
     `https://your-space/?demo=<that string>` to the reviewer
   - `ALGO_TRADE_RECOMMENDER_MODEL=claude-haiku-4-5` — pennies per live call
   - `ALGO_TRADE_EXTRACTOR_MODEL=claude-haiku-4-5` +
     `ALGO_TRADE_SEC_IDENTITY="Your Name you@example.com"` — enables the
     token-gated **Pull new filings** panel (see below)
   - Leave `ALGO_TRADE_RANKING_MODE` unset (defaults to `rules`): the public
     path serves snapshot/rules and never spends tokens; only the token
     header unlocks live calls.

Spaces injects `PORT=7860`; the CMD honors it.

## The live-extraction demo (token holders only)

With the token, the Explorer page shows a **"Pull new filings — live
pipeline"** panel: type a ticker, and the server fetches its latest filings
from EDGAR, runs Agent #1 on each, and upserts into the buffer — the
dashboard, ranking, and backtest all update because every cache keys on the
buffer version. `POST /api/v1/extract` returns 401 without the token.

Spend is bounded three ways: the token gate, one job at a time, and a
per-boot budget (`ALGO_TRADE_DEMO_MAX_FILINGS`, default 20 filings ≈ well
under $1 on Haiku). Two properties worth knowing:

- A pull makes the baked ranking snapshot stale, so the *public* ranking
  falls back to rules until the container restarts. Token holders see the
  live recommender anyway. This is by design — stale AI text is never served.
- The container filesystem is ephemeral: restarting the Space resets the
  buffer to the baked state. Reviewer pulls are sandboxed per boot.

## Any other Docker host (Render, Railway, Fly.io)

Same image; expose the injected `$PORT`. Nothing else to configure.

## What the deployed app shows

- **Forecast dashboard** — ranked materials + signal curves from the bundled
  49-filing buffer.
- **Explorer / filing audit** — every extraction with its verbatim source
  spans from the SEC filings.
- **Backtest** — the honest walk-forward replay against the bundled prices:
  per-sector alpha, exposure, the trade blotter, and open positions.

To refresh data later: run `algo-trade-extract` + the price fetch locally,
then rebuild/redeploy the image with the updated `data/`.

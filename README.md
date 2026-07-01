# algo-trade

An agentic pipeline that reads U.S. SEC EDGAR filings, extracts each company's forward-looking plans and sector dependencies, and uses a second LLM to recommend which sector(s) look most attractive to invest in.

> ⚠️ **Disclaimer:** This project is for research and educational purposes only. Nothing produced by this tool is financial advice. LLMs hallucinate, filings can be misread, and markets do not care what a model thinks. Do your own due diligence.

---

## Quickstart — run the whole thing locally

```bash
git clone https://github.com/aviad59/algo-trade.git
cd algo-trade
python dev.py
```

That's it. The first run takes ~1 minute (it does `pip install -e ".[dev]"` and `npm install` once), then opens <http://localhost:5173> in your browser.

**Requirements:** Python 3.11+ and Node 20+. Nothing else.

**No Anthropic API key?** Still works — the backend boots in read-only mode and the frontend falls back to bundled mock data, so you see a working dashboard immediately. Add `ANTHROPIC_API_KEY=sk-ant-...` to `.env` later (a template `.env` is created on first run) to enable live extraction.

### Variations

```bash
python dev.py --backend-only    # just the API on :8000 (for curl / Postman)
python dev.py --frontend-only   # just the UI on :5173 (mock data only)
python dev.py --no-open         # full stack, don't auto-open the browser
```

Press **Ctrl-C** in the terminal to stop both processes cleanly.

---

## Repository layout

| Path | Role |
|------|------|
| [`dev.py`](dev.py) | One-command local dev launcher (backend + frontend + browser) |
| [`src/algo_trade/`](src/algo_trade/) | **Python pipeline** — fetcher, extractor (Agent #1), buffer, timeline, timer, recommender (Agent #2) |
| [`tests/`](tests/README.md) | Python tests — [`unit/`](tests/unit/) and [`integration/`](tests/integration/) |
| [`backend/`](backend/README.md) | **Web serving layer** — FastAPI (`GET /api/v1/*`), [`universe/`](backend/universe/README.md) reference JSON, [`mock/v1/`](backend/mock/v1/manifest.json) demo snapshots |
| [`frontend/`](frontend/README.md) | **FilingSignal** web UI (React) |
| [`.env.example`](.env.example) | Configuration template — copied to `.env` on first `python dev.py` |
| [`docs/`](docs/ARCHITECTURE.md) | Technical docs — see links below |
| [`examples/`](examples/) | Small pipeline usage examples |

### Documentation

| Doc | Audience |
|-----|----------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Pipeline stages, contracts, SQLite schema, design decisions |
| [hld-web-interface.md](docs/hld-web-interface.md) | Web UI boundaries and JSON API contract (v1) |
| [implementation-plan-web.md](docs/implementation-plan-web.md) | Web delivery phases and checklist |
| [playwright-mcp.md](docs/playwright-mcp.md) | E2E tests and optional Cursor browser MCP |

### Run the servers

From the repo root after `pip install -e ".[dev]"`:

```bash
# API server (FastAPI) — http://localhost:8000  (docs: /docs)
algo-trade-api
```

```bash
# Frontend (separate terminal) — http://localhost:5173
cd frontend
npm install
npm run dev
```

By default the UI uses static mock JSON (`VITE_DATA_SOURCE=mock`). To serve live forecast data from the buffer, set in repo-root `.env`:

```
VITE_API_BASE=/api/v1
VITE_DATA_SOURCE=api
```

Then run **both** commands above. Vite proxies `/api/v1` → `http://localhost:8000` (`ALGO_TRADE_API_PORT`).

See [Run the pipeline on live data](#run-the-pipeline-on-live-data) for the full fetch → extract → verify flow.

---

## The idea

Public companies in the U.S. are required to file detailed disclosures with the SEC (10-K, 10-Q, 8-K, S-1, etc.). Buried inside the boilerplate are the parts that actually matter to an investor:

- What the company **plans to do** next (new products, capex, M&A, expansion, restructuring)
- What sectors / suppliers / customers it **depends on**
- What risks it **flags** as material

Reading these filings by hand for hundreds of companies is not realistic. So we let an LLM do the first pass, save structured notes into a shared buffer, and then let a second LLM read across all of those notes and ask: *if all of this is roughly true, which sector has the strongest tailwind right now?*

---

## Architecture

```
        ┌────────────────────────┐
        │   Ticker / CIK list    │
        └───────────┬────────────┘
                    │
                    ▼
        ┌────────────────────────┐      ┌──────────────────────┐
        │  EDGAR Fetcher         │ ───▶ │  Raw filing cache    │
        │  (edgartools)          │      │  (handled by lib)    │
        └───────────┬────────────┘      └──────────────────────┘
                    │
                    ▼
        ┌────────────────────────────────────────┐
        │  Agent #1 — Extractor                  │
        │  Reads each filing and emits:          │
        │    - dated_effects[] (sector × time    │
        │      window × direction × magnitude)   │
        │    - flagged_risks[]                   │
        │    - confidence + source spans         │
        └───────────┬────────────────────────────┘
                    │
                    ▼
        ┌────────────────────────┐
        │  Side buffer           │
        │  SQLite (canonical)    │
        │  + DuckDB attached for │
        │  analytical reads      │
        └───────────┬────────────┘
                    │
        ┌───────────┴───────────────────┐
        ▼                               ▼
┌──────────────────────────┐   ┌──────────────────────────────┐
│  Sector Timeline         │   │  Agent #2 — Recommender      │
│  Aggregator              │   │  Reads the full buffer       │
│  Bins dated_effects by   │   │  and emits:                  │
│  sector × month, builds  │   │    - ranked sectors          │
│  per-sector time series  │   │    - rationale per sector    │
└───────────┬──────────────┘   │    - dissenting evidence     │
            │                  │    - cited filings           │
            ▼                  └──────────────────────────────┘
┌──────────────────────────┐
│  Buy/Sell Timer          │
│  Reads sector curves,    │
│  emits BUY / SELL dates  │
│  per sector (AUC-based)  │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│  Plot                    │
│  Sector signal vs. time, │
│  BUY/SELL markers        │
└──────────────────────────┘
```

Two agents, one buffer in between. The buffer is the contract — Agent #1 can be swapped out, Agent #2 can be swapped out, the buffer schema is what holds the system together. Downstream of the buffer the recommender and the timeline aggregator run independently — one answers *which* sector, the other answers *when*.

---

## Components

### 1. EDGAR Fetcher — built on [edgartools](https://github.com/dgunning/edgartools)

We don't write our own EDGAR client. `edgartools` (MIT-licensed) already gives us:

- Ticker → CIK resolution
- Typed `Company` / `Filing` objects for 10-K, 10-Q, 8-K, Form 4, 13F, etc.
- Section extraction out of the box (`Risk Factors`, `MD&A`, subsidiary lists)
- HTML → clean text/markdown conversion (intended for LLM consumption)
- Rate-limit awareness and smart caching — handles SEC's fair-access rules for us
- Identity is set once via `set_identity("your.email@example.com")` (no API key)

In practice our fetcher layer is a thin loop around `edgartools` that pulls the section text the extractor needs and passes it on. If we outgrow `edgartools` later we can drop in a custom client behind the same interface, but there's no reason to start there.

### 2. Agent #1 — Extractor

Per-filing LLM call. Output is **strictly structured** (JSON schema enforced), not free text. The key idea: every planned action gets pinned to a **time window**, a **direction** (the company expects to *increase* or *decrease* its consumption / exposure), and a **magnitude** (qualitative, e.g. small / moderate / large). This is what lets us build a time-series later.

```json
{
  "ticker": "TSLA",
  "cik": "0001318605",
  "filing_type": "10-Q",
  "filing_date": "2026-04-30",
  "dated_effects": [
    {
      "sector": "Lithium",
      "direction": "increase",
      "magnitude": "large",
      "window_start": "2026-05-01",
      "window_end": "2026-08-31",
      "rationale": "Cell line ramp at Nevada gigafactory scheduled to begin May",
      "source_span": "Item 2, MD&A, p.18"
    },
    {
      "sector": "Gold",
      "direction": "decrease",
      "magnitude": "moderate",
      "window_start": "2026-03-01",
      "window_end": "2026-06-30",
      "rationale": "Phasing out gold-plated connector SKU; substitute qualified Q1",
      "source_span": "Item 1A, Risk Factors, p.42"
    }
  ],
  "flagged_risks": ["Lithium supply concentration in Chile/Australia"],
  "extractor_confidence": 0.79
}
```

Rules the extractor must follow:

- Every effect must have `window_start` and `window_end`. If the filing only says "in the coming months" or "next year," the extractor resolves that against the **filing date** (e.g., "next year" from a 2026-04-30 filing → 2027-01-01 to 2027-12-31).
- Every effect must have a `source_span` pointing back to the filing. No span → dropped.
- `magnitude` is qualitative (`small` / `moderate` / `large`), not a dollar figure — companies rarely commit to exact numbers and we don't want to invent them. We convert magnitude to a numeric weight downstream (e.g., 0.3 / 0.6 / 1.0).
- `direction` is `increase` or `decrease` only. "Stable" is not interesting and gets dropped.

### 3. Side buffer

Three normalized SQLite tables. The schema is committed at [`src/algo_trade/buffer/schema.sql`](src/algo_trade/buffer/schema.sql) and is the contract between the extractor (writes) and everything downstream (reads): the timeline aggregator, the recommender, the web app, the backtest harness.

```
filings          (accession_number PK, ticker, cik, filing_type, filing_date, ...)
extractions      (id PK, accession_number FK, extractor_model, extractor_confidence, ...)
                  UNIQUE (accession_number, extractor_model)   — re-running upserts
dated_effects    (id PK, extraction_id FK, sector, direction, magnitude,
                  window_start, window_end, rationale, source_span)
flagged_risks    (id PK, extraction_id FK, risk)
extraction_warnings (id PK, extraction_id FK, warning)
```

Why SQLite:

- **One file**, ACID, indexed. A read-only web app can render the Lithium curve over the last 12 months from a single query (`(sector, window_start, window_end)` index) — JSONL would mean scanning every line on every page load.
- **CHECK constraints** at write time (`direction IN ('increase','decrease')`, `window_end >= window_start`, `length(source_span) > 0`) catch extractor regressions immediately, not three weeks later in the recommender.
- **Re-run semantics.** The UNIQUE `(accession_number, extractor_model)` means re-running with the same model is idempotent; re-running with a *different* model keeps both versions side-by-side. Useful for A/B-ing prompts and models without losing history.
- **DuckDB attaches the SQLite file for analytical reads** when the timeline aggregator needs columnar perf — `ATTACH 'buffer.sqlite' (TYPE sqlite, READ_ONLY)` — no copy, no second store to keep in sync.
- **Postgres is the upgrade path** if this ever gets a real multi-user web backend. Same DDL with two trivial type changes (see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) §"Upgrade path").

### 4. Agent #2 — Sector Recommender

Implemented in [`src/algo_trade/recommender.py`](src/algo_trade/recommender.py). Reads a **compact digest** of buffer extractions (not raw filings) and produces a ranked list of materials with rationale. Model selection is centralized in [`src/algo_trade/llm_config.py`](src/algo_trade/llm_config.py) (`resolve_model` — configurable via `.env`, not hardcoded).

```json
{
  "as_of": "2026-06-08",
  "ranked_materials": [
    {
      "material_id": "lithium",
      "name": "Lithium",
      "score": 0.87,
      "rationale": "TSLA and GM both flag large lithium increases in Q2–Q3.",
      "supporting_tickers": ["TSLA", "GM"],
      "dissenting_evidence": []
    }
  ],
  "recommender_model": "claude-opus-4-7"
}
```

Every claim the recommender makes must cite tickers from the buffer. Post-validation drops unknown `material_id` values and tickers not present in the digest.

In the Web API, ranking is **rule-based by default** (`ALGO_TRADE_RANKING_MODE=rules`, CI-safe). Set `ALGO_TRADE_RANKING_MODE=recommender` and provide `ANTHROPIC_API_KEY` to use Agent #2; the API falls back to rules on failure.

### 5. Sector Timeline Aggregator

This is what turns the buffer into a graph you can actually look at.

For each `dated_effect` in the buffer we have: `(sector, direction, magnitude, window_start, window_end)`. The aggregator:

1. **Bins time** into monthly buckets (configurable — weekly is fine for short horizons).
2. **For each effect, spreads its weight uniformly across the months it covers.** A "large increase" lasting 4 months contributes `+1.0 / 4 = +0.25` per month. A "moderate decrease" lasting 3 months contributes `-0.6 / 3 = -0.2` per month.
3. **Sums across all companies, per sector, per month.** Result: one time series per sector.

So for a sector like **Lithium**, you end up with something like:

```
month     signal
2026-03   +0.10   (one company ramping early)
2026-04   +0.10
2026-05   +1.45   (Tesla + 3 others ramp in May)
2026-06   +1.45
2026-07   +1.20
2026-08   +0.55
2026-09   -0.10   (one company winding down)
```

That's the curve. Plot it (matplotlib / plotly), overlay all sectors, and you can literally see which sectors are pulling demand forward into which months.

### 6. Buy/Sell Timer

The graph is interesting, but the question the user actually cares about is *when to buy and when to sell* the sector. We compute that from the curve itself — no extra LLM call needed.

**Default algorithm: forward-looking area under the curve.**

For each sector and each month `t`, compute:

```
forward_AUC(t) = Σ signal(t+1), signal(t+2), ..., signal(t+W)
```

where `W` is a look-ahead window (default: 3 months). This answers: *if I buy this sector today, how much narrated demand is queued up over the next W months?*

- **BUY signal:** the date where `forward_AUC` is rising and crosses a positive threshold. Intuition: demand is building and we're early.
- **SELL signal:** the date where `forward_AUC` peaks and starts declining. Intuition: the queued demand has played out, what's ahead is thinner.

In other words: **buy on the leading edge of the area, sell at the top of the area.** The "area under the graph" the user described is exactly `forward_AUC`.

Alternative strategies the timer module will ship with (toggleable):

- **Slope-based.** Buy when `d(signal)/dt` turns positive, sell when it turns negative. Faster, noisier.
- **Peak detection.** Find local maxima of `signal(t)` as sell dates; the leading inflection as buy dates. Robust but lagging.
- **Threshold + dwell.** Buy when `signal` exceeds threshold `θ` for `k` consecutive months. Conservative.

Output for one sector:

```json
{
  "sector": "Lithium",
  "as_of": "2026-06-08",
  "actions": [
    {"date": "2026-04-01", "action": "BUY",  "rationale": "forward_AUC ramping into May ramp"},
    {"date": "2026-08-01", "action": "SELL", "rationale": "forward_AUC peaked in July, declining"}
  ],
  "curve": [
    {"month": "2026-03", "signal":  0.10, "forward_AUC": 3.00},
    {"month": "2026-04", "signal":  0.10, "forward_AUC": 4.10},
    ...
  ]
}
```

### 7. Plot

Matplotlib (or Plotly for an interactive version). One line per sector, x-axis = time, y-axis = signal. BUY markers as green up-arrows, SELL markers as red down-arrows. Filing dates as faint vertical ticks so you can see *what* caused a spike.

### Important caveats about the timing signal

- This is a **narrative-derived** signal, not a price signal. It measures what companies *say* they will do, not what markets are pricing in. The market may have already priced it.
- Companies are optimistic about their own plans. A "ramp in May" sometimes happens in November.
- The signal is **strongest when many companies say the same thing about the same window**. A single ticker forecasting lithium demand is noise; ten of them is signal.
- This is why a backtest harness (see roadmap) is non-negotiable before treating any of this as actionable.

---

## Why two agents instead of one big prompt?

- **Cost.** Filings are huge. You don't want to re-feed 50 × 200-page 10-Ks into the recommender every time you want a new ranking.
- **Auditability.** The buffer is human-readable. You can see exactly what the extractor pulled and challenge it before the recommender ever sees it.
- **Composability.** You can re-run the recommender with a different prompt, a different model, or a different time window without touching the extractor.
- **Determinism where it counts.** Extraction is a narrow, schema-constrained task — easier to test and validate than open-ended "what should I buy."

---

## Tech stack

- **Language:** Python 3.11+
- **LLM client:** `anthropic` SDK — models configurable via `.env` (`ALGO_TRADE_EXTRACTOR_MODEL`, `ALGO_TRADE_RECOMMENDER_MODEL`, or shared `ALGO_TRADE_LLM_MODEL`; defaults in [`llm_config.py`](src/algo_trade/llm_config.py))
- **EDGAR client:** [`edgartools`](https://github.com/dgunning/edgartools) — handles fetching, section extraction, rate limits, caching
- **Web API:** FastAPI + uvicorn (`algo-trade-api`)
- **Frontend:** React + TypeScript + Vite (FilingSignal)
- **Storage:** SQLite as the canonical buffer (one file, ACID, indexed); DuckDB attached for analytical reads when needed. Schema in [`src/algo_trade/buffer/schema.sql`](src/algo_trade/buffer/schema.sql).
- **Validation:** `pydantic` for the in-process pipeline contract, SQL CHECK constraints for the on-disk one, Zod on the frontend
- **Timeline math:** `pandas` for the per-sector monthly bucketing, `numpy` for the forward-AUC sweep
- **Config:** repo-root `.env` loaded by [`src/algo_trade/env.py`](src/algo_trade/env.py) (`python-dotenv`); shell exports override `.env`
- **Plotting:** `matplotlib` (PNG/PDF/SVG); `plotly` optional for HTML (`pip install -e ".[plot]"`)

---

## Roadmap

- [x] EDGAR fetcher wrapper around `edgartools` — pulls 10-K / 10-Q with typed MD&A + Risk Factors, falls back to full text on 8-K and on parse failure. CLI: `algo-trade-fetch`.
- [x] Extractor agent — Claude Opus 4.7 by default, adaptive thinking, `output_config.format` JSON schema enforcement, prompt-cached system prompt, streaming. Drops effects without a `source_span` or with inverted date windows. Handles `refusal` / `max_tokens` / `model_context_window_exceeded` stop reasons.
- [x] Buffer -- SQLite schema + `Buffer` Python class (`upsert`, `effects_for_sector`, `filings_citing`). CLI: `algo-trade-extract`. 23 hermetic tests. See [`src/algo_trade/buffer/`](src/algo_trade/buffer/).
- [x] **Sector timeline aggregator** — monthly bucketing via [`src/algo_trade/timeline.py`](src/algo_trade/timeline.py). Unit tests in `tests/unit/test_timeline.py`.
- [x] **Buy/Sell timer** — forward-AUC algorithm in [`src/algo_trade/timer.py`](src/algo_trade/timer.py). Unit tests in `tests/unit/test_timer.py`.
- [x] **Web API** — FastAPI `GET /api/v1/*` in [`backend/api/`](backend/api/). Integration tests in `tests/integration/`.
- [x] **Recommender agent** — Agent #2 in [`src/algo_trade/recommender.py`](src/algo_trade/recommender.py). Unit tests in `tests/unit/test_recommender.py`.
- [x] **Plot** — `plot_material_forecast()` in [`src/algo_trade/plot.py`](src/algo_trade/plot.py). CLI: `algo-trade-plot`. Unit tests in `tests/unit/test_plot.py`.
- [x] **Backtest harness** — Replays the buy/sell timer over historical buffer data and price series. Caller supplies prices (no market-data vendor lock-in). [`src/algo_trade/backtest.py`](src/algo_trade/backtest.py); 19 hermetic tests in `tests/unit/test_backtest.py`. **Empirical validation is what tells you whether the narrated signal beats hold — until you run a real backtest with real prices, treat every recommendation as a hypothesis.**
- [ ] Price-data integration (Yahoo Finance / AlphaVantage / CSV loader) — small adapter that feeds the backtest harness real ETF prices.
- [ ] Unified CLI entry: `algo-trade recommend`, `algo-trade backtest --prices prices.csv`.
- [ ] Earnings-call transcripts as a second input source alongside filings.
- [ ] "Diff" mode: highlight what changed in a company's plans between two filings.

---

## Configuration

All settings live in a single **repo-root** `.env` file. Copy the template and edit:

```bash
cp .env.example .env
```

Loaded by [`src/algo_trade/env.py`](src/algo_trade/env.py) for the Python pipeline and API; Vite reads the same file for `VITE_*` vars (`envDir` points at repo root). **Shell exports override `.env`** (useful in CI).

| Variable | Default | What it controls |
|----------|---------|------------------|
| `ANTHROPIC_API_KEY` | *(empty)* | Extractor and Recommender (required for LLM calls) |
| `ALGO_TRADE_LLM_MODEL` | *(empty)* | Shared model override for both agents |
| `ALGO_TRADE_EXTRACTOR_MODEL` | *(empty)* | Extractor model (overrides default) |
| `ALGO_TRADE_RECOMMENDER_MODEL` | *(empty)* | Recommender model (overrides default) |
| `ALGO_TRADE_DEFAULT_EXTRACTOR_MODEL` | `claude-haiku-4-5` | Extractor fallback when no override set |
| `ALGO_TRADE_DEFAULT_RECOMMENDER_MODEL` | `claude-haiku-4-5` | Recommender fallback when no override set |
| `ALGO_TRADE_EXTRACTOR_MAX_TOKENS` | `16000` | Extractor output token ceiling |
| `ALGO_TRADE_EXTRACTOR_EFFORT` | `high` | Extractor `output_config.effort` |
| `ALGO_TRADE_RECOMMENDER_MAX_TOKENS` | `8000` | Recommender output token ceiling |
| `ALGO_TRADE_RECOMMENDER_EFFORT` | `high` | Recommender `output_config.effort` |
| `ALGO_TRADE_RECOMMENDER_MAX_EXTRACTIONS` | `100` | Max extractions in ranking digest |
| `ALGO_TRADE_BUFFER_PATH` | `data/buffer.sqlite` | SQLite buffer file (relative → repo root) |
| `ALGO_TRADE_UNIVERSE_DIR` | `backend/universe` | Materials / manufacturers vocabulary |
| `ALGO_TRADE_FORECAST_SINCE` | 12 months ago | API forecast window start (ISO date) |
| `ALGO_TRADE_FORECAST_UNTIL` | today | API forecast window end / `as_of` |
| `ALGO_TRADE_RANKING_MODE` | `rules` | `rules` (deterministic) or `recommender` (Agent #2) |
| `ALGO_TRADE_API_HOST` | `0.0.0.0` | `algo-trade-api` bind host |
| `ALGO_TRADE_API_PORT` | `8000` | API port (Vite proxy uses this) |
| `ALGO_TRADE_CORS_ORIGINS` | `http://localhost:5173,...` | CORS allowlist for the API |
| `ALGO_TRADE_TIMER_LOOKAHEAD_MONTHS` | `3` | Forward-AUC look-ahead window |
| `ALGO_TRADE_TIMER_BUY_THRESHOLD` | `0.0` | BUY signal threshold |
| `ALGO_TRADE_SEC_IDENTITY` | *(empty)* | Default SEC identity for `algo-trade-extract` |
| `ALGO_TRADE_EXTRACT_FORM` | `10-K` | Default form type for `algo-trade-extract` |
| `ALGO_TRADE_EXTRACT_LIMIT` | `1` | Default filings-per-form for `algo-trade-extract` |
| `VITE_API_BASE` | `/mock/v1` | Frontend data path (`/api/v1` for live API) |
| `VITE_DATA_SOURCE` | `mock` | `mock` (static JSON) or `api` (FastAPI) |
| `VITE_MOCK_FALLBACK` | `true` (when `api`) | Retry against `/mock/v1` if the live API fails |

Full reference: [`.env.example`](.env.example) and [`backend/README.md`](backend/README.md).

---

## CLI commands

| Command | Purpose |
|---------|---------|
| `algo-trade-fetch` | Fetch SEC filings to stdout (JSONL) |
| `algo-trade-extract` | Fetch → extract → upsert into buffer (progress bar + status on stderr) |
| `algo-trade-plot` | Render material forecast curve (PNG or HTML) |
| `algo-trade-api` | Start FastAPI on `ALGO_TRADE_API_HOST`:`ALGO_TRADE_API_PORT` |

Example — populate the buffer from the command line (identity can come from `.env` via `ALGO_TRADE_SEC_IDENTITY`):

```bash
algo-trade-extract TSLA GM \
    --identity "Your Name you@example.com" \
    --form 10-Q --limit 1
```

---

## Beyond the quickstart

`python dev.py` is enough for the basic dashboard with demo data. The rest of this section is for when you want **real** SEC filings driving the UI, want to run the pieces individually, or are contributing code.

### Populate the buffer with real filings

`dev.py` boots the stack, but the buffer starts empty. On a fresh install the Forecast tab shows **"Pipeline not run"** and the Explorer shows **"0 extractions matched"** — that's the correct empty state, not a bug. It means the frontend is talking to your live backend, and the backend is honestly reporting that it has no data yet.

To fill the buffer with real filings:

1. Put your Anthropic key and an SEC contact in `.env` (the file `dev.py` created on first run):
   ```bash
   ANTHROPIC_API_KEY=sk-ant-...
   ALGO_TRADE_SEC_IDENTITY=Your Name you@example.com
   ```
   Missing `ANTHROPIC_API_KEY` → extractor errors clearly. Missing `ALGO_TRADE_SEC_IDENTITY` → EDGAR fetches fail (SEC's fair-access policy requires a contact in the User-Agent).

2. With the dev stack already running, open a **second terminal** at the repo root and run:
   ```bash
   algo-trade-extract TSLA GM FCX --form 10-Q --limit 1 -v
   ```

**What that command does, step by step:**

- Fetches the most recent 10-Q for each ticker from EDGAR.
- Runs Agent #1 (the Extractor) on each filing's MD&A + Risk Factors.
- Writes the resulting `dated_effects` into `data/buffer.sqlite`.

**What to expect while it runs:**

- **~1–3 minutes per filing** — the LLM has to read the whole MD&A and Risk Factors and emit structured JSON.
- **A few cents in Anthropic tokens per filing** on the default Haiku 4.5 model; more on Sonnet 4.6 or Opus 4.7 if you overrode the default.
- With `-v`, per-filing progress lines print to stderr so you can see it work.

**What success looks like** — the last line of output should be something like:

```text
Done. Upserted 3 filing(s), 12 dated effect(s) into data/buffer.sqlite
```

**After the command finishes**, in the browser (no restart needed):

- **Explorer** — enter `TSLA` in the ticker box, click *Show results* → you should see extractions from that filing with sectors, direction, magnitude, time windows, and a citation to the filing text.
- **Forecast** — refresh the tab → per-material signal curves and BUY/SELL markers appear for `lithium` and `copper` (the sectors those three tickers talk about).

### Picking tickers that actually surface signals

Not every filing mentions materials the pipeline recognises. **AAPL, MSFT, GOOGL** rarely produce dated effects — their filings talk about services and platforms, not commodities. **Consumer staples, media, financials** are similarly quiet.

Tickers whose filings routinely surface material signals:

| Sector | Tickers | Usually mentions |
|---|---|---|
| Autos / EV | `TSLA`, `GM`, `F` | lithium, copper, aluminum |
| Miners | `FCX`, `RIO`, `BHP`, `ALB`, `LAC`, `SQM` | copper, iron ore, lithium, cobalt |
| Steel | `NUE`, `STLD` | iron ore, manganese, coal |
| Energy | `XOM`, `CVX`, `OXY` | natural gas, oil, LNG |
| Semiconductors | `NVDA`, `AMD`, `INTC` | silicon, hyperscale cloud demand |

The canonical material vocabulary (what the extractor is looking to match against) is in [`backend/universe/materials.json`](backend/universe/materials.json).

### If you see `0 dated effect(s)`

The filings were fetched and read successfully, but nothing mapped to a canonical material. Try:

- **More tickers**: widen the batch so you increase the chance of catching a filing that mentions a tracked material.
  ```bash
  algo-trade-extract TSLA GM F FCX RIO ALB LAC NVDA --form 10-Q --limit 2 -v
  ```
- **Annual reports** (`--form 10-K`) — usually denser than quarterlies.
- **Read the verbose log** — with `-v` you can see the raw filing text going to the LLM and its response. If Claude is emitting effects but they don't survive validation (bad date order, empty source span, etc.), the log tells you exactly why.

### Run a single piece directly

| Command | What it does |
|---|---|
| `algo-trade-fetch --ticker NVDA --form 10-K --limit 1 --identity "Name email"` | Fetch from EDGAR, dump filing JSON, no LLM |
| `algo-trade-extract TSLA -v` | Fetch + extract + upsert to buffer (needs `ANTHROPIC_API_KEY`) |
| `algo-trade-plot lithium` | Render a sector forecast PNG from the buffer |
| `algo-trade-api` | Run the FastAPI backend alone on :8000 |
| `python -m pytest` | Run the Python test suite (~193 hermetic tests, no network) |

Python API examples live in [`examples/`](examples/).

### Troubleshooting

| Symptom | Check |
|---------|-------|
| Empty dashboard, demo banner visible | Buffer is empty — run `algo-trade-extract` for some tickers |
| `npm install` fails | Node version — needs 20+ |
| Backend won't start, `ModuleNotFoundError` | `pip install -e ".[dev]"` from repo root, or just re-run `python dev.py` |
| `500` on `/forecast/*` | Buffer empty, or restart the API after editing `.env` |
| `--identity is required` | Set `ALGO_TRADE_SEC_IDENTITY` in `.env` |
| Extract returns 0 effects | Filings fetched OK but no material match — try a different form / ticker; check `backend/universe/materials.json` |
| `dev.py` does not fully die on Ctrl-C | Hit it twice — the second Ctrl-C escalates to force-kill |

### Tests

```bash
python -m pytest                       # all (~193 passing)
python -m pytest tests/unit            # fast, hermetic
python -m pytest tests/integration     # API + buffer flow
```

Frontend tests: `cd frontend && npm test` (Vitest) and `npm run test:e2e` (Playwright). See [`frontend/README.md`](frontend/README.md) and [`backend/README.md`](backend/README.md).

---

## Project status

| Stage | Status | Location |
|-------|--------|----------|
| EDGAR fetcher | Done | `src/algo_trade/fetcher.py` |
| Extractor (Agent #1) | Done | `src/algo_trade/extractor.py` |
| Buffer store | Done | `src/algo_trade/buffer/` |
| Timeline aggregator | Done | `src/algo_trade/timeline.py` |
| Buy/Sell timer | Done | `src/algo_trade/timer.py` |
| Recommender (Agent #2) | Done | `src/algo_trade/recommender.py` |
| Web API | Done | `backend/api/` |
| FilingSignal UI | Done | `frontend/` |
| Plot | Done | `src/algo_trade/plot.py` |
| Backtest harness | Done | `src/algo_trade/backtest.py` |
| Price-data integration | Planned | — (caller-supplied today) |

**193** Python tests, 2 skipped (`pytest`). Ranking in the API defaults to rule-based scores; set `ALGO_TRADE_RANKING_MODE=recommender` in `.env` to use Agent #2.

---

## For contributors and AI successors

[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) is the deep technical reference. Read it before you touch the code. It documents every stage's contract, the SQLite schema, the design decisions (and *why* each one), the file map, and how to extend the pipeline. The README is the intro; ARCHITECTURE is the manual.


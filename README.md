# algo-trade

An agentic pipeline that reads U.S. SEC EDGAR filings, extracts each company's forward-looking plans and sector dependencies, and uses a second LLM to recommend which sector(s) look most attractive to invest in.

> ⚠️ **Disclaimer:** This project is for research and educational purposes only. Nothing produced by this tool is financial advice. LLMs hallucinate, filings can be misread, and markets do not care what a model thinks. Do your own due diligence.

---

## Repository layout

| Path | Role |
|------|------|
| [`src/algo_trade/`](src/algo_trade/) | **Python pipeline** — fetcher, extractor (Agent #1), buffer, timeline, timer, recommender (Agent #2). Install via `pip install -e ".[dev]"`. |
| [`tests/`](tests/README.md) | Python tests — [`unit/`](tests/unit/) and [`integration/`](tests/integration/) |
| [`backend/`](backend/README.md) | **Web serving layer** — FastAPI (`GET /api/v1/*`), [`universe/`](backend/universe/README.md) reference JSON, [`mock/v1/`](backend/mock/v1/manifest.json) demo snapshots |
| [`frontend/`](frontend/README.md) | **FilingSignal** web UI (React) — forecast dashboard, Explorer, audit drill-down. Mock or live API via `.env`. |
| [`.env.example`](.env.example) | **Configuration template** — copy to `.env` at repo root (API, pipeline, frontend) |
| [`docs/`](docs/ARCHITECTURE.md) | Technical docs — see links below |
| [`examples/`](examples/) | Small pipeline usage examples |

### Documentation

| Doc | Audience |
|-----|----------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Pipeline stages, contracts, SQLite schema, design decisions |
| [hld-web-interface.md](docs/hld-web-interface.md) | Web UI boundaries and JSON API contract (v1) |
| [implementation-plan-web.md](docs/implementation-plan-web.md) | Web delivery phases and checklist |
| [playwright-mcp.md](docs/playwright-mcp.md) | E2E tests and optional Cursor browser MCP |

The **live Python pipeline** lives under `src/algo_trade/`. The **web app** reads either static mock JSON (`VITE_DATA_SOURCE=mock`) or the FastAPI backend (`VITE_DATA_SOURCE=api`) — both controlled from the repo-root [`.env`](.env.example).

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
- [ ] CLI: `algo-trade extract --tickers nvda,msft,...`, `algo-trade recommend`, unified timeline entry
- [ ] Backtest harness: replay the recommender's output **and** the buy/sell timer's calls against subsequent sector ETF returns to see if it's actually any good
- [ ] Add earnings-call transcripts as a second input source alongside filings
- [ ] Add a "diff" mode: highlight what changed in a company's plans between two filings

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
| `ALGO_TRADE_DEFAULT_EXTRACTOR_MODEL` | `claude-opus-4-7` | Extractor fallback when no override set |
| `ALGO_TRADE_DEFAULT_RECOMMENDER_MODEL` | `claude-opus-4-7` | Recommender fallback when no override set |
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
| `algo-trade-extract` | Fetch → extract → upsert into buffer SQLite |
| `algo-trade-plot` | Render material forecast curve (PNG or HTML) |
| `algo-trade-api` | Start FastAPI on `ALGO_TRADE_API_HOST`:`ALGO_TRADE_API_PORT` |

Example — populate the buffer from the command line (identity can come from `.env` via `ALGO_TRADE_SEC_IDENTITY`):

```bash
algo-trade-extract TSLA GM \
    --identity "Your Name you@example.com" \
    --form 10-Q --limit 1
```

---

## Setup

```bash
git clone https://github.com/aviad59/algo-trade.git
cd algo-trade
python -m pip install -e ".[dev]"
cp .env.example .env   # set ANTHROPIC_API_KEY, ALGO_TRADE_SEC_IDENTITY, etc.
```

### End-to-end workflow

```bash
# 1. Populate buffer (needs ANTHROPIC_API_KEY in .env)
algo-trade-extract TSLA --identity "You you@example.com" --form 10-Q --limit 1

# 2. Start API (reads buffer + .env)
algo-trade-api

# 3. Point UI at live API — in .env set:
#    VITE_API_BASE=/api/v1
#    VITE_DATA_SOURCE=api
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. Vite proxies `/api/v1` → `http://localhost:8000` (port from `ALGO_TRADE_API_PORT`).

### Fetch only (no LLM)

```bash
algo-trade-fetch \
    --identity "Your Name you@example.com" \
    --ticker NVDA \
    --form 10-K \
    --limit 1
```

Or, from Python:

```python
from algo_trade import Fetcher

fetcher = Fetcher(identity="Your Name you@example.com")
for f in fetcher.fetch(ticker="NVDA", forms=["10-K"], limit=1):
    print(f.ticker, f.form, f.filing_date, f.accession_number)
    print(" mda chars:", len(f.section("mda") or ""))
    print(" risk_factors chars:", len(f.section("risk_factors") or ""))
```

Fetch + run Agent #1 (the Extractor) on the result (`ANTHROPIC_API_KEY` from `.env`):

```python
from algo_trade import Extractor, Fetcher

fetcher = Fetcher(identity="Your Name you@example.com")
extractor = Extractor()  # model from .env / llm_config

for f in fetcher.fetch(ticker="NVDA", forms=["10-K"], limit=1):
    extracted = extractor.extract(f)
    print(f"confidence: {extracted.extractor_confidence:.2f}")
    for e in extracted.dated_effects:
        print(f"  {e.sector:<28} {e.direction.value:<9} {e.magnitude.value:<9} "
              f"{e.window_start} -> {e.window_end}  @ {e.source_span}")
```

Run the tests:

```bash
python -m pytest              # all tests
python -m pytest tests/unit   # unit only
python -m pytest tests/integration  # integration only
```

### Web UI

**Mock mode (default)** — no buffer or API required; uses static JSON from `backend/mock/v1/`:

```bash
cd frontend
npm install
npm run dev
```

**Live API mode** — requires a populated buffer and `algo-trade-api` running. Set in repo-root `.env`:

```
VITE_API_BASE=/api/v1
VITE_DATA_SOURCE=api
ALGO_TRADE_RANKING_MODE=recommender   # optional — use Agent #2 for ranking
```

Then start both servers (see [End-to-end workflow](#end-to-end-workflow) above).

Frontend tests: `cd frontend && npm test` (Vitest) and `npm run test:e2e` (Playwright).

See [`frontend/README.md`](frontend/README.md) and [`backend/README.md`](backend/README.md).

**Prerequisites:**
- A contact email — `ALGO_TRADE_SEC_IDENTITY` or `--identity` for SEC User-Agent policy
- `ANTHROPIC_API_KEY` in `.env` — required for extraction and recommender ranking

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
| Backtest harness | Planned | — |

**142** Python tests (`pytest`). Ranking in the API defaults to rule-based scores; set `ALGO_TRADE_RANKING_MODE=recommender` in `.env` to use Agent #2.

---

## For contributors and AI successors

[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) is the deep technical reference. Read it before you touch the code. It documents every stage's contract, the SQLite schema, the design decisions (and *why* each one), the file map, and how to extend the pipeline. The README is the intro; ARCHITECTURE is the manual.


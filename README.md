# FilingSignal

**Can an LLM read SEC filings, extract genuine forward-looking signals, and turn
them into a market forecast that actually holds up?**

FilingSignal is an end-to-end research platform that puts that question to an
honest test. It reads SEC filings for raw-materials producers, uses an LLM to
extract dated, *cited* effects, scores them into a quarterly forecast with pure
deterministic math, and then — the part most demos skip — **backtests the result
point-in-time and reports the verdict without flinching**, permutation test and
all.

> **The result (first real run — 576 filings, 1,073 effects, 14 quarters):**
> the top-1 rotation **beat every tradeable baseline**, point-in-time — $100 →
> **$281** vs SPY's $204, equal-weight materials' $201, and a random-pick median
> of $193 (**+34.4% CAGR** vs SPY's +22.7%). It's a small, high-beta sample
> (Sharpe 0.94, −19.6% drawdown), so the honest read is *promising on this
> window*, not *proven* — but it beat every baseline you'd actually trade against.

The point isn't just the number — it's that every result is **point-in-time and
stress-tested**: measured against four baselines (SPY, equal-weight, a random-pick
Monte-Carlo floor, and a hindsight ceiling) with a rank-IC and a permutation test.
A result you can trust *because it's been interrogated*, not because the curve
happens to look good.

---

## The question

Markets price public filings within minutes, so any edge lives in the slow
**drift** after a filing — and in whether an LLM can read *forward-looking*
language (guidance, capex plans, offtake agreements) accurately enough to matter.
FilingSignal isolates that question to a tractable corner of the market and
answers it with real data and real statistics.

## The universe — raw materials

Six industrial materials, each frozen to its miner-equity ETF:

| Material | ETF | Material | ETF |
|---|---|---|---|
| Copper | COPX | Steel | SLX |
| Gold | GDX | Silver | SIL |
| Uranium | URNM | Rare Earths | REMX |

Behind them, ~33 companies tagged by **tier** (US → 10-K/10-Q/8-K; foreign →
40-F/20-F/6-K) and **perspective** (*producer* = supply-side, *consumer* =
demand-side). The whole map is frozen config in
[`universe/materials.yaml`](universe/materials.yaml) — the reproducibility
contract for scoring and attribution.

## Core concept

> *"If you could buy exactly one material's miner ETF next quarter, which one?"*

Each quarter, FilingSignal ranks the six materials by a **point-in-time
cross-sectional z-score** built only from filings public *before* the quarter
began — then honestly checks whether the top pick actually worked. Every score
traces back to a **verbatim quote** in a real filing, so nothing is a black box.

## The pipeline

```
  EDGAR filings                     ← ingest (US + foreign forms)
      │   section isolation + guidance-focused condensing (~5.7x fewer tokens)
      ▼
  pre-LLM filter                    ← form/item allowlist + material keyword gate
      │
      ▼
  Agent #1 — Extractor  (LLM)       ← dated, cited effects + a filing summary
      │   {material, perspective, direction, magnitude, window, evidence_quote}
      ▼
  SQLite buffer                     ← the contract; incremental (skip re-digests)
      │
      ▼
  Scorer  (deterministic math)      ← sign·magnitude·confidence·recency·overlap
      │   per-perspective sub-scores → breadth gate → cross-sectional z
      ├──────────────► Agent #2 — Rater (LLM): narrates the rank, cite-only
      ▼
  Evaluate + Backtest               ← rank-IC + permutation test; top-1 rotation
                                       vs SPY / equal-weight / random / hindsight
```

- **Math rates, LLM explains.** The deterministic scorer decides the rank; Agent
  #2 only *narrates* it and may cite nothing that isn't in the buffer.
- **Point-in-time by construction.** A quarter's score admits only filings public
  before it started — there is no look-ahead mode to switch off.
- **Provider-agnostic.** The LLM layer runs on Claude *or* Kimi (Moonshot) behind
  one interface, with a native-schema + pydantic validate-and-retry backstop.
- **Loud, never silent.** Section-isolation fallbacks, condensing, and dropped
  effects are all recorded as warnings that flow downstream.

## The rollover mechanic

The forecast is a **standing pipeline that advances with the calendar**, not a
frozen snapshot:

- The forecast quarter is `quarter_of(today())` — a single clock seam
  (`FILINGSIGNAL_TODAY` overrides it, which makes rollover deterministically
  **testable** without waiting for a real quarter to turn). On Oct 1 it
  re-anchors from Q3 to Q4 automatically — quarter label, "published" date,
  prior-quarter, filing count, ranking all recompute with zero edits.
- **`filingsignal refresh`** is the incremental sweep: it walks the universe,
  skips already-digested filings, filters routine ones pre-LLM, and only new
  filings cost a call. It aborts immediately if the provider key is missing or
  exhausted (no spend storm).
- The **Forecast page** tracks the *in-progress* quarter live (quarter-to-date
  ETF moves vs the start-of-quarter ranking, with a provisional rank-IC); the
  **Backtest page** owns the *completed* quarters and the final verdict. They
  hand off automatically as each quarter closes.

There's also a live **reviewer demo**: pick a ticker + form + date, and the app
fetches that one filing, runs Agent #1 on it in real time, and shows the summary
+ extracted effects — gated by a shared access key so the baked-in model key
can't be abused.

## The backtest — the rollover replayed through history

The backtest is just the rollover mechanic **run over past quarters**, so the
question it answers stays honest: *"if I had run this each quarter using only what
was public at the time, what would have happened?"*

Every historical pick is re-derived from a hard **point-in-time cutoff — the first
day of that quarter**:

- The **2025 Q4** ranking is scored from **only filings public on or before
  2025-09-30** — nothing from Oct 1 onward exists for that decision. The **2026 Q1**
  ranking uses only filings through 2025-12-31, and so on down the line.
- There is **no look-ahead switch to forget to turn off**. The scorer for quarter
  *Q* structurally drops any effect whose filing date is after *Q*'s start; a
  filing that lands mid-quarter simply isn't visible to that quarter's forecast.

It then walks forward: hold the top-ranked material's miner ETF for the quarter,
rotate at the next quarter's open (10 bps cost, dividend-adjusted closes), repeat.
That produces the $100 growth curve and every metric, measured against four
baselines:

- **SPY** — the do-nothing market alternative.
- **Equal-weight materials** — hold all six equally (naive diversification).
- **Random-pick (Monte-Carlo)** — the luck floor: a random material each quarter, ×10k.
- **Hindsight-best** — the ceiling: the actual winner each quarter (needs foresight).

On top of returns it runs a **rank-IC** (Spearman of forecast rank vs realized
rank) with a **permutation test**, so the outperformance is judged for skill, not
just size. The Forecast page shows the *current, unfinished* quarter live; the
moment it closes, it becomes one more point-in-time row in the backtest.

## Tech stack

**Backend** — Python 3.12 · FastAPI / uvicorn · pydantic v2 · SQLite (WAL buffer)
· pandas / numpy · [edgartools](https://github.com/dgunning/edgartools) for SEC
filings · `anthropic` + `openai` SDKs (provider-agnostic) · yfinance for
dividend-adjusted ETF prices.

**Frontend** — React 19 · TypeScript · Vite · **zero runtime dependencies**
(hand-rolled hash router, custom SVG charts, a design system in one CSS file).
Reads the read-only API and falls back to demo fixtures if the backend is down.

**Delivery** — a **single Docker image**: one FastAPI process serves the built
SPA *and* the `/api/v1` API on port 8000. `docker compose` mounts the real
`./data` buffer so the container serves live results.

## Run it

```bash
# 1) full stack, one command (serves SPA + API on :8000)
docker compose up --build          # → http://localhost:8000

# --- or run the pieces directly ---
pip install -e ".[dev]"
filingsignal serve                 # backend on :8000
cd frontend && npm install && npm run dev   # frontend on :5173
```

CLI (the pipeline is normally driven offline, then served read-only):

```bash
filingsignal fetch-prices          # real ETF + SPY prices → data/prices
filingsignal refresh --limit 4     # incremental sweep: fetch → filter → Agent #1
filingsignal score                 # current-quarter ranking
filingsignal rate --quarter "2026 Q3"   # Agent #2 explanations → buffer
filingsignal backtest --since "2023 Q1" # point-in-time backtest vs four baselines
```

Live extraction needs `ANTHROPIC_API_KEY` (or `MOONSHOT_API_KEY`) and
`FILINGSIGNAL_SEC_IDENTITY` in `.env`; the read-only dashboard needs neither.

## Layout

```
src/filingsignal/
  fetcher.py  prices.py  scorer.py  evaluation.py  backtest.py  refresh.py
  clock.py    rating.py  cli.py
  llm/        base · claude · openai_compat · structured · factory   (provider-agnostic)
  extraction/ filters · prompts (per form class) · extractor          (Agent #1)
  buffer/     store.py + schema.sql                                   (SQLite)
  api/        FastAPI: routers (forecast/filings/backtest/rating/extract+digest/meta)
universe/materials.yaml     frozen material→ETF map, companies, filters
frontend/                   React + TS + Vite dashboard (4 pages)
```

## Honest limitations

- **Small sample.** 14 backtested quarters; the outperformance is promising but
  not statistically airtight (it beat ~85% of random-pick sequences, p = 0.15),
  and it's untested across a sector downturn.
- **US-heavy.** Foreign filings (40-F/20-F/6-K) extract thin — section isolation
  for foreign forms is the next coverage win.
- **The bet is genuinely hard.** Public filings are priced fast; this is a
  post-filing-drift experiment, and the result reflects that honestly.

---

*A learning / portfolio project. Not investment advice.*

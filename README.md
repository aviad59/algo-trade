# FilingSignal

**An LLM reads SEC filings, extracts dated and cited forward-looking effects, and
deterministic math turns them into a quarterly materials-rotation forecast. Then a
point-in-time backtest checks whether it actually worked.**

Final project · *AI & Innovation in Capital Markets* · **Track 3: AI application
for investors (B2C)**. By Ron Kadosh, Idan Aviad, Barak Tubul.

| | |
|---|---|
| **Live application** | <https://filingsignal.livelyground-2a3fc950.francecentral.azurecontainerapps.io/> |
| **Spec & summary (PDF, 5 pages)** | [`docs/report.pdf`](docs/report.pdf) · source: [`docs/report.html`](docs/report.html) |
| **Design notes (deep dive)** | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| **Run locally** | `docker compose up --build` then <http://localhost:8000> |

The dashboard is read-only and needs **no API key**: the processed research buffer
and the ETF price history are committed, so a fresh clone reproduces the reported
results exactly.

---

## Submission checklist

| Requirement | Where it is |
|---|---|
| Interactive web application (UI) | React 19 + TypeScript SPA, 4 pages: [`frontend/`](frontend/) |
| Substantial AI feature | Agent #1 extractor + Agent #2 rater: [`src/filingsignal/extraction/`](src/filingsignal/extraction/), [`rating.py`](src/filingsignal/rating.py) |
| Deployed application link | top of this file |
| Spec & summary PDF (max 5 pages) | [`docs/report.pdf`](docs/report.pdf) |
| Full source code | this repository |
| `README.md` with run instructions | this file, see [Run it](#run-it) |
| `requirements.txt` | [`requirements.txt`](requirements.txt), mirrors [`pyproject.toml`](pyproject.toml) |
| No private API keys in public code | `.env` is git-ignored; template in [`.env.example`](.env.example); LLM endpoints return `503` without a key |
| Financial evaluation, not just stats | point-in-time backtest vs 4 baselines, see [Results](#results) |
| Risks & limitations | [Limitations](#limitations) and §11 of the report |

## What it does

Each quarter the system answers one decision-shaped question, *"if you could buy
exactly one material's miner ETF next quarter, which one?"*, across six materials,
each frozen to a liquid miner ETF:

| Material | ETF | Material | ETF | Material | ETF |
|---|---|---|---|---|---|
| Copper | COPX | Gold | GDX | Uranium | URNM |
| Steel | SLX | Silver | SIL | Rare Earths | REMX |

~33 companies behind them, tagged by **tier** (US: 10-K/10-Q/8-K; foreign:
40-F/20-F/6-K) and **perspective** (*producer* is the supply side, *consumer* the
demand side), frozen in [`universe/materials.yaml`](universe/materials.yaml).

```
  EDGAR filings                     <- ingest (US + foreign forms)
      |   section isolation + guidance-focused condensing (~5.7x fewer tokens)
      v
  pre-LLM filter                    <- form/item allowlist + material keyword gate
      v
  Agent #1  Extractor  (LLM)        -> dated, cited effects + a filing summary
      |   {material, perspective, direction, magnitude, window, evidence_quote}
      v
  SQLite buffer                     <- the contract; incremental (skip re-digests)
      v
  Scorer  (deterministic math)      -> sign * magnitude * confidence * recency * overlap
      |   per-perspective sub-scores -> breadth gate -> cross-sectional z
      |----------> Agent #2  Rater (LLM): narrates the rank, citation-only
      v
  Evaluate + Backtest               -> rank-IC + permutation test; top-1 rotation
                                       vs SPY / equal-weight / random / hindsight
```

Three design rules carry the project:

- **Math rates, the LLM explains.** The deterministic scorer decides the rank.
  Agent #2 only narrates it, and may cite nothing that isn't in the buffer.
- **Point-in-time by construction.** The scorer takes the decision date as a
  parameter and structurally drops any effect filed after it. The live forecast
  and the backtest call the *same* function, so there is no look-ahead switch to
  forget to turn off.
- **Loud, never silent.** Section-isolation fallbacks, condensing, and dropped
  effects are recorded as warnings (740 of them) and surfaced in the UI.

The scoring formula, the rollover mechanic and the evaluation methodology are in
§4 to §8 of the [report](docs/report.html), and §5 to §7 of
[`ARCHITECTURE.md`](ARCHITECTURE.md).

## Results

14 quarters, 2023 Q1 to 2026 Q2, point-in-time, 10 bps round-trip, $100 start:

| | **FilingSignal** | SPY | Equal-weight | Random (median) | Hindsight |
|---|---|---|---|---|---|
| Final value from $100 | **$281** | $204 | $201 | $193 | $1,332 |
| CAGR | **+34.4%** | +22.7% | +22.0% | +20.6% | +109.5% |
| Sharpe | 0.94 | **1.85** | 0.91 | 0.84 | 2.31 |
| Max drawdown | -19.6% | **-4.5%** | -13.8% | -14.0% | -8.0% |
| Hit rate vs equal-weight | 7 / 14 | n/a | n/a | n/a | n/a |

**Mean rank-IC -0.21** (12 scoreable quarters, 2,000 permutations, **p = 0.95**) ·
**return vs random-pick: p = 0.15** (2,000 Monte-Carlo sequences).

> **The honest read.** The rotation beat every *tradeable* baseline on raw return,
> but **p = 0.15 is not significant**; the **mean rank-IC is negative**, so there
> is no cross-sectional skill and whatever worked lived in the top pick alone;
> **two quarters carry everything** (strip 2023 Q3 and 2025 Q3 and $100 becomes
> $122, against equal-weight's $147 and SPY's $196); and it **loses to SPY
> risk-adjusted** (Sharpe 0.94 vs 1.85). The defensible claim is *promising on
> this window*, not *skill demonstrated*. Full analysis in §9 and §10 of the report.

Reproduce it: `filingsignal backtest --since "2023 Q1"`.

## What ships in this repo

Committed, so a fresh clone reproduces the numbers above with **no API key and no
ingestion run**:

- `data/buffer.sqlite`, the processed research buffer: **577 filings**,
  **1,102 dated effects**, 590 extraction records, 740 warnings.
- `data/prices/`, dividend-adjusted daily closes for the six ETFs plus SPY.
- `universe/materials.yaml`, the frozen material to ETF to company map.

**Not** committed: `.env` or any provider key. The frontend falls back to demo
fixtures only if the API is unreachable, and labels the data source either way.

Re-running ingestion is **optional** and is the only thing that costs money:
`filingsignal refresh` re-walks EDGAR, skips everything already digested, and
spends one LLM call per genuinely new filing.

## Run it

```bash
# Docker: full stack, one command (SPA + API on :8000)
docker compose up --build          # then http://localhost:8000
```

```bash
# or run the pieces directly
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"            # or: pip install -r requirements.txt
cp .env.example .env               # optional, not needed to serve
filingsignal serve                 # backend on :8000

cd frontend && npm install && npm run dev   # frontend on :5173
```

Requires Python 3.11+ (3.12 used here) and Node 20+. Dependencies are declared in
[`pyproject.toml`](pyproject.toml); [`requirements.txt`](requirements.txt) mirrors
them for submission compatibility. Installing via `requirements.txt` does not
create the console script, so use `python -m filingsignal.cli ...` in that case.

### CLI

```bash
filingsignal fetch-prices          # real ETF + SPY prices -> data/prices
filingsignal refresh --limit 4     # incremental sweep: fetch, filter, Agent #1
filingsignal score                 # current-quarter ranking
filingsignal rate --quarter "2026 Q3"   # Agent #2 explanations -> buffer
filingsignal backtest --since "2023 Q1" # point-in-time backtest vs four baselines
filingsignal serve                 # FastAPI (serves the built SPA too)
```

Live extraction needs `ANTHROPIC_API_KEY` (or `MOONSHOT_API_KEY`) and
`FILINGSIGNAL_SEC_IDENTITY`; the read-only dashboard needs neither.

### Configuration

All of it is environment variables, see [`.env.example`](.env.example).

| Variable | Purpose |
|---|---|
| `FILINGSIGNAL_API_KEY` | shared access key for the LLM-spending endpoints. **Unset means they return 503** |
| `ANTHROPIC_API_KEY` / `MOONSHOT_API_KEY` | provider key (only for extraction) |
| `FILINGSIGNAL_LLM_PROVIDER` / `_MODEL` | `claude` or `kimi`, and the model id |
| `FILINGSIGNAL_SEC_IDENTITY` | contact identity required on every EDGAR request |
| `FILINGSIGNAL_TODAY` | overrides the clock, which makes quarter rollover testable |
| `FILINGSIGNAL_BACKTEST_SINCE` | first quarter shown by the API/dashboard |
| `FILINGSIGNAL_BUFFER_PATH` / `_PRICES_DIR` / `_UNIVERSE_DIR` | data locations |

## Verify it

```bash
pytest                    # 34 tests, no network and no API key required
cd frontend
npm run typecheck         # tsc -b --noEmit
npm run build             # production SPA build
```

| Tests | Guarantee |
|---|---|
| `test_scorer.py` | **point-in-time cutoff enforcement**: a post-cutoff filing cannot enter a score; deterministic z-scores |
| `test_rollover.py` | quarter rollover across the clock seam; `FILINGSIGNAL_TODAY` override |
| `test_backtest.py` | transaction costs, rotation mechanics, baseline construction |
| `test_buffer.py` | duplicate-filing skip (same accession + model means no re-spend) |
| `test_extraction.py` | pre-LLM form/keyword filter; section isolation + fallback warnings |
| `test_llm.py` | structured-output validation and the validate-and-retry backstop |
| `test_api.py` | read-only endpoints; auth gate on the LLM-spending endpoints |

## API

Read endpoints are public; the two that spend LLM credit are gated by
`Authorization: Bearer $FILINGSIGNAL_API_KEY`.

| Method | Endpoint | Notes |
|---|---|---|
| `GET` | `/api/v1/forecast` | current-quarter ranking + quarter-to-date tracking |
| `GET` | `/api/v1/filings` | filings, summaries, extracted effects, evidence quotes |
| `GET` | `/api/v1/backtest` | curves, per-quarter calls, metrics, rank-IC, p-values |
| `GET` | `/api/v1/rating` | Agent #2 explanation for a quarter |
| `GET` | `/api/v1/meta` | universe, clock, data-source labels |
| `POST` | `/api/v1/digest` | 🔒 one filing to summary + effects, 10 to 30 s; persists, so a repeat costs no second LLM call |
| `POST` | `/api/v1/extract` | 🔒 batch job over tickers; one at a time (`409` if busy) |
| `GET` | `/api/v1/extract/status` | job progress |

The deployed service holds the provider key in **server-side environment
secrets**, so nothing is embedded in the image or the client bundle. If the
provider quota is exhausted, requests fail loudly with the provider's error
rather than returning a silent empty extraction.

## Layout

```
src/filingsignal/
  fetcher.py  prices.py  scorer.py  evaluation.py  backtest.py  refresh.py
  clock.py    rating.py  cli.py
  llm/        base, claude, openai_compat, structured, factory   (provider-agnostic)
  extraction/ filters, prompts (per form class), extractor        (Agent #1)
  buffer/     store.py + schema.sql                               (SQLite)
  api/        FastAPI: routers (forecast/filings/backtest/rating/extract+digest/meta)
universe/materials.yaml     frozen material to ETF map, companies, filters
frontend/src/pages/         Home, Forecast, Filings, Backtest
data/                       committed buffer.sqlite + price CSVs
docs/report.html            the 5-page spec & summary (source of the PDF)
tests/                      34 tests: cutoff, rollover, costs, filters, API
```

## Tech stack

**Backend**: Python 3.12, FastAPI / uvicorn, pydantic v2, SQLite (WAL buffer),
pandas / numpy, [edgartools](https://github.com/dgunning/edgartools), the
`anthropic` and `openai` SDKs (provider-agnostic), yfinance.

**Frontend**: React 19, TypeScript, Vite, with **no third-party routing, charting
or state-management libraries**: a hand-rolled hash router, custom SVG charts, and
a design system in one CSS file.

**Delivery**: a single Docker image; one FastAPI process serves the built SPA
*and* `/api/v1` on port 8000.

## Screenshots

<!-- Add four PNGs to docs/screenshots/ with exactly these filenames. -->

| Forecast (live quarter) | Backtest verdict |
|---|---|
| ![Forecast page](docs/screenshots/forecast.png) | ![Backtest page](docs/screenshots/backtest.png) |
| **Filing + evidence quotes** | **Live extraction demo** |
| ![Filings page](docs/screenshots/filings.png) | ![Extraction demo](docs/screenshots/extract.png) |

## Limitations

- **Not statistically significant.** Random-pick permutation p = 0.15; rank-IC
  permutation p = 0.95 on a *negative* mean IC of -0.21.
- **Concentrated in two quarters** (2023 Q3 +41%, 2025 Q3 +63%). Without them the
  strategy trails both equal-weight and SPY.
- **No cross-sectional skill.** The ordering below the top pick is uninformative.
- **Worse risk-adjusted than doing nothing.** Sharpe 0.94 vs SPY's 1.85, and a
  -19.6% drawdown vs -4.5%.
- **Small sample.** 14 quarters, 6 assets, one sector, no sector downturn tested.
- **US-heavy.** Foreign filings (40-F/20-F/6-K) extract thin; section isolation
  for foreign forms is the next coverage win.

Full discussion, plus future work, in §11 and §12 of the
[report](docs/report.html).

---

*A learning / portfolio project. Not investment advice.*

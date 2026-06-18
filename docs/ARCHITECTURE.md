# algo-trade — Architecture

> This is the technical reference for the project. The README is the marketing/design intro (what + why at a glance). This doc is what you read when you actually have to work on the code.

If you are a fresh AI agent or a new human contributor: read this doc once top-to-bottom, then jump to the stage you're touching. Each stage section has the same shape — Status, Contract, Code location, Design decisions and why, Failure modes — so you can land in the middle and know where you are.

---

## 1. System at a glance

The whole thing is a 6-stage pipeline. Stages communicate through pydantic models (in process) or through the SQLite buffer (across processes). Each stage is replaceable as long as it honors the contract on either side.

```
                                ┌─────────────────────────┐
   Ticker list  ──────────────▶ │ 1. Fetcher (DONE)       │
                                │   src/algo_trade/fetcher.py
                                │   in:  ticker, forms
                                │   out: FetchedFiling[]  │
                                └────────────┬────────────┘
                                             │ FetchedFiling
                                             ▼
                                ┌─────────────────────────┐
                                │ 2. Extractor (DONE)     │
                                │   src/algo_trade/extractor.py
                                │   in:  FetchedFiling
                                │   out: ExtractedFiling  │
                                │   (Agent #1 — Claude)   │
                                └────────────┬────────────┘
                                             │ ExtractedFiling
                                             ▼
                                ┌─────────────────────────┐
                                │ 3. Buffer (DONE)        │
                                │   src/algo_trade/buffer/store.py
                                │   SQLite (canonical)    │
                                └────────────┬────────────┘
                                             │ SQL
                       ┌─────────────────────┼─────────────────────┬───────────────┐
                       ▼                     ▼                     ▼               ▼
            ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐
            │ 4. Timeline      │  │ 6. Recommender   │  │ Web app          │  │ Backtest     │
            │    Aggregator    │  │    (Agent #2)    │  │ (read-only)      │  │ harness      │
            │    (DONE)        │  │    (PLANNED)     │  │ (PLANNED)        │  │ (PLANNED)    │
            │ → per-sector     │  │ → ranked sectors │  │ → curves + BUY/  │  │ → measure    │
            │   monthly curves │  │   with citations │  │   SELL markers   │  │   prediction │
            └────────┬─────────┘  └──────────────────┘  └──────────────────┘  │   vs sector  │
                     │ pandas DataFrame                                       │   ETFs       │
                     ▼                                                        └──────────────┘
            ┌──────────────────┐
            │ 5. Buy/Sell Timer│
            │   (DONE)         │
            │ forward-AUC      │
            │ over the curve   │
            └──────────────────┘
```

---

## 2. Stages

### Stage 1 — Fetcher

| | |
|---|---|
| **Status** | DONE |
| **Code** | [`src/algo_trade/fetcher.py`](../src/algo_trade/fetcher.py) |
| **Input** | `ticker: str`, `forms: Iterable[str]`, `limit: int` |
| **Output** | `list[FetchedFiling]` |
| **CLI** | `algo-trade-fetch --identity "Name email" --ticker NVDA --form 10-K --limit 1` |
| **Tests** | [`tests/test_fetcher.py`](../tests/test_fetcher.py) (no network — fake Filing objects) |

**What it does.** Resolves a ticker through `edgartools`, lists filings, and for each filing pulls MD&A + Risk Factors (10-K / 10-Q) or full text (8-K, or when typed extraction fails). Returns a flat list, most-recent first.

**Why `edgartools`.** SEC requires a contact-bearing User-Agent and ≤10 req/s. `edgartools` handles that plus typed section extraction (MD&A, Risk Factors), so we don't reimplement EDGAR. See README §"EDGAR Fetcher" for the full reasoning.

**Failure modes (and how the code handles them):**
- Unresolvable ticker → log warning, return `[]`. A batch of 200 tickers should survive one bad one.
- `edgartools` can't parse typed sections → fall back to `filing.text()`, record a warning on the `FetchedFiling.extraction_warnings`. The extractor agent still has something to read.
- Network error → propagated. The fetcher does not retry; that's the caller's call (cron, queue, etc.).

---

### Stage 2 — Extractor (Agent #1)

| | |
|---|---|
| **Status** | DONE |
| **Code** | [`src/algo_trade/extractor.py`](../src/algo_trade/extractor.py) |
| **Input** | `FetchedFiling` |
| **Output** | `ExtractedFiling` (contains `dated_effects[]`, `flagged_risks[]`, `extractor_confidence`) |
| **Model** | `claude-opus-4-7` by default (configurable) |
| **Tests** | [`tests/test_extractor.py`](../tests/test_extractor.py) (no API calls — fake `Anthropic` client) |

**What it does.** One LLM call per filing. The model reads MD&A + Risk Factors, identifies concrete forward-looking plans, and emits `dated_effect` records of the shape `(sector, direction, magnitude, window_start, window_end, rationale, source_span)`. The Anthropic API enforces the JSON schema server-side via `output_config.format`.

**Key API choices** (these are not arbitrary — each is justified in §5 below):
- **Model.** `claude-opus-4-7`. Grounding forward-looking claims in specific source spans is intelligence-sensitive financial reasoning. The Anthropic API skill mandates Opus 4.7 as default and explicitly says not to silently downgrade for cost.
- **Adaptive thinking** (`thinking: {"type": "adaptive"}`). Claude budgets its own thinking per filing.
- **Effort = `"high"`.** A minimum of `high` is recommended for intelligence-sensitive work.
- **Structured outputs via `output_config.format`.** One round trip; the API rejects schema-violating outputs. Cleaner than tool use for "emit this JSON."
- **Prompt caching on the system prompt** (`cache_control: {"type": "ephemeral"}`). The system prompt and the JSON schema are identical across filings — we pay the instructions+schema cost roughly once per batch instead of N times.
- **Streaming** via `client.messages.stream` + `.get_final_message()`. Filings are long inputs; non-streaming hits SDK HTTP timeouts.

**Defensive validation** (after the API call):
- Effects with `window_end < window_start` are dropped, with a warning appended to `extraction_warnings`. The model's JSON validator and our pydantic validator both check this; the second is a belt-and-braces guard.
- Effects with empty `source_span` are dropped (CHECK constraint in the buffer; pydantic validator; LLM prompt rule). Anything not grounded in the filing is noise.
- `extractor_confidence` outside `[0, 1]` is clamped; non-numeric → `0.0` with a warning.
- `flagged_risks` that isn't a list → `[]` with a warning. Defends against model regressions.

**Stop reasons handled** (per the Anthropic API skill — Claude 4.5+ can emit these):
- `"refusal"` → raise `RuntimeError` with the explanation.
- `"model_context_window_exceeded"` → raise. Mitigation is to split sections upstream or pick a model with a larger context window.
- `"max_tokens"` → record a warning, return whatever parsed. The output is structured JSON, so partial truncation usually still gives some usable effects.

**Surfaced cache metrics.** `ExtractedFiling.cache_read_input_tokens` and `.cache_creation_input_tokens` are read from the API's `usage` block so a successor can verify caching is actually working by inspecting outputs, not by reading logs.

---

### Stage 3 — Buffer

| | |
|---|---|
| **Status** | DONE |
| **Schema** | [`src/algo_trade/buffer/schema.sql`](../src/algo_trade/buffer/schema.sql) |
| **Code** | [`src/algo_trade/buffer/store.py`](../src/algo_trade/buffer/store.py) |
| **DB** | SQLite (single file: `data/buffer.sqlite`) |
| **CLI** | `algo-trade-extract --identity "Name email" TSLA --form 10-K --limit 1` |
| **Tests** | [`tests/test_buffer_store.py`](../tests/test_buffer_store.py) (23 tests, hermetic — no network) |

**What it is.** The persistent contract between Agent #1 (writes) and everything downstream (reads): the timeline aggregator, the recommender, the web app, the backtest harness.

**Schema** (full DDL in [`schema.sql`](../src/algo_trade/buffer/schema.sql)):

```
filings (accession_number PK, ticker, cik, company_name, filing_type, filing_date, fetched_at)
   ▲
   │ FK
   │
extractions (id PK, accession_number FK, extractor_model, extractor_confidence, extracted_at,
             UNIQUE (accession_number, extractor_model))
   ▲
   │ FK (CASCADE)
   │
dated_effects (id PK, extraction_id FK, sector, direction CHECK, magnitude CHECK,
               window_start, window_end CHECK window_end>=window_start, rationale, source_span)
flagged_risks (id PK, extraction_id FK, risk)
extraction_warnings (id PK, extraction_id FK, warning)
```

Three normalized tables for the core data + two child tables for the secondary metadata. Indexes are placed for the two query patterns we actually have: `(sector, window_start, window_end)` for the timeline aggregator and web app curves, and `(ticker, filing_date)` for per-company drill-down.

**Re-run semantics.** The UNIQUE constraint on `extractions(accession_number, extractor_model)` means re-running the extractor with the same model is an upsert, not a duplicate. Re-running with a *different* model produces a second `extractions` row alongside the first — both versions stay queryable side-by-side, which is what you want for A/B-ing models without losing history.

**Python API** (`src/algo_trade/buffer/store.py`):

```python
from algo_trade.buffer import Buffer

with Buffer("data/buffer.sqlite") as buf:
    buf.upsert(extracted_filing, company_name="Tesla, Inc.")  # idempotent on (accession, model)

    rows = buf.effects_for_sector(                # window-intersection query
        "Lithium",
        since=date(2026, 1, 1),
        until=date(2026, 12, 31),
    )  # -> list[SectorEffectRow]

    buf.filings_citing("Lithium")                # for the web app's drill-down
    buf.count_extractions()                      # quick sanity check
```

Internally holds a `sqlite3.Connection` with `PRAGMA foreign_keys = ON` and `PRAGMA journal_mode = WAL` for read-while-writing. `curve()` / `top_sectors()` (columnar aggregation) are deferred to Stage 4 (DuckDB).

**Sample queries the web app will run** (full Lithium curve in a window):

```sql
SELECT e.window_start, e.window_end, e.direction, e.magnitude,
       e.rationale, e.source_span,
       f.ticker, f.filing_date, f.company_name
FROM   dated_effects e
JOIN   extractions   x ON x.id = e.extraction_id
JOIN   filings       f ON f.accession_number = x.accession_number
WHERE  e.sector       = ?
  AND  e.window_start < ?   -- window_end of interval of interest
  AND  e.window_end   > ?   -- window_start of interval of interest
ORDER  BY e.window_start;
```

**Analytical reads via DuckDB.** When the timeline aggregator needs to do columnar aggregation across the whole buffer ("monthly bucketed signal per sector, all time"), DuckDB attaches the SQLite file without copying:

```python
import duckdb
con = duckdb.connect()
con.execute("ATTACH 'data/buffer.sqlite' AS buf (TYPE sqlite, READ_ONLY)")
df = con.execute("""
    SELECT date_trunc('month', window_start) AS month,
           sector,
           SUM(CASE direction WHEN 'increase' THEN 1 ELSE -1 END
               * CASE magnitude WHEN 'large' THEN 1.0
                                WHEN 'moderate' THEN 0.6
                                ELSE 0.3 END
               / (julianday(window_end) - julianday(window_start) + 1) * 30) AS signal
    FROM buf.dated_effects
    GROUP BY 1, 2
""").fetch_df()
```

SQLite is canonical (one writer, ACID); DuckDB is the analytical read layer when columnar perf matters.

**Upgrade path to Postgres** (only if/when this gets a real multi-user backend):
- The DDL ports almost verbatim. Type changes: `INTEGER PRIMARY KEY` → `BIGSERIAL PRIMARY KEY`; `TIMESTAMP` → `TIMESTAMP WITH TIME ZONE`; SQLite's permissive `DATE` (text) → Postgres `DATE`.
- The Python `Buffer` class abstracts the driver; only `__init__` changes (connection string).
- Don't migrate to Postgres until there's actually a second writer or a hosted deployment. Premature.

---

### Stage 4 — Sector Timeline Aggregator

| | |
|---|---|
| **Status** | DONE |
| **Code** | [`src/algo_trade/timeline.py`](../src/algo_trade/timeline.py) |
| **Input** | `Buffer` via `all_effects()` |
| **Output** | `pandas.DataFrame` with `(month, sector, signal)` rows |
| **Tests** | [`tests/test_timeline.py`](../tests/test_timeline.py) |

**Algorithm:**
1. For each `dated_effect`, compute its weight: `magnitude_weight × direction_sign` where `magnitude_weight ∈ {small: 0.3, moderate: 0.6, large: 1.0}` and `direction_sign ∈ {increase: +1, decrease: -1}`.
2. Spread the weight uniformly across the calendar months overlapping `window_start`–`window_end`.
3. Sum across all filings, per sector, per month. Result: one dense time series per sector.

**Python API:**

```python
from algo_trade import build_curve, build_all_curves

curve = build_curve(buf, "lithium", since=date(2026, 1, 1), until=date(2026, 12, 31))
# columns: month, sector, signal — dense monthly index, zero-filled gaps

all_curves = build_all_curves(buf, since=..., until=...)
```

When `extractor_model` is omitted, `Buffer.all_effects()` dedupes to the latest extraction per accession so A/B model runs are not double-counted.

---

### Stage 5 — Buy/Sell Timer

| | |
|---|---|
| **Status** | DONE |
| **Code** | [`src/algo_trade/timer.py`](../src/algo_trade/timer.py) |
| **Input** | The aggregator's per-sector curve |
| **Output** | `list[TimerSignal]` and mock-shaped `material_forecast()` dict |
| **Tests** | [`tests/test_timer.py`](../tests/test_timer.py) |

**Default algorithm — forward-looking area under the curve:**

```
forward_AUC(t) = Σ signal(t+1), signal(t+2), ..., signal(t+W)    # W = 3 months default
```

- **BUY** at the leading edge of the area: where `forward_AUC` is rising and crosses a positive threshold.
- **SELL** at the top of the area: where `forward_AUC` peaks and starts declining.

This is intentionally simple — it gives the web app something to render and the backtest harness something to evaluate. Alternative strategies (`slope`, `peak`, `threshold_dwell`) are stubbed in `TimerStrategy` and raise `NotImplementedError` for now.

**Python API:**

```python
from algo_trade import material_forecast, detect_actions, TimerConfig

forecast = material_forecast(buf, "lithium", since=..., until=...)
# dict aligned with mock MaterialForecast: actions, curve (signal + forward_AUC), etc.

actions = detect_actions(enriched_curve, config=TimerConfig(lookahead_months=3))
```

---

### Stage 6 — Recommender (Agent #2)

| | |
|---|---|
| **Status** | PLANNED |
| **Planned code** | `src/algo_trade/recommender.py` |
| **Input** | The buffer (full content, date-bounded slice) |
| **Output** | Ranked sectors with rationale + supporting ticker citations |
| **Planned model** | `claude-opus-4-7` (reasoning-heavy, low-volume) |

**Why a second agent at all.** The aggregator answers *when* via math. The recommender answers *which sector and why*, in prose, with citations. The buffer is the shared contract — the recommender reads from it and cannot invent claims that aren't in it. Every claim must cite at least one ticker present in the buffer; this is the rule we'll enforce in the prompt and validate in code.

---

## 3. File map

```
algo-trade/
├── README.md                          # design intro, the marketing/overview doc
├── docs/
│   └── ARCHITECTURE.md                # this file — the technical reference
├── pyproject.toml                     # deps, build, CLI entry points, package data
├── src/
│   └── algo_trade/
│       ├── __init__.py                # public API re-exports
│       ├── models.py                  # FetchedFiling, ExtractedFiling,
│       │                              # DatedEffect, Direction, Magnitude
│       ├── fetcher.py                 # Stage 1 + algo-trade-fetch CLI
│       ├── extractor.py               # Stage 2 (Agent #1)
│       ├── buffer/                    # Stage 3
│       │   ├── __init__.py            # Buffer export + schema_sql()
│       │   ├── store.py               # Buffer class
│       │   └── schema.sql             # canonical DDL
│       ├── timeline.py                # Stage 4 — monthly aggregation
│       ├── timer.py                   # Stage 5 — forward-AUC BUY/SELL
│       └── (planned: recommender.py)
├── tests/
│   ├── test_fetcher.py                # fake Filing objects — no network
│   ├── test_extractor.py              # fake Anthropic client — no API calls
│   ├── test_buffer_store.py           # Buffer upsert + query
│   ├── test_timeline.py               # monthly curve aggregation
│   └── test_timer.py                  # forward-AUC + action detection
├── examples/
│   ├── fetch_one.py                   # fetch NVDA's latest 10-K
│   └── extract_one.py                 # fetch + extract end-to-end
└── data/                              # local SQLite + cache (gitignored)
```

---

## 4. How to run, test, extend

### Install (editable, with dev deps)

```sh
pip install -e ".[dev]"
```

### Run the tests

```sh
python -m pytest
```

All tests are hermetic: the fetcher tests use fake `Filing` objects, the extractor tests inject a fake `Anthropic` client. No network, no API key required to run tests. CI-friendly.

### End-to-end smoke test (does hit the network + costs Anthropic tokens)

```sh
export ANTHROPIC_API_KEY=sk-ant-...
python examples/extract_one.py "Your Name you@example.com"
```

### Apply the buffer schema to a fresh DB

```sh
mkdir -p data
sqlite3 data/buffer.sqlite < src/algo_trade/buffer/schema.sql
```

Or programmatically:

```python
import sqlite3
from algo_trade.buffer import schema_sql

con = sqlite3.connect("data/buffer.sqlite")
con.executescript(schema_sql())
```

### Add a new stage

1. Define its pydantic input/output models in `models.py`.
2. Implement the stage as a class in its own module.
3. Add unit tests that don't require the network or the API (use injection — see how `extractor.py` accepts a `client=` argument).
4. Re-export the public symbols from `algo_trade/__init__.py`.
5. Update this doc's "Stages" and "File map" sections.

### Swap the extractor model (e.g., for cost on a backfill)

```python
Extractor(model="claude-sonnet-4-6")   # downgrades; re-running goes into a new
                                       # extractions row, original Opus extraction stays
```

---

## 5. Design decisions log

The *what* is documented above. This is the *why*. When you're about to refactor something, check here first — many obvious-looking simplifications were considered and rejected for a reason.

### Two agents instead of one big prompt
- **Cost.** Filings are huge. Re-feeding 50 × 200-page 10-Ks into the recommender every time we want a new ranking would burn tokens forever.
- **Auditability.** The buffer is human-readable. You can challenge an extraction before the recommender ever sees it.
- **Composability.** Either agent can be swapped (new model, new prompt) without touching the other.
- **Determinism where it matters.** Extraction is narrow and schema-constrained → easy to test. "What should I buy" is open-ended → hard to test. Keep them separate so the testable half stays testable.

### Magnitude is qualitative (`small`/`moderate`/`large`), not dollars
Companies almost never commit to dollar figures in MD&A. The extractor would have to invent them, and any made-up number would propagate into the aggregator and bias the curve. Qualitative magnitude is honest about the uncertainty. The aggregator turns it into a numeric weight (0.3 / 0.6 / 1.0) — that weight is a *modeling choice*, documented in one place, swappable.

### Effects are time-windowed (`window_start`, `window_end`)
The whole point of the timeline graph is that companies stage plans across months. A single date wouldn't capture "lithium ramp from May through August." A window does. The extractor's prompt is explicit that effects with no derivable window must be dropped — better to lose a signal than to invent a date.

### SQLite over JSONL for the buffer
Discussed in detail in §"Stage 3". Short version:
- The web app needs indexed queries; JSONL would mean full scans on every page load.
- The CHECK constraints catch bad extractor output at write time (e.g. `window_end < window_start`, empty `source_span`).
- Schema enforcement makes regressions visible.
- One file, ACID, plays with any SQLite driver.

### Claude Opus 4.7 as the extractor default
- The Anthropic API skill mandates Opus 4.7 as the default model and explicitly forbids silent downgrades.
- Grounding forward-looking financial claims in source spans is intelligence-sensitive — `claude-haiku-4-5` would miss subtle hedging language.
- For cost-sensitive backfills, the constructor accepts `model="claude-sonnet-4-6"` so the caller can downgrade *explicitly*. That decision is logged in the buffer (`extractions.extractor_model`) so re-extractions are comparable.

### `output_config.format` instead of tool use for structured output
- One round trip vs. an agentic tool-use loop.
- The API enforces the JSON schema server-side — invalid outputs never reach us.
- Compiled schemas are cached server-side for 24h, so the first call pays the compile cost and every subsequent call is fast.
- Tool use would be the right shape if the extractor needed to *act* on its output (call other tools); it doesn't.

### Prompt caching on the system prompt, not on the user message
- The system prompt + JSON schema is the part that's identical across every filing — that's the cacheable prefix.
- The user message (per-filing text) is volatile by definition.
- `cache_control={"type": "ephemeral"}` on the last system block caches both `tools`/`output_config` and `system` together (render order is `tools → system → messages`).
- Verification: read `ExtractedFiling.cache_read_input_tokens` after the first filing in a batch; it should be >0 on the second filing.

### A narrative-derived signal is not the same as a price signal
This is the most important caveat in the whole project. Companies say what they *plan* to do; markets price what they *think* will happen; the actual outcome is a third thing. The README and this doc both highlight that the backtest harness (Stage 6+) is non-negotiable — until we measure whether the recommender's calls outperform sector ETFs, nothing here is actionable. Build the harness *before* you ship a UI that suggests trades.

---

## 6. Open work

In priority order:

1. **Buffer Python API** — `Buffer` class that upserts `ExtractedFiling`, exposes `curve()`, `top_sectors()`, `filings_citing()`. See Stage 3 sketch.
2. **CLI extension** — `algo-trade-extract` that pipes `algo-trade-fetch` JSONL into the buffer through the Extractor. Mirrors `algo-trade-fetch`.
3. **Timeline aggregator** — Stage 4. Pandas/DuckDB on top of the buffer.
4. **Buy/Sell timer** — Stage 5. Pure NumPy on the aggregator's output.
5. **Plot** — matplotlib + plotly. One-shot static and interactive views.
6. **Recommender** — Stage 6 (Agent #2). Same Claude defaults as the extractor.
7. **Backtest harness** — measure recommender + timer calls against subsequent sector ETF returns. Required before treating any of this as actionable.
8. **Web app** — read-only Flask/FastAPI dashboard over the buffer. Schema is already shaped for it.

Each item gets its own commit; each gets its own ARCHITECTURE.md update. Don't accumulate undocumented stages.

---

## 7. Conventions

- **No silent truncation.** If an input is too long, raise — don't drop bytes. (See `_build_user_prompt` in `extractor.py`.)
- **No silent retries.** If the network or the API fails, propagate. The caller decides whether to retry. (Exception: the fetcher logs-and-skips bad filings inside a batch.)
- **Failures stay visible.** Anything dropped (an effect, a section) gets recorded on a `*_warnings` field that flows downstream. The buffer has `extraction_warnings` for the same reason.
- **Schema is the contract.** When in doubt, write the type/DDL first, then the code.
- **Tests are hermetic.** No network, no API keys, no live SQLite in the test suite. Inject fakes (see `tests/test_extractor.py` for the pattern).
- **The README is for newcomers; this doc is for contributors.** Keep them in sync but don't merge them — they have different audiences and different lengths.

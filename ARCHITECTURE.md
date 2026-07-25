# Architecture — Materials Sector-Rotation Signal from SEC Filings

> **Working title:** FilingSignal v2 (name provisional).
> **Status:** design spec for a ground-up rebuild. Stages below are marked
> `PLANNED` until implemented. This document is written to describe the code we
> intend to build; when code lands, this doc is updated to match it — never the
> reverse. (The predecessor project's docs described aspirations the code didn't
> honor; we don't repeat that.)

---

## 0. One-paragraph statement

An LLM reads the SEC filings of the companies that **produce** and **consume**
industrial materials (copper, gold, uranium, steel, silver, rare earths),
extracts their **dated, cited, forward-looking plans** into a structured,
auditable database, and turns those into a **point-in-time quarterly score** per
material. Each quarter the system answers one question — *"if I buy exactly one
material's miner-ETF for the next quarter, which one?"* — and then **honestly
measures** whether that pick beat buying the market, holding all materials, or
picking at random. The LLM extracts and explains; deterministic math does the
rating; a rigorous, look-ahead-free backtest delivers the verdict.

The star of this project is **the extraction and the honest evaluation**, not a
claim of alpha. A result of *"the signal does not beat hold, and here is the
look-ahead-free, cost-adjusted, permutation-tested evidence"* is a success.

---

## 1. Thesis and honest caveats

**Thesis.** A material's demand/supply outlook is narrated, ahead of time, in the
filings of the companies exposed to it: producers describe production, capex, and
guidance; consumers describe procurement, capacity, and substitution. Aggregated
point-in-time across many companies, that narration is a candidate predictor of
the **miner-equity ETF** for that material.

**Why the miner-equity ETF is the target (not the commodity).** The companies we
read *are constituents of the ETF we buy* — Freeport (FCX) is a top holding of
COPX. That makes the causal link short and the sign clean: a producer with a
strong outlook, or a consumer signalling more demand, is bullish for the miner
basket. Targeting the *commodity* instead (CPER, GLD) would invert the producer
sign (more supply → lower price) and force a long, leaky "narrative → commodity →
producer profit → ETF" chain. See §9.

**Caveats — these are load-bearing, not disclaimers:**

1. **It's a guidance / post-filing-drift bet.** Filings are public; the market
   prices guidance fast. Any edge lives in the drift *after* the filing. This is
   a small, hard edge — the backtest exists to find out if it's there at all.
2. **Coverage ceiling ~50–70% of ETF weight.** Miner ETFs are foreign-heavy.
   We read U.S. issuers (10-K/10-Q/8-K) and SEC-registered foreign issuers
   (40-F/20-F/6-K), but companies listed *only* abroad (Antofagasta, KGHM,
   Glencore, Shanghai names) never file with the SEC and are permanently
   invisible. We report this, we don't hide it.
3. **Small sample.** ~6 materials × ~10 quarters of history is statistically
   underpowered. We attack this by extending history and by reporting a
   **permutation test** so "is this real or luck?" is answered explicitly.
4. **Narrative ≠ price ≠ outcome.** Companies are optimistic; "ramp in Q3"
   sometimes means Q1 next year. The signal is strongest as *cross-company,
   cross-perspective consensus*, weakest as a single voice.

---

## 2. System at a glance

```
   Universe (materials → ETFs, producers + consumers)
        │
        ▼
┌──────────────────┐   US: 10-K,10-Q,8-K     ┌──────────────────────┐
│ 1. Fetcher       │──ForeigN: 40-F,20-F,6-K─▶│ raw filing sections  │
│    edgartools    │   targeted section pull  │ (MD&A / RF / exhibit)│
└────────┬─────────┘                          └──────────────────────┘
         │ FetchedFiling
         ▼
┌──────────────────┐  incremental: skip if (accession, model) already extracted
│ 2. Extractor     │  Agent #1 (Claude) — schema-enforced
│    Agent #1      │  → summary + dated_effects[ material, perspective,
└────────┬─────────┘     direction, magnitude, window, evidence_quote ]
         │ ExtractedFiling
         ▼
┌──────────────────┐   the auditable contract; filing_date = KNOWLEDGE date
│ 3. Buffer (DB)   │   SQLite: filings → extractions → dated_effects
└────────┬─────────┘
         │ point-in-time reads (filing_date ≤ decision date)
         ▼
┌──────────────────┐   deterministic, cross-sectional, per-quarter
│ 4. Scorer        │   producer_score / consumer_score / combined → z-rank
└────────┬─────────┘
         ├───────────────────────────┬──────────────────────────┐
         ▼                           ▼                          ▼
┌──────────────────┐      ┌──────────────────────┐   ┌──────────────────────┐
│ 5. Rating        │      │ 6. Evaluation        │   │ 7. Backtest          │
│    Agent #2      │      │  rank-IC, permutation │   │  top-1 quarterly pick│
│  explains pick   │      │  hit-rate, calibration│   │  vs 4 baselines +    │
│  with quotes     │      │  perspective decomp   │   │  quantstats tearsheet│
└──────────────────┘      └──────────────────────┘   └──────────────────────┘
         └───────────────────────────┴──────────────────────────┘
                                     ▼
                          ┌──────────────────────┐
                          │ 8. Slim UI           │
                          │  next-qtr pick +      │
                          │  verdict up front     │
                          └──────────────────────┘
```

The **Scorer/Evaluation/Backtest** triangle is the product. The LLM stages feed
it; the UI presents it.

---

## 3. Universe

The universe is a **fixed config file** (`universe/materials.yaml` or `.json`).
Agent #2 never edits it — the material→ETF map is frozen for reproducibility and
performance attribution.

| Material | ETF (miner-equity) | ETF quality | Producers (supply) | Consumers (demand) |
|---|---|---|---|---|
| Copper | **COPX** | clean | FCX, SCCO, Teck, Hudbay, First Quantum | grid/electrical (EMR, ABB), EV (TSLA), utilities |
| Gold | **GDX** | clean | NEM, GOLD, Agnico, Kinross, B2Gold | — (demand is macro; producer-only) |
| Uranium | **URNM** | clean | UEC, LEU, UUUU, Cameco, NexGen, Denison | nuclear utilities |
| Steel | **SLX** | steel + iron ore | NUE, STLD, CLF, RS, X, ArcelorMittal | autos (F, GM), CAT, DE, construction |
| Silver | **SIL** | byproduct-heavy | CDE, HL, Wheaton, Pan American, SSR | electronics/solar (thin) |
| Rare earth | **REMX** | strategic-metals mix | MP, USAR | defense (BA, LMT, NOC, GE) |

Benchmarks: **SPY** and an **equal-weight basket** of the material ETFs.

**Deliberately excluded and why:**
- **Lithium / LIT** — LIT is a *battery-supply-chain* ETF (Rio 20%, Panasonic,
  CATL; Albemarle only ~5%), not a lithium-miner basket. No clean pure
  lithium-miner instrument exists; lithium is deferred until one does.
- **Semiconductors / SMH** — chips are not a mined material.
- **Aluminum, coal, standalone natural gas** — delisted/contango-broken ETFs
  (JJU, KOL) or drag (UNG); these are where the predecessor's backtest got messy.

**Filing forms by issuer tier** (see §9 "coverage"):
- **U.S. domestic** → `10-K` (annual), `10-Q` (quarterly), `8-K` (events).
- **SEC-registered foreign** → `40-F`/`20-F` (annual, carry the AIF+MD&A),
  `6-K` (interim/events — content ≈ 8-K).
- **Foreign, U.S.-unregistered** → nothing on EDGAR. Invisible. Documented gap.

**8-K/6-K item priority:** `Item 1.01` (offtake/JV agreements) and `Item 8.01`
(project announcements) carry *less-priced-in* event signal (real drift
potential); `Item 2.02` (earnings) is richer but maximally priced-in — used for
coverage, not alpha. Most 8-Ks are routine noise and get gated out before the LLM.

---

## 4. Stages

Each stage is a replaceable module behind a pydantic contract. Same shape for
each: **Status · Contract · Design notes**.

### Stage 1 — Fetcher `PLANNED`

- **Contract:** `(ticker, forms, limit) → list[FetchedFiling]`. `FetchedFiling`
  carries metadata + a `sections: dict[str,str]` (`mda`, `risk_factors`,
  `exhibit`, `full_text`) + `extraction_warnings: list[str]`.
- **Design.** Thin wrapper over `edgartools`. Handles all six forms. **Section
  isolation is the priority fix over the predecessor:** for 10-K/10-Q pull
  MD&A + Risk Factors; for 40-F/20-F pull the AIF + MD&A exhibits; for 8-K/6-K
  pull the relevant `EX-99` press-release exhibit — *not* the 409K-char full
  dump. **When typed extraction falls back to full text, it MUST record a loud
  warning** (the predecessor failed this silently for Tesla, feeding the model a
  ~10× diluted input). No silent truncation.

### Stage 2 — Extractor / Agent #1 `PLANNED`

- **Contract:** `FetchedFiling → ExtractedFiling`. Schema-enforced JSON via the
  Anthropic API `output_config.format`.
- **Output shape:**
  ```
  ExtractedFiling {
    summary: str                 # human-readable one-paragraph filing description
    extractor_confidence: float  # [0,1]
    dated_effects: [ DatedEffect ]
    flagged_risks: [str]         # optional, short
  }
  DatedEffect {
    material: str                # canonical (must match universe vocabulary)
    perspective: 'producer'|'consumer'
    direction: 'increase'|'decrease'
    magnitude: 'small'|'moderate'|'large'
    window_start: date
    window_end: date             # >= window_start
    rationale: str               # paraphrase
    evidence_quote: str          # VERBATIM filing text — non-empty
    source_span: str             # locator (item/section)
  }
  ```
- **Incremental.** Before calling the model, check the DB for an extraction on
  `(accession_number, model)`. If present → **skip the LLM call**, reuse. Same
  filing + same model = no tokens spent. Different model = re-analyze (A/B kept).
- **`perspective` is inferred per-effect from context**, not from a company
  label — the same company can produce one material and consume another (Tesla
  consumes copper, refines its own lithium). Checkable against `evidence_quote`.
- **Canonical material vocabulary** (from the universe file) is injected into the
  cached system prompt with a "use EXACTLY the canonical name" rule, so labels
  join to the scorer (the predecessor emitted free-form junk like "Bauxite",
  "Bromine specialty chemicals" that never matched a curve).
- **Window discipline.** Prefer concrete near-term windows; **drop** effects
  whose window can't be bounded, and prefer dropping over inventing a vague
  full-calendar-year window (the predecessor's median window was 365 days —
  useless for quarterly discrimination).
- **Defensive post-validation** (each drop recorded as a warning): inverted date
  windows dropped; empty `evidence_quote` dropped; confidence clamped to [0,1];
  non-canonical materials flagged.
- **Model:** current tier (Opus 4.8 / Sonnet 5 / Haiku 4.5), configurable via
  env; the doc and the config default **agree** (predecessor claimed Opus, ran
  Haiku). Prompt caching on the system prompt; streaming for long inputs.

### Stage 3 — Buffer (DB) `PLANNED`

- **The contract of the whole system.** Agent #1 writes; scorer, rating,
  evaluation, backtest, UI all read. SQLite, one file. `filing_date` is the
  **knowledge date** — the point-in-time anchor everything downstream honors.
- **Schema:** see §6.
- **Idempotency:** `UNIQUE(accession_number, extractor_model)`. Re-running the
  same model upserts; a different model gets its own row (models comparable
  side-by-side). This is what makes Stage 2's skip-if-analyzed safe.

### Stage 4 — Scorer (deterministic, point-in-time) `PLANNED`

- **Contract:** `(buffer, material, quarter) → score`, and
  `(buffer, quarter) → {material: z_score}` cross-sectionally. **Pure math, no
  LLM.** See §5 for the model.
- **Point-in-time is not optional.** Every read admits only effects with
  `filing_date ≤ decision_date`. There is no "full buffer" mode — the
  predecessor made look-ahead the *default* and leaked future knowledge. Here it
  is structurally impossible.

### Stage 5 — Rating / Agent #2 (explainer) `PLANNED`

- **Contract:** `(ranked materials + supporting effects) → prose recommendation`
  per material: the call, the rationale, **supporting tickers with quoted
  evidence from both perspectives**, and dissenting evidence.
- **Agent #2 explains; it never picks the instrument or edits the rank.** The
  rating is the deterministic z-rank from Stage 4; the LLM narrates it. Grounding
  rule: every claim cites a ticker/quote present in the buffer; code drops
  unknown citations. This keeps the rated number reproducible and backtestable
  while giving the UI a human "why."

### Stage 6 — Evaluation `PLANNED`

- **Contract:** `(scores over history, realized returns) → evaluation report`.
  This is the rigor centerpiece. See §7.

### Stage 7 — Backtest `PLANNED`

- **Contract:** `(scores, prices, config) → BacktestResult + tearsheet`.
  Top-1 (and top-2/3) quarterly rotation vs four baselines, costs, quantstats.
  See §7.

### Stage 8 — Slim UI `PLANNED`

- React (salvaged, slimmed). Views: **next-quarter pick + verdict card up
  front**, per-material score history, contributing filings with quotes, and the
  **evaluation scorecard** (equity curve vs baselines, rank-IC, hit/miss grid).
  The honest backtest verdict is the first thing shown, not buried.

---

## 5. The scoring model (how math rates the extractions)

For a target quarter **Q** with decision date **d = first day of Q**:

**Eligibility.** An effect `e` counts toward material `m` in quarter `Q` iff
`e.material == m`, `e.filing_date ≤ d` (point-in-time), and
`[e.window_start, e.window_end] ∩ Q ≠ ∅`.

**Per-effect contribution:**
```
contribution(e) = sign · magnitude · confidence · recency · overlap

sign        = +1 (increase) | −1 (decrease)
magnitude   = {small:1, moderate:2, large:3}          # ordinal, tunable
confidence  = e.extractor_confidence ∈ [0,1]
recency     = exp(−λ · age_months),  age = months(d − filing_date),
              λ = ln2 / 12            # 12-month half-life, tunable
overlap     = |window ∩ Q| / |Q| ∈ (0,1]              # share of Q the plan covers
```

**Per-perspective raw scores** (the tag drives this split):
```
producer_raw(m,Q) = Σ contribution(e)  over producer-tagged e
consumer_raw(m,Q) = Σ contribution(e)  over consumer-tagged e
```

**Cross-perspective breadth gate** (consensus matters — one voice is noise):
```
n_p = # distinct producer tickers contributing positively
n_c = # distinct consumer tickers contributing positively
producer_score = producer_raw · (1 − exp(−n_p / k))    # k tunable (≈2)
consumer_score = consumer_raw · (1 − exp(−n_c / k))
```

**Combine, then standardize cross-sectionally within the quarter:**
```
combined(m,Q) = w_p · producer_score + w_c · consumer_score   # default w=1,1
z(m,Q)        = (combined(m,Q) − mean_m combined) / std_m combined
pick(Q)       = argmax_m z(m,Q)
```

A high `+z` is the claim "this material's producers and/or consumers are, on net,
credibly and recently narrating rising activity into Q, and several of them
agree." That claim is exactly what the evaluation tests.

**Hyperparameters** `{magnitude map, λ, k, w_p, w_c}` are **modeling choices,
not truths.** Rules: sensible defaults (above); **never tuned on the test
period**; report a **sensitivity sweep** (does the result survive a reasonable
range?). The predecessor's fatal tell was treating arbitrary weights as fact —
we don't. Crucially, `w_p`/`w_c` and the producer sign are **informed by the
measured per-perspective rank-IC** (§7), not assumed — a producer ramp could be
bullish (optimism) or bearish (glut) for the equity, and only the data decides.

---

## 6. Data model (SQLite DDL)

```sql
CREATE TABLE filings (
  accession_number TEXT PRIMARY KEY,
  ticker           TEXT NOT NULL,
  cik              TEXT NOT NULL,
  company_name     TEXT,
  form             TEXT NOT NULL,            -- 10-K,10-Q,8-K,40-F,20-F,6-K
  filing_date      DATE NOT NULL,            -- KNOWLEDGE date (point-in-time anchor)
  fetched_at       TIMESTAMP NOT NULL
);

CREATE TABLE extractions (
  id                   INTEGER PRIMARY KEY,
  accession_number     TEXT NOT NULL REFERENCES filings(accession_number),
  extractor_model      TEXT NOT NULL,
  extractor_confidence REAL NOT NULL,
  summary              TEXT,                 -- human-readable filing description
  extracted_at         TIMESTAMP NOT NULL,
  UNIQUE (accession_number, extractor_model) -- idempotent; enables skip-if-analyzed
);

CREATE TABLE dated_effects (
  id             INTEGER PRIMARY KEY,
  extraction_id  INTEGER NOT NULL REFERENCES extractions(id) ON DELETE CASCADE,
  material       TEXT NOT NULL,              -- canonical (matches universe vocab)
  perspective    TEXT NOT NULL CHECK (perspective IN ('producer','consumer')),
  direction      TEXT NOT NULL CHECK (direction IN ('increase','decrease')),
  magnitude      TEXT NOT NULL CHECK (magnitude IN ('small','moderate','large')),
  window_start   DATE NOT NULL,
  window_end     DATE NOT NULL CHECK (window_end >= window_start),
  rationale      TEXT NOT NULL,
  evidence_quote TEXT NOT NULL CHECK (length(evidence_quote) > 0),  -- verbatim
  source_span    TEXT
);

CREATE TABLE extraction_warnings (              -- nothing fails silently
  id            INTEGER PRIMARY KEY,
  extraction_id INTEGER NOT NULL REFERENCES extractions(id) ON DELETE CASCADE,
  warning       TEXT NOT NULL
);

CREATE INDEX ix_effects_material_window ON dated_effects(material, window_start, window_end);
CREATE INDEX ix_effects_perspective     ON dated_effects(perspective);
CREATE INDEX ix_filings_ticker_date     ON filings(ticker, filing_date);
```

---

## 7. Evaluation methodology (the rigor centerpiece)

Two questions, answered separately: **(A) is the signal informative?** and
**(B) does trading it make money after costs?** All of it is point-in-time.

### A. Forecast quality — "where it was right vs wrong"

- **Rank-IC (Spearman).** Per quarter, correlate `z(·,Q)` against realized
  next-quarter ETF returns across materials. Report **mean rank-IC ± CI** over
  all quarters. This is the small-universe form of factor IC.
- **Permutation test (the small-N honesty move).** Shuffle the material labels
  10,000× and recompute mean rank-IC to build the null distribution → **p-value**.
  Answers "real or luck?" explicitly, which ~10 quarters otherwise can't.
- **Directional hit-rate + confusion matrix.** Of the up/down calls
  (`sign(z)` vs `sign(realized excess return)`), how many were right?
- **Calibration.** Bucket materials by `z`-tertile; does a higher tertile
  actually realize a higher return?
- **Per-perspective decomposition (enabled by the tag, from day 1).** Report
  rank-IC of **producer-only**, **consumer-only**, and **combined** — the
  headline experiment: *does the demand signal add anything over the producer
  signal?* This also sets whether `w_c > 0` is justified.
- **Per-quarter × per-material hit/miss grid** — the "right vs wrong" visual.

### B. Trading performance — "does the pick make money?"

- **Strategy.** Each quarter hold the **top-1** ETF by `z` (long-only),
  rebalance quarterly. Report **top-2 / top-3 equal-weight** as lower-variance
  variants (a free portfolio-construction beat).
- **Execution realism.** Signal decided on the first trading day of Q; fills at
  the next available **dividend/split-adjusted** close (yfinance `auto_adjust`);
  **transaction-cost bps** charged per rebalance; open position marked at
  window end.
- **Baselines (a pick means nothing without them):**
  | Baseline | What it proves |
  |---|---|
  | **SPY** | Did it beat just buying the market? |
  | **Equal-weight materials** | Did *picking* beat *holding all* materials? |
  | **Best-possible hindsight pick** | The ceiling — how much upside captured? |
  | **Random-pick Monte Carlo (10k)** | The null — does it beat luck? |
- **Reporting.** A **quantstats tearsheet**: Sharpe, Sortino, Calmar, max
  drawdown, CAGR, rolling Sharpe; plus hit-rate, regret vs best, and the
  **$100 equity curve vs all four baselines** (the headline chart).

There is **no look-ahead mode.** The predecessor shipped `walkforward=False` as
the default and leaked; here point-in-time is the only path.

---

## 8. Planned repository layout

```
algo-trade-project-new/
├── ARCHITECTURE.md              # this file
├── PLAN.md                      # phased build plan
├── pyproject.toml
├── universe/
│   └── materials.yaml           # frozen material→ETF, producers, consumers
├── src/filingsignal/
│   ├── models.py                # pydantic contracts (Fetched/Extracted/Effect)
│   ├── fetcher.py               # Stage 1 (US + foreign forms, loud fallbacks)
│   ├── extractor.py             # Stage 2 (Agent #1, incremental, perspective tag)
│   ├── buffer/                  # Stage 3 (SQLite store + schema.sql)
│   ├── scorer.py                # Stage 4 (point-in-time cross-sectional score)
│   ├── rating.py                # Stage 5 (Agent #2 explainer)
│   ├── evaluation.py            # Stage 6 (rank-IC, permutation, decomposition)
│   ├── backtest.py              # Stage 7 (top-1 rotation, baselines, quantstats)
│   ├── prices.py                # yfinance/CSV price loaders (dividend-adjusted)
│   └── llm_config.py            # model resolution; doc == config
├── backend/                     # FastAPI read-only API (slim)
├── frontend/                    # React UI (salvaged, slimmed)
└── tests/                       # hermetic (fake edgar + fake Anthropic clients)
```

---

## 9. Design-decision log (the *why*)

**Producers → miner-equity ETFs (not the commodity, not consumers-only).**
The read company *is* the ETF constituent → short causal link, clean sign. A
commodity target inverts the producer sign and adds a leaky chain. See §1.

**Tag both perspectives from day 1 (not producer-only, not deferred demand).**
Tagging enables the producer-vs-consumer-vs-combined rank-IC decomposition *in
v1*. Sign is consistent at the miner-ETF target (both increase→bullish), but the
true weight of each perspective is **measured**, not assumed.

**U.S. + foreign forms.** Miner ETFs are foreign-heavy; U.S.-only coverage is
~10–20% of ETF weight — a signal swamped by the invisible majority. 40-F/20-F/6-K
lift coverage to ~50–70%. Companies with no U.S. registration are an
irreducible, documented blind spot.

**Deterministic score, LLM explains.** A model-emitted rating is subjective and
un-separable ("is the signal real?" vs "did the model guess well?"). A
deterministic score is reproducible and backtestable; the LLM adds the human
"why," grounded in quotes.

**Incremental extraction (skip already-analyzed).** The predecessor's UNIQUE
constraint deduped at *write* time but still paid for the LLM call. Checking the
DB *before* the call spends zero tokens on re-runs.

**Store verbatim `evidence_quote`.** A locator ("Item 7, p.34") is useless to
Agent #2; the actual sentence lets it cite real words and stays auditable.

**Point-in-time is non-optional.** A trading backtest with an off-by-default
look-ahead switch is not a backtest. Here it's structurally impossible.

**Top-1 quarterly rotation + random-MC baseline.** Matches the product question
("which one this quarter?"); the Monte-Carlo null is what turns "we made X%"
into "we beat luck (or didn't)."

**Qualitative magnitude (small/moderate/large).** Filings rarely commit to
dollar figures; forcing numbers invites hallucination. The ordinal→weight map is
one documented, swappable modeling choice.

**Dropped LIT and SMH.** LIT is a battery-supply-chain ETF, not lithium miners;
SMH is chips, not a mined material. Mapping a producer signal onto a mismatched
ETF is how you manufacture noise.

---

## 10. Conventions

- **No silent anything.** Dropped effects, section-parse fallbacks, truncation —
  all recorded as warnings that flow downstream.
- **Schema is the contract.** Type/DDL first, then code.
- **Tests are hermetic.** No network, no API key in the suite — inject fake
  `edgar` and `Anthropic` clients (a pattern worth salvaging from the
  predecessor, which did this well).
- **Docs match code.** If they drift, the doc is wrong, not the code.
- **Hyperparameters are never fit on the test period**, and their sensitivity is
  reported.

---

## 11. Open / future work

1. **Extend history** as far as filings + prices allow — the main lever against
   the small-sample problem.
2. **Demand-side expansion** — the full consumer table (grid capex, defense
   magnet procurement, EV cell lines) mined primarily from 8-Ks/6-Ks; its value
   is *measured* via the perspective decomposition, not assumed.
3. **Substitution signals** — chemistry shifts (e.g. LFP vs NCM) as explicit
   cross-material effects (bullish one material, bearish another).
4. **Model-vs-math** — optionally let Agent #2 make its *own* pick and backtest
   it against the deterministic score, to measure whether LLM judgment adds edge.
5. **Earnings-call transcripts** as a second, richer input source.
```

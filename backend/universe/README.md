# `universe/` — the project's reference data

This folder is the **universe**: the structured reference data the agents read *around*
the SEC filings. The filings are the live input; this folder is the fixed scaffolding that
tells the pipeline *who* to read, *what vocabulary* to speak, and *what you could buy* once
a conclusion is reached.

Everything here is plain JSON so any LLM (or human) can load it cold and use it without
extra tooling.

## How the files map to the pipeline

Recall the pipeline from the top-level [README](../../README.md): filings → **Agent #1
(Extractor)** → buffer → **Agent #2 (Recommender)** + timeline/timer → plot. The three
data files sit at three different points:

| File | Pipeline role | Answers |
|------|---------------|---------|
| [`manufacturers.json`](manufacturers.json) | **Input** | *Whose filings do we read?* |
| [`materials.json`](materials.json) | **Vocabulary** | *What can a filing be "about"?* |
| [`material-to-index.json`](material-to-index.json) | **Output / actionability** | *Given a material, what could I buy?* |

### `manufacturers.json` — the input universe

The list of companies we pull filings for: the "Ticker / CIK list" at the top of the
architecture diagram. It is the S&P 500 + Dow Jones, **filtered down to companies that
produce physical things** — goods makers plus Energy and Utilities. Pure financial,
software, services, retail, transport, and real-estate names are dropped, because they
have no material consumption to extract; a bank's 10-K won't tell you anything about
lithium demand.

Each row:
```json
{
  "ticker": "AAPL",
  "cik": "0000320193",
  "name": "Apple Inc.",
  "indexes": ["SP500", "DJIA"],
  "gics_sector": "Information Technology",
  "gics_sub_industry": "Technology Hardware, Storage & Peripherals"
}
```
- `cik` is zero-padded to 10 digits to match SEC / `edgartools`. It is the reliable key for
  fetching filings (more stable than the ticker).
- `indexes` lists every index the company belongs to (`SP500`, `DJIA`).
- There is **no per-company product list** — figuring out that "Apple makes iPhones" is
  Agent #1's job from the filing text. Baking guesses in here would pollute the input.

This file is a **point-in-time snapshot** of index membership (see the `generated` date
inside it), built from the S&P 500 + Dow constituent lists and then run through the producer
filter described under *Refreshing* below.

### `materials.json` — the controlled vocabulary

The list of materials/commodities the universe depends on. **This is the vocabulary Agent #1
must speak.** The `id` of each material (e.g. `"lithium"`, `"copper"`, `"electricity"`) is
the canonical token the extractor emits as `dated_effects[].sector`.

Each material carries the fields that let an LLM *reason about exposure*:
- `aliases` — surface forms the extractor should normalize onto the `id` (a filing saying
  "spodumene" or "lithium hydroxide" → `lithium`).
- `used_in` — the products/end-uses the material goes into.
- `consuming_sectors` — the kinds of companies that buy it.
- `category`, `name`, `description` — human/LLM context.

### `material-to-index.json` — the actionability layer

Once the recommender or the buy/sell timer settles on a material, this file says **what you
could actually buy** to express that view. It is keyed by material `id` and groups
instruments into typed **buckets**:

`producers` · `etfs` · `physical` · `futures` · `transporters` · `downstream_consumers`

Empty arrays mean "no clean instrument in that bucket." This is also what the backtest
harness (see the roadmap) would replay against real returns.

## The vocabulary contract

The files only compose if everyone respects two rules:

1. **Agent #1 emits canonical ids.** Every `dated_effects[].sector` the extractor produces
   must be an `id` that exists in `materials.json`. Use `aliases` to map filing language
   onto an id. If a filing discusses a material not in the vocabulary, prefer the closest
   existing id; genuinely new materials should be *added to `materials.json` first*.
2. **Every index key resolves to a material.** Every key in `material-to-index.json` must be
   an `id` in `materials.json`. (Enforced by the integrity check below.)

This is what lets either agent be swapped without breaking the other — the vocabulary, not
the prompts, is the contract.

## Worked example

> **Apple (AAPL)** is in `manufacturers.json` (IT / hardware producer). Agent #1 reads its
> 10-Q, sees it plans to ramp iPhone production. Looking at `materials.json`, `lithium.used_in`
> includes "consumer-electronics batteries" and `consuming_sectors` includes
> "Consumer Electronics" → the extractor emits a `dated_effect` with `sector: "lithium"`,
> `direction: "increase"`. Later, Agent #2 ranks `lithium` as attractive. To act on it, the
> user opens `material-to-index.json["lithium"]` → buy candidates are producers
> (`ALB`, `SQM`, `LAC`), an ETF (`LIT`), or futures — no clean "physical lithium" exists, so
> that bucket is empty.

## Refreshing `manufacturers.json`

The company list changes as index membership changes, so treat `manufacturers.json` as a
snapshot to be rebuilt periodically. It was produced by:

1. Pulling the S&P 500 constituents from Wikipedia "List of S&P 500 companies" (that table
   already carries ticker, GICS sector/sub-industry, and CIK) and the Dow 30 from Wikipedia
   "Dow Jones Industrial Average", with the SEC `company_tickers.json` map as a CIK fallback.
2. Applying the **producer filter**: keep GICS sectors *Materials, Industrials, Consumer
   Discretionary, Consumer Staples, Information Technology, Health Care, Energy, Utilities*;
   drop *Financials, Real Estate, Communication Services* outright; and within the kept
   sectors drop service/non-producing sub-industries (anything whose GICS sub-industry names
   retail, software, IT/health-care/professional services, distribution, or transportation).

`materials.json` and `material-to-index.json` are hand-curated and edited directly.

## Integrity check

Quick check that the vocabulary contract holds (every index key resolves to a material, JSON
is valid):

```bash
py -c "import json; m={x['id'] for x in json.load(open('backend/universe/materials.json',encoding='utf-8'))['materials']}; idx=json.load(open('backend/universe/material-to-index.json',encoding='utf-8'))['indexes']; bad=[k for k in idx if k not in m]; print('OK, all index keys resolve' if not bad else 'DANGLING KEYS: '+str(bad)); missing=[i for i in m if i not in idx]; print('materials without an index entry:', missing or 'none')"
```

## A note on scope and disclaimers

This folder is **data only** — no fetching, extraction, or plotting logic lives here. The
instrument lists in `material-to-index.json` are illustrative, not exhaustive, and **nothing
here is investment advice** (see the top-level README's disclaimer).

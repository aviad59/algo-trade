# algo-trade

An agentic pipeline that reads U.S. SEC EDGAR filings, extracts each company's forward-looking plans and sector dependencies, and uses a second LLM to recommend which sector(s) look most attractive to invest in.

> ⚠️ **Disclaimer:** This project is for research and educational purposes only. Nothing produced by this tool is financial advice. LLMs hallucinate, filings can be misread, and markets do not care what a model thinks. Do your own due diligence.

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
        │  (SEC EDGAR REST API)  │      │  (local, on disk)    │
        └───────────┬────────────┘      └──────────────────────┘
                    │
                    ▼
        ┌────────────────────────────────────────┐
        │  Agent #1 — Extractor                  │
        │  Reads each filing and emits:          │
        │    - planned_actions[]                 │
        │    - dependent_sectors[]               │
        │    - flagged_risks[]                   │
        │    - confidence + source spans         │
        └───────────┬────────────────────────────┘
                    │
                    ▼
        ┌────────────────────────┐
        │  Side buffer           │
        │  (JSONL / SQLite /     │
        │   DuckDB — one row     │
        │   per company×filing)  │
        └───────────┬────────────┘
                    │
                    ▼
        ┌────────────────────────────────────────┐
        │  Agent #2 — Sector Recommender         │
        │  Reads the full buffer and emits:      │
        │    - ranked sectors                    │
        │    - rationale per sector              │
        │    - dissenting evidence               │
        │    - cited company filings             │
        └────────────────────────────────────────┘
```

Two agents, one buffer in between. The buffer is the contract — Agent #1 can be swapped out, Agent #2 can be swapped out, the buffer schema is what holds the system together.

---

## Components

### 1. EDGAR Fetcher

Thin wrapper over the SEC EDGAR submissions and filings APIs.

- Resolves ticker → CIK
- Pulls the most recent 10-K / 10-Q / 8-K (configurable)
- Honors SEC's fair-access rules: `User-Agent` header with contact email, ≤10 requests/sec
- Caches raw filings on disk so re-runs don't hammer EDGAR

### 2. Agent #1 — Extractor

Per-filing LLM call. Output is **strictly structured** (JSON schema enforced), not free text:

```json
{
  "ticker": "NVDA",
  "cik": "0001045810",
  "filing_type": "10-K",
  "filing_date": "2025-02-21",
  "planned_actions": [
    {
      "action": "Expand data-center GPU production capacity",
      "horizon": "12-24 months",
      "source_span": "Item 7, MD&A, p.34"
    }
  ],
  "dependent_sectors": [
    {"sector": "Semiconductor foundries", "criticality": "high"},
    {"sector": "Hyperscale cloud providers", "criticality": "high"}
  ],
  "flagged_risks": ["Export controls to China", "Foundry concentration"],
  "extractor_confidence": 0.82
}
```

The extractor is deliberately conservative: if a claim is not grounded in a source span, it gets dropped.

### 3. Side buffer

One row per `(company, filing)`. Append-only. Easy to query later — the recommender does not re-read raw filings, only this buffer.

Format options (pick whichever fits — they're interchangeable):
- JSONL on disk (simplest)
- SQLite (good for ad-hoc SQL)
- DuckDB (good if buffer grows past a few hundred MB)

### 4. Agent #2 — Sector Recommender

Reads the entire buffer (or a date-bounded slice) and produces a ranked list of sectors with rationale. Output is also structured:

```json
{
  "as_of": "2026-06-08",
  "ranked_sectors": [
    {
      "sector": "Power generation / grid",
      "score": 0.87,
      "rationale": "12 of 47 companies in the buffer flag electricity supply as a binding constraint on planned capex.",
      "supporting_tickers": ["NVDA", "MSFT", "GOOGL", "..."],
      "dissenting_evidence": ["Two utilities flag demand uncertainty"]
    }
  ]
}
```

Every claim the recommender makes must cite tickers from the buffer. If it can't cite, it can't claim.

---

## Why two agents instead of one big prompt?

- **Cost.** Filings are huge. You don't want to re-feed 50 × 200-page 10-Ks into the recommender every time you want a new ranking.
- **Auditability.** The buffer is human-readable. You can see exactly what the extractor pulled and challenge it before the recommender ever sees it.
- **Composability.** You can re-run the recommender with a different prompt, a different model, or a different time window without touching the extractor.
- **Determinism where it counts.** Extraction is a narrow, schema-constrained task — easier to test and validate than open-ended "what should I buy."

---

## Tech stack (intended)

- **Language:** Python 3.11+
- **LLM client:** `anthropic` SDK (Claude Sonnet 4.6 for extraction, Claude Opus 4.7 for the recommender — extraction is volume-heavy and cheaper-model-friendly, recommendation is reasoning-heavy)
- **EDGAR client:** `requests` against `data.sec.gov` (no third-party EDGAR library required)
- **Storage:** JSONL → SQLite → DuckDB depending on scale
- **Validation:** `pydantic` for the buffer schema
- **Orchestration:** plain Python to start; consider a job queue once the universe of tickers grows

---

## Roadmap

- [ ] EDGAR fetcher with on-disk cache
- [ ] Extractor agent with strict JSON schema output
- [ ] Buffer (start with JSONL)
- [ ] Recommender agent
- [ ] CLI: `algo-trade extract --tickers nvda,msft,...` and `algo-trade recommend`
- [ ] Backtest harness: replay the recommender's output against subsequent sector ETF returns to see if it's actually any good
- [ ] Add earnings-call transcripts as a second input source alongside filings
- [ ] Add a "diff" mode: highlight what changed in a company's plans between two filings

---

## Setup

```bash
git clone https://github.com/aviad59/algo-trade.git
cd algo-trade
# (code coming — this repo currently contains the design only)
```

You will need:
- An Anthropic API key (`ANTHROPIC_API_KEY`)
- A contact email for the SEC EDGAR `User-Agent` header (SEC requires this)

---

## Project status

Early. This README is the design doc — code lands next.

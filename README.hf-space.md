---
title: FilingSignal
emoji: 📈
colorFrom: indigo
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# FilingSignal — narrative signals from SEC filings

Two AI agents with a database between them: Agent #1 (Claude) reads each
SEC filing and extracts *dated effects* — which material, which direction,
how big, over which time window, with a verbatim quote as evidence. Pure
math turns those into per-material demand curves and BUY/SELL timing; Agent
#2 ranks materials with grounded, citation-only rationale. A walk-forward
backtest page answers "does it make money?" honestly (no look-ahead bias).

This Space ships with a pre-extracted buffer (51 real filings, Nov 2023 →
May 2026), cached ETF prices, and a frozen Agent #2 ranking — the public
demo runs with **zero LLM spend**. Reviewers with a demo link additionally
get live Agent #2 ranking and can pull new tickers through the live
pipeline.

- Source, docs, and how-to-run: see the project repository README
- Research and education only — not financial advice

**Rename this file to `README.md` when pushing to the Space** (the YAML
front-matter above is what configures the Space; the repo's own README
stays authoritative on GitHub).

-- algo-trade buffer schema (SQLite dialect)
--
-- This is the canonical store for everything Agent #1 (the extractor)
-- produces. It is the contract between:
--   - the extractor (writes one extractions row + N dated_effects rows
--     per filing, idempotently per (accession_number, extractor_model))
--   - the sector timeline aggregator (reads dated_effects, bins by
--     (sector, month), weights by magnitude and direction)
--   - Agent #2, the recommender (reads dated_effects + flagged_risks
--     across many filings, ranks sectors with citations back to ticker)
--   - the web app (read-only: per-sector curves, BUY/SELL markers,
--     per-filing drill-downs)
--
-- See docs/ARCHITECTURE.md for the design rationale (why SQLite, why
-- this normalization, what the upgrade path to Postgres looks like).
--
-- To apply manually:
--     sqlite3 data/buffer.sqlite < src/algo_trade/buffer/schema.sql

PRAGMA foreign_keys = ON;

-- One row per SEC filing the fetcher has pulled. Natural primary key:
-- the SEC accession number, which is globally unique per filing.
CREATE TABLE IF NOT EXISTS filings (
    accession_number TEXT PRIMARY KEY,
    ticker           TEXT NOT NULL,
    cik              TEXT NOT NULL,
    company_name     TEXT,
    filing_type      TEXT NOT NULL,      -- e.g. '10-K', '10-Q', '8-K'
    filing_date      DATE NOT NULL,      -- ISO 8601 (SQLite stores as TEXT)
    fetched_at       TIMESTAMP NOT NULL  -- when *we* fetched it, not when SEC accepted it
);

CREATE INDEX IF NOT EXISTS idx_filings_ticker_date
    ON filings (ticker, filing_date);

-- One row per (filing, extractor_model) pair. Re-running the extractor
-- with a different model produces a second row, not an update -- both
-- versions of the extraction stay queryable side-by-side. Re-running
-- with the *same* model upserts (see UNIQUE constraint below).
CREATE TABLE IF NOT EXISTS extractions (
    id                   INTEGER PRIMARY KEY,
    accession_number     TEXT NOT NULL REFERENCES filings(accession_number),
    extractor_model      TEXT NOT NULL,  -- e.g. 'claude-opus-4-7'
    extractor_confidence REAL NOT NULL,
    extracted_at         TIMESTAMP NOT NULL,
    UNIQUE (accession_number, extractor_model)
);

CREATE INDEX IF NOT EXISTS idx_extractions_accession
    ON extractions (accession_number);

-- One row per time-windowed sector signal the extractor emitted.
-- CASCADE on the FK so dropping an extraction (e.g. to re-run) cleanly
-- takes its effects with it.
CREATE TABLE IF NOT EXISTS dated_effects (
    id            INTEGER PRIMARY KEY,
    extraction_id INTEGER NOT NULL
                  REFERENCES extractions(id) ON DELETE CASCADE,
    sector        TEXT NOT NULL,
    direction     TEXT NOT NULL CHECK (direction IN ('increase', 'decrease')),
    magnitude     TEXT NOT NULL CHECK (magnitude IN ('small', 'moderate', 'large')),
    window_start  DATE NOT NULL,
    window_end    DATE NOT NULL,
    rationale     TEXT NOT NULL,
    source_span   TEXT NOT NULL,
    CHECK (window_end >= window_start),
    CHECK (length(source_span) > 0)
);

-- The aggregator and the web app both want "all effects for sector X
-- intersecting time window [a, b]". This index makes that fast.
CREATE INDEX IF NOT EXISTS idx_effects_sector_window
    ON dated_effects (sector, window_start, window_end);

CREATE INDEX IF NOT EXISTS idx_effects_extraction
    ON dated_effects (extraction_id);

-- Risks the filing explicitly identified as material. Modeled as a
-- child table rather than a JSON blob so the recommender can join /
-- filter on them, and so the web app can render a "risks mentioned by
-- many filings this month" panel without parsing JSON.
CREATE TABLE IF NOT EXISTS flagged_risks (
    id            INTEGER PRIMARY KEY,
    extraction_id INTEGER NOT NULL
                  REFERENCES extractions(id) ON DELETE CASCADE,
    risk          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_flagged_risks_extraction
    ON flagged_risks (extraction_id);

-- Warnings the extractor recorded for this filing (e.g. "dropped
-- dated_effects[2] for inverted window"). Kept so a regression in the
-- model is debuggable from the buffer alone -- you don't need the
-- original LLM transcript.
CREATE TABLE IF NOT EXISTS extraction_warnings (
    id            INTEGER PRIMARY KEY,
    extraction_id INTEGER NOT NULL
                  REFERENCES extractions(id) ON DELETE CASCADE,
    warning       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_extraction_warnings_extraction
    ON extraction_warnings (extraction_id);

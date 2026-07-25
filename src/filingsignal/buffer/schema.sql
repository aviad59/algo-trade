-- FilingSignal buffer — the auditable contract between Agent #1 (writes) and
-- everything downstream (scorer, evaluation, backtest, rating, API). SQLite.
-- filing_date is the KNOWLEDGE date: the point-in-time anchor. See ARCHITECTURE §6.

CREATE TABLE IF NOT EXISTS filings (
    accession_number TEXT PRIMARY KEY,
    ticker           TEXT NOT NULL,
    cik              TEXT NOT NULL,
    company_name     TEXT,
    form             TEXT NOT NULL,          -- 10-K, 10-Q, 8-K, 40-F, 20-F, 6-K
    filing_date      DATE NOT NULL,
    fetched_at       TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_filings_ticker_date ON filings(ticker, filing_date);

CREATE TABLE IF NOT EXISTS extractions (
    id                   INTEGER PRIMARY KEY,
    accession_number     TEXT NOT NULL REFERENCES filings(accession_number),
    extractor_model      TEXT NOT NULL,
    extractor_confidence REAL NOT NULL,
    summary              TEXT,
    extracted_at         TIMESTAMP NOT NULL,
    UNIQUE (accession_number, extractor_model)  -- idempotent; enables skip-if-analyzed
);
CREATE INDEX IF NOT EXISTS ix_extractions_accession ON extractions(accession_number);

CREATE TABLE IF NOT EXISTS dated_effects (
    id             INTEGER PRIMARY KEY,
    extraction_id  INTEGER NOT NULL REFERENCES extractions(id) ON DELETE CASCADE,
    material       TEXT NOT NULL,
    perspective    TEXT NOT NULL CHECK (perspective IN ('producer','consumer')),
    direction      TEXT NOT NULL CHECK (direction IN ('increase','decrease')),
    magnitude      TEXT NOT NULL CHECK (magnitude IN ('small','moderate','large')),
    window_start   DATE NOT NULL,
    window_end     DATE NOT NULL CHECK (window_end >= window_start),
    rationale      TEXT NOT NULL,
    evidence_quote TEXT NOT NULL CHECK (length(evidence_quote) > 0),
    source_span    TEXT
);
CREATE INDEX IF NOT EXISTS ix_effects_material_window ON dated_effects(material, window_start, window_end);
CREATE INDEX IF NOT EXISTS ix_effects_material_persp  ON dated_effects(material, perspective);
CREATE INDEX IF NOT EXISTS ix_effects_extraction      ON dated_effects(extraction_id);

CREATE TABLE IF NOT EXISTS extraction_warnings (
    id            INTEGER PRIMARY KEY,
    extraction_id INTEGER NOT NULL REFERENCES extractions(id) ON DELETE CASCADE,
    warning       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_warnings_extraction ON extraction_warnings(extraction_id);

-- Agent #2 (rating/explainer) output, computed offline and served read-only.
CREATE TABLE IF NOT EXISTS ratings (
    id           INTEGER PRIMARY KEY,
    material     TEXT NOT NULL,
    quarter      TEXT NOT NULL,          -- e.g. "2026 Q3"
    prose        TEXT NOT NULL,
    supporting   TEXT,                   -- JSON: tickers + quotes
    model        TEXT NOT NULL,
    created_at   TIMESTAMP NOT NULL,
    UNIQUE (material, quarter)
);

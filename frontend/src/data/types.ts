/* ============================================================
   Domain types — mirror the ARCHITECTURE.md contracts so the
   UI can later bind to the real read-only API unchanged. These
   are the shapes the backend's evaluation/backtest stages emit.
   ============================================================ */

export type Perspective = "producer" | "consumer";
export type Direction = "increase" | "decrease";
export type Magnitude = "small" | "moderate" | "large";
export type FilingForm = "10-K" | "10-Q" | "8-K" | "20-F" | "40-F" | "6-K";
export type ExtractionStatus = "Extracted" | "Needs review" | "Processing";

/** One material and its frozen miner-equity ETF mapping (universe/materials.yaml). */
export interface MaterialRow {
  material: string;
  etf: string;
  /** cross-sectional z-score for the target quarter; high +z = predicted outperformer */
  z: number;
  producerScore: number;
  /** null where the material is producer-only (e.g. gold: demand is macro) */
  consumerScore: number | null;
  filings: number;
  rank: number;
}

export interface TrendSeries {
  material: string;
  colorVar: string; // CSS custom property, entity-stable
  values: number[]; // z per quarter
}

/** A dated, cited forward-looking effect extracted from one filing. */
export interface DatedEffect {
  window: string; // e.g. "2026 Q3" — resolved from window_start/window_end
  material: string;
  perspective: Perspective;
  direction: Direction;
  magnitude: Magnitude;
  text: string; // rationale (paraphrase)
  quote: string; // verbatim evidence_quote
}

/** Agent #2's stored recommendation for one material+quarter. It narrates the
    deterministic rank (never sets it) and may only cite quotes in the buffer. */
export interface Rating {
  material: string;
  quarter: string;
  prose: string;
  supporting: { ticker: string; quote: string }[];
  model?: string | null;
}

export interface Filing {
  /** EDGAR accession number — unique per filing (absent in demo fixtures). */
  accession?: string;
  ticker: string;
  company: string;
  form: FilingForm;
  filingDate: string; // knowledge date (point-in-time anchor)
  materials: string[];
  perspective: Perspective;
  status: ExtractionStatus;
  confidence: number | null;
  summary: string;
  effects: DatedEffect[];
  warnings: string[];
}

export interface QuarterCall {
  quarter: string;
  pick: string;
  etf: string;
  realized: number; // %
  benchmark: number; // equal-weight materials %, same quarter
}

export interface Metric {
  label: string;
  value: string;
  note: string;
  bad?: boolean;
}

export interface EquitySeries {
  key: string;
  label: string;
  colorVar: string;
  emphasis?: boolean;
  dashed?: boolean;
  directLabel?: string;
}

/* ---- Per-quarter backtest drill-down (Backtest page) ---- */

/** One material as it was ranked by the point-in-time forecast for a quarter. */
export interface PredictedRow {
  material: string;
  etf: string;
  z: number;
  producerScore: number;
  consumerScore: number | null;
  filings: number;
  rank: number; // predicted rank, 1 = top pick
}

/** One material as it actually finished that quarter, ranked by realized return. */
export interface ActualRow {
  material: string;
  etf: string;
  realized: number | null; // % — null if that ETF had no price that quarter
  rank: number | null;     // realized-return rank, 1 = best; null if unpriced
}

/** The pick vs each baseline for one quarter (all figures are that quarter only). */
export interface ScorecardItem {
  label: string;      // "SPY" | "Equal-weight" | "Random (median)" | "Hindsight-best"
  benchmark: number;  // baseline return %
  delta: number;      // pick − baseline, percentage points
  beat: boolean;
}

/** A filing whose extracted effect fed the pick's score for a quarter. */
export interface EvidenceItem {
  ticker: string;
  company: string;
  form: FilingForm;
  filingDate: string;
  material: string;
  perspective: Perspective;
  direction: Direction;
  magnitude: Magnitude;
  weight: number; // signed contribution to the score (recency-decayed)
  quote: string;  // verbatim evidence_quote
}

/* ---- Live tracker for the in-progress forecast quarter (Forecast page) ---- */
export interface TrackerPredicted {
  material: string;
  etf: string;
  z: number;
  rank: number; // start-of-quarter predicted rank
}
export interface TrackerActual {
  material: string;
  etf: string;
  qtd: number | null;   // quarter-to-date % return
  rank: number | null;  // QTD rank, 1 = best so far
}
export interface ForecastTracker {
  available: boolean;
  asOf?: string;        // ISO — through this date (latest price ≤ today)
  pctElapsed?: number;  // how far through the quarter (0–100)
  predicted?: TrackerPredicted[];
  actual?: TrackerActual[];
  pick?: {
    material: string;
    etf: string;
    z: number;
    predictedRank: number;
    qtd: number | null;
    actualRank: number | null;
  };
  baselines?: { spy: number | null; eqweight: number | null };
  scorecard?: ScorecardItem[]; // pick vs SPY / eq-weight, QTD
  rankIC?: number | null;      // provisional Spearman rank-IC, QTD
}

/** Everything the Backtest page needs to render one selected quarter. */
export interface QuarterReport {
  quarter: string;      // "2026 Q2"
  short: string;        // "26Q2"
  decisionDate: string; // ISO — quarter start; the point-in-time knowledge cutoff
  windowStart: string;  // ISO
  windowEnd: string;    // ISO
  predicted: PredictedRow[];
  actual: ActualRow[];
  pick: {
    material: string;
    etf: string;
    z: number;
    predictedRank: number | null;
    realized: number | null;   // raw ETF return %
    actualRank: number | null; // where the pick actually finished
    return: number;            // strategy return after costs %
  };
  baselines: {
    strategy: number;
    spy: number;
    eqweight: number;
    hindsight: number;
    random: number;
  };
  scorecard: ScorecardItem[];
  rankIC: number | null; // this quarter's Spearman rank-IC
  evidence: EvidenceItem[];
  /** Agent #2's recommendation as stored for this quarter — why we chose the pick. */
  rating?: Rating | null;
}

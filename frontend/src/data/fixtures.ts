/* ============================================================
   Demo fixtures. Numbers are illustrative, but the universe,
   ETF mapping, forms, perspective tags, and scoring semantics
   follow ARCHITECTURE.md exactly. Swap this module for the API
   client when the backend lands — the page components read only
   the exported shapes below.
   ============================================================ */

import type {
  MaterialRow, TrendSeries, Filing, QuarterCall, Metric, EquitySeries,
  QuarterReport, PredictedRow, ActualRow, EvidenceItem, ForecastTracker, Rating,
} from "./types";
import type { LiveData } from "./api";

export let FORECAST_QUARTER = "2026 Q3";
export let DATA_AS_OF = "Jul 24, 2026";
export let PUBLISHED_DATE = "Jul 1, 2026";   // forecast decision date (quarter start)
export let PRIOR_QUARTER = "2026 Q2";        // the quarter whose filings fed it
export let FILINGS_DIGESTED = 214;           // filings public before the decision date
export let META = { filings: 214, extractions: 214 };  // buffer-wide counts (from /meta)

/* ---- Current-quarter material ranking (cross-sectional z) ----
   Gold is producer-only: demand is macro, not narrated in filings,
   so consumerScore is null (a finding the perspective tag surfaces). */
export let MATERIALS: MaterialRow[] = [
  { material: "Copper",      etf: "COPX", z:  1.42, producerScore: 0.78, consumerScore: 0.55, filings: 64, rank: 1 },
  { material: "Uranium",     etf: "URNM", z:  0.86, producerScore: 0.71, consumerScore: 0.34, filings: 38, rank: 2 },
  { material: "Silver",      etf: "SIL",  z:  0.19, producerScore: 0.55, consumerScore: 0.28, filings: 31, rank: 3 },
  { material: "Gold",        etf: "GDX",  z: -0.14, producerScore: 0.47, consumerScore: null, filings: 42, rank: 4 },
  { material: "Steel",       etf: "SLX",  z: -0.83, producerScore: 0.44, consumerScore: 0.31, filings: 23, rank: 5 },
  { material: "Rare Earths", etf: "REMX", z: -1.50, producerScore: 0.30, consumerScore: 0.40, filings: 16, rank: 6 },
];

/* ---- Agent #2's stored recommendation for the current pick+quarter ----
   Lives in the ratings table (material × quarter); the API replaces this with
   the real stored prose, or null when the quarter hasn't been rated yet. */
export let PICK_RATING: Rating | null = {
  material: "Copper", quarter: "2026 Q3",
  prose:
    "Copper ranks #1 for 2026 Q3. Three producers point to near-term supply tightening — Freeport's raised Q3 " +
    "guidance, Teck's QB2 slip, and Southern Copper's grade commentary — while Eaton supplies a rare dense " +
    "consumer signal (grid-infrastructure orders +31% YoY). The main dissent is Southern Copper's China " +
    "construction softness. Bullish for COPX, the copper-miner basket.",
  supporting: [
    { ticker: "FCX", quote: "We expect consolidated copper sales of approximately 750 million pounds for the third quarter of 2026." },
    { ticker: "ETN", quote: "Order intake for grid infrastructure products increased 31% year-over-year, with backlog now extending into the second half of 2027." },
    { ticker: "TECK", quote: "The QB2 ramp-up schedule has been extended by two quarters due to water-management remediation, with full throughput now expected in early 2027." },
  ],
  model: "demo",
};

export let TREND_QUARTERS = ["25Q2", "25Q3", "25Q4", "26Q1", "26Q2", "26Q3"];

/* Top four materials by current rank; colors are entity-stable (fixed slots). */
export let TREND: TrendSeries[] = [
  { material: "Copper",  colorVar: "--s1", values: [0.11, 0.34, 0.62, 0.88, 1.16, 1.42] },
  { material: "Uranium", colorVar: "--s2", values: [0.94, 1.05, 0.88, 0.71, 0.79, 0.86] },
  { material: "Silver",  colorVar: "--s3", values: [-0.22, -0.35, 0.04, 0.18, 0.31, 0.19] },
  { material: "Gold",    colorVar: "--s4", values: [0.58, 0.71, 0.33, 0.10, -0.08, -0.14] },
];

/* ---- 28-quarter backtest window: 2019 Q3 – 2026 Q2 ---- */
export let QUARTERS: string[] = (() => {
  const out: string[] = [];
  let y = 2019, q = 3;
  for (let i = 0; i < 28; i++) {
    out.push(`${String(y).slice(2)}Q${q}`);
    q++; if (q > 4) { q = 1; y++; }
  }
  return out;
})();

/* quarterly % returns per series, 28 each */
export let RETURNS: Record<string, number[]> = {
  strategy:  [2.1, 6.8, -18.4, 21.5, 12.2, 19.8, 9.4, 6.1, -4.2, 8.9, 11.3, -14.8, -6.1, 10.4, 3.2, -3.8, 4.6, 7.9, 2.4, 5.8, -2.9, 6.4, 8.7, 4.2, 11.6, -3.4, 9.8, 5.1],
  spy:       [1.2, 8.5, -19.6, 20.5, 8.9, 11.7, 6.2, 8.5, 0.6, 11.0, -4.6, -16.1, -4.9, 7.6, 7.5, 8.7, -3.3, 11.7, 10.6, 4.3, 5.9, 2.4, -4.3, 10.9, 8.1, 2.7, 4.4, 3.9],
  eqweight:  [0.4, 5.9, -21.3, 18.2, 10.4, 14.6, 7.8, 4.9, -3.6, 7.2, 9.6, -16.9, -7.4, 9.8, 1.6, -4.7, 2.8, 6.3, 1.2, 4.1, -3.8, 4.9, 6.2, 3.0, 8.4, -4.6, 6.9, 3.7],
  random:    [-1.3, 4.2, -22.8, 15.1, 7.9, 10.2, 5.5, 2.1, -6.8, 4.9, 7.1, -19.4, -9.2, 7.7, 0.4, -6.9, 1.1, 4.8, -0.6, 2.9, -5.4, 3.2, 4.6, 1.5, 6.8, -6.1, 5.2, 2.4],
  hindsight: [4.2, 7.8, -8.9, 18.1, 10.2, 14.8, 8.4, 6.5, 1.7, 8.0, 9.6, -4.2, 0.8, 9.4, 5.5, 0.2, 5.2, 7.7, 4.8, 6.1, 2.1, 6.4, 7.9, 4.6, 9.8, 0.6, 8.2, 5.3],
};

export let EQUITY_SERIES: EquitySeries[] = [
  { key: "strategy",  label: "FilingSignal (top-1)",   colorVar: "--s1", emphasis: true, directLabel: "FilingSignal" },
  { key: "spy",       label: "SPY",                    colorVar: "--s2", directLabel: "SPY" },
  { key: "eqweight",  label: "Equal-weight materials", colorVar: "--s3" },
  { key: "random",    label: "Random pick (MC median)", colorVar: "--s4" },
  { key: "hindsight", label: "Hindsight-best pick",    colorVar: "--s5", dashed: true, directLabel: "Hindsight" },
];

/* Per-quarter rank information coefficient (Spearman). */
export let RANK_IC: number[] = [0.31, 0.18, -0.22, 0.42, 0.28, 0.36, 0.15, 0.08, -0.14, 0.24, 0.33, -0.28, -0.09, 0.29, 0.12, -0.18, 0.21, 0.26, 0.05, 0.19, -0.11, 0.22, 0.38, 0.14, 0.41, -0.06, 0.34, 0.27];

/* Perspective decomposition — the headline experiment (§7A). */
export let DECOMP = [
  { label: "Producer-only", ic: 0.17, colorVar: "--s1" },
  { label: "Consumer-only", ic: 0.06, colorVar: "--s3" },
  { label: "Combined",      ic: 0.19, colorVar: "--accent" },
];

export let METRICS: Metric[] = [
  { label: "CAGR",             value: "+15.1%",   note: "SPY +12.0%" },
  { label: "Sharpe",           value: "0.74",     note: "SPY 0.71" },
  { label: "Max drawdown",     value: "−28.4%", note: "SPY −24.5%", bad: true },
  { label: "Hit rate",         value: "61%",      note: "17 / 28 vs eq-weight" },
  { label: "Mean rank-IC",     value: "0.19",     note: "permutation p = 0.04" },
  { label: "Regret vs best",   value: "−9.3%/yr", note: "gap to hindsight", bad: true },
];

/* Last 10 quarters of top-1 calls (win = beat the equal-weight basket). */
export let QUARTER_CALLS: QuarterCall[] = [
  { quarter: "2024 Q1", pick: "Gold",    etf: "GDX",  realized:  2.1, benchmark:  1.2 },
  { quarter: "2024 Q2", pick: "Copper",  etf: "COPX", realized:  5.8, benchmark:  4.1 },
  { quarter: "2024 Q3", pick: "Copper",  etf: "COPX", realized: -4.9, benchmark: -3.8 },
  { quarter: "2024 Q4", pick: "Uranium", etf: "URNM", realized:  6.4, benchmark:  4.9 },
  { quarter: "2025 Q1", pick: "Uranium", etf: "URNM", realized:  8.7, benchmark:  6.2 },
  { quarter: "2025 Q2", pick: "Gold",    etf: "GDX",  realized:  1.1, benchmark:  3.0 },
  { quarter: "2025 Q3", pick: "Uranium", etf: "URNM", realized: 11.6, benchmark:  8.4 },
  { quarter: "2025 Q4", pick: "Silver",  etf: "SIL",  realized: -5.8, benchmark: -4.6 },
  { quarter: "2026 Q1", pick: "Copper",  etf: "COPX", realized:  9.8, benchmark:  6.9 },
  { quarter: "2026 Q2", pick: "Copper",  etf: "COPX", realized:  5.1, benchmark:  3.7 },
];

/* ---- Hit/miss grid: last 12 quarters × 6 materials ----
   rows = quarters (oldest first), cols = [Cu, Au, U, Ag, Steel, REE].
   HITS[q][m] = 1 → material m beat the basket that quarter.
   PICKS[q] = material index the strategy chose (must be internally consistent). */
export let HITGRID_MATERIALS = ["Copper", "Gold", "Uranium", "Silver", "Steel", "Rare Earths"];
export let HITS: number[][] = [
  [1, 0, 1, 0, 0, 0], [0, 1, 0, 1, 0, 1], [0, 1, 1, 0, 0, 0], [1, 0, 1, 1, 0, 0],
  [0, 1, 0, 0, 1, 0], [0, 0, 1, 1, 0, 0], [1, 0, 1, 0, 0, 1], [1, 0, 0, 1, 0, 0],
  [1, 0, 1, 0, 0, 0], [0, 1, 0, 0, 1, 0], [1, 0, 0, 0, 0, 1], [1, 0, 1, 0, 0, 0],
];
export let PICKS: number[] = [0, 2, 1, 0, 0, 2, 2, 1, 2, 3, 0, 0];

/* ---- Filings (real tickers, correct forms, perspective-tagged) ---- */
export let FILINGS: Filing[] = [
  {
    ticker: "FCX", company: "Freeport-McMoRan", form: "8-K", filingDate: "2026-07-23",
    materials: ["Copper", "Gold"], perspective: "producer", status: "Extracted", confidence: 0.92,
    summary: "Q2 2026 earnings (Item 2.02 + 7.01). Freeport raises near-term copper volume guidance and details the leach-innovation run-rate and the multi-year expansion pipeline. Bullish for COPX (FCX is the top holding) even though more mine supply is bearish for the copper price — the target is the miner basket, not the commodity.",
    effects: [
      { window: "2026 Q3", material: "Copper", perspective: "producer", direction: "increase", magnitude: "moderate", text: "Guides ~750M lbs copper sales for Q3 2026", quote: "“We expect consolidated copper sales of approximately 750 million pounds for the third quarter of 2026.”" },
      { window: "2026 Q4", material: "Copper", perspective: "producer", direction: "increase", magnitude: "small", text: "Leach run-rate target of 300M lb/yr by year-end", quote: "“Our leaching initiatives are tracking toward an annual run-rate of 300 million pounds by the end of 2026.”" },
      { window: "2027 Q1", material: "Copper", perspective: "producer", direction: "increase", magnitude: "large", text: "Expansion adds ~700M lb/yr from 2027–2030", quote: "“The project is expected to add incremental production of approximately 700 million pounds per year in the 2027 through 2030 period.”" },
    ],
    warnings: ["Earnings-release exhibit is 409K chars (mostly tables). Extraction targeted the Outlook / operations narrative; the financial statement tables were excluded from scoring."],
  },
  {
    ticker: "CCJ", company: "Cameco Corp", form: "6-K", filingDate: "2026-07-02",
    materials: ["Uranium"], perspective: "producer", status: "Extracted", confidence: 0.88,
    summary: "Interim furnishing (6-K, content ≈ 8-K). Cameco reaffirms full-year production and flags contract-book strengthening at higher realized prices.",
    effects: [
      { window: "2026 Q3", material: "Uranium", perspective: "producer", direction: "increase", magnitude: "moderate", text: "Contract book extended at higher realized prices", quote: "“We continue to add long-term contracts with improving pricing terms as utilities move to secure supply.”" },
    ],
    warnings: [],
  },
  {
    ticker: "SCCO", company: "Southern Copper", form: "10-Q", filingDate: "2026-06-30",
    materials: ["Copper", "Silver"], perspective: "producer", status: "Extracted", confidence: 0.85,
    summary: "Q2 10-Q. Flags softening Chinese construction demand as a volume headwind into fiscal 2026 — the main dissenting signal against the copper call.",
    effects: [
      { window: "2026 Q3", material: "Copper", perspective: "producer", direction: "decrease", magnitude: "moderate", text: "Chinese construction demand softening", quote: "“We are experiencing softening demand in Chinese construction end-markets and expect volume headwinds to persist through fiscal 2026.”" },
    ],
    warnings: [],
  },
  {
    ticker: "MP", company: "MP Materials", form: "10-Q", filingDate: "2026-06-26",
    materials: ["Rare Earths"], perspective: "producer", status: "Needs review", confidence: 0.64,
    summary: "Q2 10-Q. Magnet-facility ramp language present but dates are vague; two effects dropped for unbounded windows (below the confidence bar — flagged for review).",
    effects: [
      { window: "2026 Q4", material: "Rare Earths", perspective: "producer", direction: "increase", magnitude: "small", text: "Stage-II magnet output ramping", quote: "“We expect to continue ramping metal and magnet production through the second half of the year.”" },
    ],
    warnings: ["2 effects dropped: window could not be bounded to a quarter (“over the coming years”). Per window-discipline rule, vague full-year windows are dropped rather than invented."],
  },
  {
    ticker: "TECK", company: "Teck Resources", form: "40-F", filingDate: "2026-06-12",
    materials: ["Copper", "Steel"], perspective: "producer", status: "Extracted", confidence: 0.87,
    summary: "Annual (40-F, carries AIF + MD&A). QB2 ramp extended two quarters on water-management remediation — near-term supply tightening, bullish for the copper miner basket.",
    effects: [
      { window: "2026 Q3", material: "Copper", perspective: "producer", direction: "increase", magnitude: "moderate", text: "QB2 full-throughput slips to early 2027", quote: "“The QB2 ramp-up schedule has been extended by two quarters due to water-management remediation, with full throughput now expected in early 2027.”" },
    ],
    warnings: [],
  },
  {
    ticker: "ETN", company: "Eaton Corp", form: "10-Q", filingDate: "2026-05-30",
    materials: ["Copper"], perspective: "consumer", status: "Extracted", confidence: 0.81,
    summary: "Q2 10-Q. Electrical-segment order intake and backlog strengthen materially — a rare dense consumer-side demand signal for copper.",
    effects: [
      { window: "2026 Q3", material: "Copper", perspective: "consumer", direction: "increase", magnitude: "large", text: "Grid-infra order intake +31% YoY; backlog into 2H27", quote: "“Order intake for grid infrastructure products increased 31% year-over-year, with backlog now extending into the second half of 2027.”" },
    ],
    warnings: [],
  },
  {
    ticker: "NUE", company: "Nucor Corp", form: "10-Q", filingDate: "2026-05-22",
    materials: ["Steel"], perspective: "producer", status: "Extracted", confidence: 0.91,
    summary: "Q2 10-Q. Sheet-mill utilization guidance flat; sees stable but unspectacular non-residential construction demand.",
    effects: [
      { window: "2026 Q3", material: "Steel", perspective: "producer", direction: "increase", magnitude: "small", text: "Utilization steady; non-resi construction stable", quote: "“We expect steel mill utilization to remain consistent with the prior quarter as non-residential construction activity holds steady.”" },
    ],
    warnings: [],
  },
  {
    ticker: "TSLA", company: "Tesla Inc", form: "10-Q", filingDate: "2026-05-15",
    materials: ["Copper"], perspective: "consumer", status: "Needs review", confidence: 0.58,
    summary: "Q2 10-Q. No dated, quantified material-demand plan found — the filing narrates production/delivery and AI-cost topics, not procurement windows. Correctly returned near-empty (not a miss).",
    effects: [],
    warnings: [
      "MD&A section isolation fell back to full text; extraction ran on a 152K-char blob (≈10× target size) — flagged, not silent. Result reviewed and confirmed: no bounded material-demand effect present.",
    ],
  },
  {
    ticker: "AEM", company: "Agnico Eagle Mines", form: "40-F", filingDate: "2026-05-08",
    materials: ["Gold"], perspective: "producer", status: "Extracted", confidence: 0.89,
    summary: "Annual (40-F). Production guidance reaffirmed across the Canadian portfolio; unit costs guided flat.",
    effects: [
      { window: "2026 Q3", material: "Gold", perspective: "producer", direction: "increase", magnitude: "small", text: "Full-year gold guidance reaffirmed", quote: "“We reaffirm full-year gold production guidance of 3.4 to 3.6 million ounces at total cash costs consistent with prior guidance.”" },
    ],
    warnings: [],
  },
  {
    ticker: "RIO", company: "Rio Tinto plc", form: "20-F", filingDate: "2026-04-30",
    materials: ["Copper", "Steel"], perspective: "producer", status: "Extracted", confidence: 0.86,
    summary: "Annual (20-F). Oyu Tolgoi underground ramp on schedule; iron-ore shipments guided within range.",
    effects: [
      { window: "2026 Q4", material: "Copper", perspective: "producer", direction: "increase", magnitude: "moderate", text: "Oyu Tolgoi underground copper ramp on plan", quote: "“Oyu Tolgoi underground copper production continues to ramp in line with plan toward peak output.”" },
    ],
    warnings: [],
  },
  {
    ticker: "HL", company: "Hecla Mining", form: "10-Q", filingDate: "2026-04-24",
    materials: ["Silver"], perspective: "producer", status: "Extracted", confidence: 0.83,
    summary: "Q2 10-Q. Greens Creek and Lucky Friday output guided modestly higher; silver by-product credits noted.",
    effects: [
      { window: "2026 Q3", material: "Silver", perspective: "producer", direction: "increase", magnitude: "small", text: "Silver output guided modestly higher", quote: "“We expect silver production in the second half to modestly exceed the first half on improved grades at Lucky Friday.”" },
    ],
    warnings: [],
  },
  {
    ticker: "LMT", company: "Lockheed Martin", form: "8-K", filingDate: "2026-04-18",
    materials: ["Rare Earths"], perspective: "consumer", status: "Processing", confidence: null,
    summary: "Event filing (Item 1.01). Awaiting extraction — defense magnet-supply agreement is the kind of less-priced-in consumer signal the pipeline prioritizes for alpha.",
    effects: [],
    warnings: [],
  },
];

/* Rich detail lookup keyed by ticker (Filing already carries effects; this is
   the same source for the drawer). */
export let FILING_BY_TICKER: Record<string, Filing> = Object.fromEntries(
  FILINGS.map((f) => [f.ticker, f]),
);

/* ---- Per-quarter backtest reports (mock, self-consistent with QUARTER_CALLS) ----
   Built from compact specs so every derived field (ranks, scorecard, deltas)
   stays internally consistent. Replaced wholesale by the API's quarterReports. */
const MAT6 = ["Copper", "Uranium", "Silver", "Gold", "Steel", "Rare Earths"];
const ETF6 = ["COPX", "URNM", "SIL", "GDX", "SLX", "REMX"];
const Z_BY_POS = [1.35, 0.72, 0.24, -0.28, -0.85, -1.18]; // z by predicted position

interface QSpec {
  quarter: string; short: string; start: string; end: string;
  spy: number;                 // SPY return that quarter
  order: number[];             // predicted best→worst, as MAT6 indices (order[0] = pick)
  realized: number[];          // realized % per MAT6 index
  rankIC: number;
}

/* order[0] is the pick; realized[] indexes match MAT6. */
const Q_SPECS: QSpec[] = [
  { quarter: "2024 Q1", short: "24Q1", start: "2024-01-01", end: "2024-03-31", spy: 10.6, rankIC: 0.05, order: [3, 0, 1, 4, 5, 2], realized: [3.0, 0.5, -1.0, 2.1, 1.6, 1.0] },
  { quarter: "2024 Q2", short: "24Q2", start: "2024-04-01", end: "2024-06-30", spy: 4.3,  rankIC: 0.19, order: [0, 1, 3, 2, 4, 5], realized: [5.8, 6.5, 3.0, 4.2, 2.1, 3.0] },
  { quarter: "2024 Q3", short: "24Q3", start: "2024-07-01", end: "2024-09-30", spy: 5.9,  rankIC: -0.11, order: [0, 3, 1, 5, 4, 2], realized: [-4.9, -2.0, -5.0, -1.8, -5.1, -4.0] },
  { quarter: "2024 Q4", short: "24Q4", start: "2024-10-01", end: "2024-12-31", spy: 2.4,  rankIC: 0.22, order: [1, 0, 5, 4, 2, 3], realized: [5.0, 6.4, 4.0, 3.0, 5.0, 6.0] },
  { quarter: "2025 Q1", short: "25Q1", start: "2025-01-01", end: "2025-03-31", spy: -4.3, rankIC: 0.38, order: [1, 0, 5, 2, 4, 3], realized: [7.0, 8.7, 5.0, 4.5, 5.0, 7.0] },
  { quarter: "2025 Q2", short: "25Q2", start: "2025-04-01", end: "2025-06-30", spy: 10.9, rankIC: 0.14, order: [3, 0, 1, 4, 2, 5], realized: [4.0, 5.0, 2.0, 1.1, 2.9, 3.0] },
  { quarter: "2025 Q3", short: "25Q3", start: "2025-07-01", end: "2025-09-30", spy: 8.1,  rankIC: 0.41, order: [1, 0, 5, 2, 4, 3], realized: [9.0, 11.6, 7.0, 6.8, 7.0, 9.0] },
  { quarter: "2025 Q4", short: "25Q4", start: "2025-10-01", end: "2025-12-31", spy: 2.7,  rankIC: -0.06, order: [2, 0, 1, 3, 4, 5], realized: [-4.0, -3.0, -5.8, -4.8, -5.0, -5.0] },
  { quarter: "2026 Q1", short: "26Q1", start: "2026-01-01", end: "2026-03-31", spy: 4.4,  rankIC: 0.34, order: [0, 1, 5, 2, 3, 4], realized: [9.8, 8.0, 6.0, 5.6, 5.0, 7.0] },
  { quarter: "2026 Q2", short: "26Q2", start: "2026-04-01", end: "2026-06-30", spy: 3.9,  rankIC: 0.27, order: [0, 1, 5, 2, 4, 3], realized: [5.1, 4.5, 3.0, 2.6, 3.0, 4.0] },
];

const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length;
const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};
const r1 = (x: number) => Math.round(x * 10) / 10;

function buildReport(s: QSpec): QuarterReport {
  const pickIdx = s.order[0];
  // predicted rows: z assigned by predicted position, then presented in MAT6 order
  const predRankOf: Record<number, number> = {};
  s.order.forEach((mi, pos) => (predRankOf[mi] = pos + 1));
  const predicted: PredictedRow[] = MAT6.map((m, mi) => {
    const z = Z_BY_POS[predRankOf[mi] - 1];
    return {
      material: m, etf: ETF6[mi], z,
      producerScore: Math.round((0.4 + Math.max(0, z) * 0.25) * 100) / 100,
      consumerScore: m === "Gold" ? null : Math.round((0.28 + Math.max(0, z) * 0.12) * 100) / 100,
      filings: 6 + ((mi * 7 + s.short.charCodeAt(3)) % 9),
      rank: predRankOf[mi],
    };
  });
  // actual rows: rank by realized return desc
  const byReal = MAT6.map((_, mi) => mi).sort((a, b) => s.realized[b] - s.realized[a]);
  const actRankOf: Record<number, number> = {};
  byReal.forEach((mi, i) => (actRankOf[mi] = i + 1));
  const actual: ActualRow[] = byReal.map((mi) => ({
    material: MAT6[mi], etf: ETF6[mi], realized: r1(s.realized[mi]), rank: actRankOf[mi],
  }));

  const strat = r1(s.realized[pickIdx] - 0.1); // 10 bps rotation cost
  const eqweight = r1(mean(s.realized));
  const hindsight = r1(Math.max(...s.realized));
  const random = r1(median(s.realized));
  const sc = (label: string, benchmark: number, beatEq = false) => ({
    label, benchmark, delta: r1(strat - benchmark), beat: beatEq ? strat >= benchmark : strat > benchmark,
  });

  // evidence: filings on the pick material, biggest contributor first
  const evidence: EvidenceItem[] = FILINGS.filter((f) => f.materials.includes(MAT6[pickIdx]))
    .slice(0, 4)
    .map((f, i) => {
      const eff = f.effects.find((e) => e.material === MAT6[pickIdx]) ?? f.effects[0];
      const dir = eff?.direction ?? "increase";
      const magW = eff?.magnitude === "large" ? 3 : eff?.magnitude === "moderate" ? 2 : 1;
      return {
        ticker: f.ticker, company: f.company, form: f.form, filingDate: f.filingDate,
        material: MAT6[pickIdx], perspective: eff?.perspective ?? "producer",
        direction: dir, magnitude: eff?.magnitude ?? "moderate",
        weight: Math.round((dir === "decrease" ? -1 : 1) * magW * (0.9 - i * 0.18) * 100) / 100,
        quote: eff?.quote ?? f.summary,
      };
    });

  return {
    quarter: s.quarter, short: s.short,
    decisionDate: s.start, windowStart: s.start, windowEnd: s.end,
    predicted, actual,
    pick: {
      material: MAT6[pickIdx], etf: ETF6[pickIdx], z: Z_BY_POS[0],
      predictedRank: 1, realized: r1(s.realized[pickIdx]),
      actualRank: actRankOf[pickIdx], return: strat,
    },
    baselines: { strategy: strat, spy: r1(s.spy), eqweight, hindsight, random },
    scorecard: [
      sc("SPY", r1(s.spy)),
      sc("Equal-weight", eqweight),
      sc("Random (median)", random),
      sc("Hindsight-best", hindsight, true),
    ],
    rankIC: s.rankIC,
    evidence,
    rating: {
      material: MAT6[pickIdx], quarter: s.quarter,
      prose:
        `${MAT6[pickIdx]} ranked #1 for ${s.quarter} on the strongest weighted support among the six ` +
        `materials from filings public before the quarter began — ` +
        `${evidence.slice(0, 2).map((e) => e.ticker).join(" and ") || "producer guidance"} drove the score. ` +
        `The call maps to ${ETF6[pickIdx]}, the ${MAT6[pickIdx].toLowerCase()} miner basket.`,
      supporting: evidence.slice(0, 2).map((e) => ({ ticker: e.ticker, quote: e.quote })),
      model: "demo",
    },
  };
}

export let QUARTER_REPORTS: QuarterReport[] = Q_SPECS.map(buildReport);

/* ---- Live tracker for the in-progress quarter (mock, consistent w/ MATERIALS) ----
   Quarter-to-date returns are illustrative; the API replaces this with real ones. */
export let TRACKER: ForecastTracker = (() => {
  const qtd: Record<string, number> = {
    Copper: 3.2, Uranium: 1.1, Silver: -0.8, Gold: 0.4, Steel: 4.0, "Rare Earths": -6.5,
  };
  const predicted = MATERIALS.map((m) => ({ material: m.material, etf: m.etf, z: m.z, rank: m.rank }));
  const byQtd = [...MATERIALS].sort((a, b) => qtd[b.material] - qtd[a.material]);
  const actRank: Record<string, number> = {};
  byQtd.forEach((m, i) => (actRank[m.material] = i + 1));
  const actual = byQtd.map((m) => ({ material: m.material, etf: m.etf, qtd: qtd[m.material], rank: actRank[m.material] }));
  const pickM = MATERIALS[0];
  const pickQtd = qtd[pickM.material];
  const vals = MATERIALS.map((m) => qtd[m.material]);
  const eqweight = Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 10) / 10;
  const spy = 1.5;
  return {
    available: true, asOf: "Jul 24, 2026", pctElapsed: 26,
    predicted, actual,
    pick: { material: pickM.material, etf: pickM.etf, z: pickM.z, predictedRank: 1, qtd: pickQtd, actualRank: actRank[pickM.material] },
    baselines: { spy, eqweight },
    scorecard: [
      { label: "SPY", benchmark: spy, delta: Math.round((pickQtd - spy) * 10) / 10, beat: pickQtd > spy },
      { label: "Equal-weight", benchmark: eqweight, delta: Math.round((pickQtd - eqweight) * 10) / 10, beat: pickQtd > eqweight },
    ],
    rankIC: 0.66,
  };
})();

/* Overwrite the demo fixtures with live API data (called once at boot, before
   the first render). Components import these bindings live, so no re-render is
   needed. Any key the API omits keeps its demo value. */
export function hydrate(d: Partial<LiveData>): void {
  if (d.FORECAST_QUARTER !== undefined) FORECAST_QUARTER = d.FORECAST_QUARTER;
  if (d.DATA_AS_OF !== undefined) DATA_AS_OF = d.DATA_AS_OF;
  if (d.PUBLISHED_DATE !== undefined) PUBLISHED_DATE = d.PUBLISHED_DATE;
  if (d.PRIOR_QUARTER !== undefined) PRIOR_QUARTER = d.PRIOR_QUARTER;
  if (d.FILINGS_DIGESTED !== undefined) FILINGS_DIGESTED = d.FILINGS_DIGESTED;
  if (d.META) META = d.META;
  if (d.TRACKER) TRACKER = d.TRACKER;
  if (d.PICK_RATING !== undefined) PICK_RATING = d.PICK_RATING; // null clears the demo prose
  if (d.MATERIALS) MATERIALS = d.MATERIALS;
  if (d.TREND) TREND = d.TREND;
  if (d.TREND_QUARTERS) TREND_QUARTERS = d.TREND_QUARTERS;
  if (d.QUARTERS) QUARTERS = d.QUARTERS;
  if (d.RETURNS) RETURNS = d.RETURNS;
  if (d.RANK_IC) RANK_IC = d.RANK_IC;
  if (d.DECOMP) DECOMP = d.DECOMP;
  if (d.METRICS) METRICS = d.METRICS;
  if (d.QUARTER_CALLS) QUARTER_CALLS = d.QUARTER_CALLS;
  if (d.QUARTER_REPORTS) QUARTER_REPORTS = d.QUARTER_REPORTS;
  if (d.HITGRID_MATERIALS) HITGRID_MATERIALS = d.HITGRID_MATERIALS;
  if (d.HITS) HITS = d.HITS;
  if (d.PICKS) PICKS = d.PICKS;
  if (d.FILINGS) {
    FILINGS = d.FILINGS;
    FILING_BY_TICKER = Object.fromEntries(FILINGS.map((f) => [f.ticker, f]));
  }
}

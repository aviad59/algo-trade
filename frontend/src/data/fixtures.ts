/* ============================================================
   Data bindings. Everything starts EMPTY — there is no demo
   data anywhere. main.tsx hydrates these bindings from the
   read-only API before the first render; if the backend is
   unreachable, every value stays empty and the pages render
   their honest empty states instead.
   ============================================================ */

import type {
  MaterialRow, TrendSeries, Filing, QuarterCall, Metric, EquitySeries,
  QuarterReport, ForecastTracker, Rating,
} from "./types";
import type { LiveData } from "./api";

/** "live" once the API answered; "offline" when it could not be reached. */
export let DATA_STATUS: "live" | "offline" = "offline";
export function markLive(): void { DATA_STATUS = "live"; }

export let FORECAST_QUARTER = "";
export let DATA_AS_OF = "";
export let PUBLISHED_DATE = "";
export let PRIOR_QUARTER = "";
export let FILINGS_DIGESTED = 0;
export let META = { filings: 0, extractions: 0 };

/** Current-quarter material ranking (cross-sectional z). Empty until hydrated. */
export let MATERIALS: MaterialRow[] = [];

/** Agent #2's stored recommendation for the current pick+quarter (null = none). */
export let PICK_RATING: Rating | null = null;

export let TREND_QUARTERS: string[] = [];
export let TREND: TrendSeries[] = [];

/* ---- Backtest series (hydrated from /backtest; empty otherwise) ---- */
export let QUARTERS: string[] = [];
export let RETURNS: Record<string, number[]> = {};
export let RANK_IC: number[] = [];
export let DECOMP: { label: string; ic: number; colorVar: string }[] = [];
export let METRICS: Metric[] = [];
export let QUARTER_CALLS: QuarterCall[] = [];
export let QUARTER_REPORTS: QuarterReport[] = [];
export let HITGRID_MATERIALS: string[] = [];
export let HITS: number[][] = [];
export let PICKS: number[] = [];

/* Which series the growth chart draws, and with what identity. Presentation
   config, not data — colors are entity-stable CSS tokens. */
export let EQUITY_SERIES: EquitySeries[] = [
  { key: "strategy", label: "Our picks",        colorVar: "--c-strategy", emphasis: true, directLabel: "Our picks" },
  { key: "spy",      label: "The market (SPY)", colorVar: "--c-market", directLabel: "Market" },
  { key: "eqweight", label: "All six metals",   colorVar: "--c-basket" },
  { key: "random",   label: "Random guessing",  colorVar: "--c-random" },
];

export let FILINGS: Filing[] = [];
export let FILING_BY_TICKER: Record<string, Filing> = {};

export let TRACKER: ForecastTracker = { available: false };

/* Overwrite the empty bindings with live API data (called once at boot, before
   the first render). Components import these bindings live, so no re-render is
   needed. Any key the API omits stays empty. */
export function hydrate(d: Partial<LiveData>): void {
  if (d.FORECAST_QUARTER !== undefined) FORECAST_QUARTER = d.FORECAST_QUARTER;
  if (d.DATA_AS_OF !== undefined) DATA_AS_OF = d.DATA_AS_OF;
  if (d.PUBLISHED_DATE !== undefined) PUBLISHED_DATE = d.PUBLISHED_DATE;
  if (d.PRIOR_QUARTER !== undefined) PRIOR_QUARTER = d.PRIOR_QUARTER;
  if (d.FILINGS_DIGESTED !== undefined) FILINGS_DIGESTED = d.FILINGS_DIGESTED;
  if (d.META) META = d.META;
  if (d.TRACKER) TRACKER = d.TRACKER;
  if (d.PICK_RATING !== undefined) PICK_RATING = d.PICK_RATING;
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

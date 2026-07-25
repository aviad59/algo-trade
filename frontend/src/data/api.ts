/* ============================================================
   Live API client. Fetches the read-only backend and maps each
   endpoint onto the exact fixture shapes, so hydrating fixtures.ts
   flips the whole dashboard to live data with no component edits.
   Base URL: VITE_API_BASE (default "/api/v1", proxied to :8000 in dev).
   ============================================================ */

import type { Filing, ForecastTracker, MaterialRow, Metric, QuarterCall, QuarterReport, Rating, TrendSeries } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

export interface LiveData {
  FORECAST_QUARTER: string;
  DATA_AS_OF: string;
  PUBLISHED_DATE: string;
  PRIOR_QUARTER: string;
  FILINGS_DIGESTED: number;
  TRACKER: ForecastTracker;
  /** Agent #2's stored recommendation for the current pick+quarter (null = not rated yet). */
  PICK_RATING: Rating | null;
  MATERIALS: MaterialRow[];
  TREND: TrendSeries[];
  TREND_QUARTERS: string[];
  QUARTERS: string[];
  RETURNS: Record<string, number[]>;
  RANK_IC: number[];
  DECOMP: { label: string; ic: number; colorVar: string }[];
  METRICS: Metric[];
  QUARTER_CALLS: QuarterCall[];
  QUARTER_REPORTS: QuarterReport[];
  META: { filings: number; extractions: number };
  HITGRID_MATERIALS: string[];
  HITS: number[][];
  PICKS: number[];
  FILINGS: Filing[];
}

async function get(path: string): Promise<any> {
  const r = await fetch(BASE + path);
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

/** Interactive one-filing digest (auth-gated). Fetches + runs Agent #1 live. */
export async function digestFiling(p: { ticker: string; form: string; before?: string; apiKey: string }): Promise<any> {
  const r = await fetch(BASE + "/digest", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${p.apiKey}` },
    body: JSON.stringify({ ticker: p.ticker, form: p.form, before: p.before || null }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `request failed (${r.status})`);
  return data;
}

function fmtDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

/** "2026 Q3" -> the last n short quarter labels ending at it, e.g. ["25Q2",...,"26Q3"]. */
function shortQuartersEnding(label: string, n: number): string[] {
  const [y, q] = label.replace("Q", " ").trim().split(/\s+/).map(Number);
  let idx = y * 4 + (q - 1);
  const out: string[] = [];
  for (let i = n - 1; i >= 0; i--) {
    const k = idx - i;
    out.push(`${String(Math.floor(k / 4)).slice(2)}Q${(k % 4) + 1}`);
  }
  return out;
}

export async function fetchLiveData(): Promise<Partial<LiveData>> {
  const [forecast, filings, backtest, meta] = await Promise.all([
    get("/forecast"),
    get("/filings"),
    get("/backtest").catch(() => ({ available: false })),
    get("/meta").catch(() => null),
  ]);

  const out: Partial<LiveData> = {
    FORECAST_QUARTER: forecast.quarter,
    DATA_AS_OF: fmtDate(forecast.asOf),
    META: meta?.counts ? { filings: meta.counts.filings, extractions: meta.counts.extractions } : undefined,
    PUBLISHED_DATE: forecast.publishedDate ? fmtDate(forecast.publishedDate) : undefined,
    PRIOR_QUARTER: forecast.priorQuarter,
    FILINGS_DIGESTED: forecast.filingsDigested,
    TRACKER: forecast.tracker,
    PICK_RATING: forecast.rating ?? null, // null clears the demo prose — honest empty state
    MATERIALS: forecast.materials,
    TREND: forecast.trend,
    TREND_QUARTERS: shortQuartersEnding(forecast.quarter, forecast.trend?.[0]?.values.length ?? 6),
    FILINGS: filings,
  };

  if (backtest?.available) {
    out.QUARTERS = backtest.quarters;
    out.RETURNS = backtest.returns;
    out.RANK_IC = (backtest.rankIC as (number | null)[]).map((v) => (v == null ? 0 : v));
    out.DECOMP = backtest.decomp;
    out.METRICS = backtest.metrics;
    out.QUARTER_CALLS = backtest.quarterCalls;
    if (backtest.quarterReports) out.QUARTER_REPORTS = backtest.quarterReports;
    out.HITGRID_MATERIALS = backtest.hitgrid.materials;
    out.HITS = backtest.hitgrid.hits;
    out.PICKS = backtest.hitgrid.picks;
  }
  return out;
}

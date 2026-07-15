import { z } from 'zod'

export const isoDateSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}$/)
export const isoMonthSchema = z.string().regex(/^\d{4}-\d{2}$/)
export const directionSchema = z.enum(['increase', 'decrease'])
export const magnitudeSchema = z.enum(['small', 'moderate', 'large'])
export const actionSchema = z.enum(['BUY', 'SELL'])

export const datedEffectSchema = z.object({
  sector: z.string(),
  direction: directionSchema,
  magnitude: magnitudeSchema,
  window_start: isoDateSchema,
  window_end: isoDateSchema,
  rationale: z.string(),
  source_span: z.string(),
})

export const extractionSchema = z.object({
  id: z.string(),
  ticker: z.string(),
  cik: z.string(),
  filing_type: z.string(),
  filing_date: isoDateSchema,
  filing_url: z.string().url(),
  dated_effects: z.array(datedEffectSchema),
  flagged_risks: z.array(z.string()),
  extractor_confidence: z.number().min(0).max(1),
})

export const extractionListSchema = z.object({
  contract_version: z.literal('1.0'),
  total: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
  offset: z.number().int().nonnegative(),
  items: z.array(extractionSchema),
})

export const topMaterialSchema = z.object({
  material_id: z.string(),
  name: z.string(),
  rank: z.number().int().positive(),
  score: z.number(),
  latest_action: actionSchema.nullable(),
  latest_action_date: isoDateSchema.nullable(),
  current_signal: z.number(),
  supporting_ticker_count: z.number().int().nonnegative(),
})

export const forecastSummarySchema = z.object({
  contract_version: z.literal('1.0'),
  as_of: isoDateSchema,
  pipeline_run_at: z.string(),
  universe_count: z.number().int().nonnegative(),
  extractions_count: z.number().int().nonnegative(),
  top_materials: z.array(topMaterialSchema),
})

export const rankedMaterialSchema = z.object({
  material_id: z.string(),
  name: z.string(),
  score: z.number(),
  rationale: z.string(),
  supporting_tickers: z.array(z.string()),
  dissenting_evidence: z.array(z.string()),
})

export const forecastRankingSchema = z.object({
  contract_version: z.literal('1.0'),
  as_of: isoDateSchema,
  ranked_materials: z.array(rankedMaterialSchema),
})

export const forecastActionSchema = z.object({
  date: isoDateSchema,
  action: actionSchema,
  rationale: z.string(),
})

export const curvePointSchema = z.object({
  month: isoMonthSchema,
  signal: z.number(),
  forward_AUC: z.number(),
})

export const materialForecastSchema = z.object({
  contract_version: z.literal('1.0'),
  material_id: z.string(),
  as_of: isoDateSchema,
  actions: z.array(forecastActionSchema),
  curve: z.array(curvePointSchema),
  contributing_ticker_count: z.number().int().nonnegative(),
  universe_curve: z.array(curvePointSchema).nullable().optional(),
})

export const instrumentBucketsSchema = z.object({
  producers: z.array(z.string()),
  etfs: z.array(z.string()),
  physical: z.array(z.string()),
  futures: z.array(z.string()),
  transporters: z.array(z.string()),
  downstream_consumers: z.array(z.string()),
})

export const instrumentsSchema = z.object({
  contract_version: z.literal('1.0'),
  material_id: z.string(),
  buckets: instrumentBucketsSchema,
})

export const backtestTradeSchema = z.object({
  entry_date: isoDateSchema,
  entry_price: z.number(),
  exit_date: isoDateSchema,
  exit_price: z.number(),
  return_pct: z.number(),
  open_at_end: z.boolean(),
})

export const backtestOpenPositionSchema = z.object({
  entry_date: isoDateSchema,
  entry_price: z.number(),
  current_price: z.number(),
  return_pct: z.number(),
})

export const backtestResultSchema = z.object({
  sector: z.string(),
  instrument: z.string(),
  trades_closed: z.number().int().nonnegative(),
  win_rate: z.number(),
  return_pct: z.number(),
  benchmark_pct: z.number(),
  alpha_pct: z.number(),
  exposure_pct: z.number(),
  open_position: backtestOpenPositionSchema.nullable(),
  trades: z.array(backtestTradeSchema),
})

export const backtestOverallSchema = z.object({
  win_rate: z.number(),
  return_pct: z.number(),
  benchmark_pct: z.number(),
  alpha_pct: z.number(),
  exposure_pct: z.number(),
  trades_closed: z.number().int().nonnegative(),
  winners: z.number().int().nonnegative(),
  open_positions: z.number().int().nonnegative(),
})

export const backtestSchema = z.object({
  contract_version: z.literal('1.0'),
  available: z.boolean(),
  mode: z.string(),
  since: isoDateSchema,
  until: isoDateSchema,
  reason: z.string().nullable(),
  overall: backtestOverallSchema.nullable(),
  results: z.array(backtestResultSchema),
})

export const extractJobStatusSchema = z.object({
  contract_version: z.literal('1.0'),
  state: z.enum(['idle', 'running', 'done', 'error']),
  ticker: z.string().nullable(),
  forms: z.array(z.string()),
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
  filings_done: z.number().int().nonnegative(),
  effects_found: z.number().int().nonnegative(),
  events: z.array(z.string()),
  error: z.string().nullable(),
  budget_used: z.number().int().nonnegative(),
  budget_cap: z.number().int().nonnegative(),
})

export const extractStartResponseSchema = z.object({
  contract_version: z.literal('1.0'),
  status: z.literal('started'),
  message: z.string(),
})

export const healthSchema = z.object({
  contract_version: z.literal('1.0'),
  status: z.string(),
  latest_as_of: isoDateSchema,
  data_source: z.enum(['mock', 'pipeline']),
})

export type DatedEffect = z.infer<typeof datedEffectSchema>
export type Extraction = z.infer<typeof extractionSchema>
export type ExtractionList = z.infer<typeof extractionListSchema>
export type ForecastAction = z.infer<typeof actionSchema>
export type TopMaterial = z.infer<typeof topMaterialSchema>
export type RankedMaterial = z.infer<typeof rankedMaterialSchema>
export type ForecastCurvePoint = z.infer<typeof curvePointSchema>
export type ForecastSummary = z.infer<typeof forecastSummarySchema>
export type ForecastRanking = z.infer<typeof forecastRankingSchema>
export type MaterialForecast = z.infer<typeof materialForecastSchema>
export type Instruments = z.infer<typeof instrumentsSchema>
export type Health = z.infer<typeof healthSchema>
export type BacktestTrade = z.infer<typeof backtestTradeSchema>
export type BacktestResult = z.infer<typeof backtestResultSchema>
export type Backtest = z.infer<typeof backtestSchema>
export type ExtractJobStatus = z.infer<typeof extractJobStatusSchema>

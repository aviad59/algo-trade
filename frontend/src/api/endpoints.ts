import { z } from 'zod'
import {
  backtestSchema,
  extractionListSchema,
  extractionSchema,
  extractJobStatusSchema,
  extractStartResponseSchema,
  forecastRankingSchema,
  forecastSummarySchema,
  healthSchema,
  instrumentsSchema,
  materialForecastSchema,
} from '../types/contract'
import { getJson, getMockJson, postJson, ApiError } from './client'
import { DATA_SOURCE, MOCK_FALLBACK } from './config'
import { markMockFallbackUsed, type MockFallbackReason } from './fallback'
import { filterExtractions, type ExtractionFilters } from './mockFilter'

export type { ExtractionFilters }

function resourcePath(mockPath: string): string {
  if (DATA_SOURCE === 'mock') {
    return mockPath
  }
  return mockPath.replace(/\.json$/, '').replace('/index', '')
}

function getResource<T>(mockPath: string, schema: z.ZodType<T>) {
  const path = resourcePath(mockPath)
  if (DATA_SOURCE === 'mock') {
    return getJson(path, schema)
  }
  return getJson(path, schema, { mockPath })
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

const manufacturersFileSchema = z.object({
  count: z.number(),
  companies: z.array(
    z.object({
      ticker: z.string(),
      cik: z.string(),
      name: z.string(),
      indexes: z.array(z.string()).optional(),
      gics_sector: z.string(),
      gics_sub_industry: z.string().optional(),
    }),
  ),
})

const materialsFileSchema = z.object({
  materials: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      category: z.string(),
      aliases: z.array(z.string()),
      used_in: z.array(z.string()),
      consuming_sectors: z.array(z.string()),
      description: z.string(),
    }),
  ),
})

export async function fetchHealth() {
  return getResource('/meta/health.json', healthSchema)
}

export async function fetchForecastSummary() {
  return getResource('/forecast/summary.json', forecastSummarySchema)
}

export async function fetchForecastRanking() {
  return getResource('/forecast/ranking.json', forecastRankingSchema)
}

export async function fetchMaterialForecast(materialId: string) {
  return getResource(`/forecast/materials/${materialId}.json`, materialForecastSchema)
}

export async function fetchBacktest() {
  return getResource('/backtest.json', backtestSchema)
}

/** Demo-token holders only: pull a ticker's latest filings through Agent #1. */
export async function startLiveExtraction(ticker: string) {
  return postJson('/extract', { ticker, limit: 1 }, extractStartResponseSchema)
}

export async function fetchLiveExtractionStatus() {
  return getJson('/extract/status', extractJobStatusSchema)
}

export async function fetchInstruments(materialId: string) {
  return getResource(`/universe/instruments/${materialId}.json`, instrumentsSchema)
}

export async function fetchManufacturersList() {
  return getResource('/universe/manufacturers.json', manufacturersFileSchema)
}

export async function fetchMaterialsList() {
  return getResource('/universe/materials.json', materialsFileSchema)
}

async function fetchExtractionsFromMock(filters: ExtractionFilters) {
  const index = await getMockJson('/extractions/index.json', extractionListSchema)
  return filterExtractions(index.items, filters)
}

function markExtractionFallback(error: unknown): void {
  const message =
    error instanceof ApiError
      ? error.message
      : 'Could not load extractions from the live API. Showing demo data instead.'
  const reason: MockFallbackReason =
    error instanceof ApiError && error.status === 0 ? 'network' : 'server_error'
  markMockFallbackUsed({ reason, message })
}

export async function fetchExtractions(filters: ExtractionFilters = {}) {
  if (DATA_SOURCE === 'mock') {
    return fetchExtractionsFromMock(filters)
  }

  const query = buildQuery({
    ticker: filters.ticker?.join(','),
    material: filters.material,
    from: filters.from,
    to: filters.to,
    limit: filters.limit,
    offset: filters.offset,
  })

  try {
    return await getJson(`/extractions${query}`, extractionListSchema, {
      mockPath: '/extractions/index.json',
    })
  } catch (error) {
    if (!MOCK_FALLBACK) {
      throw error
    }
    markExtractionFallback(error)
    if (import.meta.env.DEV) {
      console.warn('[FilingSignal] Live API unavailable — using demo extractions.')
    }
    return fetchExtractionsFromMock(filters)
  }
}

export async function fetchExtractionById(extractionId: string) {
  if (DATA_SOURCE === 'mock') {
    const index = await getMockJson('/extractions/index.json', extractionListSchema)
    const row = index.items.find((item) => item.id === extractionId)
    if (!row) {
      throw new Error(`Extraction not found: ${extractionId}`)
    }
    return extractionSchema.parse(row)
  }

  try {
    return await getJson(`/extractions/${extractionId}`, extractionSchema)
  } catch (error) {
    if (!MOCK_FALLBACK) {
      throw error
    }
    markExtractionFallback(error)
    if (import.meta.env.DEV) {
      console.warn('[FilingSignal] Live API unavailable — using demo extraction.')
    }
    const index = await getMockJson('/extractions/index.json', extractionListSchema)
    const row = index.items.find((item) => item.id === extractionId)
    if (!row) {
      throw error
    }
    return extractionSchema.parse(row)
  }
}

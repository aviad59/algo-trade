import { z } from 'zod'
import {
  extractionListSchema,
  extractionSchema,
  forecastRankingSchema,
  forecastSummarySchema,
  healthSchema,
  instrumentsSchema,
  materialForecastSchema,
} from '../types/contract'
import { getJson } from './client'
import { DATA_SOURCE } from './config'
import { filterExtractions, type ExtractionFilters } from './mockFilter'

export type { ExtractionFilters }

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
  return getJson('/meta/health.json', healthSchema)
}

export async function fetchForecastSummary() {
  return getJson('/forecast/summary.json', forecastSummarySchema)
}

export async function fetchForecastRanking() {
  return getJson('/forecast/ranking.json', forecastRankingSchema)
}

export async function fetchMaterialForecast(materialId: string) {
  return getJson(`/forecast/materials/${materialId}.json`, materialForecastSchema)
}

export async function fetchInstruments(materialId: string) {
  return getJson(`/universe/instruments/${materialId}.json`, instrumentsSchema)
}

export async function fetchManufacturersList() {
  return getJson('/universe/manufacturers.json', manufacturersFileSchema)
}

export async function fetchMaterialsList() {
  return getJson('/universe/materials.json', materialsFileSchema)
}

export async function fetchExtractions(filters: ExtractionFilters = {}) {
  if (DATA_SOURCE === 'mock') {
    const index = await getJson('/extractions/index.json', extractionListSchema)
    return filterExtractions(index.items, filters)
  }

  const query = buildQuery({
    ticker: filters.ticker?.join(','),
    material: filters.material,
    from: filters.from,
    to: filters.to,
    limit: filters.limit,
    offset: filters.offset,
  })
  return getJson(`/extractions${query}`, extractionListSchema)
}

export async function fetchExtractionById(extractionId: string) {
  if (DATA_SOURCE === 'mock') {
    const index = await getJson('/extractions/index.json', extractionListSchema)
    const row = index.items.find((item) => item.id === extractionId)
    if (!row) {
      throw new Error(`Extraction not found: ${extractionId}`)
    }
    return extractionSchema.parse(row)
  }
  return getJson(`/extractions/${extractionId}.json`, extractionSchema)
}

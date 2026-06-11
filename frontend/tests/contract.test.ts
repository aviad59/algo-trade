import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
import { describe, expect, it } from 'vitest'
import {
  extractionListSchema,
  forecastRankingSchema,
  forecastSummarySchema,
  materialForecastSchema,
} from '../src/types/contract'

const mockRoot = join(__dirname, '../../backend/mock/v1')

function load(rel: string) {
  return JSON.parse(readFileSync(join(mockRoot, rel), 'utf-8'))
}

describe('mock contract schemas', () => {
  it('parses forecast/summary.json', () => {
    expect(() => forecastSummarySchema.parse(load('forecast/summary.json'))).not.toThrow()
  })

  it('parses forecast/ranking.json', () => {
    expect(() => forecastRankingSchema.parse(load('forecast/ranking.json'))).not.toThrow()
  })

  it('parses forecast/materials/lithium.json', () => {
    expect(() =>
      materialForecastSchema.parse(load('forecast/materials/lithium.json')),
    ).not.toThrow()
  })

  it('parses extractions/index.json', () => {
    expect(() => extractionListSchema.parse(load('extractions/index.json'))).not.toThrow()
  })
})

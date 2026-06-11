import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
import { describe, expect, it } from 'vitest'
import { filterExtractions } from '../src/api/mockFilter'
import { extractionListSchema } from '../src/types/contract'

const mockIndex = extractionListSchema.parse(
  JSON.parse(
    readFileSync(
      join(__dirname, '../../backend/mock/v1/extractions/index.json'),
      'utf-8',
    ),
  ),
)

describe('filterExtractions', () => {
  it('filters TSLA in date range with lithium effect', () => {
    const result = filterExtractions(mockIndex.items, {
      ticker: ['TSLA'],
      from: '2026-01-01',
      to: '2026-06-30',
    })
    expect(result.total).toBeGreaterThanOrEqual(1)
    expect(
      result.items.some((row) =>
        row.dated_effects.some((e) => e.sector === 'lithium'),
      ),
    ).toBe(true)
  })

  it('filters TSLA and GM with both tickers present', () => {
    const result = filterExtractions(mockIndex.items, {
      ticker: ['TSLA', 'GM'],
    })
    expect(result.total).toBeGreaterThanOrEqual(2)
    const tickers = new Set(result.items.map((r) => r.ticker))
    expect(tickers.has('TSLA')).toBe(true)
    expect(tickers.has('GM')).toBe(true)
  })

  it('filters material=copper with FCX', () => {
    const result = filterExtractions(mockIndex.items, { material: 'copper' })
    expect(result.items.some((r) => r.ticker === 'FCX')).toBe(true)
  })

  it('returns empty for out-of-range dates', () => {
    const result = filterExtractions(mockIndex.items, {
      from: '2099-01-01',
      to: '2099-12-31',
    })
    expect(result.total).toBe(0)
  })
})

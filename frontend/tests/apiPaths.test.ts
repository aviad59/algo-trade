import { describe, expect, it } from 'vitest'
import { extractionListSchema, materialForecastSchema } from '../src/types/contract'

/** Mirrors resourcePath() in endpoints.ts — api mode strips .json suffix. */
function resourcePath(mockPath: string, dataSource: 'mock' | 'api'): string {
  if (dataSource === 'mock') return mockPath
  return mockPath.replace(/\.json$/, '').replace('/index', '')
}

describe('api path mapping', () => {
  it('keeps mock paths unchanged', () => {
    expect(resourcePath('/forecast/summary.json', 'mock')).toBe('/forecast/summary.json')
    expect(resourcePath('/extractions/index.json', 'mock')).toBe('/extractions/index.json')
  })

  it('strips .json in api mode', () => {
    expect(resourcePath('/forecast/summary.json', 'api')).toBe('/forecast/summary')
    expect(resourcePath('/forecast/materials/lithium.json', 'api')).toBe(
      '/forecast/materials/lithium',
    )
    expect(resourcePath('/extractions/index.json', 'api')).toBe('/extractions')
  })
})

describe('api response contract shapes (synthetic)', () => {
  it('accepts a minimal MaterialForecast from pipeline shape', () => {
    const payload = {
      contract_version: '1.0' as const,
      material_id: 'lithium',
      as_of: '2026-06-08',
      actions: [
        {
          date: '2026-04-01',
          action: 'BUY' as const,
          rationale: 'forward_AUC rising',
        },
      ],
      curve: [{ month: '2026-05', signal: 1.45, forward_AUC: 4.1 }],
      contributing_ticker_count: 2,
      universe_curve: null,
    }
    expect(() => materialForecastSchema.parse(payload)).not.toThrow()
  })

  it('accepts a paginated extraction list', () => {
    const payload = {
      contract_version: '1.0' as const,
      total: 1,
      limit: 50,
      offset: 0,
      items: [
        {
          id: 'ext_00001',
          ticker: 'TSLA',
          cik: '0001318605',
          filing_type: '10-Q',
          filing_date: '2026-04-30',
          filing_url: 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=1318605&type=10-Q',
          dated_effects: [
            {
              sector: 'lithium',
              direction: 'increase' as const,
              magnitude: 'large' as const,
              window_start: '2026-05-01',
              window_end: '2026-08-31',
              rationale: 'ramp',
              source_span: 'Item 2',
            },
          ],
          flagged_risks: [],
          extractor_confidence: 0.79,
        },
      ],
    }
    expect(() => extractionListSchema.parse(payload)).not.toThrow()
  })
})

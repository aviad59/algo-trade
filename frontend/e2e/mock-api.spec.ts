import { expect, test } from '@playwright/test'

test.describe('Mock API static files', () => {
  test('serves forecast summary JSON', async ({ request }) => {
    const response = await request.get('/mock/v1/forecast/summary.json')
    expect(response.ok()).toBeTruthy()

    const body = await response.json()
    expect(body.contract_version).toBe('1.0')
    expect(body.top_materials.length).toBeGreaterThan(0)
  })

  test('serves extractions index JSON', async ({ request }) => {
    const response = await request.get('/mock/v1/extractions/index.json')
    expect(response.ok()).toBeTruthy()

    const body = await response.json()
    expect(body.items.length).toBe(12)
  })
})

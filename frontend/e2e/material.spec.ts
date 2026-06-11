import { expect, test } from '@playwright/test'

test.describe('Material detail', () => {
  test('lithium renders chart with BUY/SELL markers and contributors', async ({ page }) => {
    await page.goto('/materials/lithium')

    await expect(page.getByRole('heading', { name: 'Lithium' })).toBeVisible()
    await expect(page.getByText('Narrative signal, not price')).toBeVisible()
    await expect(page.getByText('Demand signal curve')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Contributing filings' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'TSLA' }).first()).toBeVisible()
    await expect(page.getByRole('link', { name: /10-Q/ }).first()).toBeVisible()
  })

  test('chart data is viewable as table', async ({ page }) => {
    await page.goto('/materials/lithium')

    await page.getByRole('button', { name: 'View as table' }).click()
    await expect(page.getByRole('columnheader', { name: 'Month' })).toBeVisible()
    await expect(page.getByRole('cell', { name: 'May 2026' })).toBeVisible()
  })

  test('contributor links navigate to company and filing', async ({ page }) => {
    await page.goto('/materials/lithium')

    await page.getByRole('link', { name: 'TSLA' }).first().click()
    await expect(page).toHaveURL('/companies/TSLA')

    await page.goto('/materials/lithium')
    await page.getByRole('link', { name: /10-Q/ }).first().click()
    await expect(page).toHaveURL(/\/filings\/ext_/)
  })

  test('unknown material shows 404', async ({ page }) => {
    await page.goto('/materials/not-a-real-material')
    await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible()
  })
})

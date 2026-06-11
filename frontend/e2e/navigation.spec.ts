import { expect, test } from '@playwright/test'

test.describe('App navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('shows disclaimer on every page', async ({ page }) => {
    await expect(page.getByRole('note')).toContainText('not financial advice')

    await page.getByRole('link', { name: 'Explorer' }).click()
    await expect(page.getByRole('note')).toContainText('not financial advice')

    await page.getByRole('link', { name: 'About' }).click()
    await expect(page.getByRole('note')).toContainText('not financial advice')
  })

  test('navigates main routes', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Forecast dashboard' })).toBeVisible()

    await page.getByRole('link', { name: 'Explorer' }).click()
    await expect(page).toHaveURL(/\/explorer/)
    await expect(page.getByRole('heading', { name: 'Explorer' })).toBeVisible()

    await page.getByRole('link', { name: 'About' }).click()
    await expect(page).toHaveURL(/\/about/)
    await expect(page.getByRole('heading', { name: 'About algo-trade' })).toBeVisible()

    await page.getByRole('link', { name: 'Forecast' }).click()
    await expect(page).toHaveURL('/')
  })

  test('supports deep-linked routes', async ({ page }) => {
    await page.goto('/materials/lithium')
    await expect(page.getByRole('heading', { name: 'lithium' })).toBeVisible()

    await page.goto('/companies/TSLA')
    await expect(page.getByRole('heading', { name: 'TSLA' })).toBeVisible()

    await page.goto('/filings/ext_00001')
    await expect(page.getByRole('heading', { name: /Filing ext_00001/ })).toBeVisible()
  })

  test('shows 404 for unknown routes', async ({ page }) => {
    await page.goto('/does-not-exist')
    await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible()
  })
})

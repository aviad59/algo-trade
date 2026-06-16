import { expect, test } from '@playwright/test'

test.describe('Explorer', () => {
  test('loads results from shareable URL', async ({ page }) => {
    await page.goto('/explorer?tickers=TSLA,GM&from=2026-01-01&to=2026-06-30')

    await expect(page.getByText(/\d+ extraction(s)? matched/i)).toBeVisible()
    await expect(page.getByRole('link', { name: 'TSLA' }).first()).toBeVisible()
    await expect(page.getByRole('link', { name: 'GM' }).first()).toBeVisible()
  })

  test('restores query on reload', async ({ page }) => {
    const url = '/explorer?tickers=TSLA&from=2026-01-01&to=2026-06-30&material=lithium'
    await page.goto(url)
    await expect(page.getByText(/\d+ extraction(s)? matched/i)).toBeVisible({ timeout: 10_000 })

    await page.reload()
    await expect(page).toHaveURL(url)
    await expect(page.getByText(/\d+ extraction(s)? matched/i)).toBeVisible({ timeout: 10_000 })
  })

  test('shows empty state for out-of-range dates', async ({ page }) => {
    await page.goto('/explorer?tickers=TSLA&from=2099-01-01&to=2099-12-31')

    await expect(page.getByText('No extractions matched')).toBeVisible()
  })

  test('shows validation error without tickers', async ({ page }) => {
    await page.goto('/explorer')
    await page.getByRole('button', { name: 'Show results' }).click()
    await expect(page.getByText('Select at least one ticker.')).toBeVisible()
  })

  test('query flow from form updates URL', async ({ page }) => {
    await page.goto('/explorer')

    await page.getByPlaceholder('Search ticker or company name').fill('TSLA')
    await page.locator('button', { hasText: 'TSLA' }).first().click()
    await page.getByPlaceholder('Search ticker or company name').fill('GM')
    await page.locator('button', { hasText: 'GM' }).first().click()

    await page.getByRole('button', { name: 'YTD' }).click()
    await page.getByRole('button', { name: 'Show results' }).click()

    await expect(page).toHaveURL(/tickers=TSLA%2CGM/)
    await expect(page.getByText(/\d+ extraction(s)? matched/i)).toBeVisible()
  })

  test('signal and prices tabs are disabled', async ({ page }) => {
    await page.goto('/explorer?tickers=TSLA&from=2026-01-01&to=2026-06-30')

    await expect(page.getByRole('tab', { name: 'Extractions' })).toBeEnabled()
    await expect(page.getByRole('tab', { name: 'Signal' })).toBeDisabled()
    await expect(page.getByRole('tab', { name: 'Prices' })).toBeDisabled()
  })
})

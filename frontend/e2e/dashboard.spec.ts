import { expect, test } from '@playwright/test'

test.describe('Forecast dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('loads ranked materials from mock data', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Forecast dashboard' })).toBeVisible()
    await expect(page.getByText('Jun 8, 2026', { exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Material ranking' })).toBeVisible()
    await expect(page.getByRole('cell', { name: 'Lithium' })).toBeVisible()
    await expect(page.getByRole('cell', { name: 'Electricity / Grid Power' })).toBeVisible()
  })

  test('navigates to material detail from ranking row', async ({ page }) => {
    await page.getByRole('row', { name: /Lithium/ }).click()
    await expect(page).toHaveURL('/materials/lithium')
    await expect(page.getByRole('heading', { name: 'Lithium' })).toBeVisible()
  })

  test('navigates to company from ticker chip', async ({ page }) => {
    const ranking = page.getByRole('heading', { name: 'Material ranking' }).locator('..')
    await ranking.getByRole('link', { name: 'TSLA' }).first().click()
    await expect(page).toHaveURL('/companies/TSLA')
    await expect(page.getByRole('heading', { name: 'Tesla, Inc.' })).toBeVisible()
  })
})

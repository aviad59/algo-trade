import { expect, test } from '@playwright/test'

test.describe('Company and filing audit', () => {
  test('company page lists filings for TSLA', async ({ page }) => {
    await page.goto('/companies/TSLA')

    await expect(page.getByRole('heading', { name: 'Tesla, Inc.' })).toBeVisible()
    await expect(page.getByText('CIK 0001318605')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Filings' })).toBeVisible()
    await expect(page.getByRole('link', { name: '10-Q' }).first()).toBeVisible()
  })

  test('filing page shows confidence, risks, and SEC link', async ({ page }) => {
    await page.goto('/filings/ext_00001')

    await expect(page.getByRole('heading', { name: 'Filing audit' })).toBeVisible()
    await expect(page.getByText('Extractor confidence')).toBeVisible()
    await expect(page.getByText('79%')).toBeVisible()
    await expect(page.getByText('Flagged risks')).toBeVisible()
    await expect(page.getByText('Lithium supply concentration in Chile/Australia')).toBeVisible()
    await expect(page.getByText('Item 2, MD&A, p.18')).toBeVisible()

    const secLink = page.getByRole('link', { name: 'View on SEC EDGAR' })
    await expect(secLink).toHaveAttribute('target', '_blank')
    await expect(secLink).toHaveAttribute('rel', 'noopener noreferrer')
  })

  test('material to company to filing navigation works', async ({ page }) => {
    await page.goto('/materials/lithium')

    await page.getByRole('link', { name: 'TSLA' }).first().click()
    await expect(page).toHaveURL('/companies/TSLA')
    await expect(page.getByRole('heading', { name: 'Tesla, Inc.' })).toBeVisible()

    await page.getByRole('link', { name: '10-Q' }).first().click()
    await expect(page).toHaveURL('/filings/ext_00001')
    await expect(page.getByRole('heading', { name: 'Filing audit' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Lithium' })).toBeVisible()
  })

  test('unknown company shows 404', async ({ page }) => {
    await page.goto('/companies/NOTREAL')
    await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible()
  })

  test('unknown filing shows 404', async ({ page }) => {
    await page.goto('/filings/ext_99999')
    await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible()
  })
})

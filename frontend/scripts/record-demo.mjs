import { chromium } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.join(__dirname, '..')
const OUT_DIR = path.join(ROOT, '..', 'docs', 'demo')
const TEMP_VIDEO_DIR = path.join(OUT_DIR, '.capture')
const OUTPUT_VIDEO = path.join(OUT_DIR, 'filingsignal-demo.webm')

const BASE_URL = process.env.DEMO_BASE_URL ?? 'http://localhost:5173'
const VIEWPORT = { width: 1280, height: 720 }

function pause(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function waitForApp(page) {
  await page.goto(BASE_URL, { waitUntil: 'networkidle' })
  await page.getByRole('heading', { name: 'Forecast dashboard' }).waitFor({ timeout: 30_000 })
}

async function smoothScroll(page, deltaY) {
  await page.evaluate(async (distance) => {
    const step = distance > 0 ? 40 : -40
    const steps = Math.ceil(Math.abs(distance) / Math.abs(step))
    for (let i = 0; i < steps; i += 1) {
      window.scrollBy(0, step)
      await new Promise((r) => setTimeout(r, 16))
    }
  }, deltaY)
}

async function main() {
  await mkdir(TEMP_VIDEO_DIR, { recursive: true })
  await mkdir(OUT_DIR, { recursive: true })

  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({
    viewport: VIEWPORT,
    recordVideo: {
      dir: TEMP_VIDEO_DIR,
      size: VIEWPORT,
    },
  })
  const page = await context.newPage()

  try {
    // Dashboard
    await waitForApp(page)
    await pause(2500)

    // Material detail
    await page.getByRole('row', { name: /Lithium/ }).click()
    await page.waitForURL('**/materials/lithium')
    await page.getByRole('heading', { name: 'Lithium' }).waitFor()
    await pause(2000)
    await smoothScroll(page, 500)
    await pause(1500)

    await page.getByRole('button', { name: 'View as table' }).click()
    await page.getByRole('columnheader', { name: 'Month' }).waitFor()
    await pause(1500)
    await page.getByRole('button', { name: 'Hide table' }).click()
    await pause(1000)

    // Company audit
    await page.getByRole('link', { name: 'TSLA' }).first().click()
    await page.waitForURL(/\/companies\/TSLA/)
    await page.getByRole('heading', { name: 'Tesla, Inc.' }).waitFor()
    await page.getByRole('heading', { name: 'Filings' }).waitFor({ timeout: 15_000 })
    await pause(2000)

    // Filing audit
    const filingLink = page.locator('table').getByRole('link', { name: '10-Q' }).first()
    await filingLink.waitFor({ timeout: 15_000 })
    await filingLink.click()
    await page.waitForURL(/\/filings\/ext_/, { timeout: 15_000 })
    await page.getByRole('heading', { name: 'Filing audit' }).waitFor()
    await pause(2500)
    await smoothScroll(page, 400)
    await pause(1500)

    // Explorer
    await page.getByRole('link', { name: 'Explorer' }).click()
    await page.getByRole('heading', { name: 'Explorer' }).waitFor()
    await pause(1500)

    await page.getByPlaceholder('Search ticker or company name').fill('TSLA')
    await page.locator('button', { hasText: 'TSLA' }).first().click()
    await page.getByPlaceholder('Search ticker or company name').fill('GM')
    await page.locator('button', { hasText: 'GM' }).first().click()
    await page.getByRole('button', { name: 'YTD' }).click()
    await page.getByRole('button', { name: 'Show results' }).click()
    await page.getByText(/\d+ extraction(s)? matched/i).waitFor({ timeout: 15_000 })
    await pause(2000)

    await page.locator('#explorer-from').click()
    await page.locator('[data-slot="popover-content"]').waitFor()
    await pause(2000)
    await page.keyboard.press('Escape')
    await pause(500)

    // About
    await page.getByRole('link', { name: 'About' }).click()
    await page.getByRole('heading', { name: 'About FilingSignal' }).waitFor()
    await pause(2000)

    // Back to dashboard
    await page.getByRole('link', { name: 'Forecast' }).click()
    await page.getByRole('heading', { name: 'Forecast dashboard' }).waitFor()
    await pause(2500)
  } finally {
    const video = page.video()
    await page.close()

    if (!video) {
      await context.close()
      await browser.close()
      throw new Error('No video was recorded.')
    }

    await video.saveAs(OUTPUT_VIDEO)
    await context.close()
    await browser.close()
    console.log(`Demo video saved to ${OUTPUT_VIDEO}`)
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})

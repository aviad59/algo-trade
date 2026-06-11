# FilingSignal demo video

A walkthrough of the mock UI is recorded with Playwright.

## Record

With the dev server running (`npm run dev` in `frontend/`):

```bash
cd frontend
npm run record-demo
```

Output: `docs/demo/filingsignal-demo.webm`

Optional: point at another URL with `DEMO_BASE_URL=http://localhost:5174 npm run record-demo`.

## What it shows

1. Forecast dashboard and material ranking
2. Lithium material detail (chart + table)
3. Company audit (Tesla)
4. Filing audit with source spans
5. Explorer query (tickers, date presets, calendar)
6. About page

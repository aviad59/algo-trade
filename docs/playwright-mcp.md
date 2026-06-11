# Playwright + MCP

Browser automation for the algo-trade web UI: **Playwright E2E tests** in CI/local, and **Playwright MCP** in Cursor for interactive verification.

## Playwright MCP (Cursor)

Create locally (gitignored): `.cursor/mcp.json`

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest", "--headless", "--browser=chromium"]
    }
  }
}
```

### Enable in Cursor

1. Open **Settings → MCP** and ensure the `playwright` server is toggled on.
2. Reload MCP if tools do not appear (toggle off/on or restart Cursor).
3. First run may download Chromium via Playwright.

### When to use MCP vs E2E tests

| Tool | Use for |
|------|---------|
| **Playwright MCP** | Exploratory checks, verifying UI while building a phase, debugging layout |
| **`npm run test:e2e`** | Repeatable regression tests in CI and before merge |

### Example prompts (Composer)

- "Use Playwright MCP to open localhost:5173 and confirm the disclaimer appears on Dashboard and Explorer."
- "Navigate to /materials/lithium and screenshot the forecast chart after Phase 4."

Run `npm run dev` in `frontend/` first so MCP hits a live server.

---

## Playwright E2E tests

From `frontend/`:

```bash
npm install
npx playwright install chromium   # first time only
npm run test:e2e
```

| Script | Description |
|--------|-------------|
| `npm run test:e2e` | Headless E2E (starts Vite via `playwright.config.ts`) |
| `npm run test:e2e:ui` | Interactive Playwright UI mode |
| `npm run test:e2e:headed` | Headed browser |

Tests live in `frontend/e2e/`:

- `navigation.spec.ts` — routes, disclaimer, 404
- `mock-api.spec.ts` — static mock JSON served under `/mock/v1/`

---

## CI (future)

```yaml
- run: npx playwright install --with-deps chromium
  working-directory: frontend
- run: npm run test:e2e
  working-directory: frontend
```

# Backend

Agent pipeline, reference data, mock API snapshots, and validation scripts.

## Layout

```
backend/
  universe/              # Reference data (manufacturers, materials, instrument map)
  mock/v1/               # Demo JSON bundle — contract v1.0 for the web UI
  scripts/
    validate-mock-contract.py
```

| Path | Owner | Purpose |
|------|-------|---------|
| [`universe/`](universe/README.md) | Agent / data team | Input universe, material vocabulary, investable instruments |
| [`mock/v1/`](mock/v1/manifest.json) | Web + agents | Forecast snapshots served to the frontend until a live API exists |
| [`scripts/`](scripts/) | Web | CI validation of mock bundle against [HLD §8](../docs/hld-web-interface.md) |

## Validate mock bundle

From repo root:

```bash
py backend/scripts/validate-mock-contract.py
```

## Future (agent team)

- EDGAR fetcher, extractor, buffer, recommender, timeline aggregator, buy/sell timer
- `GET /api/v1/*` serving pipeline snapshots (same shapes as `mock/v1/`)

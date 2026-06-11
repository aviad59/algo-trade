# Frontend

Web interface for the algo-trade forecast demo (React + TypeScript + Vite).

**Status:** Not scaffolded yet — see [implementation plan](../docs/implementation-plan-web.md) Phase 1.

## Planned layout

```
frontend/
  public/mock/v1/     # Copy or symlink from ../backend/mock/v1 at dev time
  src/
    routes/           # Dashboard, Material, Company, Filing, Explorer, About
    components/
    api/
    types/
    hooks/
```

## Data source

The UI reads JSON from `/mock/v1/*` (static) or `/api/v1/*` (live backend). Contract: [HLD §8](../docs/hld-web-interface.md).

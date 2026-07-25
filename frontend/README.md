# FilingSignal — frontend

React 19 + TypeScript + Vite. Currently a hello-world skeleton; functionality
is layered on top from here.

## Local dev

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173 (hot reload)
```

## Production build

```bash
npm run build        # -> dist/
npm run preview      # serve the built files locally
```

## Docker (full stack, one command)

From the repo root (needs Docker Desktop running). The single image builds this
frontend, installs the backend, bakes the mock dataset, and serves the SPA + the
`/api/v1` API together on one port:

```bash
docker compose up --build     # → http://localhost:8000
```

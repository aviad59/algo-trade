"""FastAPI app. Read endpoints are public; POST /extract is shared-secret gated.
Optionally serves the built frontend (SPA) when FILINGSIGNAL_FRONTEND_DIST is set.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .deps import get_settings
from .routers import backtest, extract, filings, forecast, meta, rating

app = FastAPI(title="FilingSignal API", version="0.1.0")

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

for _r in (meta, forecast, filings, backtest, rating, extract):
    app.include_router(_r.router, prefix="/api/v1")


@app.get("/api/v1/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


def _mount_frontend() -> None:
    dist = _settings.frontend_dist
    if dist and dist.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")


_mount_frontend()


def run() -> None:
    import uvicorn

    from ..env import env_int, env_str

    uvicorn.run(
        app,
        host=env_str("FILINGSIGNAL_API_HOST", "0.0.0.0"),
        port=env_int("FILINGSIGNAL_API_PORT", 8000),
    )

"""FastAPI application for GET /api/v1/*."""

from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .deps import get_settings
from .errors import http_exception_handler, unhandled_exception_handler
from .routers import backtest, extract, extractions, forecast, meta, universe

_settings = get_settings()

app = FastAPI(title="algo-trade API", version="1.0")
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(meta.router, prefix="/api/v1")
app.include_router(forecast.router, prefix="/api/v1")
app.include_router(extractions.router, prefix="/api/v1")
app.include_router(universe.router, prefix="/api/v1")
app.include_router(backtest.router, prefix="/api/v1")
app.include_router(extract.router, prefix="/api/v1")


class _SpaStaticFiles(StaticFiles):
    """Static files that fall back to index.html for client-side routes."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


# Single-container deployment: when the frontend has been built
# (`npm run build` -> frontend/dist), serve it from this process so one
# port serves both the UI and /api/v1. In dev Vite serves the UI on :5173
# and this mount never activates. Registered after the API routers, which
# therefore keep precedence. The repo-relative default only works for
# editable installs; containers set ALGO_TRADE_FRONTEND_DIST explicitly
# (a pip-installed `api` package lives in site-packages, not the repo).
from algo_trade.env import env_str as _env_str  # noqa: E402

_dist_override = _env_str("ALGO_TRADE_FRONTEND_DIST", "")
_FRONTEND_DIST = (
    Path(_dist_override)
    if _dist_override
    else Path(__file__).resolve().parents[2] / "frontend" / "dist"
)
if _FRONTEND_DIST.is_dir():
    app.mount("/", _SpaStaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")


def run() -> None:
    """Console entry point for ``algo-trade-api``."""
    settings = get_settings()
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()

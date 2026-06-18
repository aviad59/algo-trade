"""FastAPI application for GET /api/v1/*."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .deps import get_settings
from .errors import http_exception_handler, unhandled_exception_handler
from .routers import extractions, forecast, meta, universe

_settings = get_settings()

app = FastAPI(title="algo-trade API", version="1.0")
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(meta.router, prefix="/api/v1")
app.include_router(forecast.router, prefix="/api/v1")
app.include_router(extractions.router, prefix="/api/v1")
app.include_router(universe.router, prefix="/api/v1")


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

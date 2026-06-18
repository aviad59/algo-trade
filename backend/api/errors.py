"""User-safe API error responses — no stack traces or internal paths in JSON."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

BUFFER_UNAVAILABLE = {
    "error": "buffer_unavailable",
    "message": (
        "The pipeline database is not available. Run algo-trade-extract to populate "
        "the buffer, or set VITE_DATA_SOURCE=mock in .env to use demo data."
    ),
}

INTERNAL_ERROR = {
    "error": "internal_error",
    "message": "The server encountered an unexpected error. Please try again later.",
}


def error_detail(code: str, message: str) -> dict[str, str]:
    return {"error": code, "message": message}


def buffer_http_exception(cause: Exception | None = None) -> HTTPException:
    logger.warning("buffer unavailable", exc_info=cause)
    return HTTPException(status_code=503, detail=BUFFER_UNAVAILABLE)


def open_buffer(path: str):
    """Open the pipeline buffer, translating low-level SQLite errors."""
    from algo_trade.buffer import Buffer

    try:
        return Buffer(path)
    except sqlite3.OperationalError as exc:
        raise buffer_http_exception(exc) from exc


async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    detail: Any = exc.detail
    if isinstance(detail, dict) and "message" in detail:
        body = detail
    elif isinstance(detail, str):
        body = error_detail("request_error", detail)
    else:
        body = error_detail("request_error", "The request could not be completed.")
    return JSONResponse(status_code=exc.status_code, content=body)


async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled API error")
    return JSONResponse(status_code=500, content=INTERNAL_ERROR)

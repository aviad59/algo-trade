"""Demo-token-gated live extraction: pull a ticker's filings through Agent #1.

This is the POST /api/v1/extract the dev.py docstring always promised. Unlike
the read-only rest of the API it mutates the buffer, so it is available only
to requests carrying the demo token — everyone else gets a 401 without any
hint of what a valid token looks like.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..errors import error_detail
from ..services.extract_job import job_status, start_extraction
from ..services.forecast import demo_token_matches

router = APIRouter(prefix="/extract", tags=["extract"])

_STATUS_CODES = {
    "invalid": 422,
    "busy": 409,
    "budget": 429,
    "unconfigured": 503,
}


class ExtractRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    forms: list[str] | None = None
    limit: int = Field(default=1, ge=1, le=3)


def _require_token(x_demo_token: str | None) -> None:
    if not demo_token_matches(x_demo_token):
        raise HTTPException(
            status_code=401,
            detail=error_detail("unauthorized", "live extraction requires a demo token"),
        )


@router.post("")
def extract(
    body: ExtractRequest,
    x_demo_token: str | None = Header(default=None),
) -> dict:
    _require_token(x_demo_token)
    outcome, message = start_extraction(body.ticker, body.forms, body.limit)
    if outcome != "started":
        raise HTTPException(
            status_code=_STATUS_CODES[outcome],
            detail=error_detail(outcome, message),
        )
    return {"contract_version": "1.0", "status": "started", "message": message}


@router.get("/status")
def extract_status(x_demo_token: str | None = Header(default=None)) -> dict:
    _require_token(x_demo_token)
    return job_status()

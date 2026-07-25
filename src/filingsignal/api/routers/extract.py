from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from ..auth import require_api_key
from ..deps import get_settings
from ..services.digest import digest_one
from ..services.extract_job import job_status, start_job

router = APIRouter()


@router.post("/digest", dependencies=[Depends(require_api_key)])
def digest(body: dict = Body(...), settings=Depends(get_settings)):
    """Interactive one-filing digest: fetch the most-recent {form} for {ticker}
    on or before {before}, run the pipeline, return summary + effects."""
    ticker = (body.get("ticker") or "").strip()
    form = (body.get("form") or "").strip()
    before_raw = body.get("before")
    if not ticker or not form:
        raise HTTPException(status_code=422, detail="'ticker' and 'form' are required")
    try:
        before = date.fromisoformat(before_raw) if before_raw else None
    except ValueError:
        raise HTTPException(status_code=422, detail="'before' must be an ISO date (YYYY-MM-DD)")
    result = digest_one(ticker, form, before, settings)
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result["reason"])
    return result


@router.post("/extract", dependencies=[Depends(require_api_key)])
def extract(body: dict = Body(...), settings=Depends(get_settings)):
    tickers = body.get("tickers") or []
    forms: Optional[list[str]] = body.get("forms")
    if not tickers:
        raise HTTPException(status_code=422, detail="'tickers' is required")
    try:
        return start_job(tickers, forms, settings)
    except RuntimeError as exc:
        msg = str(exc)
        if "already running" in msg:
            raise HTTPException(status_code=409, detail=msg)
        if "SEC_IDENTITY" in msg:
            raise HTTPException(status_code=503, detail=msg)
        raise HTTPException(status_code=500, detail=msg)


@router.get("/extract/status")
def extract_status():
    return job_status()

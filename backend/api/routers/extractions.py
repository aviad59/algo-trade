from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from algo_trade.buffer import Buffer

from ..deps import get_buffer, get_settings
from ..services.extractions import (
    extraction_to_dict,
    list_extractions_response,
    parse_extraction_public_id,
)

router = APIRouter(prefix="/extractions", tags=["extractions"])


@router.get("")
def list_extractions(
    ticker: str | None = Query(default=None),
    material: str | None = Query(default=None),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    buf: Buffer = Depends(get_buffer),
) -> dict:
    settings = get_settings()
    tickers = [t.strip() for t in ticker.split(",") if t.strip()] if ticker else None
    return list_extractions_response(
        buf,
        universe_dir=settings.universe_dir,
        tickers=tickers,
        material=material,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )


@router.get("/{extraction_id}")
def get_extraction(extraction_id: str, buf: Buffer = Depends(get_buffer)) -> dict:
    settings = get_settings()
    parsed = parse_extraction_public_id(extraction_id)
    if parsed is None:
        raise HTTPException(status_code=404, detail="Extraction not found")
    row = buf.get_extraction(parsed)
    if row is None:
        raise HTTPException(status_code=404, detail="Extraction not found")
    return extraction_to_dict(row, settings.universe_dir)

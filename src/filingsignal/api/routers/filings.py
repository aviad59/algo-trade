from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_buffer, get_universe
from ..services.filings import filing_to_dict, list_filings

router = APIRouter()


@router.get("/filings")
def filings(
    ticker: Optional[str] = None,
    material: Optional[str] = None,
    form: Optional[str] = None,
    perspective: Optional[str] = None,
    limit: int = 200,
    buf=Depends(get_buffer),
    uni=Depends(get_universe),
):
    return list_filings(
        buf, uni,
        tickers=ticker.split(",") if ticker else None,
        materials=material.split(",") if material else None,
        forms=form.split(",") if form else None,
        perspectives=perspective.split(",") if perspective else None,
        limit=limit,
    )


@router.get("/filings/{accession}")
def filing_detail(accession: str, buf=Depends(get_buffer), uni=Depends(get_universe)):
    fr = buf.get_filing(accession)
    if fr is None:
        raise HTTPException(status_code=404, detail="filing not found")
    return filing_to_dict(fr, uni)

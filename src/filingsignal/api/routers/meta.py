from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends

from ...scorer import quarter_label
from ..deps import get_buffer, get_settings, get_universe

router = APIRouter()


@router.get("/meta")
def meta(buf=Depends(get_buffer), uni=Depends(get_universe), settings=Depends(get_settings)):
    return {
        "asOf": date.today().isoformat(),
        "forecastQuarter": quarter_label(settings.target_quarter()),
        "dataSource": "api",
        "universe": [{"material": m.name, "etf": m.etf} for m in uni.materials.values()],
        "counts": {"filings": buf.count_filings(), "extractions": buf.count_extractions()},
    }

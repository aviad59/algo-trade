from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_buffer, get_settings, get_universe
from ..services.analysis import get_forecast

router = APIRouter()


@router.get("/forecast")
def forecast(buf=Depends(get_buffer), uni=Depends(get_universe), settings=Depends(get_settings)):
    return get_forecast(buf, uni, settings)

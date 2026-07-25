from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_buffer, get_settings, get_universe
from ..services.analysis import get_backtest

router = APIRouter()


@router.get("/backtest")
def backtest(buf=Depends(get_buffer), uni=Depends(get_universe), settings=Depends(get_settings)):
    return get_backtest(buf, uni, settings)

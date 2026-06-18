from __future__ import annotations

from fastapi import APIRouter, Depends

from algo_trade.buffer import Buffer

from ..deps import get_buffer, get_settings

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/health")
def health(buf: Buffer = Depends(get_buffer)) -> dict:
    settings = get_settings()
    return {
        "contract_version": "1.0",
        "status": "ok",
        "latest_as_of": settings.forecast_until.isoformat(),
        "data_source": "pipeline",
    }

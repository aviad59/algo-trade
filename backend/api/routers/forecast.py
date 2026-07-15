from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Header

from algo_trade.buffer import Buffer

from ..deps import get_buffer, get_settings
from ..services.forecast import (
    build_material_forecast,
    build_ranking,
    build_summary,
    demo_token_matches,
)

router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.get("/summary")
def forecast_summary(
    buf: Buffer = Depends(get_buffer),
    x_demo_token: str | None = Header(default=None),
) -> dict:
    settings = get_settings()
    return build_summary(
        buf,
        settings.forecast_since,
        settings.forecast_until,
        settings.forecast_until,
        settings.universe_dir,
        live=demo_token_matches(x_demo_token),
    )


@router.get("/ranking")
def forecast_ranking(
    buf: Buffer = Depends(get_buffer),
    x_demo_token: str | None = Header(default=None),
) -> dict:
    settings = get_settings()
    return build_ranking(
        buf,
        settings.forecast_since,
        settings.forecast_until,
        settings.forecast_until,
        settings.universe_dir,
        live=demo_token_matches(x_demo_token),
    )


@router.get("/materials/{material_id}")
def forecast_material(material_id: str, buf: Buffer = Depends(get_buffer)) -> dict:
    settings = get_settings()
    return build_material_forecast(
        buf,
        material_id,
        settings.forecast_since,
        settings.forecast_until,
        settings.forecast_until,
    )

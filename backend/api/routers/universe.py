from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_settings
from ..services import universe as universe_service

router = APIRouter(prefix="/universe", tags=["universe"])


@router.get("/manufacturers")
def get_manufacturers() -> dict:
    settings = get_settings()
    return universe_service.manufacturers(settings.universe_dir)


@router.get("/materials")
def get_materials() -> dict:
    settings = get_settings()
    return universe_service.materials(settings.universe_dir)


@router.get("/instruments/{material_id}")
def get_instruments(material_id: str) -> dict:
    settings = get_settings()
    return universe_service.instruments(material_id, settings.universe_dir)

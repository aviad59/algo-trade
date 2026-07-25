from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends

from ..deps import get_buffer

router = APIRouter()


@router.get("/rating/{material}")
def rating(material: str, quarter: Optional[str] = None, buf=Depends(get_buffer)):
    r = buf.get_rating(material, quarter=quarter)
    if r is None:
        return {"available": False}
    return {"available": True, **r}

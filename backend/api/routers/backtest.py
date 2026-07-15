from __future__ import annotations

from fastapi import APIRouter, Depends

from algo_trade.buffer import Buffer

from ..deps import get_buffer
from ..services.backtest import build_backtest

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.get("")
def backtest(buf: Buffer = Depends(get_buffer)) -> dict:
    """Walk-forward backtest of the timer against cached prices."""
    return build_backtest(buf)

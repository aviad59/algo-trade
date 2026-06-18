"""FastAPI dependencies."""

from __future__ import annotations

from functools import lru_cache

from algo_trade.buffer import Buffer

from .config import Settings
from .errors import open_buffer


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


def get_buffer() -> Buffer:
    settings = get_settings()
    return open_buffer(str(settings.buffer_path))

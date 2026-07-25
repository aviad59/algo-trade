"""Shared dependencies: settings, universe, per-request buffer."""

from __future__ import annotations

from functools import lru_cache

from ..buffer import Buffer
from ..universe import Universe, load_universe
from .config import Settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


@lru_cache(maxsize=1)
def get_universe() -> Universe:
    return load_universe(get_settings().universe_dir / "materials.yaml")


def get_buffer() -> Buffer:
    """One Buffer per request (FastAPI runs sync deps on threadpool threads)."""
    buf = Buffer(get_settings().buffer_path)
    try:
        yield buf
    finally:
        buf.close()

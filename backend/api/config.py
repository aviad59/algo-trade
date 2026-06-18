"""API configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    buffer_path: Path
    universe_dir: Path
    forecast_since: date
    forecast_until: date
    cors_origins: list[str]

    @classmethod
    def from_env(cls) -> "Settings":
        today = date.today()
        default_since = today.replace(day=1) - timedelta(days=365)
        since = date.fromisoformat(os.environ.get("ALGO_TRADE_FORECAST_SINCE", default_since.isoformat()))
        until = date.fromisoformat(os.environ.get("ALGO_TRADE_FORECAST_UNTIL", today.isoformat()))
        cors = os.environ.get("ALGO_TRADE_CORS_ORIGINS", "http://localhost:5173,http://localhost:5174")
        return cls(
            buffer_path=Path(os.environ.get("ALGO_TRADE_BUFFER_PATH", "data/buffer.sqlite")),
            universe_dir=Path(os.environ.get("ALGO_TRADE_UNIVERSE_DIR", str(_repo_root() / "backend" / "universe"))),
            forecast_since=since,
            forecast_until=until,
            cors_origins=[o.strip() for o in cors.split(",") if o.strip()],
        )

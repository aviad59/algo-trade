"""API configuration from environment variables and repo-root ``.env``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from algo_trade.env import env_int, env_optional_str, env_path, env_str, load_env


@dataclass(frozen=True)
class Settings:
    buffer_path: Path
    universe_dir: Path
    forecast_since: date
    forecast_until: date
    cors_origins: list[str]
    ranking_mode: str
    recommender_model: str | None
    api_host: str
    api_port: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_env()
        today = date.today()
        default_since = today.replace(day=1) - timedelta(days=365)
        since_raw = env_str("ALGO_TRADE_FORECAST_SINCE", "")
        until_raw = env_str("ALGO_TRADE_FORECAST_UNTIL", "")
        since = (
            date.fromisoformat(since_raw) if since_raw else default_since
        )
        until = date.fromisoformat(until_raw) if until_raw else today
        cors = env_str(
            "ALGO_TRADE_CORS_ORIGINS",
            "http://localhost:5173,http://localhost:5174",
        )
        ranking_mode = env_str("ALGO_TRADE_RANKING_MODE", "rules").lower()
        if ranking_mode not in ("rules", "recommender"):
            ranking_mode = "rules"
        return cls(
            buffer_path=env_path("ALGO_TRADE_BUFFER_PATH", "data/buffer.sqlite"),
            universe_dir=env_path("ALGO_TRADE_UNIVERSE_DIR", "backend/universe"),
            forecast_since=since,
            forecast_until=until,
            cors_origins=[o.strip() for o in cors.split(",") if o.strip()],
            ranking_mode=ranking_mode,
            recommender_model=env_optional_str("ALGO_TRADE_RECOMMENDER_MODEL"),
            api_host=env_str("ALGO_TRADE_API_HOST", "0.0.0.0"),
            api_port=env_int("ALGO_TRADE_API_PORT", 8000),
        )

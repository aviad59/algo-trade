"""API settings from env + repo-root .env."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..clock import today
from ..env import env_optional_str, env_path, env_str, load_env
from ..scorer import Quarter, quarter_of


def _parse_quarter(s: str) -> Optional[Quarter]:
    try:
        y, q = s.upper().replace("Q", " ").split()
        return int(y), int(q)
    except Exception:  # noqa: BLE001
        return None


@dataclass(frozen=True)
class Settings:
    buffer_path: Path
    universe_dir: Path
    prices_dir: Path
    cors_origins: list[str]
    api_key: Optional[str]
    forecast_quarter: Optional[Quarter]
    backtest_since: Quarter
    spy_ticker: str
    sec_identity: Optional[str]
    frontend_dist: Optional[Path]

    @classmethod
    def from_env(cls) -> "Settings":
        load_env()
        cors = env_str("FILINGSIGNAL_CORS_ORIGINS", "http://localhost:5173,http://localhost:4173")
        since = _parse_quarter(env_str("FILINGSIGNAL_BACKTEST_SINCE", "2019 Q3")) or (2019, 3)
        fq = env_optional_str("FILINGSIGNAL_FORECAST_QUARTER")
        dist = env_optional_str("FILINGSIGNAL_FRONTEND_DIST")
        return cls(
            buffer_path=env_path("FILINGSIGNAL_BUFFER_PATH", "data/buffer.sqlite"),
            universe_dir=env_path("FILINGSIGNAL_UNIVERSE_DIR", "universe"),
            prices_dir=env_path("FILINGSIGNAL_PRICES_DIR", "data/prices"),
            cors_origins=[o.strip() for o in cors.split(",") if o.strip()],
            api_key=env_optional_str("FILINGSIGNAL_API_KEY"),
            forecast_quarter=_parse_quarter(fq) if fq else None,
            backtest_since=since,
            spy_ticker=env_str("FILINGSIGNAL_SPY_TICKER", "SPY"),
            sec_identity=env_optional_str("FILINGSIGNAL_SEC_IDENTITY"),
            frontend_dist=Path(dist) if dist else None,
        )

    def target_quarter(self) -> Quarter:
        return self.forecast_quarter or quarter_of(today())

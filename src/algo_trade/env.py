"""Load repo-root ``.env`` and read typed configuration values.

Copy ``.env.example`` to ``.env`` at the repository root and edit values there.
Environment variables already set in the shell take precedence over ``.env``
(``python-dotenv`` default ``override=False``).
"""

from __future__ import annotations

import os
from pathlib import Path

_loaded = False


def repo_root() -> Path:
    """Repository root (parent of ``src/``)."""
    return Path(__file__).resolve().parents[2]


def load_env() -> None:
    """Load ``<repo>/.env`` once per process."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    env_path = repo_root() / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


def env_str(key: str, default: str = "") -> str:
    load_env()
    return os.environ.get(key, default).strip()


def env_optional_str(key: str) -> str | None:
    value = env_str(key, "")
    return value or None


def env_int(key: str, default: int) -> int:
    load_env()
    raw = os.environ.get(key)
    if raw is None or not str(raw).strip():
        return default
    return int(raw)


def env_float(key: str, default: float) -> float:
    load_env()
    raw = os.environ.get(key)
    if raw is None or not str(raw).strip():
        return default
    return float(raw)


def env_path(key: str, default: str | Path) -> Path:
    load_env()
    raw = os.environ.get(key)
    if raw is None or not str(raw).strip():
        path = Path(default)
    else:
        path = Path(raw)
    if not path.is_absolute():
        path = repo_root() / path
    return path

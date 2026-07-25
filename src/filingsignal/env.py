"""Config from environment + repo-root ``.env`` (shell exports win).

Salvaged from the predecessor; ``repo_root()`` still resolves to the project
root because ``src/filingsignal/env.py`` sits at the same depth the old
``src/algo_trade/env.py`` did.
"""

from __future__ import annotations

import os
from pathlib import Path

_loaded = False


def repo_root() -> Path:
    # src/filingsignal/env.py -> parents[2] == repo root
    return Path(__file__).resolve().parents[2]


def load_env() -> None:
    """Load ``<repo>/.env`` once. Shell environment takes precedence."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    env_file = repo_root() / ".env"
    if not env_file.is_file():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_file, override=False)


def env_str(key: str, default: str = "") -> str:
    load_env()
    val = os.environ.get(key)
    return val.strip() if val is not None else default


def env_optional_str(key: str) -> str | None:
    load_env()
    val = os.environ.get(key)
    if val is None:
        return None
    val = val.strip()
    return val or None


def env_int(key: str, default: int) -> int:
    raw = env_str(key, "")
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def env_float(key: str, default: float) -> float:
    raw = env_str(key, "")
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def env_path(key: str, default: str) -> Path:
    raw = env_str(key, default)
    p = Path(raw)
    return p if p.is_absolute() else (repo_root() / p)

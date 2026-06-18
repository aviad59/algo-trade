"""Shared paths for tests (repo root, universe data, etc.)."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def universe_dir() -> Path:
    return repo_root() / "backend" / "universe"

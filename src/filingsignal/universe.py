"""Loader for the frozen universe config (``universe/materials.yaml``).

The single source of truth for the material→ETF map, the companies whose
filings feed the signal (tier + per-material perspective), the backtest
benchmarks, and the filing filters. See ARCHITECTURE §3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

from .env import env_path


@dataclass(frozen=True)
class Material:
    id: str
    name: str
    etf: str
    aliases: tuple[str, ...]
    producer_only: bool


@dataclass(frozen=True)
class Company:
    ticker: str
    name: str
    tier: str                       # "us" | "foreign"
    materials: dict[str, str]       # material_id -> "producer" | "consumer"


@dataclass
class Universe:
    materials: dict[str, Material]
    companies: dict[str, Company]
    benchmarks: dict
    filters: dict
    _keywords: dict[str, list[str]] = field(default_factory=dict)

    # -- materials -------------------------------------------------------- #
    def material_ids(self) -> list[str]:
        return list(self.materials.keys())

    def material(self, mid: str) -> Optional[Material]:
        return self.materials.get(mid.lower())

    def etf_for(self, mid: str) -> Optional[str]:
        m = self.material(mid)
        return m.etf if m else None

    def is_producer_only(self, mid: str) -> bool:
        m = self.material(mid)
        return bool(m and m.producer_only)

    def keywords(self) -> dict[str, list[str]]:
        """material_id -> lowercased [name, *aliases] for the keyword gate."""
        if not self._keywords:
            self._keywords = {
                mid: [m.name.lower(), *[a.lower() for a in m.aliases]]
                for mid, m in self.materials.items()
            }
        return self._keywords

    def all_keywords(self) -> set[str]:
        return {kw for kws in self.keywords().values() for kw in kws}

    def match_material(self, label: str) -> Optional[str]:
        """Resolve a free-form label to a canonical material id (name/alias)."""
        low = label.strip().lower()
        if low in self.materials:
            return low
        for mid, kws in self.keywords().items():
            if low in kws:
                return mid
        return None

    # -- companies / forms ------------------------------------------------ #
    def company(self, ticker: str) -> Optional[Company]:
        return self.companies.get(ticker.upper())

    def tickers(self) -> list[str]:
        return list(self.companies.keys())

    def forms_for_tier(self, tier: str) -> list[str]:
        return list(self.filters.get("forms", {}).get(tier, []))

    def forms_for_ticker(self, ticker: str) -> list[str]:
        c = self.company(ticker)
        return self.forms_for_tier(c.tier) if c else []

    # -- filters ---------------------------------------------------------- #
    def event_items_keep(self) -> set[str]:
        return set(self.filters.get("event_items_keep", []))

    def event_items_drop(self) -> set[str]:
        return set(self.filters.get("event_items_drop", []))

    def keyword_gate_enabled(self) -> bool:
        return bool(self.filters.get("keyword_gate", True))


def _default_path() -> Path:
    return env_path("FILINGSIGNAL_UNIVERSE_DIR", "universe") / "materials.yaml"


@lru_cache(maxsize=8)
def _load_cached(path_str: str) -> Universe:
    data = yaml.safe_load(Path(path_str).read_text(encoding="utf-8"))
    materials = {
        m["id"].lower(): Material(
            id=m["id"].lower(),
            name=m["name"],
            etf=m["etf"],
            aliases=tuple(m.get("aliases", [])),
            producer_only=bool(m.get("producer_only", False)),
        )
        for m in data.get("materials", [])
    }
    companies = {
        tk.upper(): Company(
            ticker=tk.upper(),
            name=info.get("name", tk),
            tier=info.get("tier", "us"),
            materials={k.lower(): v for k, v in (info.get("materials") or {}).items()},
        )
        for tk, info in (data.get("companies") or {}).items()
    }
    return Universe(
        materials=materials,
        companies=companies,
        benchmarks=data.get("benchmarks", {}),
        filters=data.get("filters", {}),
    )


def load_universe(path: Optional[Path] = None) -> Universe:
    return _load_cached(str(path or _default_path()))

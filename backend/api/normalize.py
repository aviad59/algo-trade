"""Material id normalization against universe/materials.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _material_lookup(universe_dir: str) -> dict[str, str]:
    path = Path(universe_dir) / "materials.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    lookup: dict[str, str] = {}
    for material in data["materials"]:
        material_id = material["id"]
        lookup[material_id.lower()] = material_id
        lookup[material["name"].lower()] = material_id
        for alias in material.get("aliases", []):
            lookup[str(alias).lower()] = material_id
    return lookup


def normalize_material_id(sector: str, universe_dir: Path) -> str:
    """Map a buffer sector string to canonical material id, or lowercase pass-through."""
    canonical = _material_lookup(str(universe_dir)).get(sector.lower())
    return canonical or sector.lower()


def material_sector_aliases(material_id: str, universe_dir: Path) -> list[str]:
    """Return sector strings that should match a material in buffer queries."""
    path = Path(universe_dir) / "materials.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for material in data["materials"]:
        if material["id"] == material_id:
            aliases = {material["id"], material["name"], *material.get("aliases", [])}
            return sorted(aliases)
    return [material_id]

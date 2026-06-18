"""Universe static file loaders."""

from __future__ import annotations

import json
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def manufacturers(universe_dir: Path) -> dict:
    return load_json(universe_dir / "manufacturers.json")


def materials(universe_dir: Path) -> dict:
    return load_json(universe_dir / "materials.json")


def instruments(material_id: str, universe_dir: Path) -> dict:
    index = load_json(universe_dir / "material-to-index.json")
    buckets = index["indexes"].get(material_id)
    if buckets is None:
        return {
            "contract_version": "1.0",
            "material_id": material_id,
            "buckets": {
                "producers": [],
                "etfs": [],
                "physical": [],
                "futures": [],
                "transporters": [],
                "downstream_consumers": [],
            },
        }
    return {
        "contract_version": "1.0",
        "material_id": material_id,
        "buckets": buckets,
    }

#!/usr/bin/env python3
"""Validate mock/v1 bundle against HLD contract v1.0."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND.parent
MOCK = BACKEND / "mock" / "v1"
UNIVERSE_MATERIALS = BACKEND / "universe" / "materials.json"

REQUIRED_BUCKETS = frozenset(
    {
        "producers",
        "etfs",
        "physical",
        "futures",
        "transporters",
        "downstream_consumers",
    }
)


def load_json(path: Path) -> dict | list:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"OK: {msg}")


def material_ids_from_universe() -> set[str]:
    data = load_json(UNIVERSE_MATERIALS)
    return {m["id"] for m in data["materials"]}


def check_contract_version(data: dict, path: Path) -> None:
    if data.get("contract_version") != "1.0":
        fail(f"{path}: expected contract_version '1.0', got {data.get('contract_version')!r}")


def validate_manifest() -> None:
    path = MOCK / "manifest.json"
    data = load_json(path)
    check_contract_version(data, path)
    if data.get("as_of") is None:
        fail("manifest.json: missing as_of")
    ok("manifest.json")


def validate_health() -> None:
    path = MOCK / "meta" / "health.json"
    data = load_json(path)
    check_contract_version(data, path)
    if data.get("status") != "ok":
        fail("health.json: status must be 'ok'")
    ok("meta/health.json")


def validate_forecast_summary(material_ids: set[str]) -> None:
    path = MOCK / "forecast" / "summary.json"
    data = load_json(path)
    check_contract_version(data, path)
    for item in data.get("top_materials", []):
        if item["material_id"] not in material_ids:
            fail(f"summary: unknown material_id {item['material_id']!r}")
    ok("forecast/summary.json")


def validate_forecast_ranking(material_ids: set[str]) -> None:
    path = MOCK / "forecast" / "ranking.json"
    data = load_json(path)
    check_contract_version(data, path)
    for item in data.get("ranked_materials", []):
        if item["material_id"] not in material_ids:
            fail(f"ranking: unknown material_id {item['material_id']!r}")
    ok("forecast/ranking.json")


def validate_material_forecast(path: Path, material_ids: set[str]) -> None:
    data = load_json(path)
    check_contract_version(data, path)
    mid = data.get("material_id")
    if mid not in material_ids:
        fail(f"{path}: unknown material_id {mid!r}")
    for point in data.get("curve", []):
        for key in ("month", "signal", "forward_AUC"):
            if key not in point:
                fail(f"{path}: curve point missing {key}")
    for action in data.get("actions", []):
        for key in ("date", "action", "rationale"):
            if key not in action:
                fail(f"{path}: action missing {key}")
        if action["action"] not in ("BUY", "SELL"):
            fail(f"{path}: invalid action {action['action']!r}")
    ok(str(path.relative_to(REPO_ROOT)))


def validate_instruments(path: Path, material_ids: set[str]) -> None:
    data = load_json(path)
    check_contract_version(data, path)
    mid = data.get("material_id")
    if mid not in material_ids:
        fail(f"{path}: unknown material_id {mid!r}")
    buckets = data.get("buckets", {})
    if set(buckets.keys()) != REQUIRED_BUCKETS:
        fail(f"{path}: buckets must be exactly {sorted(REQUIRED_BUCKETS)}")
    ok(str(path.relative_to(REPO_ROOT)))


def validate_extractions(material_ids: set[str]) -> list[dict]:
    path = MOCK / "extractions" / "index.json"
    data = load_json(path)
    check_contract_version(data, path)
    items = data.get("items", [])
    if data.get("total") != len(items):
        fail(f"extractions: total {data.get('total')} != len(items) {len(items)}")
    for item in items:
        for key in (
            "id",
            "ticker",
            "cik",
            "filing_type",
            "filing_date",
            "filing_url",
            "dated_effects",
            "flagged_risks",
            "extractor_confidence",
        ):
            if key not in item:
                fail(f"extractions {item.get('id')}: missing {key}")
        for effect in item["dated_effects"]:
            if effect["sector"] not in material_ids:
                fail(
                    f"extractions {item['id']}: sector {effect['sector']!r} "
                    "not in universe/materials.json"
                )
            for key in (
                "direction",
                "magnitude",
                "window_start",
                "window_end",
                "rationale",
                "source_span",
            ):
                if key not in effect:
                    fail(f"extractions {item['id']}: effect missing {key}")
    ok("extractions/index.json")
    return items


def filter_extractions(
    items: list[dict],
    *,
    tickers: set[str] | None = None,
    material: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[dict]:
    result = items
    if tickers:
        result = [i for i in result if i["ticker"] in tickers]
    if from_date:
        result = [i for i in result if i["filing_date"] >= from_date]
    if to_date:
        result = [i for i in result if i["filing_date"] <= to_date]
    if material:
        result = [
            i
            for i in result
            if any(e["sector"] == material for e in i["dated_effects"])
        ]
    return result


def validate_explorer_cases(items: list[dict]) -> None:
    """HLD §7.4 Explorer test cases."""
    # ticker=TSLA, Jan–Jun 2026 → ≥1 lithium extraction
    tsla = filter_extractions(
        items, tickers={"TSLA"}, from_date="2026-01-01", to_date="2026-06-30"
    )
    if not tsla:
        fail("Explorer: TSLA in range expected ≥1 row, got 0")
    if not any(
        e["sector"] == "lithium"
        for row in tsla
        for e in row["dated_effects"]
    ):
        fail("Explorer: TSLA in range expected ≥1 lithium effect")

    # ticker=TSLA,GM → multiple rows, both tickers
    both = filter_extractions(items, tickers={"TSLA", "GM"})
    tickers_seen = {i["ticker"] for i in both}
    if len(both) < 2:
        fail(f"Explorer: TSLA+GM expected ≥2 rows, got {len(both)}")
    if tickers_seen != {"TSLA", "GM"}:
        fail(f"Explorer: TSLA+GM expected both tickers, got {tickers_seen}")

    # material=copper → FCX-related
    copper = filter_extractions(items, material="copper")
    if not any(i["ticker"] == "FCX" for i in copper):
        fail("Explorer: material=copper expected FCX extraction")

    # empty range
    empty = filter_extractions(
        items, from_date="2099-01-01", to_date="2099-12-31"
    )
    if empty:
        fail(f"Explorer: empty range expected 0 rows, got {len(empty)}")

    ok("Explorer filter test cases (HLD §7.4)")


def main() -> None:
    if not MOCK.is_dir():
        fail(f"mock bundle not found: {MOCK}")

    material_ids = material_ids_from_universe()
    ok(f"universe materials loaded ({len(material_ids)} ids)")

    validate_manifest()
    validate_health()
    validate_forecast_summary(material_ids)
    validate_forecast_ranking(material_ids)

    for name in ("lithium", "copper", "electricity"):
        validate_material_forecast(
            MOCK / "forecast" / "materials" / f"{name}.json", material_ids
        )
        validate_instruments(
            MOCK / "universe" / "instruments" / f"{name}.json", material_ids
        )

    items = validate_extractions(material_ids)
    validate_explorer_cases(items)

    mock_materials = MOCK / "universe" / "materials.json"
    if not mock_materials.is_file():
        fail("mock/v1/universe/materials.json missing (task 0.8)")

    print("\nAll mock contract validations passed.")


if __name__ == "__main__":
    main()

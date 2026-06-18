"""Forecast API builders (rule-based ranking until recommender exists)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from algo_trade.buffer import Buffer
from algo_trade.timer import material_forecast

from ..normalize import material_sector_aliases, normalize_material_id
from .universe import materials


def _material_catalog(universe_dir) -> dict[str, dict]:
    return {m["id"]: m for m in materials(universe_dir)["materials"]}


def _distinct_materials_in_buffer(buf: Buffer, since: date, until: date, universe_dir) -> list[str]:
    effects = buf.all_effects(since, until)
    seen: set[str] = set()
    for effect in effects:
        seen.add(normalize_material_id(effect.sector, universe_dir))
    return sorted(seen)


def _rank_material(
    buf: Buffer,
    material_id: str,
    since: date,
    until: date,
    universe_dir,
) -> dict:
    catalog = _material_catalog(universe_dir)
    meta = catalog.get(material_id, {"id": material_id, "name": material_id.title()})
    sectors = material_sector_aliases(material_id, universe_dir)
    effects = buf.all_effects(since, until)
    material_effects = [
        e for e in effects if normalize_material_id(e.sector, universe_dir) == material_id
    ]
    tickers = sorted({e.ticker for e in material_effects})
    positive_signal = sum(
        1.0
        for e in material_effects
        if e.direction.value == "increase" and e.magnitude.value == "large"
    ) + sum(
        0.6
        for e in material_effects
        if e.direction.value == "increase" and e.magnitude.value == "moderate"
    ) + sum(
        0.3
        for e in material_effects
        if e.direction.value == "increase" and e.magnitude.value == "small"
    )
    score = min(1.0, 0.55 * min(positive_signal / 3.0, 1.0) + 0.45 * min(len(tickers) / 5.0, 1.0))
    ticker_text = ", ".join(tickers[:5])
    if len(tickers) > 5:
        ticker_text += ", ..."
    rationale = (
        f"{len(tickers)} companies cite {meta['name']} in filings"
        + (f" ({ticker_text})" if tickers else "")
        + "."
    )
    return {
        "material_id": material_id,
        "name": meta["name"],
        "score": round(score, 2),
        "rationale": rationale,
        "supporting_tickers": tickers,
        "dissenting_evidence": [],
        "_sectors": sectors,
    }


def build_ranking(buf: Buffer, since: date, until: date, as_of: date, universe_dir) -> dict:
    material_ids = _distinct_materials_in_buffer(buf, since, until, universe_dir)
    ranked = [
        _rank_material(buf, material_id, since, until, universe_dir)
        for material_id in material_ids
    ]
    ranked.sort(key=lambda item: item["score"], reverse=True)
    for item in ranked:
        item.pop("_sectors", None)
    return {
        "contract_version": "1.0",
        "as_of": as_of.isoformat(),
        "ranked_materials": ranked,
    }


def build_summary(buf: Buffer, since: date, until: date, as_of: date, universe_dir) -> dict:
    ranking = build_ranking(buf, since, until, as_of, universe_dir)
    top: list[dict] = []
    for rank, item in enumerate(ranking["ranked_materials"][:10], start=1):
        forecast = material_forecast(
            buf,
            item["material_id"],
            since,
            until,
            as_of=as_of,
        )
        latest_action = None
        latest_action_date = None
        if forecast["actions"]:
            last = forecast["actions"][-1]
            latest_action = last["action"]
            latest_action_date = last["date"]
        current_signal = 0.0
        if forecast["curve"]:
            current_signal = float(forecast["curve"][-1]["signal"])
        top.append(
            {
                "material_id": item["material_id"],
                "name": item["name"],
                "rank": rank,
                "score": item["score"],
                "latest_action": latest_action,
                "latest_action_date": latest_action_date,
                "current_signal": current_signal,
                "supporting_ticker_count": len(item["supporting_tickers"]),
            }
        )

    from .universe import manufacturers

    pipeline_run_at = buf.max_extracted_at()
    if pipeline_run_at is None:
        pipeline_run_at = datetime.combine(as_of, datetime.min.time(), tzinfo=timezone.utc)
    elif pipeline_run_at.tzinfo is None:
        pipeline_run_at = pipeline_run_at.replace(tzinfo=timezone.utc)

    return {
        "contract_version": "1.0",
        "as_of": as_of.isoformat(),
        "pipeline_run_at": pipeline_run_at.isoformat().replace("+00:00", "Z"),
        "universe_count": len(manufacturers(universe_dir).get("companies", [])),
        "extractions_count": buf.count_extractions(),
        "top_materials": top,
    }


def build_material_forecast(
    buf: Buffer,
    material_id: str,
    since: date,
    until: date,
    as_of: date,
) -> dict:
    return material_forecast(buf, material_id, since, until, as_of=as_of)

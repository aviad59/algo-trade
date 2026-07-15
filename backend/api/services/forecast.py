"""Forecast API builders — rule-based ranking with optional Agent #2."""

from __future__ import annotations

import json
import logging
import secrets as _secrets
import threading
from datetime import date, datetime, timezone

from algo_trade.buffer import Buffer
from algo_trade.env import env_str
from algo_trade.models import RankedMaterials
from algo_trade.timer import material_forecast

from ..deps import get_settings
from ..normalize import material_sector_aliases, normalize_material_id
from .universe import materials

logger = logging.getLogger(__name__)


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


def _build_rule_based_ranking(
    buf: Buffer, since: date, until: date, as_of: date, universe_dir
) -> dict:
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


def _ranked_materials_to_api(ranked: RankedMaterials) -> dict:
    return {
        "contract_version": "1.0",
        "as_of": ranked.as_of.isoformat(),
        "ranked_materials": [
            {
                "material_id": item.material_id,
                "name": item.name,
                "score": round(item.score, 2),
                "rationale": item.rationale,
                "supporting_tickers": item.supporting_tickers,
                "dissenting_evidence": item.dissenting_evidence,
            }
            for item in ranked.ranked_materials
        ],
    }


def _anthropic_api_key_present() -> bool:
    return bool(env_str("ANTHROPIC_API_KEY", ""))


# The ranking is deterministic until the buffer changes: since/until/as_of come
# from settings and the ranking reads only extractions. In recommender mode a
# fresh compute is a live Agent #2 call (~30s and real tokens per request), so
# results are cached keyed on the buffer's version — (max_extracted_at,
# count_extractions) changes exactly when new extractions land, which is the
# only event that can change the ranking. A recommender failure caches its
# rules fallback under the same key (no retry storm; recovery comes with the
# next pipeline run or an API restart).
_ranking_cache: dict[tuple, dict] = {}
_ranking_lock = threading.Lock()


def demo_token_matches(candidate: str | None) -> bool:
    """True when the request carries the configured demo token.

    Constant-time compare; an unset token means nobody is authorized, and a
    wrong token silently gets the public view (nothing to probe against).
    """
    expected = get_settings().demo_token
    if not expected or not candidate:
        return False
    return _secrets.compare_digest(candidate, expected)


def _buffer_version(buf: Buffer) -> tuple:
    return (buf.path, buf.max_extracted_at(), buf.count_extractions())


def _load_ranking_snapshot(settings, buf: Buffer) -> dict | None:
    """Pre-generated Agent #2 ranking, served with zero runtime LLM spend.

    Only honored when it was generated from the exact buffer being served —
    a stale snapshot (different extraction count/timestamp) is ignored rather
    than silently presenting outdated rationale.
    """
    path = settings.ranking_snapshot
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    version = payload.get("buffer_version")
    max_at = buf.max_extracted_at()
    current = {
        "max_extracted_at": max_at.isoformat() if max_at else None,
        "count_extractions": buf.count_extractions(),
    }
    if version != current:
        logger.warning(
            "ranking snapshot at %s is stale (snapshot %s != buffer %s); ignoring",
            path, version, current,
        )
        return None
    ranking = payload.get("ranking")
    if not isinstance(ranking, dict) or not ranking.get("ranked_materials"):
        return None
    return ranking


def _compute_ranking(
    buf: Buffer,
    since: date,
    until: date,
    as_of: date,
    universe_dir,
    settings,
    *,
    live: bool,
) -> dict:
    use_recommender = live or settings.ranking_mode == "recommender"
    if use_recommender and _anthropic_api_key_present():
        try:
            from algo_trade.recommender import Recommender

            recommender = Recommender(model=settings.recommender_model)
            ranked = recommender.rank(
                buf,
                since,
                until,
                as_of=as_of,
                universe_dir=universe_dir,
            )
            if ranked.ranked_materials:
                return _ranked_materials_to_api(ranked)
        except Exception:
            logger.warning("recommender ranking failed; falling back to rules", exc_info=True)

    return _build_rule_based_ranking(buf, since, until, as_of, universe_dir)


def build_ranking(
    buf: Buffer,
    since: date,
    until: date,
    as_of: date,
    universe_dir,
    *,
    live: bool = False,
) -> dict:
    """Ranking for the window; `live=True` (demo-token holders) forces a real
    Agent #2 call instead of the snapshot/rules public view."""
    settings = get_settings()
    version = _buffer_version(buf)
    key = (version, since, until, as_of, settings.ranking_mode, live)
    # The lock also serializes concurrent first requests, so a cold dashboard
    # load triggers one Agent #2 call, not one per open tab.
    with _ranking_lock:
        cached = _ranking_cache.get(key)
        if cached is not None:
            return cached
        result = None
        if not live:
            result = _load_ranking_snapshot(settings, buf)
        if result is None:
            result = _compute_ranking(
                buf, since, until, as_of, universe_dir, settings, live=live
            )
        # evict entries for older buffer versions; keep sibling variants
        # (public vs live) of the current one
        for stale in [k for k in _ranking_cache if k[0] != version]:
            del _ranking_cache[stale]
        _ranking_cache[key] = result
        return result


def build_summary(
    buf: Buffer,
    since: date,
    until: date,
    as_of: date,
    universe_dir,
    *,
    live: bool = False,
) -> dict:
    ranking = build_ranking(buf, since, until, as_of, universe_dir, live=live)
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

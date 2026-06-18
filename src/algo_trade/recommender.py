"""Agent #2 -- the Recommender.

Reads a date-bounded slice of the buffer (structured extractions, not raw
filings) and ranks materials by narrated demand tailwind. Output is
schema-enforced JSON with post-validation: every ``supporting_ticker``
must appear in the buffer context, and every ``material_id`` must exist
in the universe vocabulary.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

import anthropic
from pydantic import BaseModel, Field, ValidationError

from .buffer import Buffer
from .llm_config import resolve_model
from .models import RankedMaterials, SectorRanking

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You rank materials and sectors for investment research based ONLY on \
structured extraction data from SEC filings.

You receive a JSON digest of extractions: each filing lists \
``dated_effects`` (sector/material signals with direction, magnitude, \
time windows) and ``flagged_risks``. You also receive a \
``material_vocabulary`` of canonical material ids.

For each material you rank, emit:
  - material_id   MUST be one of the ids in material_vocabulary.
  - score         0.0 to 1.0 — strength of narrated tailwind/consensus.
  - rationale     1-3 sentences citing specific patterns in the data.
  - supporting_tickers  Tickers from the extractions that support the
                  ranking. ONLY tickers present in the input extractions.
  - dissenting_evidence   Short strings where filings weaken the thesis.
                  Empty list if none.

RULES:
1. Every supporting_ticker MUST appear in the input extractions. Never invent.
2. Every material_id MUST be from material_vocabulary. Do not invent new ids.
3. If you cannot cite at least one ticker for a material, omit it entirely.
4. Rank by score descending in your output array.
5. Prefer materials cited by multiple companies with aligned increase signals.
6. Do not mention tickers or materials absent from the input.
7. This is research synthesis, not financial advice. Be factual and grounded.

Emit ONLY the JSON object matching the schema. No prose outside JSON.
"""

RANKING_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "ranked_materials": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "material_id": {"type": "string"},
                    "score": {
                        "type": "number",
                        "description": "0.0 to 1.0",
                    },
                    "rationale": {"type": "string"},
                    "supporting_tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "dissenting_evidence": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "material_id",
                    "score",
                    "rationale",
                    "supporting_tickers",
                    "dissenting_evidence",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["ranked_materials"],
    "additionalProperties": False,
}


class _RankingResult(BaseModel):
    ranked_materials: list[dict[str, Any]] = Field(default_factory=list)


def _load_material_catalog(universe_dir: Path) -> dict[str, dict[str, Any]]:
    path = universe_dir / "materials.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {m["id"]: m for m in data["materials"]}


def _normalize_sector(sector: str, catalog: dict[str, dict[str, Any]]) -> str:
    lowered = sector.lower()
    if lowered in catalog:
        return lowered
    for material_id, meta in catalog.items():
        if meta["name"].lower() == lowered:
            return material_id
        for alias in meta.get("aliases", []):
            if str(alias).lower() == lowered:
                return material_id
    return lowered


def build_ranking_context(
    buf: Buffer,
    since: date,
    until: date,
    *,
    universe_dir: Path,
    max_extractions: int = 100,
) -> dict[str, Any]:
    """Build compact JSON digest for the recommender user message."""
    catalog = _load_material_catalog(universe_dir)
    rows, _ = buf.list_extractions(
        from_date=since,
        to_date=until,
        limit=max_extractions,
    )
    buffer_tickers = sorted({row.ticker for row in rows})
    extractions: list[dict[str, Any]] = []
    for row in rows:
        extractions.append(
            {
                "ticker": row.ticker,
                "filing_date": row.filing_date.isoformat(),
                "filing_type": row.filing_type,
                "dated_effects": [
                    {
                        "material_id": _normalize_sector(e.sector, catalog),
                        "direction": e.direction.value,
                        "magnitude": e.magnitude.value,
                        "window_start": e.window_start.isoformat(),
                        "window_end": e.window_end.isoformat(),
                        "rationale": e.rationale,
                    }
                    for e in row.dated_effects
                ],
                "flagged_risks": list(row.flagged_risks),
            }
        )

    vocabulary = [
        {
            "id": m["id"],
            "name": m["name"],
            "aliases": m.get("aliases", []),
        }
        for m in catalog.values()
    ]

    return {
        "as_of": until.isoformat(),
        "window": {"since": since.isoformat(), "until": until.isoformat()},
        "buffer_tickers": buffer_tickers,
        "material_vocabulary": vocabulary,
        "extractions": extractions,
    }


class Recommender:
    """Stateful wrapper around the Anthropic client for Agent #2."""

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: Optional[str] = None,
        client: Optional[anthropic.Anthropic] = None,
        max_tokens: int | None = None,
        effort: str | None = None,
    ) -> None:
        self._client = client or anthropic.Anthropic(api_key=api_key)
        self._model = resolve_model("recommender", override=model)
        from .env import env_int, env_str

        self._max_tokens = (
            max_tokens
            if max_tokens is not None
            else env_int("ALGO_TRADE_RECOMMENDER_MAX_TOKENS", 8000)
        )
        self._effort = (
            effort if effort is not None else env_str("ALGO_TRADE_RECOMMENDER_EFFORT", "high")
        )

    @property
    def model(self) -> str:
        return self._model

    def rank(
        self,
        buf: Buffer,
        since: date,
        until: date,
        *,
        as_of: date | None = None,
        universe_dir: Path | None = None,
        max_extractions: int | None = None,
    ) -> RankedMaterials:
        """Rank materials from buffer extractions in ``[since, until]``."""
        from .env import env_int

        if max_extractions is None:
            max_extractions = env_int("ALGO_TRADE_RECOMMENDER_MAX_EXTRACTIONS", 100)
        if universe_dir is None:
            from .env import env_path

            universe_dir = env_path("ALGO_TRADE_UNIVERSE_DIR", "backend/universe")

        context = build_ranking_context(
            buf,
            since,
            until,
            universe_dir=universe_dir,
            max_extractions=max_extractions,
        )
        if not context["extractions"]:
            return RankedMaterials(
                as_of=as_of or until,
                ranked_materials=[],
                recommender_model=self._model,
            )

        user_prompt = json.dumps(context, indent=2)
        warnings: list[str] = []

        with self._client.messages.stream(
            model=self._model,
            max_tokens=self._max_tokens,
            thinking={"type": "adaptive"},
            output_config={
                "effort": self._effort,
                "format": {
                    "type": "json_schema",
                    "schema": RANKING_JSON_SCHEMA,
                },
            },
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            final = stream.get_final_message()

        _check_stop_reason(final, warnings)
        text = _first_text_block(final)
        if not text:
            raise RuntimeError(
                f"recommender returned no text; stop_reason={final.stop_reason!r}"
            )

        raw_rankings = _parse_ranking_json(text, warnings=warnings)
        catalog = _load_material_catalog(universe_dir)
        allowed_tickers = set(context["buffer_tickers"])
        validated = _validate_rankings(
            raw_rankings,
            catalog=catalog,
            allowed_tickers=allowed_tickers,
            warnings=warnings,
        )
        validated.sort(key=lambda r: r.score, reverse=True)

        if warnings:
            logger.info("recommender validation warnings: %s", warnings)

        return RankedMaterials(
            as_of=as_of or until,
            ranked_materials=validated,
            recommender_model=self._model,
            recommended_at=datetime.now(timezone.utc),
        )


def _check_stop_reason(final: Any, warnings: list[str]) -> None:
    sr = getattr(final, "stop_reason", None)
    if sr == "refusal":
        details = getattr(final, "stop_details", None)
        reason = getattr(details, "explanation", "") if details else ""
        raise RuntimeError(f"recommender refused (stop_reason=refusal): {reason}")
    if sr == "model_context_window_exceeded":
        raise RuntimeError("buffer digest exceeded the model context window")
    if sr == "max_tokens":
        warnings.append("recommender hit max_tokens; output may be truncated")


def _first_text_block(final: Any) -> str:
    for block in final.content:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""


def _parse_ranking_json(text: str, *, warnings: list[str]) -> list[dict[str, Any]]:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"recommender returned non-JSON output: {exc}") from exc
    items = raw.get("ranked_materials", [])
    if not isinstance(items, list):
        warnings.append("ranked_materials was not a list; coerced to empty")
        return []
    return [item for item in items if isinstance(item, dict)]


def _validate_rankings(
    raw_items: list[dict[str, Any]],
    *,
    catalog: dict[str, dict[str, Any]],
    allowed_tickers: set[str],
    warnings: list[str],
) -> list[SectorRanking]:
    kept: list[SectorRanking] = []
    for i, item in enumerate(raw_items):
        material_id = str(item.get("material_id", "")).lower()
        if material_id not in catalog:
            warnings.append(f"dropped ranked_materials[{i}]: unknown material_id {material_id!r}")
            continue

        tickers_raw = item.get("supporting_tickers", [])
        if not isinstance(tickers_raw, list):
            tickers_raw = []
        tickers = sorted({t for t in tickers_raw if isinstance(t, str) and t in allowed_tickers})
        dropped = set(tickers_raw) - set(tickers) - {t for t in tickers_raw if not isinstance(t, str)}
        if dropped:
            warnings.append(
                f"ranked_materials[{i}] ({material_id}): dropped unknown tickers {sorted(dropped)!r}"
            )
        if not tickers:
            warnings.append(f"dropped ranked_materials[{i}]: no valid supporting_tickers")
            continue

        dissent = item.get("dissenting_evidence", [])
        if not isinstance(dissent, list):
            dissent = []
        dissent = [str(d) for d in dissent if isinstance(d, str) and d.strip()]

        try:
            score = float(item.get("score", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        score = max(0.0, min(1.0, score))

        rationale = str(item.get("rationale", "")).strip()
        if not rationale:
            warnings.append(f"dropped ranked_materials[{i}]: empty rationale")
            continue

        try:
            kept.append(
                SectorRanking(
                    material_id=material_id,
                    name=catalog[material_id]["name"],
                    score=score,
                    rationale=rationale,
                    supporting_tickers=tickers,
                    dissenting_evidence=dissent,
                )
            )
        except ValidationError as exc:
            warnings.append(f"dropped ranked_materials[{i}]: {exc.errors()[0].get('msg')}")

    return kept

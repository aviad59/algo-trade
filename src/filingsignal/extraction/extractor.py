"""Agent #1 — the Extractor. Provider-agnostic (Claude or Kimi), form-specific
prompts, incremental (skip already-analyzed), robust per-effect validation
(bad effects dropped with a warning — nothing silent).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

from ..env import env_int, env_str
from ..llm import LLMClient, StopReason, complete_structured, make_llm_client
from ..models import DatedEffect, ExtractedFiling, FetchedFiling
from ..universe import Universe, load_universe
from .prompts import EXTRACTION_JSON_SCHEMA, build_system_prompt, build_user_prompt

logger = logging.getLogger(__name__)


class _RawExtraction(BaseModel):
    """Permissive shape validated by the LLM backstop; individual effects are
    validated (and dropped if bad) afterward, not all-or-nothing."""

    summary: str = ""
    extractor_confidence: float = 0.0
    dated_effects: list[dict[str, Any]] = Field(default_factory=list)


class Extractor:
    def __init__(
        self,
        *,
        client: Optional[LLMClient] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        universe: Optional[Universe] = None,
        max_tokens: Optional[int] = None,
        effort: Optional[str] = None,
    ) -> None:
        self._client = make_llm_client("extractor", provider=provider, model=model, client=client)
        self._model = self._client.model
        self._uni = universe or load_universe()
        self._vocab = [
            f"{m.name} (id: {m.id}"
            + (f"; aliases: {', '.join(m.aliases)}" if m.aliases else "")
            + ")"
            for m in self._uni.materials.values()
        ]
        self._max_tokens = max_tokens or env_int("FILINGSIGNAL_EXTRACTOR_MAX_TOKENS", 8000)
        self._effort = effort or env_str("FILINGSIGNAL_EXTRACTOR_EFFORT", "high")

    @property
    def model(self) -> str:
        return self._model

    def extract(self, fetched: FetchedFiling) -> ExtractedFiling:
        system = build_system_prompt(fetched.form, self._vocab, items=fetched.items)
        user = build_user_prompt(fetched)

        schema = EXTRACTION_JSON_SCHEMA if self._client.capabilities.native_schema else None
        raw, result = complete_structured(
            self._client,
            system=system,
            user=user,
            schema=schema,
            model_cls=_RawExtraction,
            max_tokens=self._max_tokens,
            effort=self._effort,
        )

        warnings = list(fetched.extraction_warnings)
        if result.stop_reason is StopReason.max_tokens:
            warnings.append("extractor hit max_tokens; output may be truncated")

        effects = self._validate_effects(raw.dated_effects, warnings)
        confidence = max(0.0, min(1.0, float(raw.extractor_confidence or 0.0)))

        return ExtractedFiling(
            ticker=fetched.ticker,
            cik=fetched.cik,
            filing_type=fetched.form,
            filing_date=fetched.filing_date,
            accession_number=fetched.accession_number,
            summary=raw.summary.strip(),
            dated_effects=effects,
            extractor_confidence=confidence,
            extractor_model=self._model,
            extraction_warnings=warnings,
            usage=result.usage,
        )

    def _validate_effects(
        self, raw_effects: list[dict[str, Any]], warnings: list[str]
    ) -> list[DatedEffect]:
        kept: list[DatedEffect] = []
        for i, e in enumerate(raw_effects):
            if not isinstance(e, dict):
                warnings.append(f"dropped effect[{i}]: not an object")
                continue
            mid = self._uni.match_material(str(e.get("material", "")))
            if not mid:
                warnings.append(f"dropped effect[{i}]: unknown material {e.get('material')!r}")
                continue
            candidate = {**e, "material": self._uni.material(mid).name}  # canonical display name
            try:
                kept.append(DatedEffect.model_validate(candidate))
            except ValidationError as exc:
                msg = exc.errors()[0].get("msg", "validation error")
                warnings.append(f"dropped effect[{i}] ({candidate['material']}): {msg}")
        return kept

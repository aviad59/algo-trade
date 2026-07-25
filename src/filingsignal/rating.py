"""Stage 5 — Agent #2, the explainer. Reads the deterministic ranking + the
cited effects and writes a grounded recommendation per material. It NEVER
changes the rank or picks the instrument — it narrates the math. Run offline
during the score job; the prose is stored and served read-only.

Grounding rule: every supporting ticker/quote must come from the effects passed
in; unknown citations are dropped in code.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import BaseModel, Field

from .buffer import EffectRow
from .llm import LLMClient, complete_structured, make_llm_client
from .scorer import MaterialScore

logger = logging.getLogger(__name__)

SYSTEM = """\
You are a research analyst writing a one-paragraph recommendation for ONE
material's miner-equity ETF for an upcoming quarter. You are given a
deterministic score/rank (already decided — do NOT change it) and a list of
cited effects extracted from SEC filings (each with ticker, perspective,
direction, and a verbatim quote).

Write:
  - prose: 2-4 sentences. State the call implied by the rank, then WHY, citing
    specific companies and what they said. Note producer vs consumer support and
    any dissenting (decrease) evidence. Grounded, factual, not financial advice.
  - supporting: the tickers + verbatim quotes you relied on. ONLY from the input.

Rules: cite only tickers present in the input effects; never invent numbers or
companies; quotes must be copied verbatim from the input. Return ONLY JSON with
keys prose, supporting (a list of {ticker, quote}).
"""

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "prose": {"type": "string"},
        "supporting": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"ticker": {"type": "string"}, "quote": {"type": "string"}},
                "required": ["ticker", "quote"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["prose", "supporting"],
    "additionalProperties": False,
}


class _RawRating(BaseModel):
    prose: str = ""
    supporting: list[dict[str, Any]] = Field(default_factory=list)


def _context(score: MaterialScore, effects: list[EffectRow], quarter: str) -> str:
    lines = [
        f"Material: {score.material_name} (ETF {score.etf})",
        f"Quarter: {quarter}   Rank: #{score.rank}   z-score: {score.z:+.2f}",
        f"producer_score={score.producer_score}  consumer_score={score.consumer_score}",
        "",
        "Cited effects:",
    ]
    for e in effects:
        lines.append(
            f"- {e.ticker} [{e.perspective.value}/{e.direction.value}/{e.magnitude.value}] "
            f"{e.window_start}..{e.window_end}: {e.evidence_quote}"
        )
    return "\n".join(lines)


class Rater:
    def __init__(
        self,
        *,
        client: Optional[LLMClient] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self._client = make_llm_client("rating", provider=provider, model=model, client=client)
        self._model = self._client.model

    @property
    def model(self) -> str:
        return self._model

    def rate(self, score: MaterialScore, effects: list[EffectRow], quarter: str) -> dict:
        """Return {prose, supporting:[{ticker,quote}], model}. Empty effects → skip LLM."""
        if not effects:
            return {"prose": "", "supporting": [], "model": self._model}
        allowed = {e.ticker for e in effects}
        schema = _SCHEMA if self._client.capabilities.native_schema else None
        # Generous budget: on thinking models the adaptive-thinking tokens share
        # this cap, so 1200 truncated the JSON. Prose + a few verbatim quotes is
        # small, but leave headroom for thinking.
        raw, _ = complete_structured(
            self._client, system=SYSTEM, user=_context(score, effects, quarter),
            schema=schema, model_cls=_RawRating, max_tokens=6000,
        )
        supporting = [
            {"ticker": s.get("ticker", ""), "quote": s.get("quote", "")}
            for s in raw.supporting
            if isinstance(s, dict) and s.get("ticker") in allowed and s.get("quote")
        ]
        return {"prose": raw.prose.strip(), "supporting": supporting, "model": self._model}

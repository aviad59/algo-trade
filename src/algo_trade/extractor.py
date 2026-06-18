"""Agent #1 -- the Extractor.

Takes a FetchedFiling from the fetcher and uses Claude to extract
time-windowed sector impact signals (`dated_effects`), flagged risks,
and an extraction confidence. The output is strictly structured -- the
Messages API enforces the JSON schema -- and flows downstream to the
buffer, the sector timeline aggregator, and Agent #2 (the recommender).

Design choices (and why):

  - Model defaults to Opus 4.7. This is the API skill's mandatory default
    and the right tier for intelligence-sensitive financial reasoning.
    Pass `model="claude-sonnet-4-6"` to the constructor to downgrade.

  - Adaptive thinking on, effort=high. Reading a filing and grounding
    forward-looking claims in specific source spans is non-trivial.
    Adaptive lets Claude budget its own thinking per filing.

  - Structured outputs via `output_config.format` with a JSON schema.
    Cheaper than tool use here -- one round trip, no agentic loop.

  - System prompt + schema are large and identical across filings, so
    we cache the system prompt with cache_control=ephemeral. Across a
    batch of N filings we pay schema + instructions cost roughly once
    instead of N times.

  - Streaming, because filing inputs are long. .get_final_message()
    gives us the complete response without per-event handling.

  - Conservative: every emitted effect must cite a source_span. Effects
    with bad date order or empty source spans are dropped, with a
    warning recorded on the ExtractedFiling. False negatives beat
    false positives.

  - Stop reasons we handle: `refusal` (raise), `max_tokens` (warn and
    salvage what parses), `model_context_window_exceeded` (raise with
    actionable message). Per the API skill, Claude 4.5+ can emit any
    of these.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import anthropic
from pydantic import BaseModel, Field, ValidationError

from .models import (
    DatedEffect,
    ExtractedFiling,
    FetchedFiling,
)

logger = logging.getLogger(__name__)


from .llm_config import DEFAULT_EXTRACTOR_MODEL, resolve_model

DEFAULT_MODEL = DEFAULT_EXTRACTOR_MODEL


# --------------------------------------------------------------------------- #
# Prompt + schema
# --------------------------------------------------------------------------- #


SYSTEM_PROMPT = """\
You extract forward-looking sector impact signals from SEC EDGAR filings.

A "sector impact signal" is a concrete plan the filing states that will \
INCREASE or DECREASE the company's use, consumption, exposure, or demand \
for a specific sector, material, commodity, or industry vertical, over a \
specific future time window.

For each such plan you find, emit a `dated_effect` with these fields:
  - sector       Concise canonical name for the affected sector or material.
                 Examples: "Lithium", "Hyperscale cloud", "Semiconductor
                 foundries", "Natural gas", "Gold". Avoid prose phrases.
  - direction    Either "increase" or "decrease". No other values.
  - magnitude    Qualitative size: "small", "moderate", or "large". Do not
                 infer dollar amounts -- companies rarely commit to exact
                 figures and we will not invent them.
  - window_start ISO date (YYYY-MM-DD) when the effect begins.
  - window_end   ISO date (YYYY-MM-DD) when the effect ends. Must be on
                 or after window_start.
  - rationale    One sentence (~200 chars max) describing the plan.
  - source_span  Where in the filing this came from. Cite the item /
                 section / page if available, e.g. "Item 7, MD&A, p.34"
                 or "Risk Factors, paragraph beginning 'Our lithium...'".

RULES (these are not optional):

1. EVERY effect MUST cite a source_span. If you cannot point to specific
   text in the filing, DROP the effect.

2. Resolve relative time references against the filing date you are given.
   "Next year" from a 2026-04-30 filing means 2027-01-01 to 2027-12-31.
   "Coming months" means the next 3-6 months. "Q3" without a year means
   the next upcoming Q3 from the filing date.

3. If you cannot bound the time window from the filing, DROP the effect.
   Do not invent dates.

4. Only emit "increase" or "decrease". Plans that maintain status quo
   are not interesting and must be dropped.

5. Prefer fewer high-confidence effects over many speculative ones. If
   a plan is hedged ("we may", "we could", "if conditions are favorable",
   "potentially"), DROP it -- it is not a stated commitment.

6. Also collect `flagged_risks`: short strings the filing explicitly
   identifies as material risks. At most 8 items. One sentence each.

7. Emit `extractor_confidence` in [0, 1] reflecting how well your
   extraction is grounded in the filing's actual stated commitments.

You are reading this filing carefully and conservatively. False negatives
are strictly better than false positives -- downstream code aggregates
many filings, so a missing signal averages out; an invented signal does not.
"""


# Hand-written rather than generated from a pydantic model -- structured
# outputs has a small subset of JSON schema features it accepts, so we
# keep the schema explicit and minimal.
EXTRACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "dated_effects": {
            "type": "array",
            "description": (
                "Time-windowed sector impact signals stated by the filing. "
                "Each must cite a source span. Drop anything you cannot ground."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "sector": {"type": "string"},
                    "direction": {
                        "type": "string",
                        "enum": ["increase", "decrease"],
                    },
                    "magnitude": {
                        "type": "string",
                        "enum": ["small", "moderate", "large"],
                    },
                    "window_start": {"type": "string", "format": "date"},
                    "window_end": {"type": "string", "format": "date"},
                    "rationale": {"type": "string"},
                    "source_span": {"type": "string"},
                },
                "required": [
                    "sector",
                    "direction",
                    "magnitude",
                    "window_start",
                    "window_end",
                    "rationale",
                    "source_span",
                ],
                "additionalProperties": False,
            },
        },
        "flagged_risks": {
            "type": "array",
            "items": {"type": "string"},
            "description": "At most 8 short risk strings the filing explicitly flags as material.",
        },
        "extractor_confidence": {
            "type": "number",
            "description": "Overall grounding of this extraction, between 0 and 1.",
        },
    },
    "required": ["dated_effects", "flagged_risks", "extractor_confidence"],
    "additionalProperties": False,
}


class _ExtractionResult(BaseModel):
    """Just the LLM-emitted fields. We combine these with FetchedFiling
    metadata to build the full ExtractedFiling."""

    dated_effects: list[DatedEffect] = Field(default_factory=list)
    flagged_risks: list[str] = Field(default_factory=list)
    extractor_confidence: float


# --------------------------------------------------------------------------- #
# Extractor
# --------------------------------------------------------------------------- #


class Extractor:
    """Stateful wrapper around the Anthropic client. Construct once per process."""

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: Optional[str] = None,
        client: Optional[anthropic.Anthropic] = None,
        max_tokens: int | None = None,
        effort: str | None = None,
    ) -> None:
        """
        Args:
            model: Claude model ID. Default Opus 4.7. Pass
                `"claude-sonnet-4-6"` to downgrade for cost.
            api_key: Anthropic API key. Falls back to ANTHROPIC_API_KEY
                env var if omitted.
            client: Inject a pre-built client (useful for tests).
                If provided, `api_key` is ignored.
            max_tokens: Output ceiling. 16K is plenty for an extraction
                (typically <2KB of JSON). Bumping it doesn't help unless
                filings are extraordinarily dense.
            effort: Output_config effort level. Default "high" for
                intelligence-sensitive work; drop to "medium" if you
                want lower latency on a clearly-cheaper filing set.
        """
        self._client = client or anthropic.Anthropic(api_key=api_key)
        self._model = resolve_model("extractor", override=model)
        from .env import env_int, env_str

        self._max_tokens = (
            max_tokens
            if max_tokens is not None
            else env_int("ALGO_TRADE_EXTRACTOR_MAX_TOKENS", 16000)
        )
        self._effort = (
            effort if effort is not None else env_str("ALGO_TRADE_EXTRACTOR_EFFORT", "high")
        )

    def extract(self, fetched: FetchedFiling) -> ExtractedFiling:
        """Run Agent #1 on a single fetched filing."""
        user_prompt = _build_user_prompt(fetched)

        with self._client.messages.stream(
            model=self._model,
            max_tokens=self._max_tokens,
            thinking={"type": "adaptive"},
            output_config={
                "effort": self._effort,
                "format": {
                    "type": "json_schema",
                    "schema": EXTRACTION_JSON_SCHEMA,
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

        warnings: list[str] = []
        _check_stop_reason(final, warnings)

        text = _first_text_block(final)
        if not text:
            raise RuntimeError(
                "extractor response contained no text block; "
                f"stop_reason={final.stop_reason!r}"
            )

        result = _parse_extraction(text, warnings=warnings)

        usage = getattr(final, "usage", None)
        cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        cache_write = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
        if cache_read or cache_write:
            logger.info(
                "cache usage: read=%s write=%s (ticker=%s, %s)",
                cache_read,
                cache_write,
                fetched.ticker,
                fetched.accession_number,
            )

        return ExtractedFiling(
            ticker=fetched.ticker,
            cik=fetched.cik,
            filing_type=fetched.form,
            filing_date=fetched.filing_date,
            accession_number=fetched.accession_number,
            dated_effects=result.dated_effects,
            flagged_risks=result.flagged_risks,
            extractor_confidence=result.extractor_confidence,
            extractor_model=self._model,
            extraction_warnings=warnings,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=cache_write,
        )


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #


def _build_user_prompt(fetched: FetchedFiling) -> str:
    """Compose the per-filing user message.

    Includes whichever sections the fetcher managed to extract. The
    filing date is repeated explicitly so the LLM has a clear anchor
    for relative time references.
    """
    header = (
        f"Filed by {fetched.ticker} ({fetched.company_name or 'unknown'}) "
        f"on {fetched.filing_date.isoformat()}.\n"
        f"Filing type: {fetched.form}.\n"
        f"Accession: {fetched.accession_number}.\n"
        f"Treat {fetched.filing_date.isoformat()} as the anchor when "
        f"resolving relative time references in the filing text below.\n"
    )

    parts: list[str] = [header]

    # Conventional order: MD&A first (it's where forward-looking plans
    # usually live), then Risk Factors, then a full-text fallback if the
    # typed extraction failed upstream.
    section_order = [
        ("mda", "MD&A (Item 7)"),
        ("risk_factors", "Risk Factors (Item 1A)"),
        ("full_text", "Full filing text (fallback -- typed extraction was not available)"),
    ]

    for key, label in section_order:
        text = fetched.section(key)
        if not text:
            continue
        parts.append(f"\n--- {label} ---\n{text}")

    if len(parts) == 1:
        raise ValueError(
            f"FetchedFiling for {fetched.ticker} {fetched.accession_number} "
            "has no extractable sections."
        )

    return "".join(parts)


def _check_stop_reason(final: Any, warnings: list[str]) -> None:
    """Translate stop_reason into an exception or a warning.

    Per the API skill, Claude 4.5+ can emit `refusal` and
    `model_context_window_exceeded`. Both are 4.x-only stop reasons we
    must handle, not just `end_turn` / `max_tokens` / `tool_use`.
    """
    sr = getattr(final, "stop_reason", None)

    if sr == "refusal":
        details = getattr(final, "stop_details", None)
        reason = getattr(details, "explanation", "") if details else ""
        raise RuntimeError(
            f"Claude refused to extract this filing (stop_reason=refusal): {reason}"
        )

    if sr == "model_context_window_exceeded":
        raise RuntimeError(
            "filing exceeded the model context window. "
            "The fetcher should be splitting sections or you should "
            "downgrade to a model with a larger context."
        )

    if sr == "max_tokens":
        warnings.append(
            "extractor hit max_tokens -- output may be truncated; "
            "increase Extractor(max_tokens=...) if you see partial JSON parses"
        )


def _first_text_block(final: Any) -> str:
    for block in final.content:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""


def _parse_extraction(text: str, *, warnings: list[str]) -> _ExtractionResult:
    """Parse and validate the model's JSON output.

    If a single effect fails validation (e.g. bad date order), drop just
    that effect and record a warning. If the top-level shape fails, raise
    -- that's an extractor bug or a model regression worth surfacing.
    """
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"extractor returned non-JSON output (schema enforcement should "
            f"have prevented this): {exc}"
        ) from exc

    raw_effects = raw.get("dated_effects", [])
    kept_effects: list[DatedEffect] = []
    for i, e in enumerate(raw_effects):
        try:
            kept_effects.append(DatedEffect.model_validate(e))
        except ValidationError as exc:
            warnings.append(
                f"dropped dated_effects[{i}] (sector={e.get('sector')!r}): "
                f"{exc.errors()[0].get('msg', 'validation error')}"
            )

    flagged = raw.get("flagged_risks", []) or []
    if not isinstance(flagged, list):
        warnings.append("flagged_risks was not a list; coerced to empty")
        flagged = []
    flagged = [str(r) for r in flagged if isinstance(r, str) and r.strip()]

    confidence = raw.get("extractor_confidence", 0.0)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        warnings.append("extractor_confidence not a number; coerced to 0.0")
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    return _ExtractionResult(
        dated_effects=kept_effects,
        flagged_risks=flagged,
        extractor_confidence=confidence,
    )

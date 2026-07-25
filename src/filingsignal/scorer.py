"""Stage 4 — the deterministic scorer (ARCHITECTURE §5).

Turns the buffer's dated effects into a point-in-time cross-sectional z-score
per material per quarter. Pure math, no LLM. The decision date for quarter Q is
the FIRST DAY of Q: only effects whose filing became public on or before that
date are admitted — look-ahead is structurally impossible.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from statistics import pstdev
from typing import Iterable, Optional

from .buffer import EffectRow
from .models import Direction, Magnitude, Perspective
from .universe import Universe

# --------------------------------------------------------------------------- #
# Config (hyperparameters — defaults are starting points, never fit on test)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ScoreConfig:
    magnitude: dict = None                 # small/moderate/large -> weight
    recency_half_life_months: float = 12.0
    breadth_k: float = 2.0
    w_producer: float = 1.0
    w_consumer: float = 1.0

    def __post_init__(self):
        if self.magnitude is None:
            object.__setattr__(
                self, "magnitude",
                {Magnitude.small: 1.0, Magnitude.moderate: 2.0, Magnitude.large: 3.0},
            )

    @property
    def decay_lambda(self) -> float:
        return math.log(2) / self.recency_half_life_months


# --------------------------------------------------------------------------- #
# Quarter helpers
# --------------------------------------------------------------------------- #

Quarter = tuple[int, int]  # (year, q)


def quarter_of(d: date) -> Quarter:
    return d.year, (d.month - 1) // 3 + 1


def quarter_start(qtr: Quarter) -> date:
    y, q = qtr
    return date(y, (q - 1) * 3 + 1, 1)


def quarter_end(qtr: Quarter) -> date:
    nxt = quarter_start(add_quarters(qtr, 1))
    return date.fromordinal(nxt.toordinal() - 1)


def quarter_label(qtr: Quarter) -> str:
    return f"{qtr[0]} Q{qtr[1]}"


def quarter_short(qtr: Quarter) -> str:
    return f"{str(qtr[0])[2:]}Q{qtr[1]}"


def add_quarters(qtr: Quarter, n: int) -> Quarter:
    idx = qtr[0] * 4 + (qtr[1] - 1) + n
    return idx // 4, idx % 4 + 1


def quarters_between(start: Quarter, end: Quarter) -> list[Quarter]:
    out, cur = [], start
    while cur <= end:
        out.append(cur)
        cur = add_quarters(cur, 1)
    return out


def _overlap_fraction(ws: date, we: date, qs: date, qe: date) -> float:
    lo, hi = max(ws, qs), min(we, qe)
    if hi < lo:
        return 0.0
    covered = (hi - lo).days + 1
    span = (qe - qs).days + 1
    return covered / span


def _months_between(a: date, b: date) -> float:
    return max(0.0, (b - a).days / 30.44)


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #


@dataclass
class MaterialScore:
    material_id: str
    material_name: str
    etf: str
    producer_score: float
    consumer_score: Optional[float]   # None for producer-only materials
    combined: float
    z: float
    filings: int
    rank: int


def _contribution(e: EffectRow, qs: date, qe: date, decision: date, cfg: ScoreConfig) -> float:
    sign = 1.0 if e.direction is Direction.increase else -1.0
    mag = cfg.magnitude[e.magnitude]
    recency = math.exp(-cfg.decay_lambda * _months_between(e.filing_date, decision))
    overlap = _overlap_fraction(e.window_start, e.window_end, qs, qe)
    return sign * mag * e.confidence * recency * overlap


def score_quarter(
    effects: Iterable[EffectRow],
    qtr: Quarter,
    uni: Universe,
    cfg: Optional[ScoreConfig] = None,
) -> list[MaterialScore]:
    """Cross-sectional scores for every material for target quarter ``qtr``,
    using only effects known by the first day of the quarter."""
    cfg = cfg or ScoreConfig()
    qs, qe = quarter_start(qtr), quarter_end(qtr)
    decision = qs

    # material_id -> perspective -> {raw: float, tickers: set}
    agg: dict[str, dict[str, dict]] = {
        mid: {"producer": {"raw": 0.0, "tickers": set()},
              "consumer": {"raw": 0.0, "tickers": set()}}
        for mid in uni.material_ids()
    }
    filing_set: dict[str, set] = {mid: set() for mid in uni.material_ids()}

    for e in effects:
        if e.filing_date > decision:
            continue
        mid = uni.match_material(e.material)
        if mid is None or mid not in agg:
            continue
        c = _contribution(e, qs, qe, decision, cfg)
        if c == 0.0:
            continue
        p = e.perspective.value
        agg[mid][p]["raw"] += c
        # breadth counts any contributing company (a decrease signal from many
        # producers must not be zeroed — the gate un-dampens, it doesn't sign).
        agg[mid][p]["tickers"].add(e.ticker)
        filing_set[mid].add(e.accession_number)

    scores: dict[str, dict] = {}
    for mid in uni.material_ids():
        m = uni.material(mid)
        p_raw = agg[mid]["producer"]["raw"]
        c_raw = agg[mid]["consumer"]["raw"]
        n_p = len(agg[mid]["producer"]["tickers"])
        n_c = len(agg[mid]["consumer"]["tickers"])
        p_score = p_raw * (1 - math.exp(-n_p / cfg.breadth_k)) if n_p else 0.0
        c_score = c_raw * (1 - math.exp(-n_c / cfg.breadth_k)) if n_c else 0.0
        if m.producer_only:
            c_out = None
            combined = cfg.w_producer * p_score
        else:
            c_out = c_score
            combined = cfg.w_producer * p_score + cfg.w_consumer * c_score
        scores[mid] = {
            "producer": p_score, "consumer": c_out, "combined": combined,
            "filings": len(filing_set[mid]),
        }

    # cross-sectional standardization
    combos = [scores[mid]["combined"] for mid in uni.material_ids()]
    mean = sum(combos) / len(combos) if combos else 0.0
    sd = pstdev(combos) if len(combos) > 1 else 0.0

    out: list[MaterialScore] = []
    for mid in uni.material_ids():
        m = uni.material(mid)
        s = scores[mid]
        z = (s["combined"] - mean) / sd if sd > 0 else 0.0
        out.append(
            MaterialScore(
                material_id=mid, material_name=m.name, etf=m.etf,
                producer_score=round(s["producer"], 4),
                consumer_score=None if s["consumer"] is None else round(s["consumer"], 4),
                combined=round(s["combined"], 4), z=round(z, 4),
                filings=s["filings"], rank=0,
            )
        )
    out.sort(key=lambda r: r.z, reverse=True)
    for i, r in enumerate(out, 1):
        r.rank = i
    return out


def score_history(
    effects: list[EffectRow],
    quarters: list[Quarter],
    uni: Universe,
    cfg: Optional[ScoreConfig] = None,
) -> dict[Quarter, list[MaterialScore]]:
    """Score each quarter independently (point-in-time). Returns quarter -> rows."""
    return {q: score_quarter(effects, q, uni, cfg) for q in quarters}


def quarter_contributions(
    effects: Iterable[EffectRow],
    qtr: Quarter,
    uni: Universe,
    cfg: Optional[ScoreConfig] = None,
) -> dict[str, list[tuple[EffectRow, float]]]:
    """Explain a quarter's score: for each material, the effects that fed it and
    their signed contribution weight (the same `_contribution` the score uses).
    Point-in-time — only effects public by the quarter's first day. Each
    material's list is sorted by absolute contribution (biggest driver first).

    This surfaces the honest answer to "which filings did we use?": a quarter is
    informed by every effect filed before it began whose window overlaps it,
    recency-decayed — not just the previous quarter's filings.
    """
    cfg = cfg or ScoreConfig()
    qs, qe = quarter_start(qtr), quarter_end(qtr)
    decision = qs
    out: dict[str, list[tuple[EffectRow, float]]] = {mid: [] for mid in uni.material_ids()}
    for e in effects:
        if e.filing_date > decision:
            continue
        mid = uni.match_material(e.material)
        if mid is None or mid not in out:
            continue
        c = _contribution(e, qs, qe, decision, cfg)
        if c == 0.0:
            continue
        out[mid].append((e, c))
    for mid in out:
        out[mid].sort(key=lambda t: abs(t[1]), reverse=True)
    return out

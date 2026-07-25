"""Stage 6 — forecast-quality evaluation (ARCHITECTURE §7A).

Rank-IC of the score vs realized next-quarter returns, a permutation test for
significance (the small-N honesty move), and the producer/consumer/combined
decomposition — the headline experiment the perspective tag enables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .scorer import MaterialScore, Quarter, quarter_label
from .universe import Universe


def _ranks(x: np.ndarray) -> np.ndarray:
    order = np.argsort(x, kind="mergesort")
    r = np.empty(len(x), dtype=float)
    r[order] = np.arange(len(x), dtype=float)
    return r


def _spearman(a: list[float], b: list[float]) -> Optional[float]:
    aa, bb = np.asarray(a, float), np.asarray(b, float)
    if len(aa) < 2 or np.ptp(aa) == 0 or np.ptp(bb) == 0:
        return None
    ra, rb = _ranks(aa), _ranks(bb)
    return float(np.corrcoef(ra, rb)[0, 1])


@dataclass
class EvaluationResult:
    quarters: list[str] = field(default_factory=list)
    rank_ic: list[Optional[float]] = field(default_factory=list)
    mean_ic: float = 0.0
    ic_p_value: float = 1.0
    decomposition: dict = field(default_factory=dict)   # {producer, consumer, combined}
    calibration: list = field(default_factory=list)     # tertile -> mean realized
    n_quarters: int = 0


def _series_for(
    rows: list[MaterialScore],
    returns: dict[str, float],
    key: str,
) -> tuple[list[float], list[float]]:
    """Aligned (score, realized) arrays over materials present in returns."""
    xs, ys = [], []
    for r in rows:
        if r.material_id not in returns or returns[r.material_id] is None:
            continue
        if key == "producer":
            score = r.producer_score
        elif key == "consumer":
            score = r.consumer_score if r.consumer_score is not None else 0.0
        else:
            score = r.z
        xs.append(score)
        ys.append(returns[r.material_id])
    return xs, ys


def evaluate(
    score_hist: dict[Quarter, list[MaterialScore]],
    material_returns: dict[Quarter, dict[str, float]],
    uni: Universe,
    *,
    n_permutations: int = 10000,
    seed: int = 0,
) -> EvaluationResult:
    quarters = sorted(q for q in score_hist if q in material_returns)
    per_q_ic: list[Optional[float]] = []
    # matrices for the permutation test (combined score vs realized, per quarter)
    perm_scores: list[np.ndarray] = []
    perm_rets: list[np.ndarray] = []

    for q in quarters:
        xs, ys = _series_for(score_hist[q], material_returns[q], "combined")
        ic = _spearman(xs, ys)
        per_q_ic.append(ic)
        if ic is not None and len(xs) >= 2:
            perm_scores.append(_ranks(np.asarray(xs, float)))
            perm_rets.append(np.asarray(ys, float))

    valid = [v for v in per_q_ic if v is not None]
    mean_ic = float(np.mean(valid)) if valid else 0.0

    # permutation test: shuffle realized returns within each quarter, recompute
    # the mean IC; p = P(random mean IC >= observed).
    p_value = 1.0
    if perm_scores and n_permutations > 0:
        rng = np.random.default_rng(seed)
        count = 0
        for _ in range(n_permutations):
            ics = []
            for rs, rr in zip(perm_scores, perm_rets):
                shuffled = rng.permutation(rr)
                rb = _ranks(shuffled)
                ics.append(float(np.corrcoef(rs, rb)[0, 1]))
            if np.mean(ics) >= mean_ic:
                count += 1
        p_value = count / n_permutations

    # perspective decomposition
    decomposition = {}
    for key in ("producer", "consumer", "combined"):
        ics = []
        for q in quarters:
            xs, ys = _series_for(score_hist[q], material_returns[q], key)
            ic = _spearman(xs, ys)
            if ic is not None:
                ics.append(ic)
        decomposition[key] = round(float(np.mean(ics)), 4) if ics else 0.0

    # calibration: tertile of z -> mean realized return (pooled across quarters)
    pooled: list[tuple[float, float]] = []
    for q in quarters:
        for r in score_hist[q]:
            rv = material_returns[q].get(r.material_id)
            if rv is not None:
                pooled.append((r.z, rv))
    calibration = []
    if len(pooled) >= 3:
        pooled.sort(key=lambda t: t[0])
        third = len(pooled) // 3
        buckets = [pooled[:third], pooled[third:2 * third], pooled[2 * third:]]
        labels = ["low z", "mid z", "high z"]
        for lab, b in zip(labels, buckets):
            if b:
                calibration.append({"bucket": lab, "mean_return": round(sum(v for _, v in b) / len(b), 2)})

    return EvaluationResult(
        quarters=[quarter_label(q) for q in quarters],
        rank_ic=[None if v is None else round(v, 4) for v in per_q_ic],
        mean_ic=round(mean_ic, 4),
        ic_p_value=round(p_value, 4),
        decomposition=decomposition,
        calibration=calibration,
        n_quarters=len(quarters),
    )

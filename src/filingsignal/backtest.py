"""Stage 7 — the honest backtest (ARCHITECTURE §7B).

Top-1 quarterly sector rotation vs four baselines (SPY, equal-weight materials,
hindsight-best, random-pick Monte-Carlo), with transaction costs. Point-in-time
throughout: the pick for quarter Q is the top-z material scored using only
filings public by Q's start. Emits the exact shapes the frontend backtest page
consumes.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from .buffer import EffectRow
from .evaluation import EvaluationResult, evaluate
from .prices import PriceSeries, quarterly_return
from .scorer import (
    MaterialScore,
    Quarter,
    ScoreConfig,
    quarter_contributions,
    quarter_end,
    quarter_label,
    quarter_short,
    quarter_start,
    quarters_between,
    score_history,
)
from .universe import Universe


def material_returns(
    prices: dict[str, PriceSeries], uni: Universe, quarters: list[Quarter]
) -> dict[Quarter, dict[str, Optional[float]]]:
    out: dict[Quarter, dict[str, Optional[float]]] = {}
    for q in quarters:
        row: dict[str, Optional[float]] = {}
        for mid in uni.material_ids():
            etf = uni.etf_for(mid)
            ps = prices.get(etf) if etf else None
            row[mid] = quarterly_return(ps, q) if ps else None
        out[q] = row
    return out


def _equity(returns_pct: list[float]) -> list[float]:
    eq, v = [], 100.0
    for r in returns_pct:
        v *= 1 + r / 100.0
        eq.append(v)
    return eq


def _cagr(returns_pct: list[float]) -> float:
    if not returns_pct:
        return 0.0
    final = _equity(returns_pct)[-1] / 100.0
    years = len(returns_pct) / 4.0
    return (final ** (1 / years) - 1) * 100.0 if final > 0 and years > 0 else 0.0


def _sharpe(returns_pct: list[float]) -> float:
    a = np.asarray(returns_pct, float) / 100.0
    return float(a.mean() / a.std() * np.sqrt(4)) if len(a) > 1 and a.std() > 0 else 0.0


def _max_drawdown(returns_pct: list[float]) -> float:
    eq = np.asarray(_equity(returns_pct), float)
    if len(eq) == 0:
        return 0.0
    peak = np.maximum.accumulate(eq)
    return float((eq / peak - 1).min() * 100.0)


def _pct(x: float, sign: bool = True) -> str:
    s = f"{x:+.1f}%" if sign else f"{x:.1f}%"
    return s.replace("-", "−")  # minus sign


def _actual_ranks(pairs: list[tuple[str, Optional[float]]]) -> dict[str, int]:
    """material_id -> realized-return rank (1 = best). Materials with no price
    are unranked (absent from the map)."""
    ranked = sorted(
        [p for p in pairs if p[1] is not None], key=lambda t: t[1], reverse=True
    )
    return {mid: i for i, (mid, _) in enumerate(ranked, 1)}


def _build_quarter_reports(
    effects: list[EffectRow],
    uni: Universe,
    cfg: Optional[ScoreConfig],
    used: list[Quarter],
    picks: list[str],
    strategy: list[float],
    spy_s: list[float],
    eqw: list[float],
    rnd: list[float],
    hind: list[float],
    hist: dict[Quarter, list[MaterialScore]],
    rets: dict[Quarter, dict[str, Optional[float]]],
    ic_by_label: dict[str, Optional[float]],
) -> list[dict]:
    """One self-contained report per backtested quarter: the point-in-time
    prediction, what actually happened, the per-quarter scorecard vs each
    baseline, and the filings that drove the pick. Everything is already
    computed by the backtest — this just packages it per quarter."""
    mids = uni.material_ids()
    reports: list[dict] = []
    for i, q in enumerate(used):
        rows = hist[q]
        pick_mid = picks[i]
        pick_m = uni.material(pick_mid)
        ranks = _actual_ranks([(mid, rets[q][mid]) for mid in mids])

        predicted = [
            {
                "material": r.material_name, "etf": r.etf, "z": r.z,
                "producerScore": r.producer_score, "consumerScore": r.consumer_score,
                "filings": r.filings, "rank": r.rank,
            }
            for r in rows
        ]
        actual = sorted(
            [
                {
                    "material": uni.material(mid).name, "etf": uni.material(mid).etf,
                    "realized": (round(rets[q][mid], 1) if rets[q][mid] is not None else None),
                    "rank": ranks.get(mid),
                }
                for mid in mids
            ],
            key=lambda d: (d["rank"] is None, d["rank"] or 0),
        )

        strat, spy_v, ew, hv, rv = strategy[i], spy_s[i], eqw[i], hind[i], rnd[i]
        scorecard = [
            {"label": "SPY", "benchmark": round(spy_v, 1), "delta": round(strat - spy_v, 1), "beat": strat > spy_v},
            {"label": "Equal-weight", "benchmark": round(ew, 1), "delta": round(strat - ew, 1), "beat": strat > ew},
            {"label": "Random (median)", "benchmark": round(rv, 1), "delta": round(strat - rv, 1), "beat": strat > rv},
            {"label": "Hindsight-best", "benchmark": round(hv, 1), "delta": round(strat - hv, 1), "beat": strat >= hv},
        ]

        contribs = quarter_contributions(effects, q, uni, cfg).get(pick_mid, [])
        evidence = [
            {
                "ticker": e.ticker, "company": e.company_name, "form": e.form,
                "filingDate": e.filing_date.isoformat(), "material": pick_m.name,
                "perspective": e.perspective.value, "direction": e.direction.value,
                "magnitude": e.magnitude.value, "weight": round(w, 3),
                "quote": e.evidence_quote,
            }
            for e, w in contribs[:8]
        ]

        qs, qe = quarter_start(q), quarter_end(q)
        reports.append({
            "quarter": quarter_label(q), "short": quarter_short(q),
            "decisionDate": qs.isoformat(), "windowStart": qs.isoformat(), "windowEnd": qe.isoformat(),
            "predicted": predicted, "actual": actual,
            "pick": {
                "material": pick_m.name, "etf": pick_m.etf,
                "z": next((r.z for r in rows if r.material_id == pick_mid), 0.0),
                "predictedRank": next((r.rank for r in rows if r.material_id == pick_mid), None),
                "realized": (round(rets[q][pick_mid], 1) if rets[q][pick_mid] is not None else None),
                "actualRank": ranks.get(pick_mid),
                "return": round(strat, 1),
            },
            "baselines": {
                "strategy": round(strat, 1), "spy": round(spy_v, 1), "eqweight": round(ew, 1),
                "hindsight": round(hv, 1), "random": round(rv, 1),
            },
            "scorecard": scorecard,
            "rankIC": ic_by_label.get(quarter_label(q)),
            "evidence": evidence,
        })
    return reports


def run_backtest(
    effects: list[EffectRow],
    prices: dict[str, PriceSeries],
    uni: Universe,
    *,
    since: Quarter,
    until: Quarter,
    cfg: Optional[ScoreConfig] = None,
    spy_ticker: str = "SPY",
    cost_bps: float = 10.0,
    mc_runs: int = 2000,
    seed: int = 0,
) -> dict:
    quarters = quarters_between(since, until)
    hist = score_history(effects, quarters, uni, cfg)
    rets = material_returns(prices, uni, quarters)
    spy = prices.get(spy_ticker)
    cost = cost_bps / 100.0

    used: list[Quarter] = []
    strategy, spy_s, eqw, rnd, hind, picks = [], [], [], [], [], []
    for q in quarters:
        avail = {m: rets[q][m] for m in uni.material_ids() if rets[q][m] is not None}
        spy_r = quarterly_return(spy, q) if spy else None
        if len(avail) < 2 or spy_r is None:
            continue
        # top-1 pick: highest-z material whose ETF has a return this quarter
        pick_mid = next((r.material_id for r in hist[q] if r.material_id in avail), None)
        if pick_mid is None:
            continue
        used.append(q)
        vals = list(avail.values())
        strategy.append(avail[pick_mid] - cost)
        spy_s.append(spy_r)
        eqw.append(float(np.mean(vals)))
        rnd.append(float(np.median(vals)))
        hind.append(float(np.max(vals)))
        picks.append(pick_mid)

    if not used:
        return {"available": False, "reason": "no quarters with both scores and prices"}

    # Monte-Carlo null: cumulative return of random pick sequences
    rng = np.random.default_rng(seed)
    mc_final = []
    for _ in range(mc_runs):
        seq = []
        for q in used:
            vals = [rets[q][m] for m in uni.material_ids() if rets[q][m] is not None]
            seq.append(float(rng.choice(vals)) - cost)
        mc_final.append(_equity(seq)[-1])
    strat_final = _equity(strategy)[-1]
    mc_p = float(np.mean(np.asarray(mc_final) >= strat_final))

    # evaluation (rank-IC etc.) over the same window
    ev: EvaluationResult = evaluate(hist, rets, uni, n_permutations=2000, seed=seed)

    hits = sum(1 for s, e in zip(strategy, eqw) if s > e)
    metrics = [
        {"label": "CAGR", "value": _pct(_cagr(strategy)), "note": f"SPY {_pct(_cagr(spy_s))}"},
        {"label": "Sharpe", "value": f"{_sharpe(strategy):.2f}".replace("-", "−"),
         "note": f"SPY {_sharpe(spy_s):.2f}".replace("-", "−")},
        {"label": "Max drawdown", "value": _pct(_max_drawdown(strategy)),
         "note": f"SPY {_pct(_max_drawdown(spy_s))}", "bad": True},
        {"label": "Hit rate", "value": f"{round(100*hits/len(used))}%",
         "note": f"{hits} / {len(used)} vs eq-weight"},
        {"label": "Mean rank-IC", "value": f"{ev.mean_ic:.2f}",
         "note": f"permutation p = {ev.ic_p_value:.2f}"},
        {"label": "Regret vs best", "value": _pct(_cagr(strategy) - _cagr(hind)),
         "note": "gap to hindsight/yr", "bad": True},
    ]

    # last-10 quarter calls
    calls = []
    for q, pick_mid, sret in list(zip(used, picks, strategy))[-10:]:
        m = uni.material(pick_mid)
        calls.append({
            "quarter": quarter_label(q), "pick": m.name, "etf": m.etf,
            "realized": round(rets[q][pick_mid], 1),
            "benchmark": round(float(np.mean([rets[q][x] for x in uni.material_ids() if rets[q][x] is not None])), 1),
        })

    # hit/miss grid: last 12 quarters
    grid_q = used[-12:]
    mats = [uni.material(mid).name for mid in uni.material_ids()]
    hitgrid = []
    grid_picks = []
    for q in grid_q:
        ew = float(np.mean([rets[q][m] for m in uni.material_ids() if rets[q][m] is not None]))
        hitgrid.append([
            1 if (rets[q][mid] is not None and rets[q][mid] > ew) else 0
            for mid in uni.material_ids()
        ])
        pmid = next((r.material_id for r in hist[q] if rets[q][r.material_id] is not None), None)
        grid_picks.append(uni.material_ids().index(pmid) if pmid else 0)

    decomp = [
        {"label": "Producer-only", "ic": ev.decomposition.get("producer", 0.0), "colorVar": "--s1"},
        {"label": "Consumer-only", "ic": ev.decomposition.get("consumer", 0.0), "colorVar": "--s3"},
        {"label": "Combined", "ic": ev.decomposition.get("combined", 0.0), "colorVar": "--accent"},
    ]

    # Per-quarter drill-down reports (prediction vs reality, scorecard, evidence).
    ic_by_label = dict(zip(ev.quarters, ev.rank_ic))
    quarter_reports = _build_quarter_reports(
        effects, uni, cfg, used, picks, strategy, spy_s, eqw, rnd, hind, hist, rets, ic_by_label
    )

    return {
        "available": True,
        "quarters": [quarter_short(q) for q in used],
        "returns": {"strategy": strategy, "spy": spy_s, "eqweight": eqw, "random": rnd, "hindsight": hind},
        "rankIC": ev.rank_ic,
        "decomp": decomp,
        "metrics": metrics,
        "quarterCalls": calls,
        "hitgrid": {"materials": mats, "hits": hitgrid, "picks": grid_picks},
        "quarterReports": quarter_reports,
        "mc_p_value": round(mc_p, 4),
    }

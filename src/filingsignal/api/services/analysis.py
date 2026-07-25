"""Forecast + backtest payloads (frontend shapes), cached on buffer version."""

from __future__ import annotations

import threading
from typing import Optional

from ...backtest import run_backtest
from ...buffer import Buffer
from ...clock import today
from ...evaluation import _spearman
from ...prices import load_csv_prices, partial_quarter_return
from ...scorer import (
    add_quarters,
    quarter_end,
    quarter_label,
    quarter_of,
    quarter_start,
    score_history,
    score_quarter,
)
from ...universe import Universe
from ..config import Settings

_TREND_COLORS = ["--s1", "--s2", "--s3", "--s4"]
_lock = threading.Lock()
_cache: dict = {}


def _version(buf: Buffer) -> tuple:
    return (str(buf.path), str(buf.max_extracted_at()), buf.count_extractions(), buf.ratings_version())


def _rating_payload(buf: Buffer, material: str, quarter: str) -> Optional[dict]:
    """Agent #2's stored recommendation for one material+quarter, in the
    frontend `Rating` shape — or None when that quarter was never rated."""
    r = buf.get_rating(material, quarter=quarter)
    if not r or not r.get("prose"):
        return None
    supp = r.get("supporting")
    items = supp.get("items", []) if isinstance(supp, dict) else (supp or [])
    return {
        "material": r["material"],
        "quarter": r["quarter"],
        "prose": r["prose"],
        "supporting": [s for s in items if isinstance(s, dict) and s.get("quote")],
        "model": r.get("model"),
    }


def _prices_sig(prices_dir) -> tuple:
    """Fingerprint the price CSVs so refetching prices busts the backtest cache."""
    from pathlib import Path
    d = Path(prices_dir)
    if not d.is_dir():
        return (0, 0.0)
    files = sorted(d.glob("*.csv"))
    return (len(files), max((f.stat().st_mtime for f in files), default=0.0))


def forecast_payload(buf: Buffer, uni: Universe, settings: Settings) -> dict:
    effects = buf.effects()
    tq = settings.target_quarter()
    rows = score_quarter(effects, tq, uni)
    materials = [
        {
            "material": r.material_name, "etf": r.etf, "z": r.z,
            "producerScore": r.producer_score, "consumerScore": r.consumer_score,
            "filings": r.filings, "rank": r.rank,
        }
        for r in rows
    ]
    # trend: z per quarter over the last 6 quarters for the top-4 materials
    quarters = [add_quarters(tq, -i) for i in range(5, -1, -1)]
    hist = score_history(effects, quarters, uni)
    top4 = rows[:4]
    trend = []
    for i, r in enumerate(top4):
        values = []
        for q in quarters:
            match = next((s for s in hist[q] if s.material_id == r.material_id), None)
            values.append(match.z if match else 0.0)
        trend.append({"material": r.material_name, "colorVar": _TREND_COLORS[i], "values": values})
    decision = quarter_start(tq)  # the forecast's point-in-time knowledge cutoff
    return {
        "quarter": quarter_label(tq),
        "asOf": today().isoformat(),
        "publishedDate": decision.isoformat(),
        "priorQuarter": quarter_label(add_quarters(tq, -1)),
        "filingsDigested": buf.count_filings_before(decision),
        "materials": materials,
        "trend": trend,
        "tracker": _forecast_tracker(rows, uni, settings, tq),
        "rating": (_rating_payload(buf, rows[0].material_name, quarter_label(tq)) if rows else None),
    }


def _forecast_tracker(rows, uni: Universe, settings: Settings, tq) -> dict:
    """Live report card for the in-progress forecast quarter: the start-of-quarter
    ranking vs quarter-to-date ETF performance, with a provisional rank-IC."""
    asof = today()
    qs, qe = quarter_start(tq), quarter_end(tq)
    if asof < qs:
        return {"available": False, "reason": "quarter has not started"}
    asof_c = min(asof, qe)
    prices = load_csv_prices(settings.prices_dir)
    if not prices:
        return {"available": False, "reason": "no prices"}

    def qtd(mid: str):
        etf = uni.etf_for(mid)
        ps = prices.get(etf) if etf else None
        return partial_quarter_return(ps, tq, asof_c) if ps else None

    qret = {r.material_id: qtd(r.material_id) for r in rows}
    avail = {m: v for m, v in qret.items() if v is not None}
    if not avail:
        return {"available": False, "reason": "no prices for this quarter yet"}

    ranked = sorted(avail.items(), key=lambda kv: kv[1], reverse=True)
    act_rank = {mid: i for i, (mid, _) in enumerate(ranked, 1)}

    predicted = [{"material": r.material_name, "etf": r.etf, "z": r.z, "rank": r.rank} for r in rows]
    actual = sorted(
        [
            {"material": uni.material(mid).name, "etf": uni.material(mid).etf,
             "qtd": (round(qret[mid], 1) if qret[mid] is not None else None),
             "rank": act_rank.get(mid)}
            for mid in uni.material_ids()
        ],
        key=lambda d: (d["rank"] is None, d["rank"] or 0),
    )

    pick = rows[0]
    pick_qtd = qret.get(pick.material_id)
    spy = prices.get(settings.spy_ticker)
    spy_qtd = partial_quarter_return(spy, tq, asof_c) if spy else None
    eqw = sum(avail.values()) / len(avail)

    xs = [r.z for r in rows if r.material_id in avail]
    ys = [avail[r.material_id] for r in rows if r.material_id in avail]
    ic = _spearman(xs, ys)

    scorecard = []
    if pick_qtd is not None and spy_qtd is not None:
        scorecard.append({"label": "SPY", "benchmark": round(spy_qtd, 1),
                          "delta": round(pick_qtd - spy_qtd, 1), "beat": pick_qtd > spy_qtd})
    if pick_qtd is not None:
        scorecard.append({"label": "Equal-weight", "benchmark": round(eqw, 1),
                          "delta": round(pick_qtd - eqw, 1), "beat": pick_qtd > eqw})

    days_total = (qe - qs).days + 1
    days_done = (asof_c - qs).days + 1
    return {
        "available": True,
        "asOf": asof_c.isoformat(),
        "pctElapsed": round(100 * days_done / days_total),
        "predicted": predicted,
        "actual": actual,
        "pick": {
            "material": pick.material_name, "etf": pick.etf, "z": pick.z,
            "predictedRank": pick.rank,
            "qtd": (round(pick_qtd, 1) if pick_qtd is not None else None),
            "actualRank": act_rank.get(pick.material_id),
        },
        "baselines": {
            "spy": (round(spy_qtd, 1) if spy_qtd is not None else None),
            "eqweight": round(eqw, 1),
        },
        "scorecard": scorecard,
        "rankIC": (round(ic, 2) if ic is not None else None),
    }


def backtest_payload(buf: Buffer, uni: Universe, settings: Settings) -> dict:
    prices = load_csv_prices(settings.prices_dir)
    if not prices:
        return {"available": False, "reason": f"no price CSVs in {settings.prices_dir}"}
    effects = buf.effects()
    until = add_quarters(quarter_of(today()), -1)  # last completed quarter
    res = run_backtest(
        effects, prices, uni,
        since=settings.backtest_since, until=until, spy_ticker=settings.spy_ticker,
    )
    # join Agent #2's stored per-quarter recommendation onto each report, so
    # the drill-down shows WHY that quarter's pick was made, as written then
    for qr in res.get("quarterReports") or []:
        qr["rating"] = _rating_payload(buf, qr["pick"]["material"], qr["quarter"])
    return res


def get_forecast(buf: Buffer, uni: Universe, settings: Settings) -> dict:
    # salt on prices + today so the QTD tracker refreshes daily / on refetch
    kind = f"forecast:{_prices_sig(settings.prices_dir)}:{today().isoformat()}"
    return _cached(kind, buf, lambda: forecast_payload(buf, uni, settings))


def get_backtest(buf: Buffer, uni: Universe, settings: Settings) -> dict:
    kind = f"backtest:{_prices_sig(settings.prices_dir)}"
    return _cached(kind, buf, lambda: backtest_payload(buf, uni, settings))


def _cached(kind: str, buf: Buffer, compute) -> dict:
    key = (kind, _version(buf))
    with _lock:
        if key in _cache:
            return _cache[key]
    value = compute()  # compute outside the lock
    with _lock:
        _cache[key] = value
    return value

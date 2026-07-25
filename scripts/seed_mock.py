"""Seed data/buffer.sqlite with mock extractions + synthetic price CSVs so the
API serves a full, coherent dashboard without spending any LLM/EDGAR calls.

    python scripts/seed_mock.py

Current-quarter effects mirror the frontend fixtures (Copper #1 for 2026 Q3);
a light historical loop gives the backtest something to rotate over.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from filingsignal.buffer import Buffer  # noqa: E402
from filingsignal.models import (  # noqa: E402
    DatedEffect, Direction, ExtractedFiling, Magnitude, Perspective,
)
from filingsignal.scorer import (  # noqa: E402
    Quarter, add_quarters, quarter_end, quarter_label, quarter_start, quarters_between,
    score_history,
)
from filingsignal.universe import load_universe  # noqa: E402

BUF = ROOT / "data" / "buffer.sqlite"
PRICES = ROOT / "data" / "prices"
INC, DEC = Direction.increase, Direction.decrease
PRO, CON = Perspective.producer, Perspective.consumer
S, M, L = Magnitude.small, Magnitude.moderate, Magnitude.large
uni = load_universe(ROOT / "universe" / "materials.yaml")


def eff(mat, persp, dirn, mag, ws, we, text, quote):
    return DatedEffect(material=mat, perspective=persp, direction=dirn, magnitude=mag,
                       window_start=ws, window_end=we, rationale=text, evidence_quote=quote,
                       source_span="Item")


def ext(ticker, cik, company, form, filed, effects, conf, summary, warnings=None):
    return ExtractedFiling(
        ticker=ticker, cik=cik, filing_type=form, filing_date=filed,
        accession_number=f"{ticker}-{form}-{filed.isoformat()}",
        summary=summary, dated_effects=effects, extractor_confidence=conf,
        extractor_model="mock-seed", extraction_warnings=warnings or [],
    ), company


Q3 = (2026, 3)
q3s, q3e = quarter_start(Q3), quarter_end(Q3)
q4s, q4e = quarter_start((2026, 4)), quarter_end((2026, 4))

# ---- current-quarter set (mirrors the frontend fixtures) ----
CURRENT = [
    ext("FCX", "0000831259", "Freeport-McMoRan", "8-K", date(2026, 6, 23), [
        eff("Copper", PRO, INC, L, q3s, q3e, "Guides ~750M lbs copper for Q3 2026",
            '"We expect consolidated copper sales of approximately 750 million pounds for the third quarter of 2026."'),
        eff("Gold", PRO, INC, S, q3s, q3e, "Gold by-product guidance",
            '"...including approximately 160 thousand ounces of gold in the third quarter."'),
    ], 0.92, "FCX Q2 2026 earnings (Item 2.02 + 7.01). Raises near-term copper volume guidance and details the multi-year expansion pipeline. Bullish for COPX.",
        ["Earnings-release exhibit is 409K chars; extraction targeted the Outlook / operations narrative."]),
    ext("ETN", "0001551182", "Eaton Corp", "10-Q", date(2026, 5, 30), [
        eff("Copper", CON, INC, L, q3s, q3e, "Grid-infra order intake +31% YoY; backlog into 2H27",
            '"Order intake for grid infrastructure products increased 31% year-over-year, with backlog now extending into the second half of 2027."'),
    ], 0.81, "Eaton Q2 10-Q. Electrical-segment order intake and backlog strengthen materially — a rare dense consumer-side demand signal for copper."),
    ext("SCCO", "0001001838", "Southern Copper", "10-Q", date(2026, 6, 30), [
        eff("Copper", PRO, DEC, M, q3s, q3e, "Chinese construction demand softening",
            '"We are experiencing softening demand in Chinese construction end-markets and expect volume headwinds to persist through fiscal 2026."'),
    ], 0.85, "Southern Copper Q2 10-Q. Flags softening Chinese construction demand — the main dissenting signal against the copper call."),
    ext("TECK", "0000886986", "Teck Resources", "40-F", date(2026, 6, 12), [
        eff("Copper", PRO, INC, M, q3s, q3e, "QB2 full-throughput slips to early 2027 (supply tightening)",
            '"The QB2 ramp-up schedule has been extended by two quarters due to water-management remediation, with full throughput now expected in early 2027."'),
    ], 0.87, "Teck annual (40-F, carries AIF + MD&A). QB2 ramp extended two quarters — near-term supply tightening, bullish for the copper miner basket."),
    ext("CCJ", "0001009001", "Cameco Corp", "6-K", date(2026, 6, 20), [
        eff("Uranium", PRO, INC, M, q3s, q3e, "Contract book extended at higher realized prices",
            '"We continue to add long-term contracts with improving pricing terms as utilities move to secure supply."'),
    ], 0.88, "Cameco interim furnishing (6-K, content ≈ 8-K). Reaffirms production and flags contract-book strengthening at higher realized prices."),
    ext("MP", "0001801368", "MP Materials", "10-Q", date(2026, 6, 26), [
        eff("Rare Earths", PRO, INC, S, q4s, q4e, "Stage-II magnet output ramping",
            '"We expect to continue ramping metal and magnet production through the second half of the year."'),
    ], 0.64, "MP Q2 10-Q. Magnet-facility ramp language present but dates are vague; two effects dropped for unbounded windows.",
        ["2 effects dropped: window could not be bounded to a quarter (\"over the coming years\")."]),
    ext("AEM", "0000002809", "Agnico Eagle Mines", "40-F", date(2026, 5, 8), [
        eff("Gold", PRO, INC, S, q3s, q3e, "Full-year gold guidance reaffirmed",
            '"We reaffirm full-year gold production guidance of 3.4 to 3.6 million ounces at total cash costs consistent with prior guidance."'),
    ], 0.89, "Agnico annual (40-F). Production guidance reaffirmed across the Canadian portfolio; unit costs guided flat."),
    ext("HL", "0000719413", "Hecla Mining", "10-Q", date(2026, 5, 12), [
        eff("Silver", PRO, INC, S, q3s, q3e, "Silver output guided modestly higher",
            '"We expect silver production in the second half to modestly exceed the first half on improved grades at Lucky Friday."'),
    ], 0.83, "Hecla Q2 10-Q. Greens Creek and Lucky Friday output guided modestly higher."),
    ext("NUE", "0000073309", "Nucor Corp", "10-Q", date(2026, 5, 22), [
        eff("Steel", PRO, INC, S, q3s, q3e, "Utilization steady; non-resi construction stable",
            '"We expect steel mill utilization to remain consistent with the prior quarter as non-residential construction activity holds steady."'),
    ], 0.91, "Nucor Q2 10-Q. Sheet-mill utilization guidance flat; stable non-residential construction demand."),
    ext("TSLA", "0001318605", "Tesla Inc", "10-Q", date(2026, 5, 15), [], 0.58,
        "Tesla Q2 10-Q. No dated, quantified material-demand plan found — narrates production/delivery and AI-cost topics. Correctly returned near-empty (not a miss).",
        ["MD&A section isolation fell back to full text; extraction ran on a 152K-char blob (≈10× target). Reviewed: no bounded material-demand effect present."]),
    ext("LMT", "0000936468", "Lockheed Martin", "8-K", date(2026, 4, 18), [
        eff("Rare Earths", CON, INC, M, q3s, q3e, "Defense magnet-supply agreement (less-priced-in event)",
            '"The Company entered into a multi-year agreement to secure domestic rare-earth magnet supply for propulsion and actuation systems."'),
    ], 0.79, "Lockheed event filing (Item 1.01) — a defense magnet-supply agreement, the kind of less-priced-in consumer signal the pipeline prioritizes."),
]

# ---- history for the backtest (2024 Q1 .. 2026 Q2, the last completed quarter) ----
# Each material has a quarterly filer plus an annual filer whose wider window lets
# a single filing inform several quarters — so the evidence panel honestly shows
# inputs from more than just the previous quarter.
HIST_PRODUCERS = {
    "copper":      [("FCX", "0000831259", "Freeport-McMoRan"), ("SCCO", "0001001838", "Southern Copper")],
    "uranium":     [("CCJ", "0001009001", "Cameco Corp"), ("UEC", "0001334933", "Uranium Energy")],
    "gold":        [("NEM", "0001164727", "Newmont"), ("AEM", "0000002809", "Agnico Eagle Mines")],
    "silver":      [("HL", "0000719413", "Hecla Mining"), ("PAAS", "0000771992", "Pan American Silver")],
    "steel":       [("NUE", "0000073309", "Nucor Corp"), ("STLD", "0001022671", "Steel Dynamics")],
    "rare earths": [("MP", "0001801368", "MP Materials")],
}
# annual filers (40-F/10-K): one wide-window filing every four quarters per material
HIST_ANNUAL = {
    "copper": ("TECK", "0000886986", "Teck Resources", "40-F"),
    "uranium": ("CCJ", "0001009001", "Cameco Corp", "40-F"),
    "gold": ("AEM", "0000002809", "Agnico Eagle Mines", "40-F"),
    "silver": ("PAAS", "0000771992", "Pan American Silver", "40-F"),
    "steel": ("RIO", "0000863064", "Rio Tinto plc", "20-F"),
    "rare earths": ("MP", "0001801368", "MP Materials", "10-K"),
}
rng = np.random.default_rng(7)
MATS = list(HIST_PRODUCERS.keys())


def _match_id(mid: str) -> str:
    return uni.match_material(mid) or mid


history: list = []
for q in quarters_between((2024, 1), (2026, 2)):
    ws, we = quarter_start(q), quarter_end(q)
    # quarterly 10-Q filed ~1 quarter before the window opens
    filed_q = date(quarter_start(add_quarters(q, -1)).year, quarter_start(add_quarters(q, -1)).month, 20)
    for mid in MATS:
        strength = rng.random()
        if strength < 0.28:
            continue
        mat_name = uni.material(_match_id(mid)).name
        dirn = INC if rng.random() > 0.3 else DEC
        mag = L if strength > 0.8 else (M if strength > 0.55 else S)
        for tk, cik, name in HIST_PRODUCERS[mid][: 1 + (strength > 0.6)]:
            history.append(ext(tk, cik, name, "10-Q", filed_q, [
                eff(mat_name, PRO, dirn, mag, ws, we, f"{mat_name} outlook {dirn.value}",
                    f'"We expect {mat_name.lower()} production to {dirn.value} into {q[0]} Q{q[1]}."')],
                round(0.6 + 0.3 * strength, 2),
                f"{name} {q[0]} Q{q[1]} 10-Q — {mat_name.lower()} guidance {dirn.value}d."))

    # once a year (Q1 window), lay down an annual filing whose window spans this
    # quarter through the next three — it will contribute (decayed) to all four.
    if q[1] == 1:
        filed_a = date(add_quarters(q, -2)[0], (add_quarters(q, -2)[1] - 1) * 3 + 2, 15)
        aw_end = quarter_end(add_quarters(q, 3))
        for mid in MATS:
            tk, cik, name, form = HIST_ANNUAL[mid]
            mat_name = uni.material(_match_id(mid)).name
            history.append(ext(tk, cik, name, form, filed_a, [
                eff(mat_name, PRO, INC, M, ws, aw_end, f"{mat_name} multi-quarter capital plan",
                    f'"Our {mat_name.lower()} expansion program is expected to lift output progressively through {aw_end.year}."')],
                0.86,
                f"{name} annual ({form}) — {mat_name.lower()} multi-year expansion guidance."))


def seed_buffer() -> None:
    if BUF.exists():
        BUF.unlink()
    BUF.parent.mkdir(parents=True, exist_ok=True)
    n_e = 0
    with Buffer(str(BUF)) as b:
        for e, company in [*history, *CURRENT]:
            b.upsert(e, company_name=company)
            n_e += len(e.dated_effects)
        b.upsert_rating(
            material="Copper", quarter="2026 Q3",
            prose=("Copper ranks #1 for 2026 Q3. Three producers point to near-term supply "
                   "tightening — Freeport's raised Q3 guidance, Teck's QB2 slip, and Southern "
                   "Copper's grade commentary — while Eaton supplies a rare dense consumer signal "
                   "(grid-infrastructure orders +31% YoY). The dissent is Southern Copper's China "
                   "construction softness. Bullish for COPX, the copper-miner basket."),
            supporting={"items": [
                {"ticker": "FCX", "quote": "~750 million pounds for the third quarter of 2026"},
                {"ticker": "ETN", "quote": "Order intake for grid infrastructure products increased 31%"},
                {"ticker": "TECK", "quote": "QB2 ramp-up schedule has been extended by two quarters"},
            ]}, model="mock-seed")
        _seed_quarter_ratings(b)
    print(f"buffer: {len(history) + len(CURRENT)} filings, {n_e} effects -> {BUF}")


def _seed_quarter_ratings(b: Buffer) -> None:
    """One mock Agent #2 recommendation per backtest quarter for that quarter's
    top-ranked material, built only from effects public before the quarter —
    so the Backtest drill-down shows WHY each pick was made."""
    effects = b.effects()
    qs_list = quarters_between((2024, 1), (2026, 2))
    hist = score_history(effects, qs_list, uni)
    n = 0
    for q in qs_list:
        rows = hist.get(q) or []
        if not rows:
            continue
        top = rows[0]
        supp = sorted(
            (e for e in effects
             if uni.match_material(e.material) == top.material_id and e.filing_date <= quarter_start(q)),
            key=lambda e: e.filing_date, reverse=True,
        )
        if not supp:
            continue
        tks = list(dict.fromkeys(e.ticker for e in supp))
        ql = quarter_label(q)
        b.upsert_rating(
            material=top.material_name, quarter=ql,
            prose=(f"{top.material_name} ranks #1 for {ql} at z {top.z:+.2f}, on the strongest "
                   f"weighted support among the six materials from filings public before the quarter "
                   f"began — dated, quoted effects from {', '.join(tks[:3])} drive the score. "
                   f"The call maps to {top.etf}, the {top.material_name.lower()} miner basket."),
            supporting={"items": [
                {"ticker": e.ticker, "quote": e.evidence_quote.strip('"')} for e in supp[:3]
            ]},
            model="mock-seed",
        )
        n += 1
    print(f"ratings: {n} per-quarter mock recommendations (2024 Q1 .. 2026 Q2)")


def seed_prices() -> None:
    """Synthetic price CSVs — a *fallback* only. If prices already exist (e.g.
    real ones fetched via `filingsignal fetch-prices`), leave them untouched so
    the real market data isn't clobbered by a re-seed."""
    PRICES.mkdir(parents=True, exist_ok=True)
    tickers = [uni.etf_for(m) for m in uni.material_ids()] + ["SPY"]
    if all((PRICES / f"{tk}.csv").exists() for tk in tickers):
        print(f"prices: {len(tickers)} CSVs already present -> left as-is "
              f"(delete data/prices or run `filingsignal fetch-prices` to refresh)")
        return
    idx = pd.date_range("2023-07-01", "2026-07-20", freq="W")
    rng2 = np.random.default_rng(11)
    tickers = [uni.etf_for(m) for m in uni.material_ids()] + ["SPY"]
    market = np.cumsum(rng2.normal(0.0015, 0.02, len(idx)))  # shared market factor
    for i, tk in enumerate(tickers):
        beta = 0.6 + 0.25 * (i % 3)
        idio = rng2.normal(0.001 + 0.0006 * i, 0.03, len(idx))
        close = 100 * np.exp(beta * market + np.cumsum(idio))
        pd.DataFrame({"date": idx.date, "close": close}).to_csv(PRICES / f"{tk}.csv", index=False)
    print(f"prices: {len(tickers)} CSVs -> {PRICES}")


if __name__ == "__main__":
    seed_buffer()
    seed_prices()
    print("done.")

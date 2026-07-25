"""``filingsignal`` CLI — fetch / extract / score / backtest / rate / serve.

The buffer is normally populated offline with ``extract``; the same job runs
behind the auth-gated POST /extract for the live demo.
"""

from __future__ import annotations

import argparse
import json
import sys

from .clock import today
from .env import env_optional_str, env_path, env_str


def _uni():
    from .universe import load_universe
    return load_universe(env_path("FILINGSIGNAL_UNIVERSE_DIR", "universe") / "materials.yaml")


def _buffer():
    from .buffer import Buffer
    return Buffer(env_path("FILINGSIGNAL_BUFFER_PATH", "data/buffer.sqlite"))


def _identity(args) -> str:
    ident = args.identity or env_optional_str("FILINGSIGNAL_SEC_IDENTITY")
    if not ident:
        sys.exit("SEC identity required: --identity 'Name you@example.com' or FILINGSIGNAL_SEC_IDENTITY")
    return ident


def cmd_fetch(args) -> None:
    from .fetcher import Fetcher
    f = Fetcher(_identity(args), keywords=_uni().all_keywords())
    for tk in args.tickers:
        for fetched in f.fetch(tk, forms=args.forms or ("10-Q",), limit=args.limit):
            print(json.dumps({
                "ticker": fetched.ticker, "form": fetched.form,
                "filing_date": fetched.filing_date.isoformat(),
                "accession": fetched.accession_number, "items": fetched.items,
                "sections": {k: len(v) for k, v in fetched.sections.items()},
                "warnings": fetched.extraction_warnings,
            }))


def cmd_extract(args) -> None:
    from .extraction import Extractor, should_extract
    from .fetcher import Fetcher
    uni = _uni()
    fetcher = Fetcher(_identity(args), keywords=uni.all_keywords())
    extractor = Extractor(provider=args.provider, model=args.model)
    buf = _buffer()
    total_f = total_e = 0
    for tk in args.tickers:
        forms = args.forms or uni.forms_for_ticker(tk) or ["10-Q", "8-K"]
        for fetched in fetcher.fetch(tk, forms=forms, limit=args.limit):
            if buf.has_extraction(fetched.accession_number, extractor.model):
                print(f"  skip  {tk} {fetched.form} {fetched.accession_number} (already analyzed)")
                continue
            d = should_extract(fetched, uni)
            if not d.keep:
                print(f"  filter {tk} {fetched.form}: {d.reason}")
                continue
            ext = extractor.extract(fetched)
            buf.upsert(ext, company_name=fetched.company_name)
            total_f += 1
            total_e += len(ext.dated_effects)
            print(f"  ok    {tk} {fetched.form}: {len(ext.dated_effects)} effect(s), conf {ext.extractor_confidence:.2f}")
    buf.close()
    print(f"Done. {total_f} filing(s), {total_e} effect(s) -> buffer.")


def cmd_score(args) -> None:
    from .scorer import quarter_of, quarter_label, score_quarter
    uni = _uni()
    buf = _buffer()
    qtr = _parse_q(args.quarter) or quarter_of(today())
    rows = score_quarter(buf.effects(), qtr, uni)
    buf.close()
    print(f"Ranking for {quarter_label(qtr)}:")
    for r in rows:
        cs = "  n/a " if r.consumer_score is None else f"{r.consumer_score:+.2f}"
        print(f"  #{r.rank} {r.material_name:12} z={r.z:+.2f}  prod={r.producer_score:+.2f} cons={cs}  filings={r.filings}  ({r.etf})")


def cmd_backtest(args) -> None:
    from .backtest import run_backtest
    from .prices import load_csv_prices
    from .scorer import add_quarters, quarter_of
    uni = _uni()
    buf = _buffer()
    prices = load_csv_prices(env_path("FILINGSIGNAL_PRICES_DIR", "data/prices"))
    if not prices:
        buf.close()
        sys.exit("no price CSVs found (put <TICKER>.csv in FILINGSIGNAL_PRICES_DIR)")
    since = _parse_q(args.since) or (2019, 3)
    until = _parse_q(args.until) or add_quarters(quarter_of(today()), -1)
    res = run_backtest(buf.effects(), prices, uni, since=since, until=until)
    buf.close()
    if not res.get("available"):
        sys.exit(res.get("reason", "backtest unavailable"))
    print("Backtest:")
    for m in res["metrics"]:
        print(f"  {m['label']:14} {m['value']:>9}   {m['note']}")
    print(f"  {'MC p-value':14} {res['mc_p_value']:>9}   (strategy vs random-pick null)")


def cmd_rate(args) -> None:
    from .rating import Rater
    from .scorer import quarter_label, quarter_of, quarters_between, score_quarter
    uni = _uni()
    buf = _buffer()
    end = _parse_q(args.quarter) or quarter_of(today())
    start = _parse_q(args.since) or end
    rater = Rater(provider=args.provider, model=args.model)
    effects = buf.effects()
    for qtr in quarters_between(start, end):
        ql = quarter_label(qtr)
        rows = score_quarter(effects, qtr, uni)
        for r in rows[: args.top]:
            if not args.force and buf.get_rating(r.material_name, quarter=ql):
                print(f"  skip  {ql} {r.material_name} (already rated)")
                continue
            # point-in-time: Agent #2 only sees effects public before the quarter began
            supp = [e for e in effects if uni.match_material(e.material) == r.material_id and e.filing_date <= _first_day(qtr)]
            result = rater.rate(r, supp, ql)
            if result["prose"]:
                buf.upsert_rating(material=r.material_name, quarter=ql, prose=result["prose"],
                                  supporting={"items": result["supporting"]}, model=result["model"])
                print(f"  rated {ql} {r.material_name}: {result['prose'][:80]}...")
    buf.close()


def cmd_fetch_prices(args) -> None:
    from .prices import load_yfinance_prices
    uni = _uni()
    etfs = [uni.etf_for(m) for m in uni.material_ids() if uni.etf_for(m)]
    tickers = sorted({*etfs, args.spy})
    out_dir = env_path("FILINGSIGNAL_PRICES_DIR", "data/prices")
    end = args.end or today().isoformat()
    print(f"Fetching {len(tickers)} tickers ({', '.join(tickers)}) {args.start}..{end} -> {out_dir}")
    series = load_yfinance_prices(tickers, start=args.start, end=end, save_dir=out_dir)
    for tk in tickers:
        ps = series.get(tk)
        if ps and len(ps):
            lo = ps._s.index.min().date().isoformat()
            hi = ps._s.index.max().date().isoformat()
            print(f"  {tk:5} ok      {len(ps):>4} rows  {lo} .. {hi}")
        else:
            print(f"  {tk:5} MISSING (no data returned)")
    print(f"Done. {sum(1 for tk in tickers if series.get(tk))}/{len(tickers)} cached as real prices.")


def cmd_refresh(args) -> None:
    """Rollover sweep: incrementally digest new filings across the universe.
    Aborts (no spend) if the provider key is missing or invalid."""
    from .extraction import Extractor
    from .fetcher import Fetcher
    from .refresh import provider_key_present, sweep

    ok, info = provider_key_present(args.provider)
    if not ok:
        sys.exit(f"refresh aborted: {info}. Set the key or pass a valid --provider; nothing was fetched.")

    uni = _uni()
    buf = _buffer()
    fetcher = Fetcher(_identity(args), keywords=uni.all_keywords())
    extractor = Extractor(provider=args.provider, model=args.model)
    res = sweep(
        buf=buf, uni=uni, fetcher=fetcher, extractor=extractor,
        tickers=args.tickers or None, forms=args.forms or None, limit=args.limit,
        on_event=lambda kind, tk, msg: print(f"  {kind:7} {tk}: {msg}"),
    )
    buf.close()
    if res.aborted:
        sys.exit(f"refresh aborted: {res.reason}")
    print(f"Refresh done. fetched={res.fetched} extracted={res.extracted} "
          f"skipped={res.skipped} filtered={res.filtered} errors={res.errors} effects={res.effects}")


def cmd_serve(args) -> None:
    from .api.main import run
    run()


def _parse_q(s):
    if not s:
        return None
    try:
        y, q = s.upper().replace("Q", " ").split()
        return int(y), int(q)
    except Exception:  # noqa: BLE001
        return None


def _first_day(qtr):
    from .scorer import quarter_start
    return quarter_start(qtr)


def main() -> None:
    p = argparse.ArgumentParser(prog="filingsignal", description="Materials sector-rotation signal from SEC filings.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp):
        sp.add_argument("--identity", help="SEC contact 'Name you@example.com'")

    f = sub.add_parser("fetch", help="fetch filings, dump JSON (no LLM)")
    f.add_argument("tickers", nargs="+"); f.add_argument("--forms", nargs="*"); f.add_argument("--limit", type=int, default=1); add_common(f); f.set_defaults(func=cmd_fetch)

    e = sub.add_parser("extract", help="fetch -> filter -> Agent #1 -> buffer (incremental)")
    e.add_argument("tickers", nargs="+"); e.add_argument("--forms", nargs="*"); e.add_argument("--limit", type=int, default=2)
    e.add_argument("--provider"); e.add_argument("--model"); add_common(e); e.set_defaults(func=cmd_extract)

    s = sub.add_parser("score", help="print the current/target-quarter ranking")
    s.add_argument("--quarter"); s.set_defaults(func=cmd_score)

    b = sub.add_parser("backtest", help="run the honest backtest from the buffer + price CSVs")
    b.add_argument("--since"); b.add_argument("--until"); b.set_defaults(func=cmd_backtest)

    r = sub.add_parser("rate", help="Agent #2 recommendations per quarter -> buffer (--since backfills history)")
    r.add_argument("--quarter"); r.add_argument("--since", help="backfill every quarter from here through --quarter")
    r.add_argument("--top", type=int, default=3); r.add_argument("--force", action="store_true", help="re-rate quarters that already have a stored rating")
    r.add_argument("--provider"); r.add_argument("--model"); r.set_defaults(func=cmd_rate)

    rf = sub.add_parser("refresh", help="rollover sweep: incrementally digest new filings across the universe")
    rf.add_argument("tickers", nargs="*", help="tickers to sweep (default: whole universe)")
    rf.add_argument("--forms", nargs="*"); rf.add_argument("--limit", type=int, default=2)
    rf.add_argument("--provider"); rf.add_argument("--model"); add_common(rf); rf.set_defaults(func=cmd_refresh)

    fp = sub.add_parser("fetch-prices", help="download real ETF + SPY prices from yfinance -> CSV cache")
    fp.add_argument("--start", default="2019-01-01"); fp.add_argument("--end")
    fp.add_argument("--spy", default="SPY"); fp.set_defaults(func=cmd_fetch_prices)

    sv = sub.add_parser("serve", help="run the FastAPI backend")
    sv.set_defaults(func=cmd_serve)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

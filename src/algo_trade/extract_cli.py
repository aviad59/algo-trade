"""algo-trade-extract -- minimal CLI: fetch → extract → upsert.

Usage::

    algo-trade-extract TICKER [TICKER ...] \\
        --identity "Your Name you@example.com" \\
        --db data/buffer.sqlite \\
        [--form 10-K] \\
        [--limit 1] \\
        [-v]

Environment variables
---------------------
ANTHROPIC_API_KEY   Required by the Extractor (Agent #1).

Examples
--------
Upsert the latest 10-Q for two tickers::

    algo-trade-extract TSLA AAPL \\
        --identity "Jane Doe jane@example.com" \\
        --form 10-Q --limit 1

Use a specific database file::

    algo-trade-extract TSLA \\
        --identity "Jane Doe jane@example.com" \\
        --db /data/prod/buffer.sqlite
"""

from __future__ import annotations

import argparse
import logging
import sys

logger = logging.getLogger(__name__)


def _cli(argv: list[str] | None = None) -> int:  # noqa: C901
    p = argparse.ArgumentParser(
        prog="algo-trade-extract",
        description="Fetch SEC filings, run the extractor, upsert into the buffer.",
    )
    p.add_argument(
        "ticker",
        nargs="+",
        metavar="TICKER",
        help="One or more stock tickers to process (e.g. TSLA AAPL).",
    )
    p.add_argument(
        "--identity",
        required=True,
        metavar="NAME_AND_EMAIL",
        help=(
            'SEC identity string, e.g. "Jane Doe jane@example.com". '
            "Required by edgartools (and the SEC User-Agent policy)."
        ),
    )
    p.add_argument(
        "--db",
        default="data/buffer.sqlite",
        metavar="PATH",
        help="Path to the SQLite buffer file. Default: data/buffer.sqlite",
    )
    p.add_argument(
        "--form",
        nargs="+",
        default=["10-K"],
        metavar="FORM",
        help="SEC form types to fetch. Default: 10-K",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=1,
        metavar="N",
        help="Most recent N filings per form per ticker. Default: 1",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show INFO-level log lines.",
    )
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Lazy imports so help / --version are fast even without dependencies.
    from pathlib import Path

    from .buffer import Buffer
    from .extractor import Extractor
    from .fetcher import Fetcher

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    fetcher = Fetcher(identity=args.identity)
    extractor = Extractor()

    n_filings = 0
    n_effects = 0

    with Buffer(str(db_path)) as buf:
        for ticker in args.ticker:
            try:
                filings = list(
                    fetcher.fetch(ticker=ticker, forms=args.form, limit=args.limit)
                )
            except Exception as exc:
                logger.error("fetch failed for %s: %s", ticker, exc)
                continue

            for fetched in filings:
                try:
                    extracted = extractor.extract(fetched)
                except Exception as exc:
                    logger.error(
                        "extract failed for %s/%s: %s",
                        ticker,
                        fetched.accession_number,
                        exc,
                    )
                    continue

                buf.upsert(extracted, company_name=fetched.company_name)
                n_filings += 1
                n_effects += len(extracted.dated_effects)
                logger.info(
                    "upserted %s/%s: %d effects",
                    ticker,
                    fetched.accession_number,
                    len(extracted.dated_effects),
                )

    print(
        f"Done. Upserted {n_filings} filing(s), {n_effects} dated effect(s) "
        f"into {db_path}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(_cli())

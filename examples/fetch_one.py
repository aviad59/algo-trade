"""Minimal example: fetch NVIDIA's latest 10-K and print section lengths.

Run:
    python examples/fetch_one.py "Jane Doe jane@example.com"

The identity arg is required -- SEC EDGAR refuses requests without a
contact in the User-Agent. Anything containing an email works.

What you should see:
    NVDA 10-K 2025-02-21 0000950170-25-...
      [mda] 132,418 chars
      [risk_factors] 89,002 chars
"""

from __future__ import annotations

import sys

from algo_trade.fetcher import Fetcher


def main() -> int:
    if len(sys.argv) < 2:
        print(
            'usage: python examples/fetch_one.py "Your Name you@example.com"',
            file=sys.stderr,
        )
        return 2

    fetcher = Fetcher(identity=sys.argv[1])
    filings = fetcher.fetch(ticker="NVDA", forms=["10-K"], limit=1)

    if not filings:
        print("no filings returned -- check identity and network", file=sys.stderr)
        return 1

    for f in filings:
        print(f"{f.ticker} {f.form} {f.filing_date} {f.accession_number}")
        for name, text in f.sections.items():
            print(f"  [{name}] {len(text):,} chars")
        for w in f.extraction_warnings:
            print(f"  warning: {w}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

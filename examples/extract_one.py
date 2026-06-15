"""End-to-end: fetch NVIDIA's latest 10-K, run Agent #1, print the effects.

Run:
    ANTHROPIC_API_KEY=sk-... python examples/extract_one.py \\
        "Your Name you@example.com"

The identity arg goes to edgartools (SEC requires a contact in the
User-Agent). ANTHROPIC_API_KEY is read from the environment by the
Anthropic SDK.

What you should see:
    NVDA 10-K 2026-02-21 0000950170-26-...
    confidence: 0.81
    cache: read=0 write=4823     <-- on the first call, the schema +
                                     system prompt are written to cache;
                                     subsequent calls show read>0
    dated_effects:
      Lithium       increase  large     2026-05-01 -> 2026-08-31
        Cell line ramp at Nevada gigafactory scheduled to begin May
        @ Item 7, MD&A, p.34
      ...
    flagged_risks:
      - Export controls to China
      - Foundry concentration
"""

from __future__ import annotations

import logging
import os
import sys

from algo_trade import Extractor, Fetcher


def main() -> int:
    if len(sys.argv) < 2:
        print(
            'usage: python examples/extract_one.py "Your Name you@example.com"',
            file=sys.stderr,
        )
        return 2

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set", file=sys.stderr)
        return 2

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    fetcher = Fetcher(identity=sys.argv[1])
    extractor = Extractor()  # defaults to claude-opus-4-7

    fetched_list = fetcher.fetch(ticker="NVDA", forms=["10-K"], limit=1)
    if not fetched_list:
        print("no filings returned -- check identity / network", file=sys.stderr)
        return 1

    fetched = fetched_list[0]
    print(
        f"\nFetched: {fetched.ticker} {fetched.form} "
        f"{fetched.filing_date} {fetched.accession_number}"
    )
    for name, text in fetched.sections.items():
        print(f"  [{name}] {len(text):,} chars")

    print("\nRunning extractor...")
    result = extractor.extract(fetched)

    print(f"\n{result.ticker} {result.filing_type} "
          f"{result.filing_date} {result.accession_number}")
    print(f"confidence: {result.extractor_confidence:.2f}")
    print(
        f"cache: read={result.cache_read_input_tokens} "
        f"write={result.cache_creation_input_tokens}"
    )

    print("\ndated_effects:")
    if not result.dated_effects:
        print("  (none)")
    for e in result.dated_effects:
        print(
            f"  {e.sector:<28} {e.direction.value:<9} {e.magnitude.value:<9} "
            f"{e.window_start} -> {e.window_end}"
        )
        print(f"    {e.rationale}")
        print(f"    @ {e.source_span}")

    print("\nflagged_risks:")
    for r in result.flagged_risks:
        print(f"  - {r}")

    if result.extraction_warnings:
        print("\nwarnings:")
        for w in result.extraction_warnings:
            print(f"  - {w}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

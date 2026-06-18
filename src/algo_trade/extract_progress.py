"""Progress reporting for ``algo-trade-extract``."""

from __future__ import annotations

import sys
from typing import TextIO

from tqdm import tqdm


class ExtractProgress:
    """stderr progress bar + human-readable status lines for extract runs."""

    def __init__(
        self,
        *,
        tickers: list[str],
        forms: list[str],
        limit: int,
        db_path: str,
        model: str,
        enabled: bool = True,
        stream: TextIO | None = None,
    ) -> None:
        self._stream = stream if stream is not None else sys.stderr
        self._enabled = enabled
        self._tickers = tickers
        self._forms = forms
        self._limit = limit
        self._estimated = max(1, len(tickers) * len(forms) * limit)
        self._pbar: tqdm | None = None
        self._db_path = db_path
        self._model = model

    def __enter__(self) -> ExtractProgress:
        if self._enabled:
            self._pbar = tqdm(
                total=self._estimated,
                unit="filing",
                desc="Extract",
                file=self._stream,
                dynamic_ncols=True,
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
            )
        self._write(
            f"Plan: {len(self._tickers)} ticker(s) x {len(self._forms)} form(s) "
            f"x limit {self._limit} (up to {self._estimated} filing(s))"
        )
        self._write(f"Buffer: {self._db_path}")
        self._write(f"Extractor model: {self._model}")
        return self

    def __exit__(self, *exc: object) -> None:
        if self._pbar is not None:
            if self._pbar.n < self._pbar.total:
                self._pbar.total = self._pbar.n
                self._pbar.refresh()
            self._pbar.close()
            self._pbar = None

    def _write(self, message: str) -> None:
        if self._pbar is not None:
            tqdm.write(message, file=self._stream)
        else:
            print(message, file=self._stream)

    def start_ticker(self, ticker: str, index: int, total: int) -> None:
        self._set_desc(f"{ticker} fetch")
        self._write(f"[{index}/{total}] {ticker} - fetching SEC filings ({', '.join(self._forms)})...")

    def fetched(self, ticker: str, count: int) -> None:
        if count == 0:
            self._write(f"  {ticker}: no filings found for the requested forms/limit")
        else:
            self._write(f"  {ticker}: found {count} filing(s)")

    def start_extract(
        self,
        ticker: str,
        *,
        form: str,
        filing_date: str,
        accession: str,
    ) -> None:
        self._set_desc(f"{ticker} {form} extract")
        self._write(
            f"  {ticker} {form} filed {filing_date} ({accession}) - running extractor..."
        )

    def upserted(
        self,
        ticker: str,
        *,
        accession: str,
        n_effects: int,
        confidence: float,
    ) -> None:
        self._write(
            f"  ok {ticker}/{accession}: {n_effects} dated effect(s), "
            f"confidence {confidence:.2f}"
        )
        if self._pbar is not None:
            self._pbar.update(1)

    def skip(self, ticker: str, *, phase: str, detail: str) -> None:
        self._write(f"  FAIL {ticker} {phase} failed: {detail}")

    def finish(self, n_filings: int, n_effects: int) -> None:
        self._write(
            f"Done. Upserted {n_filings} filing(s), {n_effects} dated effect(s) "
            f"into {self._db_path}"
        )

    def _set_desc(self, desc: str) -> None:
        if self._pbar is not None:
            self._pbar.set_description(desc, refresh=True)

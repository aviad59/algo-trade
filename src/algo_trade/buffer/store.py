"""Buffer -- Python API over the SQLite store.

The Buffer class is the persistence layer between Agent #1 (the extractor)
and everything downstream: the sector timeline aggregator, the recommender
(Agent #2), and the read-only web app.

Usage::

    from algo_trade.buffer import Buffer
    from algo_trade import Extractor, Fetcher

    buf = Buffer("data/buffer.sqlite")
    extracted = extractor.extract(fetched)
    buf.upsert(extracted, company_name=fetched.company_name)

    rows = buf.effects_for_sector("Lithium", since=date(2026, 1, 1), until=date(2026, 12, 31))

Design decisions live in docs/ARCHITECTURE.md §Stage 3.  Short version:
- stdlib sqlite3 only (no pandas/DuckDB at this stage).
- WAL journal mode so readers don't block the writer.
- upsert is idempotent on (accession_number, extractor_model): re-running
  the same model replaces the previous extraction cleanly.
- Different models produce separate extractions rows so A/B-ing is possible.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from importlib import resources

from ..models import Direction, ExtractedFiling, Magnitude


def _schema_sql() -> str:
    return resources.files(__package__).joinpath("schema.sql").read_text(encoding="utf-8")

__all__ = ["Buffer", "SectorEffectRow"]


@dataclass(frozen=True)
class SectorEffectRow:
    """One dated_effect row joined with its parent filing metadata.

    Returned by :meth:`Buffer.effects_for_sector`.  Provides everything
    the timeline aggregator and the web-app drill-down need without
    exposing raw SQL to callers.
    """

    sector: str
    direction: Direction
    magnitude: Magnitude
    window_start: date
    window_end: date
    rationale: str
    source_span: str

    ticker: str
    cik: str
    filing_type: str
    filing_date: date
    accession_number: str
    company_name: Optional[str]
    extractor_model: str
    extractor_confidence: float


def _row_to_sector_effect(r: sqlite3.Row) -> SectorEffectRow:
    return SectorEffectRow(
        sector=r["sector"],
        direction=Direction(r["direction"]),
        magnitude=Magnitude(r["magnitude"]),
        window_start=date.fromisoformat(r["window_start"]),
        window_end=date.fromisoformat(r["window_end"]),
        rationale=r["rationale"],
        source_span=r["source_span"],
        ticker=r["ticker"],
        cik=r["cik"],
        filing_type=r["filing_type"],
        filing_date=date.fromisoformat(r["filing_date"]),
        accession_number=r["accession_number"],
        company_name=r["company_name"],
        extractor_model=r["extractor_model"],
        extractor_confidence=r["extractor_confidence"],
    )


class Buffer:
    """Persistent store for pipeline output.

    Wraps a SQLite database whose schema is defined in ``schema.sql``.
    Typical usage::

        # As a context manager (auto-closes):
        with Buffer("data/buffer.sqlite") as buf:
            buf.upsert(extracted)

        # Or manage the lifetime manually:
        buf = Buffer("data/buffer.sqlite")
        buf.upsert(extracted)
        buf.close()

    Pass ``":memory:"`` for an in-process ephemeral store (tests, smoke
    checks).
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        """Open (or create) the buffer database at *path*.

        The SQLite schema is applied with ``CREATE TABLE IF NOT EXISTS``, so
        calling this on an existing database is safe and idempotent.

        Args:
            path: Filesystem path to the SQLite file, or the special string
                ``":memory:"`` for an in-process ephemeral database.
        """
        self._path = str(path)
        self._con = sqlite3.connect(self._path)
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA foreign_keys = ON")
        self._con.execute("PRAGMA journal_mode = WAL")
        self._con.executescript(_schema_sql())

    # ---------------------------------------------------------------------- #
    # Context manager support
    # ---------------------------------------------------------------------- #

    def close(self) -> None:
        """Close the underlying database connection."""
        self._con.close()

    def __enter__(self) -> "Buffer":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---------------------------------------------------------------------- #
    # Writes
    # ---------------------------------------------------------------------- #

    def upsert(
        self,
        extracted: ExtractedFiling,
        *,
        company_name: Optional[str] = None,
        fetched_at: Optional[datetime] = None,
    ) -> int:
        """Persist one :class:`~algo_trade.models.ExtractedFiling`.

        The operation is **idempotent** on ``(accession_number,
        extractor_model)``: calling ``upsert`` a second time with the same
        filing and model deletes the previous children (effects, risks,
        warnings) and re-inserts fresh ones.  Calling it with a *different*
        model adds a second extractions row, keeping both versions
        side-by-side (useful for A/B-ing models).

        Args:
            extracted: The filing output from :class:`~algo_trade.Extractor`.
            company_name: Human-readable name from the source
                :class:`~algo_trade.models.FetchedFiling`.  Optional because
                ``ExtractedFiling`` itself doesn't carry it.
            fetched_at: Timestamp to record in ``filings.fetched_at``.
                Defaults to the extraction timestamp.

        Returns:
            The ``extractions.id`` of the inserted (or replaced) row.
        """
        ts = fetched_at or extracted.extracted_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        with self._con:
            # --- filings (INSERT OR REPLACE preserves accession_number PK) ---
            self._con.execute(
                """
                INSERT INTO filings
                    (accession_number, ticker, cik, company_name,
                     filing_type, filing_date, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(accession_number) DO UPDATE SET
                    company_name = excluded.company_name,
                    fetched_at   = excluded.fetched_at
                """,
                (
                    extracted.accession_number,
                    extracted.ticker,
                    extracted.cik,
                    company_name,
                    extracted.filing_type,
                    extracted.filing_date.isoformat(),
                    ts.isoformat(),
                ),
            )

            # --- extractions: delete old row for same (accession, model) ---
            # Cascade removes dated_effects / flagged_risks / warnings.
            self._con.execute(
                """
                DELETE FROM extractions
                WHERE accession_number = ? AND extractor_model = ?
                """,
                (extracted.accession_number, extracted.extractor_model),
            )

            cur = self._con.execute(
                """
                INSERT INTO extractions
                    (accession_number, extractor_model,
                     extractor_confidence, extracted_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    extracted.accession_number,
                    extracted.extractor_model,
                    extracted.extractor_confidence,
                    extracted.extracted_at.isoformat(),
                ),
            )
            extraction_id: int = cur.lastrowid  # type: ignore[assignment]

            # --- dated_effects ---
            self._con.executemany(
                """
                INSERT INTO dated_effects
                    (extraction_id, sector, direction, magnitude,
                     window_start, window_end, rationale, source_span)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        extraction_id,
                        e.sector,
                        e.direction.value,
                        e.magnitude.value,
                        e.window_start.isoformat(),
                        e.window_end.isoformat(),
                        e.rationale,
                        e.source_span,
                    )
                    for e in extracted.dated_effects
                ],
            )

            # --- flagged_risks ---
            self._con.executemany(
                "INSERT INTO flagged_risks (extraction_id, risk) VALUES (?, ?)",
                [(extraction_id, r) for r in extracted.flagged_risks],
            )

            # --- extraction_warnings ---
            self._con.executemany(
                "INSERT INTO extraction_warnings (extraction_id, warning) VALUES (?, ?)",
                [(extraction_id, w) for w in extracted.extraction_warnings],
            )

        return extraction_id

    # ---------------------------------------------------------------------- #
    # Reads
    # ---------------------------------------------------------------------- #

    def effects_for_sector(
        self,
        sector: str,
        since: date,
        until: date,
    ) -> list[SectorEffectRow]:
        """Return all dated effects whose window overlaps ``[since, until]``.

        A window ``[window_start, window_end]`` overlaps ``[since, until]``
        when ``window_start <= until AND window_end >= since`` -- this is the
        standard interval-intersection test.

        Results are ordered by ``window_start`` ascending, then by
        ``filing_date`` ascending.

        Args:
            sector: The canonical sector/material id (e.g. ``"Lithium"``).
            since: Start of the query window (inclusive).
            until: End of the query window (inclusive).

        Returns:
            List of :class:`SectorEffectRow` dataclasses, one per
            ``dated_effects`` row matched.
        """
        rows = self._con.execute(
            """
            SELECT
                de.sector,
                de.direction,
                de.magnitude,
                de.window_start,
                de.window_end,
                de.rationale,
                de.source_span,
                f.ticker,
                f.cik,
                f.filing_type,
                f.filing_date,
                f.accession_number,
                f.company_name,
                x.extractor_model,
                x.extractor_confidence
            FROM   dated_effects de
            JOIN   extractions   x  ON x.id             = de.extraction_id
            JOIN   filings       f  ON f.accession_number = x.accession_number
            WHERE  de.sector       = ?
              AND  de.window_start <= ?
              AND  de.window_end   >= ?
            ORDER  BY de.window_start, f.filing_date
            """,
            (sector, until.isoformat(), since.isoformat()),
        ).fetchall()

        return [_row_to_sector_effect(r) for r in rows]

    def all_effects(
        self,
        since: date,
        until: date,
        *,
        sector: str | None = None,
        extractor_model: str | None = None,
    ) -> list[SectorEffectRow]:
        """Return dated effects whose window overlaps ``[since, until]``.

        Unlike :meth:`effects_for_sector`, *sector* is optional — omit it to
        pull every sector in the window.

        When *extractor_model* is ``None``, only the **latest** extraction per
        ``accession_number`` (by ``extracted_at``) is included so A/B model
        runs are not double-counted.  Pass an explicit model name to pin a
        specific version.
        """
        params: list[str] = [until.isoformat(), since.isoformat()]
        sector_clause = ""
        if sector is not None:
            sector_clause = "AND de.sector = ?"
            params.append(sector)

        if extractor_model is not None:
            extraction_join = """
                JOIN extractions x ON x.id = de.extraction_id
                  AND x.extractor_model = ?
            """
            params.insert(0, extractor_model)
        else:
            extraction_join = """
                JOIN extractions x ON x.id = de.extraction_id
                JOIN (
                    SELECT accession_number, MAX(extracted_at) AS latest_at
                    FROM   extractions
                    GROUP  BY accession_number
                ) latest ON latest.accession_number = x.accession_number
                        AND latest.latest_at = x.extracted_at
            """

        rows = self._con.execute(
            f"""
            SELECT
                de.sector,
                de.direction,
                de.magnitude,
                de.window_start,
                de.window_end,
                de.rationale,
                de.source_span,
                f.ticker,
                f.cik,
                f.filing_type,
                f.filing_date,
                f.accession_number,
                f.company_name,
                x.extractor_model,
                x.extractor_confidence
            FROM   dated_effects de
            {extraction_join}
            JOIN   filings f ON f.accession_number = x.accession_number
            WHERE  de.window_start <= ?
              AND  de.window_end   >= ?
              {sector_clause}
            ORDER  BY de.sector, de.window_start, f.filing_date
            """,
            params,
        ).fetchall()

        return [_row_to_sector_effect(r) for r in rows]

    def filings_citing(self, sector: str) -> list[dict]:
        """Return one record per distinct filing that mentions *sector*.

        Useful for the web-app audit drill-down: "which filings contributed
        to the Lithium curve?"

        Returns:
            List of dicts with keys: ``accession_number``, ``ticker``,
            ``cik``, ``company_name``, ``filing_type``, ``filing_date``,
            ``extractor_model``, ``extractor_confidence``,
            ``effect_count``.
        """
        rows = self._con.execute(
            """
            SELECT
                f.accession_number,
                f.ticker,
                f.cik,
                f.company_name,
                f.filing_type,
                f.filing_date,
                x.extractor_model,
                x.extractor_confidence,
                COUNT(de.id) AS effect_count
            FROM   dated_effects de
            JOIN   extractions   x  ON x.id              = de.extraction_id
            JOIN   filings       f  ON f.accession_number = x.accession_number
            WHERE  de.sector = ?
            GROUP  BY f.accession_number, x.id
            ORDER  BY f.filing_date DESC
            """,
            (sector,),
        ).fetchall()

        return [dict(r) for r in rows]

    # ---------------------------------------------------------------------- #
    # Utilities
    # ---------------------------------------------------------------------- #

    def count_extractions(self) -> int:
        """Return the total number of extraction rows in the buffer.

        Useful as a quick sanity check after a batch run.
        """
        row = self._con.execute("SELECT COUNT(*) FROM extractions").fetchone()
        return int(row[0])

    def __repr__(self) -> str:  # pragma: no cover
        return f"Buffer({self._path!r}, extractions={self.count_extractions()})"

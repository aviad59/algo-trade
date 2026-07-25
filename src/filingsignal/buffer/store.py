"""SQLite buffer — the persistent contract between Agent #1 and everything
downstream. Salvaged wiring from the predecessor (check_same_thread=False for
FastAPI's threadpool, WAL, foreign_keys ON, idempotent upsert on
(accession, model)), extended for the new schema (material/perspective/
evidence_quote/summary + ratings) and with ``has_extraction`` for the
incremental skip.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Optional

from ..models import (
    Direction,
    ExtractedFiling,
    Magnitude,
    Perspective,
)

__all__ = ["Buffer", "EffectRow", "FilingRow"]


def _schema_sql() -> str:
    return resources.files("filingsignal.buffer").joinpath("schema.sql").read_text(
        encoding="utf-8"
    )


def _parse_date(v) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


def _parse_dt(v) -> datetime:
    if isinstance(v, datetime):
        return v
    return datetime.fromisoformat(str(v))


@dataclass(frozen=True)
class EffectRow:
    ticker: str
    company_name: str
    accession_number: str
    form: str
    filing_date: date
    material: str
    perspective: Perspective
    direction: Direction
    magnitude: Magnitude
    window_start: date
    window_end: date
    rationale: str
    evidence_quote: str
    source_span: str
    confidence: float


@dataclass
class FilingRow:
    accession_number: str
    ticker: str
    company_name: str
    form: str
    filing_date: date
    summary: str
    confidence: float
    extractor_model: str
    extracted_at: datetime
    effects: list[EffectRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class Buffer:
    """Connection wrapper. One instance per thread/request (see the predecessor's
    note): FastAPI runs sync deps/endpoints on different threadpool threads, so
    ``check_same_thread=False`` plus one Buffer per request is the pattern."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._path = str(path)
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(self._path, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA foreign_keys = ON")
        self._con.execute("PRAGMA journal_mode = WAL")
        self._con.executescript(_schema_sql())

    # -- lifecycle -------------------------------------------------------- #
    def close(self) -> None:
        self._con.close()

    def __enter__(self) -> "Buffer":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @property
    def path(self) -> str:
        return self._path

    # -- incremental skip ------------------------------------------------- #
    def has_extraction(self, accession_number: str, model: str) -> bool:
        row = self._con.execute(
            "SELECT 1 FROM extractions WHERE accession_number = ? AND extractor_model = ?",
            (accession_number, model),
        ).fetchone()
        return row is not None

    # -- write ------------------------------------------------------------ #
    def upsert(
        self,
        extracted: ExtractedFiling,
        *,
        company_name: Optional[str] = None,
        fetched_at: Optional[datetime] = None,
    ) -> int:
        """Persist one filing + extraction idempotently on (accession, model).
        Re-running the same model deletes and re-inserts its children."""
        fetched_at = fetched_at or datetime.now(timezone.utc)
        with self._con:
            self._con.execute(
                """
                INSERT INTO filings
                    (accession_number, ticker, cik, company_name, form, filing_date, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(accession_number) DO UPDATE SET
                    ticker=excluded.ticker, cik=excluded.cik,
                    company_name=COALESCE(excluded.company_name, filings.company_name),
                    form=excluded.form, filing_date=excluded.filing_date
                """,
                (
                    extracted.accession_number,
                    extracted.ticker,
                    extracted.cik,
                    company_name,
                    extracted.filing_type,
                    extracted.filing_date.isoformat(),
                    fetched_at.isoformat(),
                ),
            )

            # Upsert the extraction row; capture its id.
            self._con.execute(
                """
                INSERT INTO extractions
                    (accession_number, extractor_model, extractor_confidence, summary, extracted_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(accession_number, extractor_model) DO UPDATE SET
                    extractor_confidence=excluded.extractor_confidence,
                    summary=excluded.summary, extracted_at=excluded.extracted_at
                """,
                (
                    extracted.accession_number,
                    extracted.extractor_model,
                    float(extracted.extractor_confidence),
                    extracted.summary,
                    extracted.extracted_at.isoformat(),
                ),
            )
            row = self._con.execute(
                "SELECT id FROM extractions WHERE accession_number = ? AND extractor_model = ?",
                (extracted.accession_number, extracted.extractor_model),
            ).fetchone()
            extraction_id = int(row["id"])

            # Replace children.
            self._con.execute("DELETE FROM dated_effects WHERE extraction_id = ?", (extraction_id,))
            self._con.execute("DELETE FROM extraction_warnings WHERE extraction_id = ?", (extraction_id,))
            self._con.executemany(
                """
                INSERT INTO dated_effects
                    (extraction_id, material, perspective, direction, magnitude,
                     window_start, window_end, rationale, evidence_quote, source_span)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        extraction_id,
                        e.material,
                        e.perspective.value,
                        e.direction.value,
                        e.magnitude.value,
                        e.window_start.isoformat(),
                        e.window_end.isoformat(),
                        e.rationale,
                        e.evidence_quote,
                        e.source_span,
                    )
                    for e in extracted.dated_effects
                ],
            )
            self._con.executemany(
                "INSERT INTO extraction_warnings (extraction_id, warning) VALUES (?, ?)",
                [(extraction_id, w) for w in extracted.extraction_warnings],
            )
        return extraction_id

    # -- read: effects (for the scorer) ----------------------------------- #
    def _latest_clause(self, extractor_model: Optional[str]) -> tuple[str, list]:
        if extractor_model is not None:
            return "x.extractor_model = ?", [extractor_model]
        # dedupe to the latest extraction per accession (any model)
        return "x.id IN (SELECT MAX(id) FROM extractions GROUP BY accession_number)", []

    def effects(
        self,
        *,
        material: Optional[str] = None,
        extractor_model: Optional[str] = None,
    ) -> list[EffectRow]:
        clause, params = self._latest_clause(extractor_model)
        sql = f"""
            SELECT e.material, e.perspective, e.direction, e.magnitude,
                   e.window_start, e.window_end, e.rationale, e.evidence_quote,
                   e.source_span, x.extractor_confidence AS confidence,
                   f.ticker, f.company_name, f.form, f.filing_date, f.accession_number
            FROM dated_effects e
            JOIN extractions x ON x.id = e.extraction_id
            JOIN filings f ON f.accession_number = x.accession_number
            WHERE {clause}
        """
        if material is not None:
            sql += " AND LOWER(e.material) = LOWER(?)"
            params = params + [material]
        rows = self._con.execute(sql, params).fetchall()
        return [
            EffectRow(
                ticker=r["ticker"],
                company_name=r["company_name"] or "",
                accession_number=r["accession_number"],
                form=r["form"],
                filing_date=_parse_date(r["filing_date"]),
                material=r["material"],
                perspective=Perspective(r["perspective"]),
                direction=Direction(r["direction"]),
                magnitude=Magnitude(r["magnitude"]),
                window_start=_parse_date(r["window_start"]),
                window_end=_parse_date(r["window_end"]),
                rationale=r["rationale"],
                evidence_quote=r["evidence_quote"],
                source_span=r["source_span"] or "",
                confidence=float(r["confidence"]),
            )
            for r in rows
        ]

    # -- read: filings (for the /filings endpoint) ------------------------ #
    def list_filings(
        self,
        *,
        tickers: Optional[list[str]] = None,
        materials: Optional[list[str]] = None,
        forms: Optional[list[str]] = None,
        perspectives: Optional[list[str]] = None,
        limit: int = 100,
        offset: int = 0,
        extractor_model: Optional[str] = None,
    ) -> tuple[list[FilingRow], int]:
        clause, params = self._latest_clause(extractor_model)
        where = [clause]
        if tickers:
            where.append("f.ticker IN (%s)" % ",".join("?" * len(tickers)))
            params += [t.upper() for t in tickers]
        if forms:
            where.append("f.form IN (%s)" % ",".join("?" * len(forms)))
            params += forms
        # material/perspective filters are applied post-load against effects.
        base = f"""
            FROM extractions x
            JOIN filings f ON f.accession_number = x.accession_number
            WHERE {" AND ".join(where)}
        """
        total = int(
            self._con.execute(f"SELECT COUNT(*) AS n {base}", params).fetchone()["n"]
        )
        rows = self._con.execute(
            f"""SELECT x.id, x.extractor_model, x.extractor_confidence, x.summary, x.extracted_at,
                       f.accession_number, f.ticker, f.company_name, f.form, f.filing_date
                {base}
                ORDER BY f.filing_date DESC, f.accession_number
                LIMIT ? OFFSET ?""",
            params + [max(1, min(limit, 500)), max(0, offset)],
        ).fetchall()

        out: list[FilingRow] = []
        mats = {m.lower() for m in materials} if materials else None
        persps = {p.lower() for p in perspectives} if perspectives else None
        for r in rows:
            fr = self._load_filing_row(r)
            if mats and not any(e.material.lower() in mats for e in fr.effects):
                continue
            if persps and not any(e.perspective.value in persps for e in fr.effects):
                continue
            out.append(fr)
        return out, total

    def get_filing(
        self, accession_number: str, *, extractor_model: Optional[str] = None
    ) -> Optional[FilingRow]:
        clause, params = self._latest_clause(extractor_model)
        r = self._con.execute(
            f"""SELECT x.id, x.extractor_model, x.extractor_confidence, x.summary, x.extracted_at,
                       f.accession_number, f.ticker, f.company_name, f.form, f.filing_date
                FROM extractions x
                JOIN filings f ON f.accession_number = x.accession_number
                WHERE {clause} AND f.accession_number = ?""",
            params + [accession_number],
        ).fetchone()
        return self._load_filing_row(r) if r else None

    def _load_filing_row(self, r: sqlite3.Row) -> FilingRow:
        extraction_id = int(r["id"])
        effects = [
            EffectRow(
                ticker=r["ticker"],
                company_name=r["company_name"] or "",
                accession_number=r["accession_number"],
                form=r["form"],
                filing_date=_parse_date(r["filing_date"]),
                material=er["material"],
                perspective=Perspective(er["perspective"]),
                direction=Direction(er["direction"]),
                magnitude=Magnitude(er["magnitude"]),
                window_start=_parse_date(er["window_start"]),
                window_end=_parse_date(er["window_end"]),
                rationale=er["rationale"],
                evidence_quote=er["evidence_quote"],
                source_span=er["source_span"] or "",
                confidence=float(r["extractor_confidence"]),
            )
            for er in self._con.execute(
                "SELECT * FROM dated_effects WHERE extraction_id = ? ORDER BY window_start",
                (extraction_id,),
            ).fetchall()
        ]
        warnings = [
            w["warning"]
            for w in self._con.execute(
                "SELECT warning FROM extraction_warnings WHERE extraction_id = ?",
                (extraction_id,),
            ).fetchall()
        ]
        return FilingRow(
            accession_number=r["accession_number"],
            ticker=r["ticker"],
            company_name=r["company_name"] or "",
            form=r["form"],
            filing_date=_parse_date(r["filing_date"]),
            summary=r["summary"] or "",
            confidence=float(r["extractor_confidence"]),
            extractor_model=r["extractor_model"],
            extracted_at=_parse_dt(r["extracted_at"]),
            effects=effects,
            warnings=warnings,
        )

    # -- ratings (Agent #2) ----------------------------------------------- #
    def upsert_rating(
        self, *, material: str, quarter: str, prose: str, supporting: dict, model: str
    ) -> None:
        with self._con:
            self._con.execute(
                """
                INSERT INTO ratings (material, quarter, prose, supporting, model, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(material, quarter) DO UPDATE SET
                    prose=excluded.prose, supporting=excluded.supporting,
                    model=excluded.model, created_at=excluded.created_at
                """,
                (
                    material,
                    quarter,
                    prose,
                    json.dumps(supporting),
                    model,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def get_rating(self, material: str, *, quarter: Optional[str] = None) -> Optional[dict]:
        if quarter:
            r = self._con.execute(
                "SELECT * FROM ratings WHERE LOWER(material)=LOWER(?) AND quarter=?",
                (material, quarter),
            ).fetchone()
        else:
            r = self._con.execute(
                "SELECT * FROM ratings WHERE LOWER(material)=LOWER(?) ORDER BY quarter DESC LIMIT 1",
                (material,),
            ).fetchone()
        if not r:
            return None
        return {
            "material": r["material"],
            "quarter": r["quarter"],
            "prose": r["prose"],
            "supporting": json.loads(r["supporting"] or "{}"),
            "model": r["model"],
        }

    def ratings_version(self) -> tuple:
        """Fingerprint of the ratings table, for cache keys — re-rating a
        quarter must bust payload caches even though extractions are unchanged."""
        r = self._con.execute("SELECT COUNT(*) AS n, MAX(created_at) AS m FROM ratings").fetchone()
        return (int(r["n"]), r["m"] or "")

    # -- meta ------------------------------------------------------------- #
    def max_extracted_at(self) -> Optional[datetime]:
        r = self._con.execute("SELECT MAX(extracted_at) AS m FROM extractions").fetchone()
        return _parse_dt(r["m"]) if r and r["m"] else None

    def count_extractions(self) -> int:
        return int(self._con.execute("SELECT COUNT(*) AS n FROM extractions").fetchone()["n"])

    def count_filings(self) -> int:
        return int(self._con.execute("SELECT COUNT(*) AS n FROM filings").fetchone()["n"])

    def count_filings_before(self, d: date) -> int:
        """Extracted filings public strictly before ``d`` — the point-in-time
        corpus a forecast dated ``d`` was built from."""
        row = self._con.execute(
            "SELECT COUNT(DISTINCT f.accession_number) AS n "
            "FROM filings f JOIN extractions x ON x.accession_number = f.accession_number "
            "WHERE f.filing_date < ?",
            (d.isoformat(),),
        ).fetchone()
        return int(row["n"])

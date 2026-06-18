"""Smoke tests for the buffer schema.

These guard against three classes of regression:
  1. The DDL file going missing or not being shipped as package data.
  2. Syntax errors in the DDL.
  3. The CHECK constraints we documented in ARCHITECTURE.md silently
     getting dropped from the schema.

No actual Buffer class exists yet -- these tests load the raw SQL into
an in-memory SQLite and probe the constraints directly. When the Buffer
class lands, swap these tests for higher-level ones that go through it.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone

import pytest

from algo_trade.buffer import schema_sql


def _fresh_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(schema_sql())
    return con


def _insert_filing_and_extraction(con: sqlite3.Connection) -> int:
    con.execute(
        "INSERT INTO filings "
        "(accession_number, ticker, cik, company_name, filing_type, "
        " filing_date, fetched_at) VALUES (?,?,?,?,?,?,?)",
        (
            "0001628280-26-005001",
            "TSLA",
            "0001318605",
            "TESLA INC",
            "10-Q",
            "2026-04-30",
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    cur = con.execute(
        "INSERT INTO extractions "
        "(accession_number, extractor_model, extractor_confidence, extracted_at) "
        "VALUES (?,?,?,?)",
        (
            "0001628280-26-005001",
            "claude-opus-4-7",
            0.79,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    return cur.lastrowid


# --------------------------------------------------------------------------- #
# Loader + shape
# --------------------------------------------------------------------------- #


def test_schema_sql_returns_nonempty_ddl():
    sql = schema_sql()
    assert "CREATE TABLE" in sql
    assert "dated_effects" in sql


def test_schema_loads_into_fresh_sqlite():
    con = _fresh_db()
    names = {
        row[0]
        for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {
        "filings",
        "extractions",
        "dated_effects",
        "flagged_risks",
        "extraction_warnings",
    }.issubset(names)


# --------------------------------------------------------------------------- #
# Constraints we documented in ARCHITECTURE.md
# --------------------------------------------------------------------------- #


def test_direction_check_constraint_rejects_invalid_value():
    con = _fresh_db()
    ext_id = _insert_filing_and_extraction(con)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO dated_effects "
            "(extraction_id, sector, direction, magnitude, "
            " window_start, window_end, rationale, source_span) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                ext_id,
                "Lithium",
                "stable",          # not in CHECK enum
                "large",
                "2026-05-01",
                "2026-08-31",
                "ramp",
                "Item 2, p.18",
            ),
        )


def test_magnitude_check_constraint_rejects_invalid_value():
    con = _fresh_db()
    ext_id = _insert_filing_and_extraction(con)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO dated_effects "
            "(extraction_id, sector, direction, magnitude, "
            " window_start, window_end, rationale, source_span) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                ext_id,
                "Lithium",
                "increase",
                "huge",            # not in CHECK enum
                "2026-05-01",
                "2026-08-31",
                "ramp",
                "Item 2, p.18",
            ),
        )


def test_window_order_check_constraint_rejects_inverted_dates():
    con = _fresh_db()
    ext_id = _insert_filing_and_extraction(con)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO dated_effects "
            "(extraction_id, sector, direction, magnitude, "
            " window_start, window_end, rationale, source_span) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                ext_id,
                "Copper",
                "increase",
                "moderate",
                "2026-08-01",
                "2026-06-01",      # window_end < window_start
                "Copper uptick",
                "Item 7, p.51",
            ),
        )


def test_empty_source_span_rejected():
    con = _fresh_db()
    ext_id = _insert_filing_and_extraction(con)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO dated_effects "
            "(extraction_id, sector, direction, magnitude, "
            " window_start, window_end, rationale, source_span) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                ext_id,
                "Nickel",
                "increase",
                "small",
                "2026-09-01",
                "2026-12-01",
                "no citation",
                "",                # empty source_span
            ),
        )


def test_extractions_uniqueness_on_accession_and_model():
    con = _fresh_db()
    _insert_filing_and_extraction(con)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO extractions "
            "(accession_number, extractor_model, extractor_confidence, extracted_at) "
            "VALUES (?,?,?,?)",
            (
                "0001628280-26-005001",
                "claude-opus-4-7",  # same (accession, model) as the seeded one
                0.85,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def test_different_models_can_extract_same_filing():
    """The UNIQUE constraint is on (accession, model), not on accession
    alone -- A/B-ing models is supposed to work."""
    con = _fresh_db()
    _insert_filing_and_extraction(con)
    cur = con.execute(
        "INSERT INTO extractions "
        "(accession_number, extractor_model, extractor_confidence, extracted_at) "
        "VALUES (?,?,?,?)",
        (
            "0001628280-26-005001",
            "claude-sonnet-4-6",   # different model -- should be allowed
            0.71,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    assert cur.lastrowid > 0


def test_cascade_delete_removes_effects():
    """Dropping an extraction should clean up its effects -- otherwise
    re-running an extractor leaks rows."""
    con = _fresh_db()
    ext_id = _insert_filing_and_extraction(con)
    con.execute(
        "INSERT INTO dated_effects "
        "(extraction_id, sector, direction, magnitude, "
        " window_start, window_end, rationale, source_span) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            ext_id, "Lithium", "increase", "large",
            "2026-05-01", "2026-08-31", "ramp", "Item 2, p.18",
        ),
    )
    assert con.execute("SELECT COUNT(*) FROM dated_effects").fetchone()[0] == 1

    con.execute("DELETE FROM extractions WHERE id = ?", (ext_id,))
    assert con.execute("SELECT COUNT(*) FROM dated_effects").fetchone()[0] == 0

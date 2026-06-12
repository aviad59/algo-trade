"""Buffer -- the canonical SQLite store between Agent #1 and downstream stages.

This package is the persistence layer that sits between the Extractor
(Agent #1) and everything that reads its output: the sector timeline
aggregator, the buy/sell timer, the recommender (Agent #2), and the
read-only web app.

Status: schema only. The schema is committed at `schema.sql`. A Python
`Buffer` class that upserts ExtractedFiling rows and exposes query
helpers is the next implementation step -- see docs/ARCHITECTURE.md
for the planned interface and the rationale for the schema shape.

The schema is the contract; the code around it is replaceable. If we
ever outgrow SQLite, the same DDL ports to Postgres with two trivial
type changes (see docs/ARCHITECTURE.md \xc2\xa7"Upgrade path").
"""

from __future__ import annotations

from importlib import resources

__all__ = ["schema_sql"]


def schema_sql() -> str:
    """Return the DDL bundled with this package.

    Callers apply it to a fresh SQLite database with
    `connection.executescript(schema_sql())`.
    """
    return resources.files(__package__).joinpath("schema.sql").read_text(
        encoding="utf-8"
    )

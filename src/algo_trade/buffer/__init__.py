"""Buffer -- the canonical SQLite store between Agent #1 and downstream stages.

This package is the persistence layer that sits between the Extractor
(Agent #1) and everything that reads its output: the sector timeline
aggregator, the buy/sell timer, the recommender (Agent #2), and the
read-only web app.

Primary public API::

    from algo_trade.buffer import Buffer

    with Buffer("data/buffer.sqlite") as buf:
        buf.upsert(extracted, company_name="Tesla, Inc.")
        rows = buf.effects_for_sector("Lithium", since=..., until=...)

The schema is the contract; the code around it is replaceable. If we
ever outgrow SQLite, the same DDL ports to Postgres with two trivial
type changes (see docs/ARCHITECTURE.md §"Upgrade path").
"""

from __future__ import annotations

from importlib import resources

from .store import Buffer, SectorEffectRow

__all__ = ["Buffer", "SectorEffectRow", "schema_sql"]


def schema_sql() -> str:
    """Return the DDL bundled with this package.

    Callers apply it to a fresh SQLite database with
    ``connection.executescript(schema_sql())``.
    """
    return resources.files(__package__).joinpath("schema.sql").read_text(
        encoding="utf-8"
    )

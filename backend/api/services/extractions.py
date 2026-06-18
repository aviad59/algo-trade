"""Extractions API builder."""

from __future__ import annotations

from datetime import date

from algo_trade.buffer import Buffer
from algo_trade.buffer.store import ExtractionRow

from ..normalize import normalize_material_id


def extraction_public_id(extraction_id: int) -> str:
    return f"ext_{extraction_id:05d}"


def parse_extraction_public_id(public_id: str) -> int | None:
    if not public_id.startswith("ext_"):
        return None
    try:
        return int(public_id.removeprefix("ext_"))
    except ValueError:
        return None


def filing_url(cik: str, filing_type: str) -> str:
    cik_num = cik.lstrip("0") or "0"
    return (
        "https://www.sec.gov/cgi-bin/browse-edgar"
        f"?action=getcompany&CIK={cik_num}&type={filing_type}"
    )


def extraction_to_dict(row: ExtractionRow, universe_dir) -> dict:
    return {
        "id": extraction_public_id(row.id),
        "ticker": row.ticker,
        "cik": row.cik,
        "filing_type": row.filing_type,
        "filing_date": row.filing_date.isoformat(),
        "filing_url": filing_url(row.cik, row.filing_type),
        "dated_effects": [
            {
                "sector": normalize_material_id(e.sector, universe_dir),
                "direction": e.direction.value,
                "magnitude": e.magnitude.value,
                "window_start": e.window_start.isoformat(),
                "window_end": e.window_end.isoformat(),
                "rationale": e.rationale,
                "source_span": e.source_span,
            }
            for e in row.dated_effects
        ],
        "flagged_risks": list(row.flagged_risks),
        "extractor_confidence": row.extractor_confidence,
    }


def list_extractions_response(
    buf: Buffer,
    *,
    universe_dir,
    tickers: list[str] | None,
    material: str | None,
    from_date: date | None,
    to_date: date | None,
    limit: int,
    offset: int,
) -> dict:
    sectors = None
    if material:
        from ..normalize import material_sector_aliases

        sectors = material_sector_aliases(material, universe_dir)

    rows, total = buf.list_extractions(
        tickers=tickers,
        sectors=sectors,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )
    return {
        "contract_version": "1.0",
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [extraction_to_dict(row, universe_dir) for row in rows],
    }

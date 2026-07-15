"""Generate the public ranking snapshot served with zero runtime LLM spend.

Runs Agent #2 once against the current buffer (needs ANTHROPIC_API_KEY
locally) and freezes the result, stamped with the buffer version, to
ALGO_TRADE_RANKING_SNAPSHOT (default data/ranking-snapshot.json). The API
serves it to unauthenticated visitors only while it matches the live buffer;
re-run this after every extraction batch, before deploying.

    python backend/scripts/make-ranking-snapshot.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ -> api

from api.deps import get_settings
from api.services.forecast import _anthropic_api_key_present, _ranked_materials_to_api

from algo_trade.buffer import Buffer
from algo_trade.recommender import Recommender


def main() -> int:
    settings = get_settings()
    if not _anthropic_api_key_present():
        print("ANTHROPIC_API_KEY is required to generate the snapshot", file=sys.stderr)
        return 1

    with Buffer(str(settings.buffer_path)) as buf:
        max_at = buf.max_extracted_at()
        if max_at is None:
            print("buffer is empty; run algo-trade-extract first", file=sys.stderr)
            return 1

        recommender = Recommender(model=settings.recommender_model)
        ranked = recommender.rank(
            buf,
            settings.forecast_since,
            settings.forecast_until,
            as_of=settings.forecast_until,
            universe_dir=settings.universe_dir,
        )
        if not ranked.ranked_materials:
            print("recommender returned no materials; not writing snapshot", file=sys.stderr)
            return 1

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "recommender_model": ranked.recommender_model,
            "buffer_version": {
                "max_extracted_at": max_at.isoformat(),
                "count_extractions": buf.count_extractions(),
            },
            "ranking": _ranked_materials_to_api(ranked),
        }

    out = settings.ranking_snapshot
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {out} ({len(payload['ranking']['ranked_materials'])} materials, "
          f"model {payload['recommender_model']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""algo-trade-plot — render a material forecast curve from the buffer."""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path


def _forecast_window() -> tuple[date, date]:
    from .env import env_str, load_env

    load_env()
    today = date.today()
    default_since = today.replace(day=1) - timedelta(days=365)
    since_raw = env_str("ALGO_TRADE_FORECAST_SINCE", "")
    until_raw = env_str("ALGO_TRADE_FORECAST_UNTIL", "")
    since = date.fromisoformat(since_raw) if since_raw else default_since
    until = date.fromisoformat(until_raw) if until_raw else today
    return since, until


def _cli(argv: list[str] | None = None) -> int:
    from .buffer import Buffer
    from .env import env_path, load_env
    from .plot import plot_material_forecast
    from .timer import material_forecast

    load_env()
    default_since, default_until = _forecast_window()
    default_db = str(env_path("ALGO_TRADE_BUFFER_PATH", "data/buffer.sqlite"))

    parser = argparse.ArgumentParser(
        prog="algo-trade-plot",
        description="Plot a material demand-signal curve from the buffer.",
    )
    parser.add_argument(
        "material_id",
        metavar="MATERIAL",
        help="Canonical material id (e.g. lithium, copper).",
    )
    parser.add_argument(
        "--db",
        default=default_db,
        metavar="PATH",
        help="SQLite buffer path. Default: ALGO_TRADE_BUFFER_PATH.",
    )
    parser.add_argument(
        "--since",
        default=default_since.isoformat(),
        help="Forecast window start (ISO date). Default: ALGO_TRADE_FORECAST_SINCE.",
    )
    parser.add_argument(
        "--until",
        default=default_until.isoformat(),
        help="Forecast window end / as_of (ISO date). Default: ALGO_TRADE_FORECAST_UNTIL.",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="PATH",
        help="Output file (.png, .pdf, .svg, or .html). Default: plots/<material>.png",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Write interactive plotly HTML (same as -o path.html).",
    )
    parser.add_argument(
        "--no-forward-auc",
        action="store_true",
        help="Omit the forward-AUC overlay line.",
    )
    args = parser.parse_args(argv)

    since = date.fromisoformat(args.since)
    until = date.fromisoformat(args.until)
    material_id = args.material_id.lower().strip()

    if args.output:
        output_path = Path(args.output)
    elif args.html:
        output_path = Path("plots") / f"{material_id}.html"
    else:
        output_path = Path("plots") / f"{material_id}.png"

    buf = Buffer(str(args.db))
    try:
        forecast = material_forecast(buf, material_id, since, until, as_of=until)
    finally:
        buf.close()

    plot_material_forecast(
        forecast,
        output_path=output_path,
        show_forward_auc=not args.no_forward_auc,
        interactive=args.html or output_path.suffix.lower() == ".html",
    )

    print(f"Wrote {output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(_cli())

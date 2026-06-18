"""Plot material forecast curves — matplotlib static PNG and optional plotly HTML.

Accepts the dict returned by :func:`~algo_trade.timer.material_forecast` (same
shape as the web mock ``MaterialForecast`` contract).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

__all__ = ["plot_material_forecast"]


def _parse_month(month: str) -> datetime:
    return datetime.strptime(month, "%Y-%m")


def _actions_by_month(forecast: dict[str, Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for action in forecast.get("actions", []):
        month = str(action["date"])[:7]
        indexed[month] = action
    return indexed


def _material_title(forecast: dict[str, Any]) -> str:
    material_id = forecast.get("material_id", "material")
    as_of = forecast.get("as_of", "")
    return f"{material_id} demand signal (as of {as_of})"


def plot_material_forecast(
    forecast: dict[str, Any],
    *,
    output_path: str | Path,
    show_forward_auc: bool = True,
    interactive: bool | None = None,
) -> Path:
    """Render a material forecast chart to *output_path*.

    Uses matplotlib for raster/vector image formats (``.png``, ``.pdf``, ``.svg``).
    Uses plotly when *interactive* is ``True`` or the path ends with ``.html``.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    use_plotly = interactive if interactive is not None else path.suffix.lower() == ".html"
    if use_plotly:
        return _plot_plotly(forecast, path, show_forward_auc=show_forward_auc)
    return _plot_matplotlib(forecast, path, show_forward_auc=show_forward_auc)


def _plot_matplotlib(
    forecast: dict[str, Any],
    path: Path,
    *,
    show_forward_auc: bool,
) -> Path:
    curve = forecast.get("curve", [])
    if not curve:
        raise ValueError("forecast curve is empty — nothing to plot")

    months = [_parse_month(point["month"]) for point in curve]
    signals = [float(point["signal"]) for point in curve]
    forward_auc = [float(point["forward_AUC"]) for point in curve]
    actions = _actions_by_month(forecast)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(months, signals, color="#2563eb", linewidth=2, label="Signal", marker="o", markersize=4)

    if show_forward_auc:
        ax.plot(
            months,
            forward_auc,
            color="#7c3aed",
            linewidth=1.8,
            linestyle="--",
            label="Forward AUC",
            marker=".",
        )

    for month_dt, signal in zip(months, signals, strict=True):
        month_key = month_dt.strftime("%Y-%m")
        action = actions.get(month_key)
        if not action:
            continue
        color = "#10b981" if action["action"] == "BUY" else "#ef4444"
        marker = "^" if action["action"] == "BUY" else "v"
        ax.scatter([month_dt], [signal], color=color, marker=marker, s=120, zorder=5)
        ax.annotate(
            action["action"],
            (month_dt, signal),
            textcoords="offset points",
            xytext=(0, 10 if action["action"] == "BUY" else -14),
            ha="center",
            fontsize=8,
            color=color,
        )

    ax.set_title(_material_title(forecast))
    ax.set_xlabel("Month")
    ax.set_ylabel("Narrative signal")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate()
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _plot_plotly(
    forecast: dict[str, Any],
    path: Path,
    *,
    show_forward_auc: bool,
) -> Path:
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        raise RuntimeError(
            "plotly is required for HTML output. Install with: pip install -e '.[plot]'"
        ) from exc

    curve = forecast.get("curve", [])
    if not curve:
        raise ValueError("forecast curve is empty — nothing to plot")

    months = [point["month"] for point in curve]
    signals = [float(point["signal"]) for point in curve]
    forward_auc = [float(point["forward_AUC"]) for point in curve]
    actions = _actions_by_month(forecast)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=months,
            y=signals,
            mode="lines+markers",
            name="Signal",
            line=dict(color="#2563eb", width=2),
        )
    )

    if show_forward_auc:
        fig.add_trace(
            go.Scatter(
                x=months,
                y=forward_auc,
                mode="lines",
                name="Forward AUC",
                line=dict(color="#7c3aed", width=2, dash="dash"),
            )
        )

    buy_x: list[str] = []
    buy_y: list[float] = []
    sell_x: list[str] = []
    sell_y: list[float] = []
    for point in curve:
        action = actions.get(point["month"])
        if not action:
            continue
        if action["action"] == "BUY":
            buy_x.append(point["month"])
            buy_y.append(float(point["signal"]))
        else:
            sell_x.append(point["month"])
            sell_y.append(float(point["signal"]))

    if buy_x:
        fig.add_trace(
            go.Scatter(
                x=buy_x,
                y=buy_y,
                mode="markers+text",
                name="BUY",
                text=["BUY"] * len(buy_x),
                textposition="top center",
                marker=dict(color="#10b981", size=12, symbol="triangle-up"),
            )
        )
    if sell_x:
        fig.add_trace(
            go.Scatter(
                x=sell_x,
                y=sell_y,
                mode="markers+text",
                name="SELL",
                text=["SELL"] * len(sell_x),
                textposition="bottom center",
                marker=dict(color="#ef4444", size=12, symbol="triangle-down"),
            )
        )

    fig.update_layout(
        title=_material_title(forecast),
        xaxis_title="Month",
        yaxis_title="Narrative signal",
        template="plotly_white",
        hovermode="x unified",
    )
    fig.write_html(str(path), include_plotlyjs="cdn")
    return path

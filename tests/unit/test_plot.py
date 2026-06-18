"""Unit tests for material forecast plotting."""

from __future__ import annotations

import builtins
import json
from pathlib import Path
from typing import Any

import pytest

from algo_trade.plot import (
    _actions_by_month,
    _material_title,
    _parse_month,
    plot_material_forecast,
)

_MOCK_FORECAST: dict[str, Any] = {
    "contract_version": "1.0",
    "material_id": "lithium",
    "as_of": "2026-06-08",
    "actions": [
        {
            "date": "2026-04-01",
            "action": "BUY",
            "rationale": "forward_AUC ramping",
        },
        {
            "date": "2026-08-01",
            "action": "SELL",
            "rationale": "forward_AUC peaked",
        },
    ],
    "curve": [
        {"month": "2026-01", "signal": 0.15, "forward_AUC": 2.4},
        {"month": "2026-02", "signal": 0.2, "forward_AUC": 2.8},
        {"month": "2026-03", "signal": 0.25, "forward_AUC": 3.2},
        {"month": "2026-04", "signal": 0.35, "forward_AUC": 3.8},
        {"month": "2026-05", "signal": 1.45, "forward_AUC": 4.1},
        {"month": "2026-06", "signal": 1.45, "forward_AUC": 3.9},
        {"month": "2026-07", "signal": 1.2, "forward_AUC": 2.5},
        {"month": "2026-08", "signal": 0.55, "forward_AUC": 1.1},
    ],
    "contributing_ticker_count": 2,
    "universe_curve": None,
}


def _curve_point(
    month: str,
    *,
    signal: float = 0.5,
    forward_auc: float = 1.0,
) -> dict[str, float | str]:
    return {"month": month, "signal": signal, "forward_AUC": forward_auc}


def _forecast(
    *,
    curve: list[dict[str, Any]] | None = None,
    actions: list[dict[str, Any]] | None = None,
    material_id: str = "lithium",
    as_of: str = "2026-06-08",
) -> dict[str, Any]:
    return {
        "contract_version": "1.0",
        "material_id": material_id,
        "as_of": as_of,
        "actions": actions if actions is not None else [],
        "curve": curve if curve is not None else [_curve_point("2026-01")],
        "contributing_ticker_count": 0,
        "universe_curve": None,
    }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def test_parse_month() -> None:
    assert _parse_month("2026-05").month == 5
    assert _parse_month("2026-05").year == 2026


def test_actions_by_month_indexes_by_yyyy_mm() -> None:
    actions = _actions_by_month(
        {
            "actions": [
                {"date": "2026-04-15", "action": "BUY"},
                {"date": "2026-08-01", "action": "SELL"},
            ]
        }
    )
    assert actions["2026-04"]["action"] == "BUY"
    assert actions["2026-08"]["action"] == "SELL"


def test_actions_by_month_last_duplicate_wins() -> None:
    actions = _actions_by_month(
        {
            "actions": [
                {"date": "2026-04-01", "action": "BUY"},
                {"date": "2026-04-20", "action": "SELL"},
            ]
        }
    )
    assert actions["2026-04"]["action"] == "SELL"


def test_material_title_uses_defaults_for_missing_fields() -> None:
    assert _material_title({}) == "material demand signal (as of )"
    assert "copper" in _material_title({"material_id": "copper", "as_of": "2026-01-01"})


# --------------------------------------------------------------------------- #
# Matplotlib static output
# --------------------------------------------------------------------------- #


def test_plot_material_forecast_writes_png(tmp_path) -> None:
    output = tmp_path / "lithium.png"
    result = plot_material_forecast(_MOCK_FORECAST, output_path=output)
    assert result == output
    assert output.is_file()
    assert output.stat().st_size > 0


@pytest.mark.parametrize("suffix", [".png", ".pdf", ".svg"])
def test_plot_material_forecast_writes_vector_and_raster(tmp_path, suffix: str) -> None:
    output = tmp_path / f"copper{suffix}"
    plot_material_forecast(_MOCK_FORECAST, output_path=output)
    assert output.is_file()
    assert output.stat().st_size > 0


def test_plot_material_forecast_accepts_string_path(tmp_path) -> None:
    output = tmp_path / "nested" / "dir" / "lithium.png"
    result = plot_material_forecast(_MOCK_FORECAST, output_path=str(output))
    assert result == output
    assert output.is_file()


def test_plot_material_forecast_creates_parent_directories(tmp_path) -> None:
    output = tmp_path / "deep" / "nested" / "plot.png"
    plot_material_forecast(_MOCK_FORECAST, output_path=output)
    assert output.parent.is_dir()
    assert output.is_file()


def test_plot_material_forecast_png_without_forward_auc(tmp_path) -> None:
    output = tmp_path / "lithium-no-auc.png"
    with_auc = tmp_path / "lithium-with-auc.png"
    plot_material_forecast(_MOCK_FORECAST, output_path=output, show_forward_auc=False)
    plot_material_forecast(_MOCK_FORECAST, output_path=with_auc, show_forward_auc=True)
    assert output.is_file()
    # Overlay line should change the rendered image size (not a strict guarantee, but
    # catches accidental no-op when toggling the flag).
    assert output.stat().st_size != with_auc.stat().st_size


def test_plot_single_point_curve(tmp_path) -> None:
    forecast = _forecast(curve=[_curve_point("2026-03", signal=0.1, forward_auc=0.2)])
    output = tmp_path / "single.png"
    plot_material_forecast(forecast, output_path=output)
    assert output.is_file()


def test_plot_no_actions(tmp_path) -> None:
    forecast = _forecast(
        curve=[
            _curve_point("2026-01", signal=0.1, forward_auc=0.2),
            _curve_point("2026-02", signal=0.3, forward_auc=0.4),
        ],
        actions=[],
    )
    plot_material_forecast(forecast, output_path=tmp_path / "no-actions.png")


def test_plot_only_buy_action(tmp_path) -> None:
    forecast = _forecast(
        curve=[_curve_point("2026-04", signal=1.0, forward_auc=2.0)],
        actions=[{"date": "2026-04-01", "action": "BUY", "rationale": "ramp"}],
    )
    plot_material_forecast(forecast, output_path=tmp_path / "buy-only.png")


def test_plot_only_sell_action(tmp_path) -> None:
    forecast = _forecast(
        curve=[_curve_point("2026-08", signal=0.5, forward_auc=0.1)],
        actions=[{"date": "2026-08-01", "action": "SELL", "rationale": "peak"}],
    )
    plot_material_forecast(forecast, output_path=tmp_path / "sell-only.png")


def test_plot_action_month_not_on_curve_does_not_crash(tmp_path) -> None:
    forecast = _forecast(
        curve=[_curve_point("2026-01")],
        actions=[{"date": "2026-12-01", "action": "SELL", "rationale": "off-curve"}],
    )
    plot_material_forecast(forecast, output_path=tmp_path / "off-curve-action.png")


def test_plot_negative_and_zero_signals(tmp_path) -> None:
    forecast = _forecast(
        curve=[
            _curve_point("2026-01", signal=-0.5, forward_auc=-1.0),
            _curve_point("2026-02", signal=0.0, forward_auc=0.0),
            _curve_point("2026-03", signal=2.5, forward_auc=3.0),
        ]
    )
    plot_material_forecast(forecast, output_path=tmp_path / "negative.png")


def test_plot_non_contiguous_months(tmp_path) -> None:
    forecast = _forecast(
        curve=[
            _curve_point("2026-01", signal=0.2, forward_auc=0.5),
            _curve_point("2026-04", signal=1.5, forward_auc=2.0),
            _curve_point("2026-09", signal=0.1, forward_auc=0.0),
        ]
    )
    plot_material_forecast(forecast, output_path=tmp_path / "gapped.png")


def test_plot_large_signal_values(tmp_path) -> None:
    forecast = _forecast(
        curve=[_curve_point("2026-06", signal=999.99, forward_auc=5000.0)]
    )
    plot_material_forecast(forecast, output_path=tmp_path / "large.png")


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


def test_plot_material_forecast_empty_curve_raises(tmp_path) -> None:
    with pytest.raises(ValueError, match="empty"):
        plot_material_forecast(
            {**_MOCK_FORECAST, "curve": []},
            output_path=tmp_path / "empty.png",
        )


def test_plot_material_forecast_missing_curve_key_raises(tmp_path) -> None:
    bare = {"material_id": "lithium", "as_of": "2026-06-08", "actions": []}
    with pytest.raises(ValueError, match="empty"):
        plot_material_forecast(bare, output_path=tmp_path / "no-curve.png")


def test_plot_html_empty_curve_raises(tmp_path) -> None:
    pytest.importorskip("plotly")
    with pytest.raises(ValueError, match="empty"):
        plot_material_forecast(
            {**_MOCK_FORECAST, "curve": []},
            output_path=tmp_path / "empty.html",
        )


def test_plotly_missing_raises_runtime_error(tmp_path, monkeypatch) -> None:
    real_import = builtins.__import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "plotly" or name == "plotly.graph_objects":
            raise ImportError("plotly not installed")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    with pytest.raises(RuntimeError, match="plotly is required"):
        plot_material_forecast(
            _MOCK_FORECAST,
            output_path=tmp_path / "needs-plotly.html",
            interactive=True,
        )


# --------------------------------------------------------------------------- #
# Plotly HTML
# --------------------------------------------------------------------------- #


def test_plot_material_forecast_plotly_html_explicit_flag(tmp_path) -> None:
    pytest.importorskip("plotly")
    output = tmp_path / "lithium.html"
    result = plot_material_forecast(_MOCK_FORECAST, output_path=output, interactive=True)
    assert result == output
    body = output.read_text(encoding="utf-8").lower()
    assert "plotly" in body
    assert "lithium demand signal" in body


def test_plot_material_forecast_html_inferred_from_suffix(tmp_path) -> None:
    pytest.importorskip("plotly")
    output = tmp_path / "copper.html"
    plot_material_forecast(_MOCK_FORECAST, output_path=output)
    assert output.is_file()
    assert "plotly" in output.read_text(encoding="utf-8").lower()


def test_plot_html_without_forward_auc(tmp_path) -> None:
    pytest.importorskip("plotly")
    output = tmp_path / "no-auc.html"
    plot_material_forecast(
        _forecast(curve=[_curve_point("2026-01")]),
        output_path=output,
        show_forward_auc=False,
    )
    assert output.is_file()


def test_interactive_false_png_does_not_require_plotly(tmp_path, monkeypatch) -> None:
    """interactive=False on a raster path must work even when plotly is unavailable."""
    real_import = builtins.__import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "plotly" or name == "plotly.graph_objects":
            raise ImportError("plotly not installed")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    output = tmp_path / "forced-mpl.png"
    plot_material_forecast(_MOCK_FORECAST, output_path=output, interactive=False)
    assert output.is_file()
    assert output.stat().st_size > 0


def test_interactive_false_html_suffix_raises(tmp_path) -> None:
    """interactive=False forces matplotlib, which cannot write .html files."""
    with pytest.raises(ValueError, match="not supported"):
        plot_material_forecast(
            _MOCK_FORECAST,
            output_path=tmp_path / "forced-mpl.html",
            interactive=False,
        )


# --------------------------------------------------------------------------- #
# Integration with repo mock bundle
# --------------------------------------------------------------------------- #


def test_plot_from_repo_mock_json(tmp_path) -> None:
    mock_path = (
        Path(__file__).resolve().parents[2]
        / "backend"
        / "mock"
        / "v1"
        / "forecast"
        / "materials"
        / "lithium.json"
    )
    forecast = json.loads(mock_path.read_text(encoding="utf-8"))
    output = tmp_path / "mock-lithium.png"
    plot_material_forecast(forecast, output_path=output)
    assert output.stat().st_size > 0


@pytest.mark.parametrize("material_id", ["copper", "natural-gas", "semiconductors"])
def test_plot_other_repo_mock_materials(tmp_path, material_id: str) -> None:
    mock_path = (
        Path(__file__).resolve().parents[2]
        / "backend"
        / "mock"
        / "v1"
        / "forecast"
        / "materials"
        / f"{material_id}.json"
    )
    if not mock_path.is_file():
        pytest.skip(f"mock file missing: {material_id}")
    forecast = json.loads(mock_path.read_text(encoding="utf-8"))
    plot_material_forecast(forecast, output_path=tmp_path / f"{material_id}.png")

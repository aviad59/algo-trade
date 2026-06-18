"""Unit tests for material forecast plotting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from algo_trade.plot import plot_material_forecast

_MOCK_FORECAST = {
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


def test_plot_material_forecast_writes_png(tmp_path) -> None:
    output = tmp_path / "lithium.png"
    result = plot_material_forecast(_MOCK_FORECAST, output_path=output)
    assert result == output
    assert output.is_file()
    assert output.stat().st_size > 0


def test_plot_material_forecast_png_without_forward_auc(tmp_path) -> None:
    output = tmp_path / "lithium-no-auc.png"
    plot_material_forecast(
        _MOCK_FORECAST,
        output_path=output,
        show_forward_auc=False,
    )
    assert output.is_file()


def test_plot_material_forecast_empty_curve_raises(tmp_path) -> None:
    with pytest.raises(ValueError, match="empty"):
        plot_material_forecast(
            {**_MOCK_FORECAST, "curve": []},
            output_path=tmp_path / "empty.png",
        )


def test_plot_material_forecast_plotly_html(tmp_path) -> None:
    plotly = pytest.importorskip("plotly")
    assert plotly is not None

    output = tmp_path / "lithium.html"
    result = plot_material_forecast(_MOCK_FORECAST, output_path=output, interactive=True)
    assert result == output
    assert output.is_file()
    assert "plotly" in output.read_text(encoding="utf-8").lower()


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

"""Hermetic tests for the reference price loaders (prices.py).

No network: yfinance is never imported here. The CSV loaders and the
save/load round-trip are the hermetic path the backtest CLI relies on.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from algo_trade.backtest import BacktestResult, BacktestSummary, PriceSeries, Trade
from algo_trade.backtest_cli import _format_summary
from algo_trade.prices import load_csv_prices, load_prices_dir, save_csv_prices


def _write_csv(path, header, rows):
    lines = [header] + rows
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_load_csv_prices_basic(tmp_path):
    csv_path = tmp_path / "LIT.csv"
    _write_csv(csv_path, "date,close", ["2026-01-02,40.0", "2026-01-05,41.5"])

    series = load_csv_prices(csv_path)

    assert series.instrument == "LIT"
    assert series.first_date() == date(2026, 1, 2)
    assert series.price_on_or_after(date(2026, 1, 3)) == (date(2026, 1, 5), 41.5)


def test_load_csv_prices_sorts_and_accepts_capitalized_headers(tmp_path):
    csv_path = tmp_path / "smh.csv"
    _write_csv(csv_path, "Date,Close", ["2026-02-03,210.0", "2026-01-02,200.0"])

    series = load_csv_prices(csv_path)

    assert series.instrument == "SMH"
    assert series.first_date() == date(2026, 1, 2)
    assert series.last_date() == date(2026, 2, 3)


def test_load_csv_prices_explicit_instrument_wins(tmp_path):
    csv_path = tmp_path / "whatever.csv"
    _write_csv(csv_path, "date,close", ["2026-01-02,10.0"])

    series = load_csv_prices(csv_path, instrument="COPX")

    assert series.instrument == "COPX"


def test_load_csv_prices_missing_columns_raises(tmp_path):
    csv_path = tmp_path / "BAD.csv"
    _write_csv(csv_path, "day,price", ["2026-01-02,10.0"])

    with pytest.raises(ValueError, match="need 'date' and 'close'"):
        load_csv_prices(csv_path)


def test_load_prices_dir_skips_bad_files(tmp_path):
    _write_csv(tmp_path / "LIT.csv", "date,close", ["2026-01-02,40.0"])
    _write_csv(tmp_path / "BAD.csv", "day,price", ["2026-01-02,10.0"])

    prices = load_prices_dir(tmp_path)

    assert set(prices) == {"LIT"}


def test_save_then_load_round_trips(tmp_path):
    series = PriceSeries(
        pd.Series([40.0, 41.5], index=pd.to_datetime(["2026-01-02", "2026-01-05"])),
        instrument="JJU",
    )

    save_csv_prices({"JJU": series}, tmp_path)
    reloaded = load_prices_dir(tmp_path)

    assert set(reloaded) == {"JJU"}
    assert reloaded["JJU"].price_on_or_after(date(2026, 1, 2)) == (date(2026, 1, 2), 40.0)
    assert reloaded["JJU"].last_date() == date(2026, 1, 5)


def test_format_summary_renders_table():
    trade = Trade(
        sector="lithium",
        instrument="LIT",
        entry_date=date(2025, 10, 1),
        entry_price=40.0,
        exit_date=date(2026, 1, 2),
        exit_price=44.0,
        return_pct=0.10,
        open_at_end=False,
    )
    result = BacktestResult(sector="lithium", instrument="LIT", trades=[trade])
    result.total_return_pct = 0.10
    result.benchmark_return_pct = 0.04
    summary = BacktestSummary(results=[result])

    text = _format_summary(summary)

    assert "lithium" in text
    assert "LIT" in text
    assert "+10.00%" in text
    assert "+6.00%" in text  # alpha column = strategy - hold
    assert "overall" in text

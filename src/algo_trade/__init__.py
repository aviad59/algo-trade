"""algo-trade: agentic pipeline over SEC EDGAR filings.

The first stage — implemented — is the EDGAR fetcher. See `algo_trade.fetcher`.
"""

from .models import (
    CurvePoint,
    DatedEffect,
    Direction,
    ExtractedFiling,
    FetchedFiling,
    Magnitude,
    RankedMaterials,
    SectorRanking,
    TimerAction,
    TimerSignal,
)
from .fetcher import Fetcher
from .extractor import Extractor
from .buffer import Buffer
from .timeline import build_all_curves, build_curve
from .timer import TimerConfig, detect_actions, material_forecast
from .recommender import Recommender, build_ranking_context
from .plot import plot_material_forecast
from .backtest import (
    BacktestResult,
    BacktestSummary,
    PriceSeries,
    Trade,
    backtest_actions,
    backtest_buffer,
    default_instrument_for_sector,
)

__all__ = [
    "BacktestResult",
    "BacktestSummary",
    "Buffer",
    "backtest_actions",
    "backtest_buffer",
    "build_all_curves",
    "build_curve",
    "build_ranking_context",
    "CurvePoint",
    "DatedEffect",
    "default_instrument_for_sector",
    "detect_actions",
    "Direction",
    "ExtractedFiling",
    "Extractor",
    "FetchedFiling",
    "Fetcher",
    "material_forecast",
    "Magnitude",
    "plot_material_forecast",
    "PriceSeries",
    "RankedMaterials",
    "Recommender",
    "SectorRanking",
    "TimerAction",
    "TimerConfig",
    "TimerSignal",
    "Trade",
]
__version__ = "0.0.1"

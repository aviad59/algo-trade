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

__all__ = [
    "Buffer",
    "build_all_curves",
    "build_curve",
    "build_ranking_context",
    "CurvePoint",
    "DatedEffect",
    "detect_actions",
    "Direction",
    "ExtractedFiling",
    "Extractor",
    "FetchedFiling",
    "Fetcher",
    "material_forecast",
    "Magnitude",
    "plot_material_forecast",
    "RankedMaterials",
    "Recommender",
    "SectorRanking",
    "TimerAction",
    "TimerConfig",
    "TimerSignal",
]
__version__ = "0.0.1"

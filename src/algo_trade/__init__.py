"""algo-trade: agentic pipeline over SEC EDGAR filings.

The first stage — implemented — is the EDGAR fetcher. See `algo_trade.fetcher`.
"""

from .models import (
    DatedEffect,
    Direction,
    ExtractedFiling,
    FetchedFiling,
    Magnitude,
)
from .fetcher import Fetcher
from .extractor import Extractor
from .buffer import Buffer

__all__ = [
    "Buffer",
    "DatedEffect",
    "Direction",
    "ExtractedFiling",
    "Extractor",
    "FetchedFiling",
    "Fetcher",
    "Magnitude",
]
__version__ = "0.0.1"

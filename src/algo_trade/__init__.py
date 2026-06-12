"""algo-trade: agentic pipeline over SEC EDGAR filings.

The first stage — implemented — is the EDGAR fetcher. See `algo_trade.fetcher`.
"""

from .models import FetchedFiling
from .fetcher import Fetcher

__all__ = ["FetchedFiling", "Fetcher"]
__version__ = "0.0.1"

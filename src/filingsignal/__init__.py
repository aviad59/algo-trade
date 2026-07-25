"""FilingSignal — materials sector-rotation signal from SEC filings.

Pipeline: fetch → filter → extract (Agent #1, provider-agnostic) → buffer →
score (point-in-time, cross-sectional) → evaluate / backtest → serve.

See ARCHITECTURE.md for the full design.
"""

__version__ = "0.1.0"

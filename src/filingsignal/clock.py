"""The single source of 'now' for the whole app.

Everything time-dependent (which quarter to forecast, the tracker's as-of date,
the backtest's last-completed quarter) reads ``today()`` instead of
``date.today()`` directly. That makes calendar rollover deterministic and
testable: set ``FILINGSIGNAL_TODAY=YYYY-MM-DD`` and the app behaves as if that
were the date — no waiting for the quarter to actually turn.
"""

from __future__ import annotations

from datetime import date

from .env import env_optional_str


def today() -> date:
    """Current date, overridable via ``FILINGSIGNAL_TODAY=YYYY-MM-DD``.
    An unparseable override is ignored (falls back to the real date)."""
    raw = env_optional_str("FILINGSIGNAL_TODAY")
    if raw:
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
    return date.today()

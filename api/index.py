"""Vercel serverless entrypoint for the FastAPI backend.

Vercel's Python runtime auto-discovers files under ``api/`` and treats
them as serverless functions. We re-export the FastAPI ASGI ``app`` so
the runtime can hand HTTP requests straight to it.

The repo's source layout puts the actual package at
``src/algo_trade/`` and the FastAPI app at ``backend/api/main.py``.
We add ``src`` to ``sys.path`` so the package resolves without an
editable install (Vercel runs the build with whatever ``requirements.txt``
ships, not ``pip install -e .``).

⚠️  KNOWN LIMITATION: Vercel's serverless filesystem is read-only outside
``/tmp``, and ``/tmp`` does NOT persist across invocations. Endpoints
that write to ``data/buffer.sqlite`` (``POST /api/v1/extract``) will not
survive cold starts. For a real backend, deploy to Fly.io / Railway /
Render with a persistent volume. See ``docs/web-integration.md``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make src/algo_trade importable in the Vercel function runtime.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Re-export the FastAPI ASGI app -- Vercel's @vercel/python runtime
# detects this `app` symbol and hands requests directly to it.
from backend.api.main import app  # noqa: E402, F401

"""Simple shared-secret auth for the LLM-spending endpoint. One key
(FILINGSIGNAL_API_KEY); read endpoints stay public. Unset key ⇒ 503 (nobody can
spend the baked-in provider keys)."""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException

from .deps import get_settings


def require_api_key(authorization: str = Header(default="")) -> None:
    key = get_settings().api_key
    if not key:
        raise HTTPException(status_code=503, detail="extraction disabled (no FILINGSIGNAL_API_KEY set)")
    token = authorization[7:] if authorization.lower().startswith("bearer ") else authorization
    if not hmac.compare_digest(token.strip(), key):
        raise HTTPException(status_code=401, detail="invalid or missing API key")

import logging
import time
from typing import Any

import httpx
from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

from app.config import settings

logger = logging.getLogger(__name__)

_ANONYMOUS_USER: dict[str, Any] = {"sub": "anonymous", "email": "anonymous"}

# Simple in-memory JWKS cache: {"keys": [...], "cached_at": float}
_jwks_cache: dict[str, Any] = {}
_JWKS_TTL = 3600  # refresh JWKS every hour


async def _fetch_jwks() -> list[dict]:
    now = time.monotonic()
    if _jwks_cache.get("keys") and now - _jwks_cache.get("cached_at", 0) < _JWKS_TTL:
        return _jwks_cache["keys"]

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(settings.okta_jwks_uri)
        resp.raise_for_status()
        data = resp.json()

    _jwks_cache["keys"] = data["keys"]
    _jwks_cache["cached_at"] = now
    return _jwks_cache["keys"]


async def _validate_token(token: str) -> dict[str, Any]:
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token header",
        ) from exc

    kid = unverified_header.get("kid")
    keys = await _fetch_jwks()
    signing_key = next((k for k in keys if k.get("kid") == kid), None)

    if signing_key is None:
        # Force refresh and retry once
        _jwks_cache.clear()
        keys = await _fetch_jwks()
        signing_key = next((k for k in keys if k.get("kid") == kid), None)

    if signing_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to find matching signing key",
        )

    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=settings.okta_audience,
            issuer=settings.okta_issuer,
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {exc}",
        ) from exc

    return claims


def _extract_bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


async def get_current_user(request: Request) -> dict[str, Any]:
    """FastAPI dependency — validates JWT from Authorization header.

    When okta_validation_enabled=False, skips validation and returns a
    synthetic anonymous user. Intended for local dev/test only.
    """
    if not settings.okta_validation_enabled:
        return _ANONYMOUS_USER

    token = _extract_bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _validate_token(token)


async def get_optional_user(request: Request) -> dict[str, Any] | None:
    """FastAPI dependency for read endpoints — returns user claims or None.

    When okta_validation_enabled=False, always returns the anonymous user.
    """
    if not settings.okta_validation_enabled:
        return _ANONYMOUS_USER

    token = _extract_bearer_token(request)
    if not token:
        return None

    try:
        return await _validate_token(token)
    except HTTPException:
        return None

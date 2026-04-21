"""JWT Authentication Middleware.

Validates the Bearer JWT on every request except exempt paths.
Stores decoded claims in ``request.state.user_claims`` for downstream use.

Requirements: 1.6, 9.1, 9.5
"""

from __future__ import annotations

import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.services.auth_service import decode_session_token

# Paths that do not require authentication.
_EXEMPT_PREFIXES = ("/auth/",)
_EXEMPT_EXACT = {"/docs", "/openapi.json", "/redoc"}


def _is_exempt(path: str) -> bool:
    """Return True if *path* is exempt from JWT validation."""
    if path in _EXEMPT_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in _EXEMPT_PREFIXES)


def _unauthorized(detail: str) -> Response:
    body = json.dumps({"detail": detail})
    return Response(
        content=body,
        status_code=401,
        media_type="application/json",
    )


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that enforces JWT authentication on protected routes.

    Exempt paths: any path starting with ``/auth/`` and the OpenAPI docs
    endpoints (``/docs``, ``/openapi.json``, ``/redoc``).

    For protected routes:
    - Extracts the Bearer token from the ``Authorization`` header.
    - Validates the token via :func:`decode_session_token`.
    - Stores the decoded claims dict in ``request.state.user_claims``.
    - Returns a JSON 401 response if the header is missing or the token is
      invalid / expired / revoked.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        if _is_exempt(request.url.path):
            return await call_next(request)

        auth_header: str | None = request.headers.get("Authorization")
        if not auth_header:
            return _unauthorized("Missing Authorization header")

        parts = auth_header.split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return _unauthorized("Invalid Authorization header format")

        token = parts[1]
        try:
            claims = decode_session_token(token)
        except ValueError as exc:
            return _unauthorized(str(exc))

        request.state.user_claims = claims
        return await call_next(request)

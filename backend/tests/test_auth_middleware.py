"""Tests for Task 2.3: JWT authentication middleware.

Covers:
- /auth/* paths are exempt (no 401)
- Protected routes without a token return 401
- Protected routes with a valid token pass through and expose user_claims

Requirements: 1.6, 9.1, 9.5
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.middleware.auth_middleware import JWTAuthMiddleware
from app.services.auth_service import _issue_jwt


# ── Test app factory ──────────────────────────────────────────────────────────

def _make_app() -> FastAPI:
    """Build a minimal FastAPI app with JWTAuthMiddleware and a few test routes."""
    app = FastAPI()
    app.add_middleware(JWTAuthMiddleware)

    @app.get("/auth/google")
    async def auth_google():
        return {"status": "oauth_start"}

    @app.get("/auth/callback")
    async def auth_callback():
        return {"status": "callback"}

    @app.get("/protected")
    async def protected(request: Request):
        return {"claims": request.state.user_claims}

    @app.get("/docs-check")
    async def docs_check():
        return {"ok": True}

    return app


# ── Exempt path tests ─────────────────────────────────────────────────────────

def test_auth_prefix_is_exempt_no_token():
    """/auth/* paths must not require a JWT (Req 1.6)."""
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/auth/google")
    assert resp.status_code == 200
    assert resp.json() == {"status": "oauth_start"}


def test_auth_callback_is_exempt_no_token():
    """/auth/callback is also exempt."""
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/auth/callback")
    assert resp.status_code == 200


def test_docs_endpoint_is_exempt():
    """/docs is exempt from JWT validation."""
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/docs")
    # FastAPI serves the Swagger UI; we just need it not to 401
    assert resp.status_code != 401


def test_openapi_json_is_exempt():
    """/openapi.json is exempt from JWT validation."""
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/openapi.json")
    assert resp.status_code != 401


# ── Protected route — no token ────────────────────────────────────────────────

def test_protected_route_no_token_returns_401():
    """Protected route without Authorization header returns 401 (Req 1.6, 9.5)."""
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/protected")
    assert resp.status_code == 401
    assert "detail" in resp.json()


def test_protected_route_wrong_scheme_returns_401():
    """Non-Bearer Authorization scheme returns 401."""
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/protected", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert resp.status_code == 401


def test_protected_route_invalid_token_returns_401():
    """Malformed JWT returns 401 (Req 9.5)."""
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/protected", headers={"Authorization": "Bearer not.a.valid.jwt"})
    assert resp.status_code == 401
    assert "detail" in resp.json()


# ── Protected route — valid token ─────────────────────────────────────────────

def test_protected_route_valid_token_passes_through():
    """Valid JWT allows the request through and exposes claims (Req 1.6, 9.1)."""
    user_id = str(uuid.uuid4())
    session = _issue_jwt(user_id)

    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get(
        "/protected",
        headers={"Authorization": f"Bearer {session.access_token}"},
    )
    assert resp.status_code == 200
    claims = resp.json()["claims"]
    assert claims["sub"] == user_id


def test_user_claims_stored_in_request_state():
    """Decoded claims are stored in request.state.user_claims (Req 1.6)."""
    user_id = str(uuid.uuid4())
    session = _issue_jwt(user_id)

    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get(
        "/protected",
        headers={"Authorization": f"Bearer {session.access_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "claims" in data
    assert data["claims"]["sub"] == user_id

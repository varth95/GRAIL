"""Tests for Task 2.2: user profile creation and retrieval.

Covers:
- GET /users/me returns 401 when no/invalid token
- GET /users/me returns 404 when user not found
- GET /users/me returns user profile including vault_ready
- validate_token creates new user with vault_ready=False on first login
- validate_token returns existing user without duplication on returning login

Requirements: 1.4, 1.5
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models import SessionToken, User
from app.routers.user_router import router, _extract_user_id
from app.services.auth_service import _issue_jwt


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_user(vault_ready: bool = False) -> User:
    return User(
        id=uuid.uuid4(),
        google_id="g_test_123",
        email="test@example.com",
        display_name="Test User",
        avatar_url="",
        created_at=datetime.now(timezone.utc),
        last_login_at=datetime.now(timezone.utc),
        vault_ready=vault_ready,
    )


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


# ── _extract_user_id unit tests ───────────────────────────────────────────────

def test_extract_user_id_missing_bearer_raises():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        _extract_user_id("Token abc123")
    assert exc_info.value.status_code == 401


def test_extract_user_id_invalid_token_raises():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        _extract_user_id("Bearer not.a.valid.jwt")
    assert exc_info.value.status_code == 401


def test_extract_user_id_valid_token():
    user_id = str(uuid.uuid4())
    session = _issue_jwt(user_id)
    result = _extract_user_id(f"Bearer {session.access_token}")
    assert result == user_id


# ── GET /users/me endpoint tests ──────────────────────────────────────────────

def test_get_me_missing_authorization():
    app = _make_app()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/users/me")
    assert resp.status_code == 422  # FastAPI validation: required header missing


def test_get_me_invalid_token():
    app = _make_app()

    async def override_db():
        yield MagicMock()

    app.dependency_overrides = {}
    from app.db.session import get_db
    app.dependency_overrides[get_db] = override_db

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/users/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code == 401


def test_get_me_user_not_found():
    app = _make_app()
    user_id = str(uuid.uuid4())
    session = _issue_jwt(user_id)

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def override_db():
        yield mock_session

    from app.db.session import get_db
    app.dependency_overrides[get_db] = override_db

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/users/me", headers={"Authorization": f"Bearer {session.access_token}"})
    assert resp.status_code == 404


def test_get_me_returns_user_profile():
    app = _make_app()
    user = _make_user(vault_ready=False)
    session = _issue_jwt(str(user.id))

    # Build a mock ORM object that mirrors the User fields
    mock_orm = MagicMock()
    mock_orm.id = user.id
    mock_orm.google_id = user.google_id
    mock_orm.email = user.email
    mock_orm.display_name = user.display_name
    mock_orm.avatar_url = user.avatar_url
    mock_orm.created_at = user.created_at
    mock_orm.last_login_at = user.last_login_at
    mock_orm.vault_ready = user.vault_ready

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_orm
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def override_db():
        yield mock_session

    from app.db.session import get_db
    app.dependency_overrides[get_db] = override_db

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/users/me", headers={"Authorization": f"Bearer {session.access_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == user.email
    assert data["vault_ready"] is False
    assert "id" in data


def test_get_me_vault_ready_true_reflected():
    app = _make_app()
    user = _make_user(vault_ready=True)
    session = _issue_jwt(str(user.id))

    mock_orm = MagicMock()
    mock_orm.id = user.id
    mock_orm.google_id = user.google_id
    mock_orm.email = user.email
    mock_orm.display_name = user.display_name
    mock_orm.avatar_url = user.avatar_url
    mock_orm.created_at = user.created_at
    mock_orm.last_login_at = user.last_login_at
    mock_orm.vault_ready = True

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_orm
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def override_db():
        yield mock_session

    from app.db.session import get_db
    app.dependency_overrides[get_db] = override_db

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/users/me", headers={"Authorization": f"Bearer {session.access_token}"})
    assert resp.status_code == 200
    assert resp.json()["vault_ready"] is True


# ── validate_token upsert logic tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_validate_token_creates_user_on_first_login():
    """Req 1.4: first login creates a new User with vault_ready=False."""
    google_claims = {
        "sub": "google_new_user",
        "email": "new@example.com",
        "name": "New User",
        "picture": "",
    }

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # no existing user
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    created_orm = None

    def capture_add(obj):
        nonlocal created_orm
        created_orm = obj

    mock_db.add.side_effect = capture_add

    async def fake_refresh(obj):
        # Simulate DB assigning an id
        if not hasattr(obj, '_id_set'):
            obj.id = uuid.uuid4()
            obj._id_set = True

    mock_db.refresh = fake_refresh

    from app.services.auth_service import validate_token
    with patch("app.services.auth_service._verify_google_id_token", return_value=google_claims):
        session_token, user = await validate_token("fake_id_token", mock_db)

    assert user.vault_ready is False
    assert user.email == "new@example.com"
    assert isinstance(session_token, SessionToken)
    mock_db.add.assert_called_once()


@pytest.mark.asyncio
async def test_validate_token_returns_existing_user_on_returning_login():
    """Req 1.5: returning login returns existing profile without duplication."""
    existing_id = uuid.uuid4()
    google_claims = {
        "sub": "google_existing_user",
        "email": "existing@example.com",
        "name": "Existing User",
        "picture": "",
    }

    existing_orm = MagicMock()
    existing_orm.id = existing_id
    existing_orm.google_id = "google_existing_user"
    existing_orm.email = "existing@example.com"
    existing_orm.display_name = "Existing User"
    existing_orm.avatar_url = ""
    existing_orm.vault_ready = False
    existing_orm.created_at = datetime.now(timezone.utc)
    existing_orm.last_login_at = datetime.now(timezone.utc)

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_orm
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    from app.services.auth_service import validate_token
    with patch("app.services.auth_service._verify_google_id_token", return_value=google_claims):
        session_token, user = await validate_token("fake_id_token", mock_db)

    # Should NOT call db.add (no new user created)
    mock_db.add.assert_not_called()
    assert user.email == "existing@example.com"
    assert isinstance(session_token, SessionToken)

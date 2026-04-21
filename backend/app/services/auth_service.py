"""Auth Service: Google OAuth 2.0 validation and JWT session management.

Implements:
- initiate_oauth()        → OAuth redirect URL
- validate_token()        → SessionToken (verifies Google ID token, issues JWT)
- revoke_session()        → None (invalidates session token)
- refresh_session()       → SessionToken

Requirements: 1.1, 1.2, 1.3, 1.6, 1.7, 9.1, 9.5
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import httpx
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.orm_models import UserORM
from app.models import SessionToken, User

# ── Google JWKS ───────────────────────────────────────────────────────────────

GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URI = "https://www.googleapis.com/oauth2/v3/userinfo"

# ── In-memory revocation store (production: Redis) ────────────────────────────
# Stores JTI (JWT ID) or raw token strings that have been revoked.
_revoked_tokens: set[str] = set()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_signing_key() -> tuple[str, str]:
    """Return (key_material, algorithm) for JWT signing.

    Uses RS256 when an RSA private key PEM is configured via ``settings.secret_key``.
    Falls back to HS256 with the raw secret for dev/test environments where no
    RSA key is available.
    """
    key = settings.secret_key
    algo = settings.algorithm  # "RS256" by default

    # Detect whether the configured key is a PEM-encoded RSA private key.
    if algo == "RS256" and key.strip().startswith("-----BEGIN"):
        return key, "RS256"

    # Fallback: use HS256 so tests/dev work without a real RSA key pair.
    return key, "HS256"


def _issue_jwt(subject: str, extra_claims: dict[str, Any] | None = None) -> SessionToken:
    """Create and sign a JWT session token for *subject* (user UUID string)."""
    key, algo = _get_signing_key()
    expire_seconds = settings.access_token_expire_minutes * 60
    now = int(time.time())

    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + expire_seconds,
        "aud": settings.google_client_id or "grail",
    }
    if extra_claims:
        payload.update(extra_claims)

    token = jwt.encode(payload, key, algorithm=algo)
    return SessionToken(access_token=token, token_type="bearer", expires_in=expire_seconds)


async def _fetch_google_jwks() -> dict[str, Any]:
    """Fetch Google's public JWKS for ID-token verification."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(GOOGLE_JWKS_URI, timeout=10.0)
        resp.raise_for_status()
        return resp.json()


async def _verify_google_id_token(id_token: str) -> dict[str, Any]:
    """Verify a Google ID token and return its claims.

    Raises:
        ValueError: if the token is invalid, expired, or audience mismatch.
    """
    jwks = await _fetch_google_jwks()

    try:
        # python-jose accepts a JWKS dict directly.
        claims = jwt.decode(
            id_token,
            jwks,
            algorithms=["RS256"],
            audience=settings.google_client_id or None,
            options={"verify_aud": bool(settings.google_client_id)},
        )
    except ExpiredSignatureError as exc:
        raise ValueError("Google ID token has expired") from exc
    except JWTError as exc:
        raise ValueError(f"Google ID token validation failed: {exc}") from exc

    return claims


# ── Public API ────────────────────────────────────────────────────────────────

def initiate_oauth() -> str:
    """Return the Google OAuth 2.0 authorization URL.

    The client should redirect the user to this URL to begin the OAuth flow.
    Requirement 1.1.
    """
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


async def validate_token(id_token: str, db: AsyncSession) -> tuple[SessionToken, User]:
    """Validate a Google ID token and issue a signed JWT session token.

    On first login creates a new User profile (vault_ready=False).
    On returning login returns the existing profile.

    Requirements: 1.2, 1.3, 1.4, 1.5, 9.1.

    Raises:
        ValueError: if the Google ID token is invalid or expired.
    """
    claims = await _verify_google_id_token(id_token)

    google_id: str = claims["sub"]
    email: str = claims.get("email", "")
    display_name: str = claims.get("name", email)
    avatar_url: str = claims.get("picture", "")

    # Upsert user profile (Req 1.4, 1.5).
    result = await db.execute(select(UserORM).where(UserORM.google_id == google_id))
    user_orm: UserORM | None = result.scalar_one_or_none()

    if user_orm is None:
        # First login — create new profile.
        user_orm = UserORM(
            google_id=google_id,
            email=email,
            display_name=display_name,
            avatar_url=avatar_url,
            vault_ready=False,
            created_at=datetime.now(timezone.utc),
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(user_orm)
    else:
        # Returning login — update last_login_at only.
        user_orm.last_login_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(user_orm)

    user = User.model_validate(user_orm)
    session_token = _issue_jwt(str(user_orm.id))
    return session_token, user


async def revoke_session(session_token: str) -> None:
    """Invalidate a session token so it cannot be used again.

    Adds the token to the in-memory revocation set.
    Production deployments should store revoked JTIs in Redis with TTL.

    Requirements: 1.7, 9.5.
    """
    _revoked_tokens.add(session_token)


def is_token_revoked(session_token: str) -> bool:
    """Return True if *session_token* has been revoked."""
    return session_token in _revoked_tokens


async def refresh_session(refresh_token: str, db: AsyncSession) -> SessionToken:
    """Exchange a refresh token for a new session token.

    For simplicity this implementation re-validates the existing JWT (treating
    it as a long-lived refresh token) and issues a fresh access token.

    Requirements: 1.6.

    Raises:
        ValueError: if the refresh token is invalid or revoked.
    """
    if is_token_revoked(refresh_token):
        raise ValueError("Refresh token has been revoked")

    key, algo = _get_signing_key()
    try:
        payload = jwt.decode(
            refresh_token,
            key,
            algorithms=[algo],
            audience=settings.google_client_id or "grail",
            options={"verify_aud": bool(settings.google_client_id)},
        )
    except JWTError as exc:
        raise ValueError(f"Invalid refresh token: {exc}") from exc

    user_id: str = payload.get("sub", "")
    if not user_id:
        raise ValueError("Refresh token missing subject claim")

    return _issue_jwt(user_id)


def decode_session_token(session_token: str) -> dict[str, Any]:
    """Decode and validate a session JWT.  Returns the claims dict.

    Raises:
        ValueError: if the token is invalid, expired, or revoked.
    """
    if is_token_revoked(session_token):
        raise ValueError("Token has been revoked")

    key, algo = _get_signing_key()
    try:
        claims = jwt.decode(
            session_token,
            key,
            algorithms=[algo],
            audience=settings.google_client_id or "grail",
            options={"verify_aud": bool(settings.google_client_id)},
        )
    except ExpiredSignatureError as exc:
        raise ValueError("Session token has expired") from exc
    except JWTError as exc:
        raise ValueError(f"Invalid session token: {exc}") from exc

    return claims

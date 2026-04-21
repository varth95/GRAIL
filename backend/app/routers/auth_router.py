"""Auth router: Google OAuth 2.0 endpoints.

Routes:
  GET  /auth/google           → redirect to Google OAuth consent screen
  GET  /auth/google/callback  → exchange code for tokens, issue JWT
  POST /auth/logout           → revoke current session

Requirements: 1.1, 1.2, 1.3, 1.6, 1.7, 9.1, 9.5
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.models import SessionToken, User
from app.services.auth_service import (
    GOOGLE_TOKEN_URI,
    initiate_oauth,
    revoke_session,
    validate_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ── GET /auth/google ──────────────────────────────────────────────────────────

@router.get("/google", summary="Initiate Google OAuth 2.0 flow")
async def google_login() -> RedirectResponse:
    """Redirect the user to Google's OAuth 2.0 consent screen.

    Requirement 1.1.
    """
    redirect_url = initiate_oauth()
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


# ── GET /auth/google/callback ─────────────────────────────────────────────────

@router.get(
    "/google/callback",
    response_model=SessionToken,
    summary="Handle Google OAuth 2.0 callback",
)
async def google_callback(
    code: str = Query(..., description="Authorization code returned by Google"),
    db: AsyncSession = Depends(get_db),
) -> SessionToken:
    """Exchange the authorization code for a Google ID token, validate it,
    and issue a signed JWT session token.

    Requirements: 1.2, 1.3, 1.4, 1.5, 9.1.
    """
    # Exchange authorization code for tokens.
    async with httpx.AsyncClient() as client:
        try:
            token_resp = await client.post(
                GOOGLE_TOKEN_URI,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
                timeout=10.0,
            )
            token_resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to exchange authorization code with Google",
            ) from exc

    token_data = token_resp.json()
    id_token: str | None = token_data.get("id_token")
    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google did not return an ID token",
        )

    try:
        session_token, _user = await validate_token(id_token, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    return session_token


# ── POST /auth/logout ─────────────────────────────────────────────────────────

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke session")
async def logout(
    authorization: str = Header(..., description="Bearer <session_token>"),
) -> None:
    """Revoke the current session token.

    Requirements: 1.7, 9.5.
    """
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must use Bearer scheme",
        )
    token = authorization[len("bearer "):].strip()
    await revoke_session(token)

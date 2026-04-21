"""User router: current user profile endpoint.

Routes:
  GET /users/me → return the authenticated user's profile

Requirements: 1.4, 1.5
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.orm_models import UserORM
from app.db.session import get_db
from app.models import User
from app.services.auth_service import decode_session_token

router = APIRouter(prefix="/users", tags=["users"])


def _extract_user_id(authorization: str) -> str:
    """Parse Bearer token from Authorization header and return the subject claim."""
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must use Bearer scheme",
        )
    token = authorization[len("bearer "):].strip()
    try:
        claims = decode_session_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    return claims["sub"]


@router.get("/me", response_model=User, summary="Get current user profile")
async def get_current_user(
    authorization: str = Header(..., description="Bearer <session_token>"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Return the authenticated user's profile including vault_ready status.

    Requirements: 1.4, 1.5.
    """
    user_id = _extract_user_id(authorization)

    result = await db.execute(select(UserORM).where(UserORM.id == user_id))
    user_orm: UserORM | None = result.scalar_one_or_none()

    if user_orm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return User.model_validate(user_orm)

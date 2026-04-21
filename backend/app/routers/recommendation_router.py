"""Recommendation router: outfit generation and missing-link endpoints.

Routes:
  POST /recommend/outfits       → ranked OutfitSet list for a user
  POST /recommend/missing-links → ranked MissingLinkItem list for a user

Requirements: 4.1–4.7, 6.1–6.5
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.orm_models import GarmentItemORM
from app.db.session import get_db
from app.models import GarmentItem, MissingLinkItem, OutfitSet, TrendSignal
from app.services.recommendation_engine import find_missing_links, generate_outfits
from app.services.trend_service import fetch_trends

router = APIRouter(prefix="/recommend", tags=["recommend"])


class RecommendRequest(BaseModel):
    user_id: UUID


async def _fetch_wardrobe(user_id: UUID, db: AsyncSession) -> list[GarmentItem]:
    result = await db.execute(
        select(GarmentItemORM).where(GarmentItemORM.user_id == user_id)
    )
    return [GarmentItem.model_validate(row) for row in result.scalars().all()]


def _fetch_trends_safe() -> list[TrendSignal]:
    """Fetch trends, falling back to empty list on any exception. Req 4.7"""
    try:
        return fetch_trends("global", date.today())
    except Exception:
        return []


@router.post("/outfits", response_model=list[OutfitSet], summary="Generate ranked outfit sets")
async def recommend_outfits(
    body: RecommendRequest,
    db: AsyncSession = Depends(get_db),
) -> list[OutfitSet]:
    """Requirements: 4.1–4.7"""
    wardrobe = await _fetch_wardrobe(body.user_id, db)
    trends = _fetch_trends_safe()
    return generate_outfits(wardrobe, trends)


@router.post("/missing-links", response_model=list[MissingLinkItem], summary="Return missing-link suggestions")
async def recommend_missing_links(
    body: RecommendRequest,
    db: AsyncSession = Depends(get_db),
) -> list[MissingLinkItem]:
    """Requirements: 6.1–6.5"""
    wardrobe = await _fetch_wardrobe(body.user_id, db)
    trends = _fetch_trends_safe()
    return find_missing_links(wardrobe, trends)

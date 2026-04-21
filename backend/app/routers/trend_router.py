"""Trend router: exposes trend signal data to clients.

Routes:
  GET /trends → fetch and return trend signals with staleness indicator

Requirements: 7.3, 7.4
"""

from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Query

from app.models import TrendSignal
from app.services.trend_service import CACHE_TTL, _cache, fetch_trends, is_cache_stale

router = APIRouter(prefix="/trends", tags=["trends"])


@router.get("", summary="Get current trend signals")
async def get_trends(
    region: str = Query(default="global", description="Region for trend signals"),
    date: date_type = Query(default=None, description="Date for trend signals"),
) -> dict:
    """Return trend signals with a staleness indicator.

    - trends_stale=True when data is older than 6 hours or fetch fails.
    - On fetch failure: return cached data with trends_stale=True.
    - If no cache on failure: return empty list with trends_stale=True.

    Requirements: 7.3, 7.4
    """
    if date is None:
        date = date_type.today()

    stale = False
    trends: list[TrendSignal] = []

    try:
        trends = fetch_trends(region, date)
        stale = is_cache_stale(region, date)
    except Exception:
        # Fetch failed — try to return cached data
        stale = True
        cache_key = f"{region}:{date}"
        cached = _cache.get(cache_key)
        if cached is not None:
            _, trends = cached
        else:
            trends = []

    return {
        "trends": [t.model_dump() for t in trends],
        "trends_stale": stale,
    }

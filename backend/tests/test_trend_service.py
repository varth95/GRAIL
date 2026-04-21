"""Tests for trend_service: caching behaviour and get_trend_score.

Requirements: 7.1, 7.2, 7.3
"""

from __future__ import annotations

import time
from datetime import date
from unittest.mock import patch

import pytest

from app.services.trend_service import (
    CACHE_TTL,
    _cache,
    clear_cache,
    fetch_trends,
    get_trend_score,
)


@pytest.fixture(autouse=True)
def reset_cache():
    """Ensure a clean cache state before every test."""
    clear_cache()
    yield
    clear_cache()


# ── Cache behaviour ───────────────────────────────────────────────────────────

def test_cache_miss_populates_cache():
    """First call should populate the cache."""
    today = date.today()
    signals = fetch_trends("global", today)
    assert len(signals) == 3
    assert f"global:{today}" in _cache


def test_cache_hit_within_ttl_returns_same_data():
    """Second call within TTL must return the identical list without re-fetching."""
    today = date.today()
    first = fetch_trends("global", today)

    # Patch _stub_signals so a re-fetch would return different data
    with patch("app.services.trend_service._stub_signals") as mock_stub:
        mock_stub.return_value = []  # would return empty if re-fetched
        second = fetch_trends("global", today)

    # Cache hit — stub was NOT called again
    mock_stub.assert_not_called()
    assert first is second  # same list object from cache


def test_cache_miss_after_ttl_refetches():
    """After TTL expires the service should re-fetch."""
    today = date.today()
    fetch_trends("global", today)

    # Backdate the cache timestamp to simulate expiry
    cache_key = f"global:{today}"
    ts, signals = _cache[cache_key]
    _cache[cache_key] = (ts - CACHE_TTL - 1, signals)

    with patch("app.services.trend_service._stub_signals") as mock_stub:
        mock_stub.return_value = signals  # return same data for simplicity
        fetch_trends("global", today)

    mock_stub.assert_called_once()


def test_different_regions_cached_separately():
    """Each region+date combination should have its own cache entry."""
    today = date.today()
    fetch_trends("us", today)
    fetch_trends("eu", today)
    assert f"us:{today}" in _cache
    assert f"eu:{today}" in _cache


# ── get_trend_score ───────────────────────────────────────────────────────────

def test_get_trend_score_no_match_returns_zero():
    """Unknown category and color should return 0.0."""
    fetch_trends("global", date.today())  # populate _latest_signals
    score = get_trend_score("Footwear - Boots", "#FFFFFF")
    assert score == 0.0


def test_get_trend_score_exact_match_returns_positive():
    """Matching category substring and exact color_hex should return > 0."""
    fetch_trends("global", date.today())
    # "Trousers" is a substring of "Lower Body - Trousers"
    score = get_trend_score("Trousers", "#3D5A80")
    assert score > 0.0


def test_get_trend_score_case_insensitive_category():
    """Category matching should be case-insensitive."""
    fetch_trends("global", date.today())
    score_lower = get_trend_score("trousers", "#3D5A80")
    score_upper = get_trend_score("TROUSERS", "#3D5A80")
    assert score_lower == score_upper
    assert score_lower > 0.0


def test_get_trend_score_wrong_color_returns_zero():
    """Correct category but wrong color should return 0.0."""
    fetch_trends("global", date.today())
    score = get_trend_score("Trousers", "#000000")
    assert score == 0.0


def test_get_trend_score_returns_max_on_multiple_matches():
    """When multiple signals match, the highest score should be returned."""
    from app.models import TrendSignal
    import app.services.trend_service as svc

    svc._latest_signals = [
        TrendSignal(category="Upper Torso - Jacket", color_hex="#AABBCC", score=0.5, color_name="X"),
        TrendSignal(category="Upper Torso - Jacket", color_hex="#AABBCC", score=0.9, color_name="Y"),
    ]
    score = get_trend_score("Jacket", "#AABBCC")
    assert score == pytest.approx(0.9)

"""Trend Service: ingestion, caching, and scoring of fashion trend signals.

Requirements: 7.1, 7.2, 7.3
"""

from __future__ import annotations

import time
from datetime import date, datetime

from app.models import TrendSignal

# ── Cache ─────────────────────────────────────────────────────────────────────

CACHE_TTL: float = 6 * 3600  # 6 hours in seconds

# key: "{region}:{date}"  →  value: (timestamp, signals)
_cache: dict[str, tuple[float, list[TrendSignal]]] = {}

# Holds the most recently fetched signals for get_trend_score lookups
_latest_signals: list[TrendSignal] = []


# ── Stub data ─────────────────────────────────────────────────────────────────

def _stub_signals() -> list[TrendSignal]:
    """Return a hardcoded list of realistic trend signals."""
    return [
        TrendSignal(
            category="Lower Body - Trousers",
            color_hex="#3D5A80",
            color_name="Steel Blue",
            score=0.88,
            source="Instagram",
        ),
        TrendSignal(
            category="Upper Torso - Jacket",
            color_hex="#C8A96E",
            color_name="Warm Camel",
            score=0.76,
            source="Pinterest",
        ),
        TrendSignal(
            category="Upper Torso - T-Shirt",
            color_hex="#E8D5B7",
            color_name="Oat Cream",
            score=0.65,
            source="TikTok",
        ),
    ]


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_trends(region: str, date: date) -> list[TrendSignal]:
    """Fetch trend signals for a region/date, using a 6-hour server-side cache.

    Requirements: 7.1, 7.2, 7.3
    """
    global _latest_signals

    cache_key = f"{region}:{date}"
    now = time.time()

    cached = _cache.get(cache_key)
    if cached is not None:
        ts, signals = cached
        if now - ts < CACHE_TTL:
            return signals

    # Cache miss or expired — fetch fresh data (stub)
    signals = _stub_signals()
    _cache[cache_key] = (now, signals)
    _latest_signals = signals
    return signals


def get_trend_score(category: str, color_hex: str) -> float:
    """Return a trend score in [0.0, 1.0] for the given category and color.

    Matches against the latest cached trend signals.
    - category match: case-insensitive substring
    - color_hex match: exact
    - Multiple matches: return max score
    - No match: return 0.0

    Requirements: 7.2
    """
    best = 0.0
    for signal in _latest_signals:
        category_match = category.lower() in signal.category.lower()
        color_match = signal.color_hex == color_hex
        if category_match and color_match:
            best = max(best, signal.score)
    return best


def is_cache_stale(region: str, date: date) -> bool:
    """Return True if the cache entry is missing or older than TTL."""
    cache_key = f"{region}:{date}"
    cached = _cache.get(cache_key)
    if cached is None:
        return True
    ts, _ = cached
    return (time.time() - ts) >= CACHE_TTL


def clear_cache() -> None:
    """Clear all cached trend data (used in tests)."""
    global _latest_signals
    _cache.clear()
    _latest_signals = []

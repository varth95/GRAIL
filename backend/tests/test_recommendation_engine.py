"""Tests for recommendation_engine: outfit generation and missing-link detection.

Requirements: 4.1–4.7, 6.1–6.5
"""

from __future__ import annotations

from uuid import uuid4

from app.config import MIN_UNLOCK_THRESHOLD
from app.models import GarmentCategory, GarmentItem, TrendSignal
from app.services.recommendation_engine import (
    compute_trend_score,
    compute_unlock_count,
    find_missing_links,
    generate_outfits,
)

USER_ID = uuid4()


def make_upper(color_hex: str = "#FF0000", sub_category: str = "T-Shirt") -> GarmentItem:
    return GarmentItem(
        user_id=USER_ID,
        image_url="http://example.com/img.jpg",
        category=GarmentCategory.UPPER_TORSO,
        sub_category=sub_category,
        color_hex=color_hex,
        color_pending=False,
    )


def make_lower(color_hex: str = "#0000FF", sub_category: str = "Jeans") -> GarmentItem:
    return GarmentItem(
        user_id=USER_ID,
        image_url="http://example.com/img.jpg",
        category=GarmentCategory.LOWER_BODY,
        sub_category=sub_category,
        color_hex=color_hex,
        color_pending=False,
    )


def make_trend(category: str = "Upper Torso - T-Shirt", color_hex: str = "#FF0000", score: float = 0.8) -> TrendSignal:
    return TrendSignal(category=category, color_hex=color_hex, color_name="Red", score=score)


# ── compute_trend_score ───────────────────────────────────────────────────────

def test_compute_trend_score_empty_trends_returns_zero():
    assert compute_trend_score(make_upper(), make_lower(), []) == 0.0


def test_compute_trend_score_matching_upper():
    upper = make_upper(color_hex="#FF0000", sub_category="T-Shirt")
    lower = make_lower(color_hex="#0000FF")
    trend = make_trend(category="Upper Torso - T-Shirt", color_hex="#FF0000", score=0.8)
    score = compute_trend_score(upper, lower, [trend])
    assert abs(score - 0.4) < 1e-6


def test_compute_trend_score_both_match():
    upper = make_upper(color_hex="#FF0000", sub_category="T-Shirt")
    lower = make_lower(color_hex="#0000FF", sub_category="Jeans")
    trends = [
        make_trend(category="Upper Torso - T-Shirt", color_hex="#FF0000", score=0.8),
        make_trend(category="Lower Body - Jeans", color_hex="#0000FF", score=0.6),
    ]
    score = compute_trend_score(upper, lower, trends)
    assert abs(score - 0.7) < 1e-6


def test_compute_trend_score_in_range():
    score = compute_trend_score(make_upper(), make_lower(), [make_trend(score=1.0)])
    assert 0.0 <= score <= 1.0


# ── generate_outfits ──────────────────────────────────────────────────────────

def test_generate_outfits_empty_wardrobe_returns_empty():
    assert generate_outfits([], []) == []


def test_generate_outfits_no_upper_returns_empty():
    assert generate_outfits([make_lower()], []) == []


def test_generate_outfits_no_lower_returns_empty():
    assert generate_outfits([make_upper()], []) == []


def test_generate_outfits_cartesian_product_count():
    n, m = 3, 4
    wardrobe = [make_upper(f"#FF{i:02X}00") for i in range(n)] + [make_lower(f"#0000{i:02X}") for i in range(m)]
    assert len(generate_outfits(wardrobe, [])) == n * m


def test_generate_outfits_1x1():
    assert len(generate_outfits([make_upper(), make_lower()], [])) == 1


def test_generate_outfits_scores_in_range():
    wardrobe = [make_upper("#FF0000"), make_upper("#00FF00"), make_lower("#0000FF"), make_lower("#FFFF00")]
    outfits = generate_outfits(wardrobe, [make_trend(score=0.9)])
    for outfit in outfits:
        assert 0.0 <= outfit.total_score <= 1.0
        assert 0.0 <= outfit.trend_score <= 1.0
        assert 0.0 <= outfit.harmony_score <= 1.0


def test_generate_outfits_sorted_descending():
    wardrobe = [make_upper(), make_upper("#00FF00"), make_lower(), make_lower("#FFFF00")]
    outfits = generate_outfits(wardrobe, [])
    scores = [o.total_score for o in outfits]
    assert scores == sorted(scores, reverse=True)


def test_generate_outfits_skips_color_pending():
    upper_pending = GarmentItem(
        user_id=USER_ID,
        image_url="http://example.com/img.jpg",
        category=GarmentCategory.UPPER_TORSO,
        color_hex="",
        color_pending=True,
    )
    assert generate_outfits([upper_pending, make_lower()], []) == []


def test_generate_outfits_category_pairing():
    wardrobe = [make_upper(), make_upper("#00FF00"), make_lower(), make_lower("#FFFF00")]
    outfits = generate_outfits(wardrobe, [])
    for outfit in outfits:
        assert outfit.upper_item.category == GarmentCategory.UPPER_TORSO
        assert outfit.lower_item.category == GarmentCategory.LOWER_BODY


# ── compute_unlock_count ──────────────────────────────────────────────────────

def test_compute_unlock_count_empty_wardrobe():
    assert compute_unlock_count(make_trend(category="Lower Body - Jeans"), []) == 0


def test_compute_unlock_count_no_complementary():
    gap = make_trend(category="Lower Body - Jeans")
    assert compute_unlock_count(gap, [make_lower()]) == 0


def test_compute_unlock_count_with_complementary():
    gap = make_trend(category="Lower Body - Jeans")
    wardrobe = [make_upper("#FF0000"), make_upper("#00FF00"), make_lower()]
    assert compute_unlock_count(gap, wardrobe) == 2


def test_compute_unlock_count_skips_pending():
    gap = make_trend(category="Lower Body - Jeans")
    upper_pending = GarmentItem(
        user_id=USER_ID,
        image_url="http://example.com/img.jpg",
        category=GarmentCategory.UPPER_TORSO,
        color_hex="",
        color_pending=True,
    )
    assert compute_unlock_count(gap, [upper_pending, make_upper("#FF0000")]) == 1


def test_compute_unlock_count_upper_gap():
    gap = make_trend(category="Upper Torso - T-Shirt")
    wardrobe = [make_lower("#0000FF"), make_lower("#00FF00"), make_upper()]
    assert compute_unlock_count(gap, wardrobe) == 2


# ── find_missing_links ────────────────────────────────────────────────────────

def test_find_missing_links_empty_wardrobe_returns_suggestions():
    trends = [make_trend(category="Lower Body - Jeans", score=0.8)]
    result = find_missing_links([], trends)
    assert isinstance(result, list)


def test_find_missing_links_filters_by_min_unlock_threshold():
    trends = [
        make_trend(category="Lower Body - Jeans", color_hex="#0000FF", score=0.8),
        make_trend(category="Upper Torso - Jacket", color_hex="#00FF00", score=0.7),
    ]
    wardrobe = [make_upper("#FF0000")]
    result = find_missing_links(wardrobe, trends)
    for item in result:
        assert item.unlock_count >= MIN_UNLOCK_THRESHOLD


def test_find_missing_links_sorted_by_unlock_count_descending():
    trends = [
        make_trend(category="Lower Body - Jeans", color_hex="#0000FF", score=0.8),
        make_trend(category="Lower Body - Trousers", color_hex="#00FF00", score=0.7),
    ]
    wardrobe = [make_upper("#FF0000"), make_upper("#AABBCC")]
    result = find_missing_links(wardrobe, trends)
    counts = [item.unlock_count for item in result]
    assert counts == sorted(counts, reverse=True)


def test_find_missing_links_excludes_wardrobe_matches():
    trend = make_trend(category="Lower Body - Jeans", color_hex="#0000FF", score=0.9)
    wardrobe = [make_lower("#0000FF"), make_upper("#FF0000")]
    result = find_missing_links(wardrobe, [trend])
    for item in result:
        assert not (item.color_hex == "#0000FF" and item.category == GarmentCategory.LOWER_BODY)


def test_find_missing_links_no_trends_returns_empty():
    assert find_missing_links([make_upper(), make_lower()], []) == []

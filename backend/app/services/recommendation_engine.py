"""Recommendation Engine: outfit generation and missing-link detection.

Requirements: 4.1–4.7, 6.1–6.5
"""

from __future__ import annotations

from app.config import (
    COLOR_MATCH_TOLERANCE,
    HARMONY_WEIGHT,
    MIN_UNLOCK_THRESHOLD,
    TREND_WEIGHT,
)
from app.models import GarmentCategory, GarmentItem, MissingLinkItem, OutfitSet, TrendSignal
from app.utils.color_utils import compute_color_harmony, hex_to_hsl


# ── Internal helpers ──────────────────────────────────────────────────────────

def _hue_distance(hex_a: str, hex_b: str) -> float:
    """Return the circular hue distance (0–180) between two hex colors."""
    hsl_a = hex_to_hsl(hex_a)
    hsl_b = hex_to_hsl(hex_b)
    raw = abs(hsl_a.hue - hsl_b.hue)
    return min(raw, 360.0 - raw)


def _best_trend_score(item: GarmentItem, trends: list[TrendSignal]) -> float:
    """Return the highest matching trend score for a single garment item."""
    best = 0.0
    for signal in trends:
        category_match = item.sub_category.lower() in signal.category.lower()
        color_match = signal.color_hex == item.color_hex
        if category_match and color_match:
            best = max(best, signal.score)
    return best


def _gap_category(trend: TrendSignal) -> GarmentCategory:
    """Infer GarmentCategory from a TrendSignal's category string."""
    if "upper" in trend.category.lower():
        return GarmentCategory.UPPER_TORSO
    return GarmentCategory.LOWER_BODY


# ── Public API ────────────────────────────────────────────────────────────────

def compute_trend_score(
    upper: GarmentItem,
    lower: GarmentItem,
    trends: list[TrendSignal],
) -> float:
    """Compute a trend score [0.0, 1.0] for an upper+lower outfit pair.

    Returns 0.0 if trends list is empty.
    Requirements: 4.3, 4.4
    """
    if not trends:
        return 0.0
    upper_score = _best_trend_score(upper, trends)
    lower_score = _best_trend_score(lower, trends)
    raw = (upper_score + lower_score) / 2.0
    return max(0.0, min(1.0, raw))


def generate_outfits(
    wardrobe: list[GarmentItem],
    trends: list[TrendSignal],
) -> list[OutfitSet]:
    """Generate all valid upper×lower outfit combinations, ranked by total_score.

    Returns empty list if no upper or lower items exist.
    Requirements: 4.1–4.6
    """
    upper_items = [
        g for g in wardrobe
        if g.category == GarmentCategory.UPPER_TORSO and not g.color_pending
    ]
    lower_items = [
        g for g in wardrobe
        if g.category == GarmentCategory.LOWER_BODY and not g.color_pending
    ]

    if not upper_items or not lower_items:
        return []

    outfits: list[OutfitSet] = []
    for upper in upper_items:
        for lower in lower_items:
            trend_score = compute_trend_score(upper, lower, trends)
            harmony_score = compute_color_harmony(upper.color_hex, lower.color_hex)
            total_score = max(0.0, min(1.0,
                (trend_score * TREND_WEIGHT) + (harmony_score * HARMONY_WEIGHT)
            ))
            outfits.append(OutfitSet(
                user_id=upper.user_id,
                upper_item=upper,
                lower_item=lower,
                trend_score=trend_score,
                harmony_score=harmony_score,
                total_score=total_score,
            ))

    outfits.sort(key=lambda o: o.total_score, reverse=True)
    return outfits


def compute_unlock_count(gap: TrendSignal, wardrobe: list[GarmentItem]) -> int:
    """Count new outfit combinations the gap item would enable.

    Returns 0 if wardrobe is empty or no complementary items exist.
    Requirements: 6.1, 6.2
    """
    if not wardrobe:
        return 0

    gap_cat = _gap_category(gap)
    opposite = (
        GarmentCategory.LOWER_BODY
        if gap_cat == GarmentCategory.UPPER_TORSO
        else GarmentCategory.UPPER_TORSO
    )
    return sum(1 for g in wardrobe if g.category == opposite and not g.color_pending)


def find_missing_links(
    wardrobe: list[GarmentItem],
    trends: list[TrendSignal],
) -> list[MissingLinkItem]:
    """Identify trending items not present in wardrobe and rank by unlock potential.

    Requirements: 6.1–6.5
    """
    from uuid import uuid4
    user_id = wardrobe[0].user_id if wardrobe else uuid4()

    candidate_gaps: list[TrendSignal] = []
    for trend in trends:
        trend_cat = _gap_category(trend)
        match_found = False
        for item in wardrobe:
            if item.category != trend_cat or item.color_pending:
                continue
            try:
                dist = _hue_distance(item.color_hex, trend.color_hex)
            except ValueError:
                continue
            if dist <= COLOR_MATCH_TOLERANCE:
                match_found = True
                break
        if not match_found:
            candidate_gaps.append(trend)

    missing_links: list[MissingLinkItem] = []
    for gap in candidate_gaps:
        unlock_count = compute_unlock_count(gap, wardrobe)
        if unlock_count >= MIN_UNLOCK_THRESHOLD:
            missing_links.append(MissingLinkItem(
                user_id=user_id,
                suggested_item=f"{gap.color_name} {gap.category}",
                category=_gap_category(gap),
                color_hex=gap.color_hex,
                unlock_count=unlock_count,
                trend_score=gap.score,
            ))

    missing_links.sort(key=lambda m: m.unlock_count, reverse=True)
    return missing_links

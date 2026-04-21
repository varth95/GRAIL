"""Smoke tests for Task 1: project scaffold and shared foundations."""

import re
import uuid
from datetime import datetime

import pytest

from app.config import (
    COLOR_CONFIDENCE_THRESHOLD,
    COLOR_MATCH_TOLERANCE,
    HARMONY_WEIGHT,
    MAX_IMAGE_SIZE,
    MIN_UNLOCK_THRESHOLD,
    SIGNED_URL_EXPIRY_SECONDS,
    TREND_WEIGHT,
)
from app.models import (
    GarmentCategory,
    GarmentItem,
    MissingLinkItem,
    OutfitSet,
    TrendSignal,
    User,
)

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


# ── Config constants ──────────────────────────────────────────────────────────

def test_constants_types_and_ranges():
    assert 0.0 < COLOR_CONFIDENCE_THRESHOLD < 1.0
    assert MIN_UNLOCK_THRESHOLD >= 1
    assert COLOR_MATCH_TOLERANCE > 0
    assert TREND_WEIGHT + HARMONY_WEIGHT == pytest.approx(1.0)
    assert MAX_IMAGE_SIZE > 0
    assert SIGNED_URL_EXPIRY_SECONDS <= 900  # must be ≤ 15 minutes (Req 9.3)


# ── Pydantic models ───────────────────────────────────────────────────────────

def test_user_defaults():
    user = User(google_id="g123", email="a@b.com", display_name="Alice")
    assert user.vault_ready is False
    assert isinstance(user.id, uuid.UUID)


def test_garment_item_valid_hex():
    item = GarmentItem(
        user_id=uuid.uuid4(),
        image_url="https://example.com/img.jpg",
        category=GarmentCategory.UPPER_TORSO,
        color_hex="#1A2B3C",
    )
    assert HEX_RE.match(item.color_hex)


def test_garment_item_invalid_hex_raises():
    with pytest.raises(Exception):
        GarmentItem(
            user_id=uuid.uuid4(),
            image_url="https://example.com/img.jpg",
            category=GarmentCategory.LOWER_BODY,
            color_hex="ZZZZZZ",
        )


def test_garment_item_color_pending_allows_empty_hex():
    # When color is pending the hex may be empty
    item = GarmentItem(
        user_id=uuid.uuid4(),
        image_url="https://example.com/img.jpg",
        category=GarmentCategory.UPPER_TORSO,
        color_pending=True,
    )
    assert item.color_pending is True
    assert item.color_hex == ""


def test_garment_category_enum_values():
    assert GarmentCategory.UPPER_TORSO.value == "UPPER_TORSO"
    assert GarmentCategory.LOWER_BODY.value == "LOWER_BODY"


def test_outfit_set_score_bounds():
    uid = uuid.uuid4()
    upper = GarmentItem(
        user_id=uid,
        image_url="u.jpg",
        category=GarmentCategory.UPPER_TORSO,
        color_hex="#FFFFFF",
    )
    lower = GarmentItem(
        user_id=uid,
        image_url="l.jpg",
        category=GarmentCategory.LOWER_BODY,
        color_hex="#000000",
    )
    outfit = OutfitSet(
        user_id=uid,
        upper_item=upper,
        lower_item=lower,
        trend_score=0.8,
        harmony_score=0.6,
        total_score=0.7,
    )
    assert 0.0 <= outfit.total_score <= 1.0


def test_missing_link_item_valid():
    item = MissingLinkItem(
        user_id=uuid.uuid4(),
        suggested_item="Tan Chinos",
        category=GarmentCategory.LOWER_BODY,
        color_hex="#C8A96E",
        unlock_count=3,
        trend_score=0.9,
    )
    assert HEX_RE.match(item.color_hex)
    assert item.unlock_count >= 0


def test_trend_signal_valid():
    signal = TrendSignal(
        category="Lower Body - Trousers",
        color_hex="#3D5A80",
        color_name="Steel Blue",
        score=0.85,
        source="Instagram",
    )
    assert HEX_RE.match(signal.color_hex)
    assert 0.0 <= signal.score <= 1.0

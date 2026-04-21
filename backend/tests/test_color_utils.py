"""Tests for color_utils: hex_to_hsl and compute_color_harmony."""

import pytest
from app.utils.color_utils import HSL, compute_color_harmony, hex_to_hsl


# ── hex_to_hsl ────────────────────────────────────────────────────────────────

def test_hex_to_hsl_known_red():
    hsl = hex_to_hsl("#FF0000")
    assert abs(hsl.hue - 0.0) < 1.0
    assert abs(hsl.saturation - 100.0) < 1.0
    assert abs(hsl.lightness - 50.0) < 1.0


def test_hex_to_hsl_known_white():
    hsl = hex_to_hsl("#FFFFFF")
    assert abs(hsl.lightness - 100.0) < 1.0
    assert abs(hsl.saturation - 0.0) < 1.0


def test_hex_to_hsl_known_black():
    hsl = hex_to_hsl("#000000")
    assert abs(hsl.lightness - 0.0) < 1.0
    assert abs(hsl.saturation - 0.0) < 1.0


def test_hex_to_hsl_known_blue():
    # Pure blue: hue=240, sat=100, light=50
    hsl = hex_to_hsl("#0000FF")
    assert abs(hsl.hue - 240.0) < 1.0
    assert abs(hsl.saturation - 100.0) < 1.0
    assert abs(hsl.lightness - 50.0) < 1.0


def test_hex_to_hsl_invalid_raises():
    with pytest.raises(ValueError):
        hex_to_hsl("FF0000")  # missing #
    with pytest.raises(ValueError):
        hex_to_hsl("#GGGGGG")  # invalid chars
    with pytest.raises(ValueError):
        hex_to_hsl("#FFF")  # too short


# ── compute_color_harmony ─────────────────────────────────────────────────────

def test_complementary_pair_score_gte_09():
    # Red (#FF0000, hue≈0) vs Cyan (#00FFFF, hue≈180) → diff≈180 → complementary
    score = compute_color_harmony("#FF0000", "#00FFFF")
    assert score >= 0.9


def test_clashing_pair_score_lte_04():
    # Red (#FF0000, hue=0) vs Chartreuse (#7FFF00, hue≈90.1) → diff≈90.1 → clashing
    score = compute_color_harmony("#FF0000", "#7FFF00")
    assert score <= 0.4


def test_analogous_pair_score_approx_085():
    # Red (#FF0000, hue≈0) vs Orange-red (#FF2000, hue≈8) → diff≈8 → analogous
    score = compute_color_harmony("#FF0000", "#FF2000")
    assert abs(score - 0.85) < 0.05


def test_score_always_in_range():
    pairs = [
        ("#FF0000", "#00FF00"),
        ("#000000", "#FFFFFF"),
        ("#1A2B3C", "#3C2B1A"),
        ("#AABBCC", "#CCBBAA"),
        ("#FF0000", "#00FFFF"),
    ]
    for a, b in pairs:
        score = compute_color_harmony(a, b)
        assert 0.0 <= score <= 1.0, f"Score out of range for {a}, {b}: {score}"


def test_invalid_hex_raises():
    with pytest.raises(ValueError):
        compute_color_harmony("FF0000", "#00FFFF")
    with pytest.raises(ValueError):
        compute_color_harmony("#FF0000", "00FFFF")


def test_lightness_penalty_dark():
    # Two very dark, similar-hue colors → lightDiff < 10, lightness < 20 → penalty 0.2
    # #0A0A0A and #0F0F0F are both near-black (lightness ~4%), hue diff ~0 (analogous base 0.85)
    # Expected: 0.85 - 0.2 = 0.65
    score = compute_color_harmony("#0A0A0A", "#0F0F0F")
    assert abs(score - 0.65) < 0.05


def test_lightness_penalty_light():
    # Two very light, similar-hue colors → lightDiff < 10, lightness > 80 → penalty 0.15
    # #F5F5F5 and #FAFAFA are both near-white (lightness ~96%), hue diff ~0 (analogous base 0.85)
    # Expected: 0.85 - 0.15 = 0.70
    score = compute_color_harmony("#F5F5F5", "#FAFAFA")
    assert abs(score - 0.70) < 0.05

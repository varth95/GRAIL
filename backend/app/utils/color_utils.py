"""Color harmony utilities for the GRail AI Personal Stylist."""

from __future__ import annotations

import re
from typing import NamedTuple

HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class HSL(NamedTuple):
    hue: float        # 0–360
    saturation: float # 0–100
    lightness: float  # 0–100


def hex_to_hsl(hex_color: str) -> HSL:
    """Convert a 6-digit hex color string to HSL."""
    if not HEX_COLOR_RE.match(hex_color):
        raise ValueError(f"hex_color must match #[0-9A-Fa-f]{{6}}, got: {hex_color!r}")

    r = int(hex_color[1:3], 16) / 255.0
    g = int(hex_color[3:5], 16) / 255.0
    b = int(hex_color[5:7], 16) / 255.0

    cmax = max(r, g, b)
    cmin = min(r, g, b)
    delta = cmax - cmin

    # Lightness
    l = (cmax + cmin) / 2.0

    # Saturation
    if delta == 0:
        s = 0.0
    else:
        s = delta / (1.0 - abs(2 * l - 1))

    # Hue
    if delta == 0:
        h = 0.0
    elif cmax == r:
        h = 60.0 * (((g - b) / delta) % 6)
    elif cmax == g:
        h = 60.0 * (((b - r) / delta) + 2)
    else:
        h = 60.0 * (((r - g) / delta) + 4)

    if h < 0:
        h += 360.0

    return HSL(hue=round(h, 4), saturation=round(s * 100, 4), lightness=round(l * 100, 4))


def compute_color_harmony(hex_a: str, hex_b: str) -> float:
    """Compute a harmony score [0.0, 1.0] between two hex colors.

    Scoring rules:
    - complementary (hue diff 150–210°) → base 1.0
    - analogous     (hue diff ≤ 30° or ≥ 330°) → base 0.85
    - clashing      (hue diff 90–150°) → base 0.3
    - neutral       (everything else) → base 0.6

    Lightness penalty:
    - lightDiff < 10 AND lightness < 20 → −0.2
    - lightDiff < 10 AND lightness > 80 → −0.15
    - otherwise → 0.0
    """
    if not HEX_COLOR_RE.match(hex_a):
        raise ValueError(f"hex_a must match #[0-9A-Fa-f]{{6}}, got: {hex_a!r}")
    if not HEX_COLOR_RE.match(hex_b):
        raise ValueError(f"hex_b must match #[0-9A-Fa-f]{{6}}, got: {hex_b!r}")

    hsl_a = hex_to_hsl(hex_a)
    hsl_b = hex_to_hsl(hex_b)

    # Circular hue difference (0–180)
    raw_diff = abs(hsl_a.hue - hsl_b.hue)
    hue_diff = min(raw_diff, 360.0 - raw_diff)

    # Base score from hue bucket
    if 150.0 <= hue_diff <= 210.0:
        base_score = 1.0
    elif hue_diff <= 30.0 or hue_diff >= 330.0:
        base_score = 0.85
    elif 90.0 <= hue_diff <= 150.0:
        base_score = 0.3
    else:
        base_score = 0.6

    # Lightness penalty
    light_diff = abs(hsl_a.lightness - hsl_b.lightness)
    if light_diff < 10 and hsl_a.lightness < 20:
        penalty = 0.2
    elif light_diff < 10 and hsl_a.lightness > 80:
        penalty = 0.15
    else:
        penalty = 0.0

    score = base_score - penalty
    return max(0.0, min(1.0, score))

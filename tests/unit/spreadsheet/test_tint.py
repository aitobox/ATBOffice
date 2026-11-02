"""Unit tests for Excel theme-color tinting (ECMA-376 Part 1 §18.8.3).

Ported from .vibeoffice/tests/ledger/tint.test.js.
"""

from __future__ import annotations

from atboffice.modules.spreadsheet.models.color_utils import (
    apply_tint,
    hsl_to_rgb,
    rgb_to_hsl,
)


def test_rgb_to_hsl_and_back():
    """Verify lossless RGB <-> HSL conversions for primary colors."""
    cases = [
        (255, 0, 0),      # Red
        (0, 255, 0),      # Green
        (0, 0, 255),      # Blue
        (255, 255, 255),  # White
        (0, 0, 0),        # Black
        (128, 128, 128),  # Gray
        (79, 129, 189),   # Excel Accent 1 (#4F81BD)
    ]
    for r, g, b in cases:
        h, s, lum = rgb_to_hsl(r, g, b)
        r2, g2, b2 = hsl_to_rgb(h, s, lum)
        assert abs(r - r2) <= 1
        assert abs(g - g2) <= 1
        assert abs(b - b2) <= 1


def test_lighter_and_darker_shades_of_theme_colors():
    """Verify exact parity with .vibeoffice/tests/ledger/tint.test.js."""
    # #4F81BD + 0.4 -> #95B3D7 (40% lighter)
    assert apply_tint("#4F81BD", 0.4) == "#95B3D7"

    # #4F81BD - 0.25 -> #376092 (25% darker)
    assert apply_tint("#4F81BD", -0.25) == "#376092"

    # #4F81BD + 0.0 -> #4F81BD (no tint)
    assert apply_tint("#4F81BD", 0.0) == "#4F81BD"

    # #000000 + 0.5 -> #808080 (black lightened by 50%)
    assert apply_tint("#000000", 0.5) == "#808080"

    # #FFFFFF - 0.5 -> #808080 (white darkened by 50%)
    assert apply_tint("#FFFFFF", -0.5) == "#808080"


def test_edge_cases_and_clean_formats():
    """Verify robustness with 8-character ARGB and missing hash prefix."""
    assert apply_tint("FF4F81BD", 0.4) == "#95B3D7"
    assert apply_tint("4F81BD", -0.25) == "#376092"
    assert apply_tint("#123456", 0.0) == "#123456"

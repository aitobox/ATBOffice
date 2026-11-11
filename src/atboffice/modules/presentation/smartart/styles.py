"""SmartArt Color Palettes, Texture Styles, and Shape Painting.

Supports 13 color palettes and 3 visual style families (Filled, Outlined, Tinted).
"""

from __future__ import annotations

from atboffice.modules.presentation.smartart.palettes import (
    DEFAULT_COLORS,
    DEFAULT_STYLE,
    PALETTES,
    STYLES,
    color_spec,
    mix_hex,
    paint_shape,
    style_info,
    style_lang,
    style_refs,
)

# 3 Visual Style Groups (Filled, Outlined, Tinted) matching .vibeoffice DG.STYLE_GROUPS
STYLE_GROUPS: list[tuple[str, str]] = [
    ("fill", "Filled"),
    ("outline", "Outlined"),
    ("tint", "Tinted"),
]

__all__ = [
    "PALETTES",
    "STYLES",
    "STYLE_GROUPS",
    "DEFAULT_COLORS",
    "DEFAULT_STYLE",
    "mix_hex",
    "style_info",
    "style_lang",
    "style_refs",
    "color_spec",
    "paint_shape",
]

"""SmartArt (IntelliArt) diagramming system for Lectern."""

from .engine import (
    CATEGORIES,
    LAYOUTS,
    PALETTES,
    STYLES,
    SmartArtEngine,
    SmartArtItem,
    relayout,
    to_shapes,
)
from .io import (
    colors_xml,
    data_xml,
    layout_xml,
    style_xml,
)
from .styles import STYLE_GROUPS, color_spec, paint_shape
from .text_pane import SmartArtTextPane

__all__ = [
    "SmartArtEngine",
    "SmartArtItem",
    "SmartArtTextPane",
    "LAYOUTS",
    "CATEGORIES",
    "PALETTES",
    "STYLES",
    "STYLE_GROUPS",
    "color_spec",
    "paint_shape",
    "relayout",
    "to_shapes",
    "data_xml",
    "layout_xml",
    "colors_xml",
    "style_xml",
]

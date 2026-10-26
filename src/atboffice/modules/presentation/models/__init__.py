"""Presentation models package."""

from atboffice.modules.presentation.models.designs import (
    DESIGNS,
    ColorScheme,
    DesignDefinition,
    DesignTemplate,
    build_design,
    color_mix,
    resolve_color,
)
from atboffice.modules.presentation.models.shape import (
    Fill,
    Line,
    PlaceholderInfo,
    Shadow,
    Shape,
)
from atboffice.modules.presentation.models.text import (
    BODY_BULLETS,
    BODY_INDENT,
    BODY_MARL,
    BODY_SIZES,
    BulletInfo,
    Paragraph,
    TextBody,
    TextRun,
    TextStyleLevel,
    get_default_body_styles,
    get_default_other_styles,
    get_default_title_style,
)

__all__ = [
    "BODY_BULLETS",
    "BODY_INDENT",
    "BODY_MARL",
    "BODY_SIZES",
    "BulletInfo",
    "ColorScheme",
    "DESIGNS",
    "DesignDefinition",
    "DesignTemplate",
    "Fill",
    "Line",
    "Paragraph",
    "PlaceholderInfo",
    "Shadow",
    "Shape",
    "TextBody",
    "TextRun",
    "TextStyleLevel",
    "build_design",
    "color_mix",
    "get_default_body_styles",
    "get_default_other_styles",
    "get_default_title_style",
    "resolve_color",
]

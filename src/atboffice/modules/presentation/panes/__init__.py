"""Presentation task panes package for Lectern."""

from atboffice.modules.presentation.panes.animation_schemes_pane import AnimationSchemesPane
from atboffice.modules.presentation.panes.color_schemes_pane import ColorSchemesPane
from atboffice.modules.presentation.panes.slide_design_pane import SlideDesignPane
from atboffice.modules.presentation.panes.slide_layout_pane import SlideLayoutPane

__all__ = [
    "SlideLayoutPane",
    "SlideDesignPane",
    "ColorSchemesPane",
    "AnimationSchemesPane",
]

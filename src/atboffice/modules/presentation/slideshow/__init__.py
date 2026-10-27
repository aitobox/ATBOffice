"""Slide show presentation and transition animation engine for Lectern."""

from __future__ import annotations

from atboffice.modules.presentation.slideshow.presenter_view import (
    InkPoint,
    InkStroke,
    InteractiveSlideCanvas,
    PresenterConsole,
    PresenterView,
)
from atboffice.modules.presentation.slideshow.slideshow_view import SlideShowView
from atboffice.modules.presentation.slideshow.transitions import (
    TRANSITION_CATALOGUE,
    TransitionEffect,
    get_transition_duration,
    get_transition_name,
    list_transitions,
    render_slide_to_image,
    render_transition_frame,
)

__all__ = [
    "InkPoint",
    "InkStroke",
    "InteractiveSlideCanvas",
    "PresenterConsole",
    "PresenterView",
    "SlideShowView",
    "TRANSITION_CATALOGUE",
    "TransitionEffect",
    "get_transition_duration",
    "get_transition_name",
    "list_transitions",
    "render_slide_to_image",
    "render_transition_frame",
]

"""View modes for Quire word-processing."""

from __future__ import annotations

from enum import Enum


class ViewMode(str, Enum):
    """View display modes supported by Quire."""

    PRINT = "print"
    NORMAL = "normal"
    WEB = "web"
    READING = "reading"
    OUTLINE = "outline"
    FULL_SCREEN = "full_screen"

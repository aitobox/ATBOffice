"""SmartArt (IntelliArt) Task Pane for Lectern.

Provides interactive outline hierarchy text editing (Enter, Tab, Shift+Tab),
layout galleries, palettes, and style controls with bidirectional canvas synchronization.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from atboffice.modules.presentation.smartart.text_pane import (
    SmartArtRowEdit,
    SmartArtTextPane,
    safe_tr,
)


class SmartArtPane(SmartArtTextPane):
    """Task pane alias for SmartArtTextPane in presentation task panes."""

    def __init__(self, presentation: Any = None, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self.presentation = presentation


__all__ = [
    "SmartArtPane",
    "SmartArtTextPane",
    "SmartArtRowEdit",
    "safe_tr",
]

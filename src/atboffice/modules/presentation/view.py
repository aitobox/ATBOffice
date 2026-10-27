"""Main view for the presentation module (Lectern)."""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.views.slide_canvas import (
    SlideCanvasView,
    SlideScene,
    safe_tr,
)
from atboffice.modules.presentation.views.workspace import LecternWorkspace


class PresentationView(QWidget):
    """Interactive PowerPoint 2003 presentation view for Lectern."""

    def __init__(
        self,
        presentation: Presentation | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.presentation = presentation or Presentation()
        self.current_slide_index = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.workspace = LecternWorkspace(presentation=self.presentation, parent=self)
        self.scene: SlideScene = self.workspace.scene
        self.canvas_view: SlideCanvasView = self.workspace.canvas_view

        layout.addWidget(self.workspace)
        self.retranslate_ui()

    def load_presentation(self, pres: Presentation) -> None:
        """Load presentation document and refresh slide canvas."""
        self.presentation = pres
        self.current_slide_index = 0
        self.workspace.load_presentation(pres)
        self.scene = self.workspace.scene
        self.canvas_view = self.workspace.canvas_view

    def load_slide(self, slide: Slide) -> None:
        """Switch active slide shown on the canvas."""
        self.workspace.load_slide(slide)

    def start_slideshow(
        self,
        from_current: bool = False,
        fullscreen: bool = False,
    ) -> Any | None:
        """Launch presentation in slide show mode."""
        return self.workspace.start_slideshow(from_current=from_current, fullscreen=fullscreen)

    def retranslate_ui(self) -> None:
        """Retranslate presentation UI controls."""
        self.setWindowTitle(safe_tr("演示文稿"))
        self.workspace.retranslate_ui()

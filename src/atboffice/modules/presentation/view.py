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

        current_slide = self.presentation.slides[0] if self.presentation.slides else None
        self.scene = SlideScene(
            slide=current_slide,
            slide_width=self.presentation.w,
            slide_height=self.presentation.h,
            parent=self,
        )
        self.canvas_view = SlideCanvasView(scene=self.scene, parent=self)
        layout.addWidget(self.canvas_view)

        self.retranslate_ui()

    def load_presentation(self, pres: Presentation) -> None:
        """Load presentation document and refresh slide canvas."""
        self.presentation = pres
        self.current_slide_index = 0
        current_slide = pres.slides[0] if pres.slides else None
        self.scene.slide_width = pres.w
        self.scene.slide_height = pres.h
        if current_slide:
            self.scene.load_slide(current_slide)
        self.canvas_view.zoom_fit()

    def load_slide(self, slide: Slide) -> None:
        """Switch active slide shown on the canvas."""
        self.scene.load_slide(slide)

    def retranslate_ui(self) -> None:
        """Retranslate presentation UI controls."""
        self.setWindowTitle(safe_tr("演示文稿"))
        self.canvas_view.retranslate_ui()

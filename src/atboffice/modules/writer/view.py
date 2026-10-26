"""Main view for the Quire word-processing module."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QVBoxLayout, QWidget

from atboffice.modules.writer.models.document import Document
from atboffice.modules.writer.views.canvas_view import WriterCanvasView


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("WriterView", text)


class WriterView(QWidget):
    """Word 2003 styled document editing viewport widget."""

    def __init__(self, doc: Document | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.canvas_view = WriterCanvasView(doc=doc, parent=self)
        layout.addWidget(self.canvas_view)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        """Update localized UI strings."""
        self.canvas_view.retranslate_ui()

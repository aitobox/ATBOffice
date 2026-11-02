"""Left navigation dock widget hosting Document Map and Thumbnails panes for Quire."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.writer.models.document import Document
from atboffice.modules.writer.views.document_map_pane import DocumentMapPane
from atboffice.modules.writer.views.thumbnails_pane import ThumbnailsPane

if TYPE_CHECKING:
    from atboffice.modules.writer.views.canvas_view import WriterCanvasView
    from atboffice.modules.writer.views.caret_controller import CaretController


def safe_tr(text: str) -> str:
    """Translate UI text safely for QuireNavDock."""
    return QCoreApplication.translate("QuireNavDock", text)


class QuireNavDock(QDockWidget):
    """Word 2003 styled left navigation dock housing Document Map and Thumbnails."""

    pane_switched = Signal(str)  # "doc_map" | "thumbnails"

    def __init__(
        self,
        doc: Document | None = None,
        canvas_view: WriterCanvasView | None = None,
        controller: CaretController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dock_quire_nav")
        self.setWindowTitle(safe_tr("导航"))
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        # Title bar custom widget
        title_widget = QWidget(self)
        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(6, 4, 6, 4)
        title_layout.setSpacing(6)

        self._combo_mode = QComboBox(title_widget)
        self._combo_mode.addItem(safe_tr("文档结构图"), "doc_map")
        self._combo_mode.addItem(safe_tr("缩略图"), "thumbnails")
        self._combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        title_layout.addWidget(self._combo_mode, 1)

        self._btn_close = QPushButton("✕", title_widget)
        self._btn_close.setFixedSize(18, 18)
        self._btn_close.setToolTip(safe_tr("关闭导航窗格"))
        self._btn_close.clicked.connect(self.hide)
        self._btn_close.setStyleSheet(
            """
            QPushButton {
                border: none;
                background: transparent;
                font-weight: bold;
                color: #555555;
            }
            QPushButton:hover {
                background: #FFD2D2;
                color: #B00000;
                border-radius: 2px;
            }
            """
        )
        title_layout.addWidget(self._btn_close)
        self.setTitleBarWidget(title_widget)

        # Container & Stack
        container = QWidget(self)
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(0)

        self.stack = QStackedWidget(container)

        self.doc_map_pane = DocumentMapPane(doc=doc, controller=controller, parent=self.stack)
        self.stack.addWidget(self.doc_map_pane)

        self.thumbnails_pane = ThumbnailsPane(doc=doc, canvas_view=canvas_view, parent=self.stack)
        self.stack.addWidget(self.thumbnails_pane)

        c_layout.addWidget(self.stack)
        self.setWidget(container)

        self.retranslate_ui()

    def show_document_map(self) -> None:
        """Switch to Document Map and ensure dock is visible."""
        self._combo_mode.setCurrentIndex(0)
        self.stack.setCurrentIndex(0)
        self.doc_map_pane.refresh_headings()
        self.show()

    def show_thumbnails(self) -> None:
        """Switch to Thumbnails and ensure dock is visible."""
        self._combo_mode.setCurrentIndex(1)
        self.stack.setCurrentIndex(1)
        self.thumbnails_pane.refresh_thumbnails()
        self.show()

    def active_mode(self) -> str:
        """Return active navigation mode ('doc_map' or 'thumbnails')."""
        return self._combo_mode.currentData() or "doc_map"

    def _on_mode_changed(self, idx: int) -> None:
        if idx == 0:
            self.stack.setCurrentIndex(0)
            self.doc_map_pane.refresh_headings()
            self.pane_switched.emit("doc_map")
        else:
            self.stack.setCurrentIndex(1)
            self.thumbnails_pane.refresh_thumbnails()
            self.pane_switched.emit("thumbnails")

    def set_document(self, doc: Document) -> None:
        """Propagate new document to subpanes."""
        self.doc_map_pane.set_document(doc)
        self.thumbnails_pane.set_document(doc)

    def refresh(self) -> None:
        """Refresh active pane."""
        if self.stack.currentIndex() == 0:
            self.doc_map_pane.refresh_headings()
        else:
            self.thumbnails_pane.refresh_thumbnails()

    def retranslate_ui(self) -> None:
        """Update localized UI text."""
        self.setWindowTitle(safe_tr("导航"))
        self._btn_close.setToolTip(safe_tr("关闭导航窗格"))
        self._combo_mode.blockSignals(True)
        self._combo_mode.setItemText(0, safe_tr("文档结构图"))
        self._combo_mode.setItemText(1, safe_tr("缩略图"))
        self._combo_mode.blockSignals(False)
        self.doc_map_pane.retranslate_ui()
        self.thumbnails_pane.retranslate_ui()

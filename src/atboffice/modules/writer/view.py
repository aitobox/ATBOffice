"""Main view for the Quire word-processing module."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QGridLayout, QWidget

from atboffice.modules.writer.models.document import Document, Paragraph
from atboffice.modules.writer.views.canvas_view import WriterCanvasView
from atboffice.modules.writer.views.review_pane import ReviewPane, ReviewToolbar
from atboffice.modules.writer.views.ruler import (
    HorizontalRuler,
    RulerUnit,
    TabSelectorWidget,
    VerticalRuler,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("WriterView", text)


class WriterView(QWidget):
    """Word 2003 styled document editing viewport widget with interactive dual rulers."""

    def __init__(self, doc: Document | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Corner tab selector button
        self.tab_selector = TabSelectorWidget(parent=self)
        layout.addWidget(self.tab_selector, 0, 0)

        # 2. Horizontal ruler
        self.h_ruler = HorizontalRuler(parent=self)
        layout.addWidget(self.h_ruler, 0, 1)

        # 3. Vertical ruler
        self.v_ruler = VerticalRuler(parent=self)
        layout.addWidget(self.v_ruler, 1, 0)

        # 4. Canvas viewport
        self.canvas_view = WriterCanvasView(doc=doc, parent=self)
        layout.addWidget(self.canvas_view, 1, 1)

        # 5. Collapsible Reviewing Pane on the right
        self.review_pane = ReviewPane(doc=self.canvas_view.doc, parent=self)
        self.review_pane.setVisible(False)
        layout.addWidget(self.review_pane, 0, 2, 2, 1)

        # 6. Reviewing Toolbar (floating / dockable toolbar)
        self.review_toolbar = ReviewToolbar(parent=self)
        self.review_toolbar.setVisible(False)

        # Wire ruler interactions and canvas attachments
        self.tab_selector.tab_kind_changed.connect(self.h_ruler.set_tab_selector_kind)
        self.h_ruler.attach_canvas(self.canvas_view)
        self.v_ruler.attach_canvas(self.canvas_view)

        # Wire canvas scroll, zoom, and cursor movements to rulers
        self.canvas_view.horizontalScrollBar().valueChanged.connect(self.h_ruler.update_scroll)
        self.canvas_view.verticalScrollBar().valueChanged.connect(self.v_ruler.update_scroll)
        self.canvas_view.zoom_changed.connect(self._on_zoom_changed)
        self.canvas_view.caret_moved.connect(self._on_caret_moved)
        self.canvas_view.controller.document_modified.connect(self._on_document_modified)

        # Wire review components
        self.review_toolbar.review_pane_toggled.connect(self.set_review_pane_visible)
        self.review_pane.item_activated.connect(self._on_review_item_activated)

        self.retranslate_ui()

    def _on_zoom_changed(self, zoom: float) -> None:
        self.h_ruler.update_zoom(zoom)
        self.v_ruler.update_zoom(zoom)

    def _on_caret_moved(self, para_id: int, offset: int) -> None:
        self.h_ruler.update_geometry_from_canvas()
        self.v_ruler.update_geometry_from_canvas()

    def _on_document_modified(self) -> None:
        self.h_ruler.update_geometry_from_canvas()
        self.v_ruler.update_geometry_from_canvas()
        self.review_pane.refresh_items()

    def _on_review_item_activated(self, para: Paragraph, start: int, end: int) -> None:
        """Focus and position caret on activated review item."""
        self.canvas_view.controller.set_caret(para.id, start)
        self.canvas_view.update()

    def set_review_pane_visible(self, visible: bool) -> None:
        """Toggle Reviewing Pane visibility."""
        self.review_pane.setVisible(visible)
        self.review_toolbar.set_pane_state(visible)

    def set_review_toolbar_visible(self, visible: bool) -> None:
        """Toggle Reviewing Toolbar visibility."""
        self.review_toolbar.setVisible(visible)

    def set_ruler_visible(self, visible: bool) -> None:
        """Toggle visibility of rulers and corner tab selector."""
        self.tab_selector.setVisible(visible)
        self.h_ruler.setVisible(visible)
        self.v_ruler.setVisible(visible)

    def set_ruler_unit(self, unit: RulerUnit | str) -> None:
        """Set measurement unit for both horizontal and vertical rulers."""
        self.h_ruler.set_unit(unit)
        self.v_ruler.set_unit(unit)

    def retranslate_ui(self) -> None:
        """Update localized UI strings."""
        self.tab_selector.retranslate_ui()
        self.h_ruler.retranslate_ui()
        self.v_ruler.retranslate_ui()
        self.canvas_view.retranslate_ui()
        self.review_pane.retranslate_ui()
        self.review_toolbar.retranslate_ui()

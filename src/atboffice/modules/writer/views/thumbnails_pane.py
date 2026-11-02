"""Thumbnails (页面缩略图) navigation pane for Quire (Word 2003 port)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.writer.layout.pagination import (
    PaginationResult,
    paginate_document,
)
from atboffice.modules.writer.models.document import Document

if TYPE_CHECKING:
    from atboffice.modules.writer.views.canvas_view import WriterCanvasView


def safe_tr(text: str) -> str:
    """Translate UI text safely for ThumbnailsPane."""
    return QCoreApplication.translate("ThumbnailsPane", text)


class ThumbnailsPane(QWidget):
    """Left sidebar pane displaying rendered page thumbnails for visual navigation."""

    page_selected = Signal(int)  # 0-based page_index

    def __init__(
        self,
        doc: Document | None = None,
        canvas_view: WriterCanvasView | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.doc: Document = doc or Document()
        self.canvas_view = canvas_view
        self._updating: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        self.list_widget = QListWidget(self)
        self.list_widget.setIconSize(QSize(100, 130))
        self.list_widget.setSpacing(6)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

        self.refresh_thumbnails()
        self.retranslate_ui()

    def set_document(self, doc: Document) -> None:
        """Update active document and rebuild thumbnails."""
        self.doc = doc
        self.refresh_thumbnails()

    def refresh_thumbnails(self) -> None:
        """Render thumbnails for each page in pagination."""
        self._updating = True
        self.list_widget.clear()

        pagination = (
            self.canvas_view.pagination
            if self.canvas_view and self.canvas_view.pagination
            else paginate_document(self.doc)
        )

        pages = pagination.pages if pagination and pagination.pages else []

        if not pages:
            item = QListWidgetItem(safe_tr("无页面"), self.list_widget)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._updating = False
            return

        for idx, page in enumerate(pages):
            pixmap = self._render_page_thumbnail(page, idx)
            item = QListWidgetItem(self.list_widget)
            item.setIcon(QIcon(pixmap))
            item.setText(str(idx + 1))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setData(Qt.ItemDataRole.UserRole, idx)

        self._updating = False

    def _render_page_thumbnail(self, page: Any, page_idx: int) -> QPixmap:
        """Render lightweight thumbnail pixmap for specified page."""
        w_px, h_px = 100, 130
        pixmap = QPixmap(w_px, h_px)
        pixmap.fill(QColor(235, 237, 240))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Draw paper sheet with subtle border and shadow
        paper_rect = QRectF(8, 6, w_px - 16, h_px - 14)
        painter.fillRect(paper_rect.adjusted(2, 2, 2, 2), QColor(200, 200, 200, 120))
        painter.fillRect(paper_rect, QColor(255, 255, 255))
        painter.setPen(QColor(160, 160, 160))
        painter.drawRect(paper_rect)

        # Draw simulated text lines
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(180, 180, 180))

        y = paper_rect.top() + 10.0
        line_spacing = 6.0
        max_y = paper_rect.bottom() - 10.0

        for reg in getattr(page, "regions", []):
            for col in getattr(reg, "columns", []):
                for fr in getattr(col, "fragments", []):
                    if y > max_y:
                        break
                    line_w = (paper_rect.width() - 16) * 0.85
                    painter.drawRect(QRectF(paper_rect.left() + 8, y, line_w, 2))
                    y += line_spacing

        painter.end()
        return pixmap

    def set_current_page(self, page_idx: int) -> None:
        """Highlight active page thumbnail."""
        if 0 <= page_idx < self.list_widget.count():
            self._updating = True
            self.list_widget.setCurrentRow(page_idx)
            self._updating = False

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        if self._updating:
            return
        page_idx = item.data(Qt.ItemDataRole.UserRole)
        if page_idx is not None:
            self.page_selected.emit(page_idx)
            if self.canvas_view:
                self.canvas_view.scroll_to_page(page_idx)

    def retranslate_ui(self) -> None:
        """Update localized UI text."""
        self.setWindowTitle(safe_tr("页面缩略图"))

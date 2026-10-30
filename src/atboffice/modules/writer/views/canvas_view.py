"""Word 2003 high-fidelity paper canvas viewport for Quire word processing."""

from __future__ import annotations

import copy
import math
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import (
    QCoreApplication,
    QPoint,
    QPointF,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QWidget,
)

from atboffice.modules.writer.layout.math_layout import paint_math
from atboffice.modules.writer.layout.pagination import (
    Page,
    PaginationResult,
    paginate_document,
)
from atboffice.modules.writer.layout.portions import (
    PortionType,
    measure_text_width,
)
from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    TextItem,
    info,
    normalize,
    paras_between,
    plen,
    ptext,
    reindex,
    split_at,
)
from atboffice.modules.writer.models.omml import OfficeMathItem
from atboffice.modules.writer.models.properties import (
    IndentProperties,
    NumberingRef,
    ParagraphProperties,
    RunProperties,
    SpacingProperties,
)
from atboffice.modules.writer.models.revision import (
    accept_all_revisions,
    accept_revision,
    insert_comment,
    list_revisions,
    reject_all_revisions,
    reject_revision,
    toggle_tracking,
)
from atboffice.modules.writer.models.table import (
    create_simple_table,
    delete_cols,
    delete_rows,
    insert_cols,
    insert_rows,
    merge_cells,
    split_cells,
    table_map,
)
from atboffice.modules.writer.views.caret_controller import (
    CaretController,
    DocPos,
    Selection,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("WriterCanvasView", text)


# Standard Word 2003 visual styling constants
COLOR_WORKSPACE_BG = QColor(140, 140, 140)  # Classic neutral gray workspace
COLOR_PAGE_PAPER = QColor(255, 255, 255)  # Pure white paper sheet
COLOR_PAGE_BORDER = QColor(112, 112, 112)  # 1px border around page
COLOR_SHADOW_DARK = QColor(58, 58, 58, 160)  # Classic drop shadow (dark core)
COLOR_SHADOW_LIGHT = QColor(80, 80, 80, 70)  # Soft drop shadow ambient falloff
COLOR_SELECTION = QColor(51, 153, 255, 110)  # Word selection highlight blue
COLOR_CARET = QColor(0, 0, 0)  # Blinking caret black
COLOR_MARGIN_GUIDE = QColor(200, 200, 200, 120)  # Subtle margin boundary guides


class WriterCanvasView(QAbstractScrollArea):
    """Word 2003 styled physical paper canvas viewport."""

    zoom_changed = Signal(float)
    caret_moved = Signal(int, int)  # para_id, offset

    def __init__(
        self,
        doc: Document | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.doc: Document = doc or Document()
        if not self.doc.main.blocks:
            self.doc.main.blocks.append(Paragraph())
        reindex(self.doc)

        self.pagination: PaginationResult = paginate_document(self.doc)
        self.controller = CaretController(self.doc, self.pagination, self)

        # Zoom settings: 50% to 400%
        self._zoom: float = 1.0
        self._min_zoom: float = 0.5
        self._max_zoom: float = 4.0
        self.pt_to_px_ratio: float = 96.0 / 72.0  # 1.33333
        self.page_gap_pt: float = 20.0

        # Mouse drag state
        self._is_dragging: bool = False

        # Table divider interactive resizing
        self._resizing_table: bool = False
        self._resize_info: dict[str, Any] | None = None
        self._resize_guide_pos: QPoint | None = None

        # Ruler guide lines (canvas coordinates)
        self._ruler_guide_x: float | None = None
        self._ruler_guide_y: float | None = None

        # Connect controller signals
        self.controller.caret_changed.connect(self._on_caret_changed)
        self.controller.selection_changed.connect(self.viewport().update)
        self.controller.document_modified.connect(self._on_document_modified)

        # Setup scroll area and viewport attributes
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.viewport().setMouseTracking(True)
        self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.retranslate_ui()
        self._update_scroll_ranges()

    # -----------------------------------------------------------------------
    # Document & Pagination Handling
    # -----------------------------------------------------------------------

    def set_document(self, doc: Document) -> None:
        """Set a new document and repaginate."""
        self.doc = doc
        if not self.doc.main.blocks:
            self.doc.main.blocks.append(Paragraph())
        reindex(self.doc)
        self.pagination = paginate_document(self.doc)
        self.controller.set_document_and_pagination(self.doc, self.pagination)
        self._update_scroll_ranges()
        self.viewport().update()

    def _on_document_modified(self) -> None:
        self.pagination = self.controller.pagination
        self._update_scroll_ranges()
        self.viewport().update()

    def _on_caret_changed(self) -> None:
        self.caret_moved.emit(self.controller.pos.para_id, self.controller.pos.offset)
        self.viewport().update()

    # -----------------------------------------------------------------------
    # Coordinate Conversion Helpers
    # -----------------------------------------------------------------------

    @property
    def zoom(self) -> float:
        """Current zoom multiplier (1.0 = 100%)."""
        return self._zoom

    def set_zoom(self, zoom: float) -> None:
        """Set zoom scale factor clamped between min and max zoom."""
        clamped = max(self._min_zoom, min(self._max_zoom, zoom))
        if math.isclose(clamped, self._zoom, abs_tol=1e-4):
            return
        self._zoom = clamped
        self._update_scroll_ranges()
        self.zoom_changed.emit(self._zoom)
        self.viewport().update()

    def zoom_in(self) -> None:
        """Increase zoom by 10%."""
        self.set_zoom(self._zoom + 0.1)

    def zoom_out(self) -> None:
        """Decrease zoom by 10%."""
        self.set_zoom(self._zoom - 0.1)

    def pt_to_px(self, pt: float) -> float:
        """Convert document logical points to canvas pixels under active zoom."""
        return pt * self.pt_to_px_ratio * self._zoom

    def px_to_pt(self, px: float) -> float:
        """Convert canvas pixels to document logical points."""
        return px / (self.pt_to_px_ratio * self._zoom)

    def total_canvas_size(self) -> QSize:
        """Compute the total bounding size (in px) of all pages stacked vertically."""
        if not self.pagination or not self.pagination.pages:
            return QSize(800, 600)

        max_w = 0.0
        total_h = 24.0  # Top padding
        gap_px = self.pt_to_px(self.page_gap_pt)

        for page in self.pagination.pages:
            w_px = self.pt_to_px(page.width)
            h_px = self.pt_to_px(page.height)
            if w_px > max_w:
                max_w = w_px
            total_h += h_px + gap_px

        total_h += 24.0  # Bottom padding
        max_w += 48.0  # Horizontal padding
        return QSize(int(math.ceil(max_w)), int(math.ceil(total_h)))

    def page_rect_canvas(self, page_idx: int) -> QRectF:
        """Return the physical QRectF bounding box (in canvas px) of page page_idx."""
        if not self.pagination or not self.pagination.pages:
            return QRectF(24, 24, 600, 800)

        vp_width = max(float(self.viewport().width()), float(self.total_canvas_size().width()))
        gap_px = self.pt_to_px(self.page_gap_pt)
        cur_y = 24.0

        for idx, page in enumerate(self.pagination.pages):
            w_px = self.pt_to_px(page.width)
            h_px = self.pt_to_px(page.height)
            x_px = max(24.0, (vp_width - w_px) / 2.0)

            if idx == page_idx:
                return QRectF(x_px, cur_y, w_px, h_px)
            cur_y += h_px + gap_px

        return QRectF(24, cur_y, 600, 800)

    def _update_scroll_ranges(self) -> None:
        total = self.total_canvas_size()
        vp_w = self.viewport().width()
        vp_h = self.viewport().height()

        h_bar = self.horizontalScrollBar()
        v_bar = self.verticalScrollBar()

        h_bar.setRange(0, max(0, total.width() - vp_w))
        v_bar.setRange(0, max(0, total.height() - vp_h))
        h_bar.setPageStep(vp_w)
        v_bar.setPageStep(vp_h)

    def viewport_to_canvas(self, vp_pt: QPoint) -> QPointF:
        """Convert viewport pixel coordinates to virtual canvas coordinates."""
        return QPointF(
            vp_pt.x() + self.horizontalScrollBar().value(),
            vp_pt.y() + self.verticalScrollBar().value(),
        )

    def canvas_to_viewport(self, canvas_pt: QPointF) -> QPointF:
        """Convert virtual canvas coordinates to viewport coordinates."""
        return QPointF(
            canvas_pt.x() - self.horizontalScrollBar().value(),
            canvas_pt.y() - self.verticalScrollBar().value(),
        )

    def viewport_to_doc_coords(self, vp_pt: QPoint) -> tuple[int, QPointF]:
        """Convert viewport coordinates to (page_index, page_relative_point_in_points)."""
        canvas_pt = self.viewport_to_canvas(vp_pt)
        if not self.pagination or not self.pagination.pages:
            return 0, QPointF(0.0, 0.0)

        # Check which page rect encloses or is closest to canvas_pt.y
        best_page = 0
        min_dist = float("inf")

        for idx in range(len(self.pagination.pages)):
            rect = self.page_rect_canvas(idx)
            if rect.top() <= canvas_pt.y() <= rect.bottom():
                best_page = idx
                min_dist = 0
                break
            dist = min(abs(canvas_pt.y() - rect.top()), abs(canvas_pt.y() - rect.bottom()))
            if dist < min_dist:
                min_dist = dist
                best_page = idx

        rect = self.page_rect_canvas(best_page)
        rel_x_px = canvas_pt.x() - rect.left()
        rel_y_px = canvas_pt.y() - rect.top()

        pt_x = self.px_to_pt(rel_x_px)
        pt_y = self.px_to_pt(rel_y_px)
        return best_page, QPointF(pt_x, pt_y)

    def scroll_to_caret(self) -> None:
        """Ensure caret is visible within the viewport."""
        page_idx, pt_page, h_pt = self.controller.pos_to_canvas(self.controller.pos)
        page_rect = self.page_rect_canvas(page_idx)

        caret_canvas_x = page_rect.left() + self.pt_to_px(pt_page.x())
        caret_canvas_y = page_rect.top() + self.pt_to_px(pt_page.y())
        caret_canvas_h = self.pt_to_px(h_pt)

        vp_w = self.viewport().width()
        vp_h = self.viewport().height()
        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()

        # Check horizontal bounds
        margin = 40
        if caret_canvas_x < scroll_x + margin:
            self.horizontalScrollBar().setValue(int(max(0, caret_canvas_x - margin)))
        elif caret_canvas_x > scroll_x + vp_w - margin:
            self.horizontalScrollBar().setValue(int(caret_canvas_x - vp_w + margin))

        # Check vertical bounds
        if caret_canvas_y < scroll_y + margin:
            self.verticalScrollBar().setValue(int(max(0, caret_canvas_y - margin)))
        elif caret_canvas_y + caret_canvas_h > scroll_y + vp_h - margin:
            self.verticalScrollBar().setValue(int(caret_canvas_y + caret_canvas_h - vp_h + margin))

    # -----------------------------------------------------------------------
    # Painting & Rendering Pipeline
    # -----------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint workspace background, paper pages, shadow, text portions, selection, and caret."""
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # 1. Paint Workspace Background
        painter.fillRect(self.viewport().rect(), COLOR_WORKSPACE_BG)

        if not self.pagination or not self.pagination.pages:
            painter.end()
            return

        visible_rect = self.viewport().rect()
        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()

        # Render each page
        for p_idx, page in enumerate(self.pagination.pages):
            rect_canvas = self.page_rect_canvas(p_idx)
            rect_vp = QRectF(
                rect_canvas.left() - scroll_x,
                rect_canvas.top() - scroll_y,
                rect_canvas.width(),
                rect_canvas.height(),
            )

            # Viewport culling
            if not rect_vp.intersects(QRectF(visible_rect)):
                continue

            # 2. Paint Page Drop Shadow
            self._paint_page_shadow(painter, rect_vp)

            # 3. Paint Page Sheet Background & Border
            painter.fillRect(rect_vp, COLOR_PAGE_PAPER)
            painter.setPen(QPen(COLOR_PAGE_BORDER, 1.0))
            painter.drawRect(rect_vp)

            # 4. Paint Selection Highlights on this page
            self._paint_selection(painter, p_idx, rect_vp, page)

            # 5. Paint Document Content (Text Lines & Portions)
            self._paint_page_content(painter, rect_vp, page)

        # 6. Paint Blinking Caret
        if self.hasFocus() and self.controller.caret_visible:
            self._paint_caret(painter)

        # 7. Paint Table Resize Guide Line
        if self._resizing_table and self._resize_guide_pos and self._resize_info:
            guide_pen = QPen(QColor(0, 51, 153), 1.5, Qt.PenStyle.DashLine)
            painter.setPen(guide_pen)
            if self._resize_info.get("kind") == "col":
                gx = float(self._resize_guide_pos.x())
                painter.drawLine(QPointF(gx, 0), QPointF(gx, self.viewport().height()))
            elif self._resize_info.get("kind") == "row":
                gy = float(self._resize_guide_pos.y())
                painter.drawLine(QPointF(0, gy), QPointF(self.viewport().width(), gy))

        # 8. Paint Ruler Guide Line
        if self._ruler_guide_x is not None or self._ruler_guide_y is not None:
            ruler_pen = QPen(QColor(60, 60, 60, 200), 1.0, Qt.PenStyle.DashLine)
            painter.setPen(ruler_pen)
            if self._ruler_guide_x is not None:
                gx = self._ruler_guide_x - scroll_x
                painter.drawLine(QPointF(gx, 0), QPointF(gx, float(self.viewport().height())))
            if self._ruler_guide_y is not None:
                gy = self._ruler_guide_y - scroll_y
                painter.drawLine(QPointF(0, gy), QPointF(float(self.viewport().width()), gy))

        painter.end()

    def set_ruler_guide(self, x: float | None = None, y: float | None = None) -> None:
        """Set alignment guide line position in virtual canvas coordinates and repaint."""
        self._ruler_guide_x = x
        self._ruler_guide_y = y
        self.viewport().update()

    def clear_ruler_guide(self) -> None:
        """Clear active ruler alignment guide lines and repaint."""
        if self._ruler_guide_x is not None or self._ruler_guide_y is not None:
            self._ruler_guide_x = None
            self._ruler_guide_y = None
            self.viewport().update()

    def _paint_page_shadow(self, painter: QPainter, page_rect: QRectF) -> None:
        """Draw classic Word 2003 physical paper drop shadow."""
        # Multi-layer shadow offset
        offset_x = 4.0
        offset_y = 4.0

        # Light ambient outer shadow
        outer_shadow = QRectF(
            page_rect.left() + 1.0,
            page_rect.top() + 1.0,
            page_rect.width() + offset_x + 1.0,
            page_rect.height() + offset_y + 1.0,
        )
        painter.fillRect(outer_shadow, COLOR_SHADOW_LIGHT)

        # Dark primary shadow
        primary_shadow = QRectF(
            page_rect.left() + 2.0,
            page_rect.top() + 2.0,
            page_rect.width() + offset_x - 1.0,
            page_rect.height() + offset_y - 1.0,
        )
        painter.fillRect(primary_shadow, COLOR_SHADOW_DARK)

    def _paint_page_content(self, painter: QPainter, page_rect: QRectF, page: Page) -> None:
        """Render lines, formatted portions, and table structures on a single page."""
        for reg in page.regions:
            for col in reg.columns:
                for frag in col.fragments:
                    if frag.table_layout is not None:
                        tl = frag.table_layout
                        frag_x = page.body_left + col.left
                        frag_y = page.body_top + col.top + frag.top

                        for rl in tl.rows:
                            for cl in rl.cells:
                                cell_x_px = page_rect.left() + self.pt_to_px(frag_x + cl.x)
                                cell_y_px = page_rect.top() + self.pt_to_px(frag_y + cl.y)
                                cell_w_px = self.pt_to_px(cl.width)
                                cell_h_px = self.pt_to_px(cl.height)
                                cell_rect = QRectF(cell_x_px, cell_y_px, cell_w_px, cell_h_px)

                                # Shading
                                fill_val = getattr(cl.shd, "fill", "auto")
                                if fill_val and fill_val not in ("auto", "clear", "none"):
                                    hex_fill = (
                                        fill_val if fill_val.startswith("#") else f"#{fill_val}"
                                    )
                                    painter.fillRect(cell_rect, QColor(hex_fill))

                                # Border
                                painter.setPen(QPen(QColor(120, 120, 120), 1.0))
                                painter.drawRect(cell_rect)

                                # Cell text content
                                cell_inner_x = frag_x + cl.x + 5.4
                                cell_inner_y = frag_y + cl.y + cl.content_offset_y
                                for playout in cl.paragraphs_layout:
                                    for line in playout.lines:
                                        line_y = cell_inner_y + line.top
                                        cur_x = cell_inner_x + line.indent_left
                                        for po in line.portions:
                                            po_w = po.width
                                            if po.type == PortionType.TEXT and po.text:
                                                font_family = po.font_family or "Times New Roman"
                                                font_size_pt = po.font_size or 12.0
                                                font = QFont(font_family)
                                                font.setPointSizeF(font_size_pt * self._zoom)
                                                painter.setFont(font)
                                                x_px = page_rect.left() + self.pt_to_px(cur_x)
                                                y_px = page_rect.top() + self.pt_to_px(line_y)
                                                baseline_px = y_px + self.pt_to_px(line.baseline)
                                                painter.setPen(QPen(QColor(0, 0, 0)))
                                                painter.drawText(
                                                    QPointF(x_px, baseline_px), po.text
                                                )
                                            elif po.type == PortionType.GRAPHIC and isinstance(
                                                po.data, OfficeMathItem
                                            ):
                                                x_px = page_rect.left() + self.pt_to_px(cur_x)
                                                y_px = page_rect.top() + self.pt_to_px(line_y)
                                                baseline_px = y_px + self.pt_to_px(line.baseline)
                                                paint_math(
                                                    painter, po.data, x_px, baseline_px, self._zoom
                                                )
                                            cur_x += po_w
                        continue

                    frag_top = page.body_top + col.top + frag.top
                    for line in frag.lines:
                        line_y = frag_top + line.top
                        cur_x = page.body_left + col.left + line.indent_left

                        for po in line.portions:
                            po_w = po.width
                            if po.type == PortionType.TEXT and po.text:
                                # Font setup
                                font_family = po.font_family or "Times New Roman"
                                font_size_pt = po.font_size or 12.0

                                font = QFont(font_family)
                                font.setPointSizeF(font_size_pt * self._zoom)
                                painter.setFont(font)

                                # Calculate portion rect on viewport
                                x_px = page_rect.left() + self.pt_to_px(cur_x)
                                y_px = page_rect.top() + self.pt_to_px(line_y)
                                baseline_px = y_px + self.pt_to_px(line.baseline)

                                # Draw text string
                                painter.setPen(QPen(QColor(0, 0, 0)))
                                painter.drawText(
                                    QPointF(x_px, baseline_px),
                                    po.text,
                                )
                            elif po.type == PortionType.TAB and po_w > 0:
                                tab_data = getattr(po, "data", None)
                                leader = getattr(tab_data, "leader", "none") if tab_data else "none"
                                if leader and leader != "none":
                                    x_px = page_rect.left() + self.pt_to_px(cur_x)
                                    y_px = page_rect.top() + self.pt_to_px(line_y)
                                    baseline_px = y_px + self.pt_to_px(line.baseline)
                                    w_px = self.pt_to_px(po_w)

                                    p1 = QPointF(x_px, baseline_px)
                                    p2 = QPointF(x_px + w_px, baseline_px)
                                    if leader == "dot":
                                        pen = QPen(QColor(100, 100, 100), 1.0, Qt.PenStyle.DotLine)
                                        painter.setPen(pen)
                                        painter.drawLine(p1, p2)
                                    elif leader == "hyphen":
                                        pen = QPen(QColor(100, 100, 100), 1.0, Qt.PenStyle.DashLine)
                                        painter.setPen(pen)
                                        painter.drawLine(p1, p2)
                                    elif leader == "underscore":
                                        pen = QPen(
                                            QColor(100, 100, 100), 1.0, Qt.PenStyle.SolidLine
                                        )
                                        painter.setPen(pen)
                                        p1_u = QPointF(x_px, baseline_px + 2)
                                        p2_u = QPointF(x_px + w_px, baseline_px + 2)
                                        painter.drawLine(p1_u, p2_u)

                            elif po.type == PortionType.GRAPHIC and isinstance(
                                po.data, OfficeMathItem
                            ):
                                x_px = page_rect.left() + self.pt_to_px(cur_x)
                                y_px = page_rect.top() + self.pt_to_px(line_y)
                                baseline_px = y_px + self.pt_to_px(line.baseline)
                                paint_math(painter, po.data, x_px, baseline_px, self._zoom)

                            cur_x += po_w

    def render_page_to_painter(
        self,
        painter: QPainter,
        page: Page,
        origin_x: float = 0.0,
        origin_y: float = 0.0,
    ) -> None:
        """Render page contents in vector points directly onto a QPainter target (e.g. QPrinter)."""

        def _setup_font_and_pen(
            po: Portion, default_size: float = 12.0, default_color: str = "#000000"
        ) -> tuple[QFont, QPen]:
            family = getattr(po, "font_family", None) or "Times New Roman"
            sz = getattr(po, "font_size", None) or default_size
            f = QFont(family)
            f.setPointSizeF(sz)
            is_bold = bool(
                getattr(po, "bold", False)
                or (isinstance(getattr(po, "data", None), dict) and po.data.get("bold"))
            )
            is_italic = bool(
                getattr(po, "italic", False)
                or (isinstance(getattr(po, "data", None), dict) and po.data.get("italic"))
            )
            f.setBold(is_bold)
            f.setItalic(is_italic)
            col = getattr(po, "color", None) or default_color
            return f, QPen(QColor(col))

        # 1. Render Header if present
        if page.header:
            header_top = origin_y + page.header.y
            for frag in page.header.fragments:
                for line in frag.lines:
                    line_y = header_top + line.top
                    cur_x = origin_x + page.body_left + line.indent_left
                    for po in line.portions:
                        po_w = po.width
                        if po.type == PortionType.TEXT and po.text:
                            font, pen = _setup_font_and_pen(po, 10.0, "#666666")
                            painter.setFont(font)
                            painter.setPen(pen)
                            baseline = line_y + line.baseline
                            painter.drawText(QPointF(cur_x, baseline), po.text)
                        elif po.type == PortionType.GRAPHIC and isinstance(po.data, OfficeMathItem):
                            paint_math(painter, po.data, cur_x, line_y + line.baseline, 1.0)
                        cur_x += po_w

        # 2. Render Page Regions and Paragraphs/Tables
        for reg in page.regions:
            for col in reg.columns:
                for frag in col.fragments:
                    if frag.table_layout is not None:
                        tl = frag.table_layout
                        frag_x = origin_x + page.body_left + col.left
                        frag_y = origin_y + page.body_top + col.top + frag.top

                        for rl in tl.rows:
                            for cl in rl.cells:
                                cell_x = frag_x + cl.x
                                cell_y = frag_y + cl.y
                                cell_rect = QRectF(cell_x, cell_y, cl.width, cl.height)

                                # Shading
                                fill_val = getattr(cl.shd, "fill", "auto")
                                if fill_val and fill_val not in ("auto", "clear", "none"):
                                    hex_fill = (
                                        fill_val if fill_val.startswith("#") else f"#{fill_val}"
                                    )
                                    painter.fillRect(cell_rect, QColor(hex_fill))

                                # Border
                                painter.setPen(QPen(QColor(120, 120, 120), 0.75))
                                painter.drawRect(cell_rect)

                                # Cell text content
                                cell_inner_x = frag_x + cl.x + 5.4
                                cell_inner_y = frag_y + cl.y + cl.content_offset_y
                                for playout in cl.paragraphs_layout:
                                    for line in playout.lines:
                                        line_y = cell_inner_y + line.top
                                        cur_x = cell_inner_x + line.indent_left
                                        for po in line.portions:
                                            po_w = po.width
                                            if po.type == PortionType.TEXT and po.text:
                                                font, pen = _setup_font_and_pen(po, 12.0, "#000000")
                                                painter.setFont(font)
                                                painter.setPen(pen)
                                                baseline = line_y + line.baseline
                                                painter.drawText(QPointF(cur_x, baseline), po.text)
                                            elif po.type == PortionType.GRAPHIC and isinstance(
                                                po.data, OfficeMathItem
                                            ):
                                                paint_math(
                                                    painter,
                                                    po.data,
                                                    cur_x,
                                                    line_y + line.baseline,
                                                    1.0,
                                                )
                                            cur_x += po_w
                        continue

                    frag_top = origin_y + page.body_top + col.top + frag.top
                    for line in frag.lines:
                        line_y = frag_top + line.top
                        cur_x = origin_x + page.body_left + col.left + line.indent_left

                        for po in line.portions:
                            po_w = po.width
                            if po.type == PortionType.TEXT and po.text:
                                font, pen = _setup_font_and_pen(po, 12.0, "#000000")
                                painter.setFont(font)
                                painter.setPen(pen)
                                baseline = line_y + line.baseline
                                painter.drawText(QPointF(cur_x, baseline), po.text)

                                if getattr(po, "underline", False):
                                    pen_u = QPen(pen.color(), 0.75)
                                    painter.setPen(pen_u)
                                    painter.drawLine(
                                        QPointF(cur_x, baseline + 1.5),
                                        QPointF(cur_x + po_w, baseline + 1.5),
                                    )
                                if getattr(po, "strikethrough", False):
                                    pen_s = QPen(pen.color(), 0.75)
                                    painter.setPen(pen_s)
                                    mid_y = line_y + line.baseline - (po.font_size or 12.0) * 0.3
                                    painter.drawLine(
                                        QPointF(cur_x, mid_y),
                                        QPointF(cur_x + po_w, mid_y),
                                    )
                            elif po.type == PortionType.TAB and po_w > 0:
                                tab_data = getattr(po, "data", None)
                                leader = getattr(tab_data, "leader", "none") if tab_data else "none"
                                if leader and leader != "none":
                                    baseline = line_y + line.baseline
                                    p1 = QPointF(cur_x, baseline)
                                    p2 = QPointF(cur_x + po_w, baseline)
                                    if leader == "dot":
                                        pen_l = QPen(QColor(100, 100, 100), 0.75, Qt.PenStyle.DotLine)
                                        painter.setPen(pen_l)
                                        painter.drawLine(p1, p2)
                                    elif leader == "hyphen":
                                        pen_l = QPen(
                                            QColor(100, 100, 100), 0.75, Qt.PenStyle.DashLine
                                        )
                                        painter.setPen(pen_l)
                                        painter.drawLine(p1, p2)
                                    elif leader == "underscore":
                                        pen_l = QPen(
                                            QColor(100, 100, 100), 0.75, Qt.PenStyle.SolidLine
                                        )
                                        painter.setPen(pen_l)
                                        painter.drawLine(
                                            QPointF(cur_x, baseline + 1.5),
                                            QPointF(cur_x + po_w, baseline + 1.5),
                                        )

                            elif po.type == PortionType.GRAPHIC and isinstance(
                                po.data, OfficeMathItem
                            ):
                                paint_math(painter, po.data, cur_x, line_y + line.baseline, 1.0)

                            cur_x += po_w

        # 3. Render Footer if present
        if page.footer:
            footer_top = origin_y + page.footer.y
            for frag in page.footer.fragments:
                for line in frag.lines:
                    line_y = footer_top + line.top
                    cur_x = origin_x + page.body_left + line.indent_left
                    for po in line.portions:
                        po_w = po.width
                        if po.type == PortionType.TEXT and po.text:
                            font, pen = _setup_font_and_pen(po, 10.0, "#666666")
                            painter.setFont(font)
                            painter.setPen(pen)
                            baseline = line_y + line.baseline
                            painter.drawText(QPointF(cur_x, baseline), po.text)
                        elif po.type == PortionType.GRAPHIC and isinstance(po.data, OfficeMathItem):
                            paint_math(painter, po.data, cur_x, line_y + line.baseline, 1.0)
                        cur_x += po_w

    def _paint_selection(
        self, painter: QPainter, page_idx: int, page_rect: QRectF, page: Page
    ) -> None:
        """Render selection highlight rects for active text selection."""
        sel = self.controller.selection
        if sel.is_collapsed:
            return

        start, end = sel.ordered_range(self.doc)

        for reg in page.regions:
            for col in reg.columns:
                for frag in col.fragments:
                    if frag.paragraph is None:
                        continue
                    pid = frag.paragraph.id
                    inf = info(self.doc, pid)
                    if not inf or "p" not in inf:
                        continue
                    p_order = inf["p"]._o

                    inf_s = info(self.doc, start.para_id)
                    inf_e = info(self.doc, end.para_id)
                    order_s = inf_s["p"]._o if inf_s and "p" in inf_s else 0
                    order_e = inf_e["p"]._o if inf_e and "p" in inf_e else 0

                    # Check if paragraph is within selection range
                    if p_order < order_s or p_order > order_e:
                        continue

                    p_len = plen(frag.paragraph)
                    sel_start_in_p = start.offset if p_order == order_s else 0
                    sel_end_in_p = end.offset if p_order == order_e else p_len

                    frag_top = page.body_top + col.top + frag.top
                    for line in frag.lines:
                        if not line.portions:
                            continue
                        l_start = line.portions[0].char_offset
                        l_end = line.portions[-1].char_offset + line.portions[-1].length

                        # Check line overlap with paragraph selection
                        inter_start = max(l_start, sel_start_in_p)
                        inter_end = min(l_end, sel_end_in_p)

                        if inter_start < inter_end:
                            # Calculate x coordinates of selection on this line
                            x1 = page.body_left + col.left + line.indent_left
                            for po in line.portions:
                                if inter_start >= po.char_offset + po.length:
                                    x1 += po.width
                                else:
                                    sub = max(0, inter_start - po.char_offset)
                                    x1 += measure_text_width(
                                        po.text[:sub], po.font_size, po.font_family
                                    )
                                    break

                            x2 = page.body_left + col.left + line.indent_left
                            for po in line.portions:
                                if inter_end >= po.char_offset + po.length:
                                    x2 += po.width
                                else:
                                    sub = max(0, inter_end - po.char_offset)
                                    x2 += measure_text_width(
                                        po.text[:sub], po.font_size, po.font_family
                                    )
                                    break

                            rect_x = page_rect.left() + self.pt_to_px(x1)
                            rect_y = page_rect.top() + self.pt_to_px(frag_top + line.top)
                            rect_w = max(4.0, self.pt_to_px(x2 - x1))
                            rect_h = self.pt_to_px(max(line.height, 14.0))

                            painter.fillRect(
                                QRectF(rect_x, rect_y, rect_w, rect_h),
                                COLOR_SELECTION,
                            )

    def _paint_caret(self, painter: QPainter) -> None:
        """Render blinking caret at active position."""
        page_idx, pt_page, h_pt = self.controller.pos_to_canvas(self.controller.pos)
        page_rect = self.page_rect_canvas(page_idx)

        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()

        caret_vp_x = page_rect.left() - scroll_x + self.pt_to_px(pt_page.x())
        caret_vp_y = page_rect.top() - scroll_y + self.pt_to_px(pt_page.y())
        caret_vp_h = self.pt_to_px(h_pt)

        painter.setPen(QPen(COLOR_CARET, 1.5))
        painter.drawLine(
            QPointF(caret_vp_x, caret_vp_y),
            QPointF(caret_vp_x, caret_vp_y + caret_vp_h),
        )

    def _hit_test_table_divider(self, vp_pt: QPoint) -> dict[str, Any] | None:
        """Hit test viewport position against table column or row dividers."""
        if not self.pagination or not self.pagination.pages:
            return None

        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()
        threshold = 4.0

        for p_idx, page in enumerate(self.pagination.pages):
            page_rect = self.page_rect_canvas(p_idx)
            page_vp_left = page_rect.left() - scroll_x
            page_vp_top = page_rect.top() - scroll_y

            for reg in page.regions:
                for col in reg.columns:
                    for frag in col.fragments:
                        if frag.table_layout is None:
                            continue
                        tl = frag.table_layout
                        frag_x = page.body_left + col.left
                        frag_y = page.body_top + col.top + frag.top

                        frag_vp_top = page_vp_top + self.pt_to_px(frag_y)
                        frag_vp_bottom = frag_vp_top + self.pt_to_px(tl.height)
                        frag_vp_left = page_vp_left + self.pt_to_px(frag_x)
                        frag_vp_right = frag_vp_left + self.pt_to_px(tl.width)

                        # Test vertical column dividers
                        cur_x = frag_x
                        for c_idx, col_w in enumerate(tl.grid):
                            cur_x += col_w
                            div_vp_x = page_vp_left + self.pt_to_px(cur_x)
                            if (
                                abs(vp_pt.x() - div_vp_x) <= threshold
                                and frag_vp_top - 2 <= vp_pt.y() <= frag_vp_bottom + 2
                            ):
                                return {
                                    "table": tl.table,
                                    "kind": "col",
                                    "index": c_idx,
                                    "start_pt": vp_pt,
                                    "initial_size": col_w,
                                }

                        # Test horizontal row dividers
                        for r_idx, rl in enumerate(tl.rows):
                            div_y = frag_y + rl.y + rl.height
                            div_vp_y = page_vp_top + self.pt_to_px(div_y)
                            if (
                                abs(vp_pt.y() - div_vp_y) <= threshold
                                and frag_vp_left - 2 <= vp_pt.x() <= frag_vp_right + 2
                            ):
                                return {
                                    "table": tl.table,
                                    "kind": "row",
                                    "index": rl.row_idx,
                                    "start_pt": vp_pt,
                                    "initial_size": rl.height,
                                }

        return None

    # -----------------------------------------------------------------------
    # Mouse & Keyboard Event Handlers
    # -----------------------------------------------------------------------

    def _event_pos(self, event: QMouseEvent) -> QPoint:
        """Extract integer pixel QPoint from QMouseEvent safely across Qt versions."""
        if hasattr(event, "position"):
            return event.position().toPoint()
        return event.pos()

    def jump_to_bookmark(self, name: str) -> bool:
        """Jump to bookmark target by scrolling canvas and setting caret position."""
        from atboffice.modules.writer.models.field import find_bookmarks
        from atboffice.modules.writer.views.caret_controller import DocPos

        bms = find_bookmarks(self.doc)
        b = bms.get(name)
        if not b:
            return False
        target_pos = DocPos(b.p.id, b.offset)
        self.controller.set_pos(target_pos, extend_selection=False)
        self.scroll_to_caret()
        self.viewport().update()
        return True

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle single-click, double-click, triple-click, and table divider resize."""
        pos_pt = self._event_pos(event)
        if event.button() == Qt.MouseButton.LeftButton:
            hit = self._hit_test_table_divider(pos_pt)
            if hit is not None:
                self._resizing_table = True
                self._resize_info = hit
                self._resize_guide_pos = pos_pt
                self.viewport().update()
                return

            page_idx, pt_doc = self.viewport_to_doc_coords(pos_pt)
            pos = self.controller.canvas_to_pos(page_idx, pt_doc)

            # Hyperlink navigation check
            p = self.controller._paragraph_by_id(pos.para_id)
            if p:
                from atboffice.modules.writer.models.document import locate

                item_idx, _, _ = locate(p, pos.offset, side="after")
                if 0 <= item_idx < len(p.runs):
                    it = p.runs[item_idx]
                    link = getattr(it.r_pr, "link", None) if hasattr(it, "r_pr") else None
                    if link and isinstance(link, dict) and "anchor" in link:
                        if self.jump_to_bookmark(link["anchor"]):
                            return

            modifiers = event.modifiers()
            shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

            self._is_dragging = True
            self.setFocus()
            self.controller.set_pos(pos, extend_selection=shift)
            self.viewport().update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse dragging for continuous selection and table resizing."""
        pos_pt = self._event_pos(event)
        if self._resizing_table:
            self._resize_guide_pos = pos_pt
            self.viewport().update()
            return

        if self._is_dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            page_idx, pt_doc = self.viewport_to_doc_coords(pos_pt)
            pos = self.controller.canvas_to_pos(page_idx, pt_doc)
            self.controller.set_pos(pos, extend_selection=True)
            self.viewport().update()
            return

        # Divider cursor hover detection
        hit = self._hit_test_table_divider(pos_pt)
        if hit is not None:
            if hit["kind"] == "col":
                self.viewport().setCursor(Qt.CursorShape.SplitHCursor)
            else:
                self.viewport().setCursor(Qt.CursorShape.SplitVCursor)
        else:
            page_idx, pt_doc = self.viewport_to_doc_coords(pos_pt)
            pos = self.controller.canvas_to_pos(page_idx, pt_doc)
            p = self.controller._paragraph_by_id(pos.para_id)
            is_link = False
            if p:
                from atboffice.modules.writer.models.document import locate

                item_idx, _, _ = locate(p, pos.offset, side="after")
                if 0 <= item_idx < len(p.runs):
                    it = p.runs[item_idx]
                    link = getattr(it.r_pr, "link", None) if hasattr(it, "r_pr") else None
                    if link and isinstance(link, dict) and "anchor" in link:
                        is_link = True
            if is_link:
                self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.viewport().setCursor(Qt.CursorShape.IBeamCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """End mouse selection drag or commit table resize."""
        pos_pt = self._event_pos(event)
        if event.button() == Qt.MouseButton.LeftButton:
            if self._resizing_table and self._resize_info:
                table = self._resize_info["table"]
                idx = self._resize_info["index"]
                kind = self._resize_info["kind"]
                init_sz = self._resize_info["initial_size"]

                if kind == "col":
                    delta_px = pos_pt.x() - self._resize_info["start_pt"].x()
                    delta_pt = self.px_to_pt(delta_px)
                    if 0 <= idx < len(table.grid):
                        table.grid[idx] = max(12.0, round(init_sz + delta_pt, 2))
                elif kind == "row":
                    delta_px = pos_pt.y() - self._resize_info["start_pt"].y()
                    delta_pt = self.px_to_pt(delta_px)
                    if 0 <= idx < len(table.rows):
                        table.rows[idx].tr_pr.h = max(12.0, round(init_sz + delta_pt, 2))
                        table.rows[idx].tr_pr.h_rule = "exact"

                self._resizing_table = False
                self._resize_info = None
                self._resize_guide_pos = None
                self.set_document(self.doc)
                return

            self._is_dragging = False

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Handle double-click for word selection."""
        pos_pt = self._event_pos(event)
        if event.button() == Qt.MouseButton.LeftButton:
            page_idx, pt_doc = self.viewport_to_doc_coords(pos_pt)
            pos = self.controller.canvas_to_pos(page_idx, pt_doc)
            self.controller.select_word_at(pos)
            self.viewport().update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Dispatch keyboard events to CaretController."""
        if self.controller.handle_key_event(event):
            event.accept()
            self.scroll_to_caret()
            self.viewport().update()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Update scroll ranges and repaginate/repaint upon resize."""
        super().resizeEvent(event)
        self._update_scroll_ranges()

    # -----------------------------------------------------------------------
    # Paragraph & Character Formatting Operations
    # -----------------------------------------------------------------------

    def _get_selected_paragraphs(self) -> list[Paragraph]:
        """Return all paragraphs covered by the current selection."""
        if self.controller.selection.is_collapsed:
            p = self.controller._paragraph_by_id(self.controller.pos.para_id)
            return [p] if p is not None else []
        a, b = self.controller.selection.ordered_range(self.doc)
        pa = self.controller._paragraph_by_id(a.para_id)
        pb = self.controller._paragraph_by_id(b.para_id)
        if pa is not None and pb is not None:
            return paras_between(self.doc, pa, pb)
        return [pa] if pa is not None else []

    def set_paragraph_alignment(self, jc: str) -> None:
        """Set paragraph alignment (left, center, right, both/justify)."""
        for p in self._get_selected_paragraphs():
            if p.p_pr is None:
                p.p_pr = ParagraphProperties()
            p.p_pr.jc = jc
        self._on_formatting_applied()

    def change_indent(self, delta_pt: float) -> None:
        """Increase or decrease left indent for selected paragraphs."""
        for p in self._get_selected_paragraphs():
            if p.p_pr is None:
                p.p_pr = ParagraphProperties()
            if p.p_pr.ind is None:
                p.p_pr.ind = IndentProperties()
            p.p_pr.ind.left = max(0.0, (p.p_pr.ind.left or 0.0) + delta_pt)
        self._on_formatting_applied()

    def set_line_spacing(self, line: float, line_rule: str = "auto") -> None:
        """Set line spacing multiplier (e.g. 1.0, 1.5, 2.0)."""
        for p in self._get_selected_paragraphs():
            if p.p_pr is None:
                p.p_pr = ParagraphProperties()
            if p.p_pr.sp is None:
                p.p_pr.sp = SpacingProperties()
            p.p_pr.sp.line = line
            p.p_pr.sp.line_rule = line_rule
        self._on_formatting_applied()

    def toggle_list_style(self, kind: str) -> None:
        """Toggle bullet or numbering list on selected paragraphs."""
        paras = self._get_selected_paragraphs()
        if not paras:
            return
        first = paras[0]
        has_num = first.p_pr and first.p_pr.num is not None
        num_target = "1" if kind == "bullet" else "2"
        is_same = has_num and first.p_pr.num.id == num_target

        for p in paras:
            if p.p_pr is None:
                p.p_pr = ParagraphProperties()
            if is_same:
                p.p_pr.num = None
            else:
                p.p_pr.num = NumberingRef(id=num_target, lvl=0)
        self._on_formatting_applied()

    def format_range(self, fn: Callable[[RunProperties], None]) -> None:
        """Apply a formatting function to all runs in the current selection."""
        if self.controller.selection.is_collapsed:
            p = self.controller._paragraph_by_id(self.controller.pos.para_id)
            if p is not None:
                if p.r_pr is None:
                    p.r_pr = RunProperties()
                fn(p.r_pr)
                for r in p.runs:
                    if getattr(r, "t", "") == "text":
                        if r.r_pr is None:
                            r.r_pr = RunProperties()
                        fn(r.r_pr)
        else:
            a, b = self.controller.selection.ordered_range(self.doc)
            pa = self.controller._paragraph_by_id(a.para_id)
            pb = self.controller._paragraph_by_id(b.para_id)
            if pa is not None and pb is not None:
                paras = paras_between(self.doc, pa, pb)
                for p in paras:
                    s = a.offset if p == pa else 0
                    e = b.offset if p == pb else plen(p)
                    if s < e:
                        i0 = split_at(p, s)
                        i1 = split_at(p, e)
                        for i in range(i0, i1):
                            it = p.runs[i]
                            if getattr(it, "t", "") == "text":
                                if it.r_pr is None:
                                    it.r_pr = RunProperties()
                                fn(it.r_pr)
                        normalize(p)
        self._on_formatting_applied()

    def toggle_character_format(self, attr: str) -> None:
        """Toggle a boolean or choice character formatting attribute."""
        curr_val = False
        p = self.controller._paragraph_by_id(self.controller.pos.para_id)
        if p is not None:
            if attr == "bold":
                curr_val = bool(p.r_pr and p.r_pr.b)
            elif attr == "italic":
                curr_val = bool(p.r_pr and p.r_pr.i)
            elif attr == "underline":
                curr_val = bool(p.r_pr and p.r_pr.u and p.r_pr.u != "none")
            elif attr == "strike":
                curr_val = bool(p.r_pr and p.r_pr.strike)
            elif attr == "superscript":
                curr_val = bool(p.r_pr and p.r_pr.vert == "superscript")
            elif attr == "subscript":
                curr_val = bool(p.r_pr and p.r_pr.vert == "subscript")

        def _apply(r: RunProperties) -> None:
            if attr == "bold":
                r.b = not curr_val
            elif attr == "italic":
                r.i = not curr_val
            elif attr == "underline":
                r.u = "none" if curr_val else "single"
            elif attr == "strike":
                r.strike = not curr_val
            elif attr == "superscript":
                r.vert = "baseline" if curr_val else "superscript"
            elif attr == "subscript":
                r.vert = "baseline" if curr_val else "subscript"

        self.format_range(_apply)

    def set_font_family(self, name: str) -> None:
        """Set font family for selection."""
        self.format_range(lambda r: setattr(r, "font", name))

    def set_font_size(self, size_pt: float) -> None:
        """Set font size in points for selection."""
        self.format_range(lambda r: setattr(r, "sz", size_pt))

    def set_font_color(self, color: str) -> None:
        """Set font color (hex string or 'auto') for selection."""
        self.format_range(lambda r: setattr(r, "color", color))

    def set_highlight_color(self, color: str | None) -> None:
        """Set highlight fill color for selection."""
        self.format_range(lambda r: setattr(r, "highlight", color))

    def _on_formatting_applied(self) -> None:
        """Repaginate, re-render, and notify modification."""
        self.set_document(self.doc)
        self.controller.document_modified.emit()

    # -----------------------------------------------------------------------
    # Table Operations
    # -----------------------------------------------------------------------

    def get_current_table_context(self) -> dict[str, Any] | None:
        """Return table, row, cell and grid coordinates if caret is within a table."""
        inf = info(self.doc, self.controller.pos.para_id)
        if not inf or not inf.get("parents"):
            return None
        for parent in inf["parents"]:
            if isinstance(parent, dict) and "tbl" in parent:
                tbl = parent["tbl"]
                cell = parent.get("cell")
                r_idx, c_idx = 0, 0
                grid = table_map(tbl)
                for r_i, row in enumerate(grid):
                    for entry in row:
                        if entry.cell is cell:
                            r_idx, c_idx = entry.row_idx, entry.col_idx
                            break
                return {
                    "tbl": tbl,
                    "row": parent.get("row"),
                    "cell": cell,
                    "row_idx": r_idx,
                    "col_idx": c_idx,
                }
        return None

    def insert_table(self, rows: int = 2, cols: int = 2) -> None:
        """Insert a new table at the current position."""
        tbl = create_simple_table(rows, cols)
        inf = info(self.doc, self.controller.pos.para_id)
        story = inf["story"] if inf and "story" in inf else self.doc.main
        curr_p = self.controller._paragraph_by_id(self.controller.pos.para_id)
        idx = story.blocks.index(curr_p) if curr_p in story.blocks else len(story.blocks)
        story.blocks.insert(idx + 1, tbl)
        self.set_document(self.doc)
        first_p = tbl.rows[0].cells[0].blocks[0]
        self.controller.pos = DocPos(first_p.id, 0)
        self.controller.selection = Selection(self.controller.pos, self.controller.pos)
        self.controller.repaginate_and_refresh()

    def insert_table_row(self, above: bool = False) -> None:
        """Insert a row above or below current cell."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        r_idx = ctx["row_idx"]
        insert_rows(tbl, r_idx, count=1, above=above)
        self._on_formatting_applied()

    def insert_table_col(self, left: bool = False) -> None:
        """Insert a column to the left or right of current cell."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        c_idx = ctx["col_idx"]
        insert_cols(tbl, c_idx, count=1, left=left)
        self._on_formatting_applied()

    def delete_table_row(self) -> None:
        """Delete the current table row."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        r_idx = ctx["row_idx"]
        if len(tbl.rows) > 1:
            target_r = r_idx - 1 if r_idx > 0 else r_idx + 1
            surviving_p = tbl.rows[target_r].cells[0].blocks[0]
            delete_rows(tbl, r_idx, r_idx)
            self._on_formatting_applied()
            self.controller.pos = DocPos(surviving_p.id, 0)
            self.controller.selection = Selection(self.controller.pos, self.controller.pos)
            self.controller.caret_changed.emit()

    def delete_table_col(self) -> None:
        """Delete the current table column."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        c_idx = ctx["col_idx"]
        r_idx = ctx["row_idx"]
        if len(tbl.grid) > 1:
            delete_cols(tbl, c_idx, c_idx)
            self._on_formatting_applied()
            grid = table_map(tbl)
            target_c = min(c_idx, len(tbl.grid) - 1)
            target_r = min(r_idx, len(tbl.rows) - 1)
            surviving_cell = grid[target_r][target_c].cell
            surviving_p = surviving_cell.blocks[0] if surviving_cell.blocks else None
            if surviving_p is not None:
                self.controller.pos = DocPos(surviving_p.id, 0)
                self.controller.selection = Selection(self.controller.pos, self.controller.pos)
                self.controller.caret_changed.emit()

    def merge_table_cells(self) -> None:
        """Merge cells in the current table."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        r_idx = ctx["row_idx"]
        c_idx = ctx["col_idx"]
        if c_idx + 1 < len(tbl.grid):
            merge_cells(tbl, r_idx, r_idx, c_idx, c_idx + 1)
            self._on_formatting_applied()

    def split_table_cells(self, num_rows: int = 1, num_cols: int = 2) -> None:
        """Split the current cell into num_rows x num_cols."""
        ctx = self.get_current_table_context()
        if not ctx or not ctx["cell"]:
            return
        split_cells(ctx["tbl"], ctx["cell"], num_rows, num_cols)
        self._on_formatting_applied()

    def distribute_table_rows(self) -> None:
        """Equalize height of all rows in current table."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        for row in tbl.rows:
            row.tr_pr.h = 24.0
            row.tr_pr.h_rule = "exact"
        self._on_formatting_applied()

    def distribute_table_cols(self) -> None:
        """Equalize width of all columns in current table."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        if tbl.grid:
            avg = sum(tbl.grid) / len(tbl.grid)
            tbl.grid = [round(avg, 2)] * len(tbl.grid)
        self._on_formatting_applied()

    def sort_table(self, ascending: bool = True) -> None:
        """Sort data rows of the current table by the current column text."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        c_idx = ctx["col_idx"]
        if len(tbl.rows) > 1:
            grid = table_map(tbl)

            def _key(row_entry: list):
                if c_idx < len(row_entry):
                    p = (
                        row_entry[c_idx].cell.blocks[0]
                        if row_entry[c_idx].cell.blocks
                        else None
                    )
                    return ptext(p) if p else ""
                return ""

            header = tbl.rows[0]
            rest = tbl.rows[1:]
            rest.sort(key=lambda r: _key(grid[tbl.rows.index(r)]), reverse=not ascending)
            tbl.rows = [header] + rest
            self._on_formatting_applied()

    def auto_sum_table(self) -> None:
        """Calculate and insert the sum of numbers above current cell."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        r_idx = ctx["row_idx"]
        c_idx = ctx["col_idx"]
        grid = table_map(tbl)
        total = 0.0
        for r in range(r_idx):
            cell = grid[r][c_idx].cell
            for b in cell.blocks:
                if isinstance(b, Paragraph):
                    txt = ptext(b).strip()
                    try:
                        total += float(txt)
                    except ValueError:
                        pass
        curr_p = ctx["cell"].blocks[0] if ctx["cell"].blocks else None
        if curr_p is not None:
            curr_p.runs = [TextItem(text=f"{total:g}", r_pr=copy.deepcopy(curr_p.r_pr))]
            self._on_formatting_applied()

    # -----------------------------------------------------------------------
    # Revision & Comment Operations
    # -----------------------------------------------------------------------

    def toggle_track_changes(self) -> bool:
        """Toggle track changes mode on document."""
        res = toggle_tracking(self.doc)
        self._on_formatting_applied()
        return res

    def accept_current_revision(self, all_revisions: bool = False) -> None:
        """Accept revision at current position or all revisions."""
        if all_revisions:
            accept_all_revisions(self.doc)
        else:
            revs = list_revisions(self.doc)
            if revs:
                accept_revision(self.doc, revs[0])
        self._on_formatting_applied()

    def reject_current_revision(self, all_revisions: bool = False) -> None:
        """Reject revision at current position or all revisions."""
        if all_revisions:
            reject_all_revisions(self.doc)
        else:
            revs = list_revisions(self.doc)
            if revs:
                reject_revision(self.doc, revs[0])
        self._on_formatting_applied()

    def insert_comment(self, author: str = "User", text: str = "") -> None:
        """Insert a comment on the current paragraph/selection."""
        p = self.controller._paragraph_by_id(self.controller.pos.para_id)
        if p is not None:
            a, b = self.controller.selection.ordered_range(self.doc)
            s = a.offset if a.para_id == p.id else 0
            e = b.offset if b.para_id == p.id else plen(p)
            insert_comment(
                self.doc,
                (p, s),
                (p, max(s + 1, e)),
                text=text or safe_tr("新批注"),
                author=author,
            )
            self._on_formatting_applied()

    def change_outline_level(self, delta: int) -> None:
        """Promote (delta < 0) or demote (delta > 0) outline level."""
        for p in self._get_selected_paragraphs():
            if p.p_pr is None:
                p.p_pr = ParagraphProperties()
            curr = p.p_pr.outline_level or 1
            new_lvl = max(1, min(9, curr + delta))
            p.p_pr.outline_level = new_lvl
        self._on_formatting_applied()

    def set_outline_level(self, level: int | None) -> None:
        """Set outline level (1-9 or None for body text)."""
        for p in self._get_selected_paragraphs():
            if p.p_pr is None:
                p.p_pr = ParagraphProperties()
            p.p_pr.outline_level = level
        self._on_formatting_applied()

    def move_paragraph(self, delta: int) -> None:
        """Move selected paragraph up (delta < 0) or down (delta > 0)."""
        p = self.controller._paragraph_by_id(self.controller.pos.para_id)
        if not p:
            return
        inf = info(self.doc, p)
        story = inf["story"] if inf and "story" in inf else self.doc.main
        if p in story.blocks:
            idx = story.blocks.index(p)
            new_idx = idx + delta
            if 0 <= new_idx < len(story.blocks):
                story.blocks.pop(idx)
                story.blocks.insert(new_idx, p)
                self._on_formatting_applied()

    # -----------------------------------------------------------------------
    # i18n & Localization
    # -----------------------------------------------------------------------

    def retranslate_ui(self) -> None:
        """Localize UI strings, status tips, and accessibility descriptions."""
        self.setToolTip(safe_tr("页面编辑画布 (Word 2003 视图)"))
        self.setStatusTip(safe_tr("点击编辑文本，支持打字、退格、多页排版与选区"))
        self.viewport().setAccessibleName(safe_tr("文档排版画布"))
        self.viewport().setAccessibleDescription(
            safe_tr("Word 2003 高保真多页仿真编辑视口，支持原位光标与选区交互")
        )

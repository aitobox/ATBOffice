"""Horizontal interactive ruler widget for Quire word processing."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import QWidget

from atboffice.modules.writer.models.document import Paragraph, sect_for
from atboffice.modules.writer.models.properties import SectionProperties, TabStop
from atboffice.modules.writer.views.rulers.types import (
    COLOR_DEFTAB_TICK,
    COLOR_MARKER_BORDER,
    COLOR_MARKER_FILL,
    COLOR_MARKER_HIGHLIGHT,
    COLOR_RULER_BG_MARGIN,
    COLOR_RULER_BG_PAGE,
    COLOR_RULER_BORDER,
    COLOR_RULER_TEXT,
    COLOR_RULER_TICK,
    PT_PER_CM,
    PT_PER_INCH,
    PT_PER_MM,
    RulerUnit,
    TabKind,
    draw_tab_glyph,
    pt_to_unit,
    safe_tr,
    snap_to_grid,
    unit_to_pt,
)

if TYPE_CHECKING:
    from atboffice.modules.writer.views.canvas_view import WriterCanvasView


class HorizontalRuler(QWidget):
    """Word 2003 styled interactive horizontal ruler."""

    guide_line_requested = Signal(float, bool)  # canvas_x_px, is_vertical=True
    guide_line_cleared = Signal()
    indent_changed = Signal(float, float, float)  # left_pt, first_line_pt, right_pt
    tab_stops_changed = Signal(list)  # list[TabStop]
    margin_changed = Signal(str, float)  # "left" | "right", margin_pt
    tabs_dialog_requested = Signal()
    page_setup_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(24)
        self.setMouseTracking(True)

        # Active display metrics
        self._unit: RulerUnit = RulerUnit.INCH
        self._zoom: float = 1.0
        self._scroll_x: float = 0.0
        self._pt_to_px_ratio: float = 96.0 / 72.0

        # Document geometry in canvas coords
        self._page_x_canvas: float = 24.0
        self._page_w_pt: float = 612.0  # Letter width in pt
        self._margin_left_pt: float = 90.0
        self._margin_right_pt: float = 90.0
        self._def_tab_pt: float = 36.0

        # Paragraph & Section models
        self._active_para: Paragraph | None = None
        self._active_sect: SectionProperties | None = None
        self._active_canvas: WriterCanvasView | None = None

        # Drag state
        self._drag_kind: str | None = None
        self._drag_start_x: float = 0.0
        self._drag_current_x: float = 0.0
        self._drag_current_y: float = 0.0
        self._drag_tab_index: int = -1
        self._active_selector_kind: TabKind = TabKind.LEFT

        self.retranslate_ui()

    # -----------------------------------------------------------------------
    # Configuration & Synchronization
    # -----------------------------------------------------------------------

    @property
    def unit(self) -> RulerUnit:
        return self._unit

    def set_unit(self, unit: RulerUnit | str) -> None:
        """Set measurement unit (cm, inch, pt)."""
        self._unit = RulerUnit(unit) if isinstance(unit, str) else unit
        self.update()

    def set_tab_selector_kind(self, kind: TabKind | str) -> None:
        """Update active tab selector kind from corner button."""
        self._active_selector_kind = TabKind(kind) if isinstance(kind, str) else kind

    def attach_canvas(self, canvas: WriterCanvasView) -> None:
        """Attach to a WriterCanvasView to track zoom, scrolling, and geometry."""
        self._active_canvas = canvas
        self._zoom = canvas.zoom
        self._scroll_x = float(canvas.horizontalScrollBar().value())
        self.guide_line_requested.connect(lambda x, v: canvas.set_ruler_guide(x=x))
        self.guide_line_cleared.connect(canvas.clear_ruler_guide)
        self.update_geometry_from_canvas()

    def update_scroll(self, scroll_x: float) -> None:
        """Synchronize horizontal scroll offset."""
        if not math.isclose(self._scroll_x, scroll_x, abs_tol=1e-3):
            self._scroll_x = scroll_x
            self.update()

    def update_zoom(self, zoom: float) -> None:
        """Synchronize zoom factor."""
        if not math.isclose(self._zoom, zoom, abs_tol=1e-3):
            self._zoom = zoom
            self.update()

    def update_geometry_from_canvas(self) -> None:
        """Refresh page and paragraph positions from attached canvas view."""
        if not self._active_canvas:
            return

        canvas = self._active_canvas
        self._zoom = canvas.zoom
        self._scroll_x = float(canvas.horizontalScrollBar().value())

        # Current page
        page_idx, _, _ = canvas.controller.pos_to_canvas(canvas.controller.pos)
        page_rect = canvas.page_rect_canvas(page_idx)
        self._page_x_canvas = page_rect.left()

        # Current section and paragraph
        doc = canvas.doc
        p = canvas.controller._paragraph_by_id(canvas.controller.pos.para_id)
        self._active_para = p

        sect = sect_for(doc, p) if (doc and p) else (doc.sect if doc else None)
        self._active_sect = sect

        if sect:
            self._page_w_pt = sect.pg_w
            self._margin_left_pt = sect.ml
            self._margin_right_pt = sect.mr
        else:
            self._page_w_pt = 612.0
            self._margin_left_pt = 90.0
            self._margin_right_pt = 90.0

        self.update()

    def retranslate_ui(self) -> None:
        """Update localized tooltips and text."""
        self.setToolTip(safe_tr("Horizontal Ruler (Drag indents, margins, or click to add tab stops)"))

    # -----------------------------------------------------------------------
    # Coordinate Mapping Helpers
    # -----------------------------------------------------------------------

    def px_per_pt(self) -> float:
        return self._pt_to_px_ratio * self._zoom

    def page_left_ruler(self) -> float:
        return self._page_x_canvas - self._scroll_x

    def page_right_ruler(self) -> float:
        return self.page_left_ruler() + self._page_w_pt * self.px_per_pt()

    def text_left_ruler(self) -> float:
        return self.page_left_ruler() + self._margin_left_pt * self.px_per_pt()

    def text_right_ruler(self) -> float:
        return self.page_right_ruler() - self._margin_right_pt * self.px_per_pt()

    def pt_to_ruler_x(self, pt_from_margin: float) -> float:
        return self.text_left_ruler() + pt_from_margin * self.px_per_pt()

    def ruler_x_to_pt(self, x_ruler: float) -> float:
        return (x_ruler - self.text_left_ruler()) / self.px_per_pt()

    def ruler_x_to_canvas_x(self, x_ruler: float) -> float:
        return x_ruler + self._scroll_x

    # -----------------------------------------------------------------------
    # Markers Hit-Testing & Layout
    # -----------------------------------------------------------------------

    def _get_marker_rects(self) -> dict[str, QRectF]:
        """Compute the bounding boxes of indent markers in ruler pixel coordinates."""
        p = self._active_para
        l_pt = p.indent_left if p else 0.0
        fl_pt = p.indent_first if p else 0.0
        r_pt = p.indent_right if p else 0.0

        text_l = self.text_left_ruler()
        text_r = self.text_right_ruler()
        px_pt = self.px_per_pt()

        first_x = text_l + (l_pt + fl_pt) * px_pt
        hang_x = text_l + l_pt * px_pt
        left_x = hang_x
        right_x = text_r - r_pt * px_pt

        return {
            "first": QRectF(first_x - 5.0, 1.0, 10.0, 8.0),
            "hang": QRectF(hang_x - 5.0, 9.0, 10.0, 8.0),
            "left": QRectF(left_x - 5.0, 17.0, 10.0, 6.0),
            "right": QRectF(right_x - 5.0, 13.0, 10.0, 10.0),
        }

    def _get_tab_rects(self) -> list[tuple[int, TabStop, QRectF]]:
        """Compute bounding boxes for all paragraph tab stops."""
        p = self._active_para
        if not p:
            return []
        rects = []
        for i, t in enumerate(p.p_pr.tabs):
            x = self.pt_to_ruler_x(t.pos)
            rects.append((i, t, QRectF(x - 5.0, 12.0, 10.0, 11.0)))
        return rects

    # -----------------------------------------------------------------------
    # Painting
    # -----------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        width = float(self.width())
        height = float(self.height())
        page_l = self.page_left_ruler()
        page_r = self.page_right_ruler()
        text_l = self.text_left_ruler()
        text_r = self.text_right_ruler()

        # 1. Background outside page (workspace neutral gray)
        painter.fillRect(self.rect(), QColor(140, 140, 140))

        # 2. Page Margins Background (soft blue-gray)
        if page_r > 0 and page_l < width:
            clamped_page_l = max(0.0, page_l)
            clamped_page_w = min(width, page_r) - clamped_page_l
            painter.fillRect(QRectF(clamped_page_l, 2.0, clamped_page_w, height - 4.0), COLOR_RULER_BG_MARGIN)

        # 3. Text Column Background (pure white)
        if text_r > 0 and text_l < width:
            clamped_text_l = max(0.0, text_l)
            clamped_text_w = max(0.0, min(width, text_r) - clamped_text_l)
            painter.fillRect(QRectF(clamped_text_l, 2.0, clamped_text_w, height - 4.0), COLOR_RULER_BG_PAGE)

        # 4. Draw Ruler Border Lines
        painter.setPen(QPen(COLOR_RULER_BORDER, 1.0))
        painter.drawLine(QPointF(0, 1.0), QPointF(width, 1.0))
        painter.drawLine(QPointF(0, height - 1.0), QPointF(width, height - 1.0))

        # 5. Draw Scale Ticks and Unit Numbers
        self._paint_ticks_and_numbers(painter, page_l, page_r, text_l, height)

        # 6. Draw Default Tab Ticks
        self._paint_default_tabs(painter, text_l, text_r, height)

        # 7. Draw Custom Tab Stops
        self._paint_tab_stops(painter)

        # 8. Draw Indent Markers (first, hang, left, right)
        self._paint_indent_markers(painter)

    def _paint_ticks_and_numbers(
        self,
        painter: QPainter,
        page_l: float,
        page_r: float,
        text_l: float,
        height: float,
    ) -> None:
        """Render major/minor ticks and numeric labels measured from left text margin."""
        px_pt = self.px_per_pt()
        if self._unit == RulerUnit.CM:
            unit_pt = PT_PER_CM
            subs = 4  # 2.5 mm per tick
        elif self._unit == RulerUnit.PT:
            unit_pt = 72.0
            subs = 6
        else:
            unit_pt = PT_PER_INCH
            subs = 8  # 1/8 inch per tick

        step_px = (unit_pt / subs) * px_pt
        if step_px < 2.0:
            return

        font = QFont("Tahoma", 8)
        font.setStyleHint(QFont.StyleHint.SansSerif)
        painter.setFont(font)
        painter.setPen(QPen(COLOR_RULER_TICK, 1.0))

        k_min = math.ceil((max(0.0, page_l) - text_l) / step_px)
        k_max = math.floor((min(float(self.width()), page_r) - text_l) / step_px)

        for k in range(k_min, k_max + 1):
            x = round(text_l + k * step_px) + 0.5
            if k % subs == 0:
                # Major tick with number
                n = abs(k // subs)
                if n != 0:
                    painter.setPen(QPen(COLOR_RULER_TEXT))
                    painter.drawText(QRectF(x - 12.0, 3.0, 24.0, height - 6.0), Qt.AlignmentFlag.AlignCenter, str(n))
                painter.setPen(QPen(COLOR_RULER_TICK, 1.0))
                painter.drawLine(QPointF(x, height - 8.0), QPointF(x, height - 3.0))
            else:
                # Sub-ticks
                tick_len = 5.0 if k % (subs // 2) == 0 else 2.5
                painter.setPen(QPen(COLOR_RULER_TICK, 1.0))
                painter.drawLine(QPointF(x, height - 3.0 - tick_len), QPointF(x, height - 3.0))

    def _paint_default_tabs(self, painter: QPainter, text_l: float, text_r: float, height: float) -> None:
        """Draw small default tab stop tick marks at the bottom of the ruler."""
        px_pt = self.px_per_pt()
        def_tab_px = self._def_tab_pt * px_pt
        if def_tab_px < 6.0:
            return

        p = self._active_para
        last_tab_pt = p.indent_left if p else 0.0
        if p and p.p_pr.tabs:
            last_tab_pt = max(last_tab_pt, max(t.pos for t in p.p_pr.tabs))

        start_px = text_l + math.ceil((last_tab_pt + 1.0) * px_pt / def_tab_px) * def_tab_px
        painter.setPen(QPen(COLOR_DEFTAB_TICK, 1.0))

        cur_x = start_px
        while cur_x < text_r:
            painter.drawLine(QPointF(round(cur_x) + 0.5, height - 3.0), QPointF(round(cur_x) + 0.5, height - 1.0))
            cur_x += def_tab_px

    def _paint_tab_stops(self, painter: QPainter) -> None:
        """Render custom tab stops from active paragraph."""
        for idx, tab, rect in self._get_tab_rects():
            center = QPointF(rect.center().x(), rect.center().y())
            draw_tab_glyph(painter, tab.align, center, size=9.0)

    def _paint_indent_markers(self, painter: QPainter) -> None:
        """Render First Line, Hanging, Left, and Right indent triangles and boxes."""
        rects = self._get_marker_rects()

        # 1. First Line Indent (Downward pointing triangle/pentagon)
        r_first = rects["first"]
        path_first = QPainterPath()
        path_first.moveTo(r_first.left(), r_first.top())
        path_first.lineTo(r_first.right(), r_first.top())
        path_first.lineTo(r_first.right(), r_first.top() + 3.0)
        path_first.lineTo(r_first.center().x(), r_first.bottom())
        path_first.lineTo(r_first.left(), r_first.top() + 3.0)
        path_first.closeSubpath()

        painter.setBrush(COLOR_MARKER_FILL)
        painter.setPen(QPen(COLOR_MARKER_BORDER, 1.0))
        painter.drawPath(path_first)

        # 2. Hanging Indent (Upward pointing triangle)
        r_hang = rects["hang"]
        path_hang = QPainterPath()
        path_hang.moveTo(r_hang.center().x(), r_hang.top())
        path_hang.lineTo(r_hang.right(), r_hang.bottom())
        path_hang.lineTo(r_hang.left(), r_hang.bottom())
        path_hang.closeSubpath()
        painter.drawPath(path_hang)

        # 3. Left Indent Box (Rectangle beneath hanging triangle)
        r_left = rects["left"]
        painter.drawRect(r_left)

        # 4. Right Indent (Upward pointing triangle)
        r_right = rects["right"]
        path_right = QPainterPath()
        path_right.moveTo(r_right.center().x(), r_right.top())
        path_right.lineTo(r_right.right(), r_right.bottom())
        path_right.lineTo(r_right.left(), r_right.bottom())
        path_right.closeSubpath()
        painter.drawPath(path_right)

    # -----------------------------------------------------------------------
    # Mouse Interaction & Dragging
    # -----------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        x = float(event.position().x())
        y = float(event.position().y())
        text_l = self.text_left_ruler()
        text_r = self.text_right_ruler()

        # Check indent markers first
        marker_rects = self._get_marker_rects()
        for kind in ("first", "left", "hang", "right"):
            if marker_rects[kind].contains(QPointF(x, y)):
                self._drag_kind = kind
                self._drag_start_x = x
                self._drag_current_x = x
                self._drag_current_y = y
                self.guide_line_requested.emit(self.ruler_x_to_canvas_x(x), True)
                event.accept()
                return

        # Check existing tab stops
        for idx, tab, rect in self._get_tab_rects():
            if rect.contains(QPointF(x, y)):
                self._drag_kind = "tab"
                self._drag_tab_index = idx
                self._drag_start_x = x
                self._drag_current_x = x
                self._drag_current_y = y
                self.guide_line_requested.emit(self.ruler_x_to_canvas_x(x), True)
                event.accept()
                return

        # Check page margins
        if abs(x - text_l) <= 4.0:
            self._drag_kind = "margin_left"
            self._drag_start_x = x
            self.guide_line_requested.emit(self.ruler_x_to_canvas_x(x), True)
            event.accept()
            return
        if abs(x - text_r) <= 4.0:
            self._drag_kind = "margin_right"
            self._drag_start_x = x
            self.guide_line_requested.emit(self.ruler_x_to_canvas_x(x), True)
            event.accept()
            return

        # Click in text area adds a new tab stop or sets indent depending on tab selector
        if text_l <= x <= text_r:
            if self._active_selector_kind == TabKind.FIRST_LINE:
                self._drag_kind = "first"
            elif self._active_selector_kind == TabKind.HANGING:
                self._drag_kind = "hang"
            else:
                self._drag_kind = "new_tab"

            self._drag_start_x = x
            self._drag_current_x = x
            self._drag_current_y = y
            self.guide_line_requested.emit(self.ruler_x_to_canvas_x(x), True)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        x = float(event.position().x())
        y = float(event.position().y())
        self._drag_current_x = x
        self._drag_current_y = y

        # Cursor update when hovering over margins
        text_l = self.text_left_ruler()
        text_r = self.text_right_ruler()
        if abs(x - text_l) <= 4.0 or abs(x - text_r) <= 4.0:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        if not self._drag_kind:
            super().mouseMoveEvent(event)
            return

        # Snapping logic
        alt_pressed = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        raw_pt = self.ruler_x_to_pt(x)
        snapped_pt = snap_to_grid(raw_pt, self._unit, disable_snap=alt_pressed)
        guide_x = self.text_left_ruler() + snapped_pt * self.px_per_pt()

        # Update guideline on canvas
        self.guide_line_requested.emit(self.ruler_x_to_canvas_x(guide_x), True)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if not self._drag_kind:
            super().mouseReleaseEvent(event)
            return

        self.guide_line_cleared.emit()
        kind = self._drag_kind
        self._drag_kind = None

        alt_pressed = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        x = float(event.position().x())
        y = float(event.position().y())
        raw_pt = self.ruler_x_to_pt(x)
        pt = snap_to_grid(raw_pt, self._unit, disable_snap=alt_pressed)

        p = self._active_para
        if not p:
            self.update()
            return

        # Apply paragraph indent / tab changes
        if kind == "first":
            p.indent_first = round(pt - p.indent_left, 2)
        elif kind == "hang":
            first_abs = p.indent_left + p.indent_first
            p.indent_left = round(max(-72.0, pt), 2)
            p.indent_first = round(first_abs - pt, 2)
        elif kind == "left":
            p.indent_left = round(max(-72.0, pt), 2)
        elif kind == "right":
            from_right = (self.text_right_ruler() - x) / self.px_per_pt()
            p.indent_right = round(max(0.0, snap_to_grid(from_right, self._unit, disable_snap=alt_pressed)), 2)
        elif kind == "tab":
            # If dragged vertically out of ruler area (> 18px), delete the tab stop
            is_off = y < -18.0 or y > float(self.height()) + 18.0
            if 0 <= self._drag_tab_index < len(p.p_pr.tabs):
                if is_off:
                    del p.p_pr.tabs[self._drag_tab_index]
                else:
                    p.p_pr.tabs[self._drag_tab_index].pos = max(0.0, pt)
                    p.p_pr.tabs.sort(key=lambda t: t.pos)
            self.tab_stops_changed.emit(p.p_pr.tabs)
        elif kind == "new_tab":
            if pt > 0:
                new_tab = TabStop(pos=pt, align=self._active_selector_kind.value)
                p.p_pr.tabs = [t for t in p.p_pr.tabs if abs(t.pos - pt) > 2.0]
                p.p_pr.tabs.append(new_tab)
                p.p_pr.tabs.sort(key=lambda t: t.pos)
                self.tab_stops_changed.emit(p.p_pr.tabs)
        elif kind in ("margin_left", "margin_right") and self._active_sect:
            dx_pt = (x - self._drag_start_x) / self.px_per_pt()
            if kind == "margin_left":
                self._active_sect.ml = round(max(18.0, self._active_sect.ml + dx_pt), 2)
                self.margin_changed.emit("left", self._active_sect.ml)
            else:
                self._active_sect.mr = round(max(18.0, self._active_sect.mr - dx_pt), 2)
                self.margin_changed.emit("right", self._active_sect.mr)

        self.indent_changed.emit(p.indent_left, p.indent_first, p.indent_right)

        # Trigger repagination and view refresh on attached canvas
        if self._active_canvas:
            self._active_canvas.controller.repaginate_and_refresh()
            self.update_geometry_from_canvas()

        self.update()
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        x = float(event.position().x())
        y = float(event.position().y())

        # If double clicked on tab stop: open tabs dialog
        for _, _, rect in self._get_tab_rects():
            if rect.contains(QPointF(x, y)):
                self.tabs_dialog_requested.emit()
                event.accept()
                return

        # Double click on text area: open tabs dialog; outside: open page setup
        if self.text_left_ruler() <= x <= self.text_right_ruler():
            self.tabs_dialog_requested.emit()
        else:
            self.page_setup_requested.emit()
        event.accept()

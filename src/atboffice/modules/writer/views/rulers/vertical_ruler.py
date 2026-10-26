"""Vertical interactive ruler widget for Quire word processing."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import QWidget

from atboffice.modules.writer.models.document import sect_for
from atboffice.modules.writer.models.properties import SectionProperties
from atboffice.modules.writer.views.rulers.types import (
    COLOR_RULER_BG_MARGIN,
    COLOR_RULER_BG_PAGE,
    COLOR_RULER_BORDER,
    COLOR_RULER_TEXT,
    COLOR_RULER_TICK,
    PT_PER_CM,
    PT_PER_INCH,
    RulerUnit,
    safe_tr,
    snap_to_grid,
)

if TYPE_CHECKING:
    from atboffice.modules.writer.views.canvas_view import WriterCanvasView


class VerticalRuler(QWidget):
    """Word 2003 styled interactive vertical ruler."""

    guide_line_requested = Signal(float, bool)  # canvas_y_px, is_vertical=False
    guide_line_cleared = Signal()
    margin_changed = Signal(str, float)  # "top" | "bottom", margin_pt
    page_setup_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(24)
        self.setMouseTracking(True)

        self._unit: RulerUnit = RulerUnit.INCH
        self._zoom: float = 1.0
        self._scroll_y: float = 0.0
        self._pt_to_px_ratio: float = 96.0 / 72.0

        # Geometry
        self._page_y_canvas: float = 24.0
        self._page_h_pt: float = 792.0  # Letter height
        self._margin_top_pt: float = 72.0
        self._margin_bottom_pt: float = 72.0

        self._active_sect: SectionProperties | None = None
        self._active_canvas: WriterCanvasView | None = None

        # Drag state
        self._drag_kind: str | None = None  # "top" | "bottom"
        self._drag_start_y: float = 0.0

        self.retranslate_ui()

    @property
    def unit(self) -> RulerUnit:
        return self._unit

    def set_unit(self, unit: RulerUnit | str) -> None:
        """Set measurement unit (cm, inch, pt)."""
        self._unit = RulerUnit(unit) if isinstance(unit, str) else unit
        self.update()

    def attach_canvas(self, canvas: WriterCanvasView) -> None:
        """Attach to a WriterCanvasView to track zoom, scrolling, and geometry."""
        self._active_canvas = canvas
        self._zoom = canvas.zoom
        self._scroll_y = float(canvas.verticalScrollBar().value())
        self.guide_line_requested.connect(lambda y, v: canvas.set_ruler_guide(y=y))
        self.guide_line_cleared.connect(canvas.clear_ruler_guide)
        self.update_geometry_from_canvas()

    def update_scroll(self, scroll_y: float) -> None:
        """Synchronize vertical scroll offset."""
        if not math.isclose(self._scroll_y, scroll_y, abs_tol=1e-3):
            self._scroll_y = scroll_y
            self.update()

    def update_zoom(self, zoom: float) -> None:
        """Synchronize zoom factor."""
        if not math.isclose(self._zoom, zoom, abs_tol=1e-3):
            self._zoom = zoom
            self.update()

    def update_geometry_from_canvas(self) -> None:
        """Refresh page and section positions from attached canvas view."""
        if not self._active_canvas:
            return

        canvas = self._active_canvas
        self._zoom = canvas.zoom
        self._scroll_y = float(canvas.verticalScrollBar().value())

        page_idx, _, _ = canvas.controller.pos_to_canvas(canvas.controller.pos)
        page_rect = canvas.page_rect_canvas(page_idx)
        self._page_y_canvas = page_rect.top()

        doc = canvas.doc
        p = canvas.controller._paragraph_by_id(canvas.controller.pos.para_id)
        sect = sect_for(doc, p) if (doc and p) else (doc.sect if doc else None)
        self._active_sect = sect

        if sect:
            self._page_h_pt = sect.pg_h
            self._margin_top_pt = sect.mt
            self._margin_bottom_pt = sect.mb
        else:
            self._page_h_pt = 792.0
            self._margin_top_pt = 72.0
            self._margin_bottom_pt = 72.0

        self.update()

    def retranslate_ui(self) -> None:
        """Update localized tooltips and text."""
        self.setToolTip(safe_tr("Vertical Ruler (Drag top and bottom page margins)"))

    # -----------------------------------------------------------------------
    # Coordinate Mapping Helpers
    # -----------------------------------------------------------------------

    def px_per_pt(self) -> float:
        return self._pt_to_px_ratio * self._zoom

    def page_top_ruler(self) -> float:
        return self._page_y_canvas - self._scroll_y

    def page_bottom_ruler(self) -> float:
        return self.page_top_ruler() + self._page_h_pt * self.px_per_pt()

    def text_top_ruler(self) -> float:
        return self.page_top_ruler() + self._margin_top_pt * self.px_per_pt()

    def text_bottom_ruler(self) -> float:
        return self.page_bottom_ruler() - self._margin_bottom_pt * self.px_per_pt()

    def ruler_y_to_pt(self, y_ruler: float) -> float:
        return (y_ruler - self.text_top_ruler()) / self.px_per_pt()

    def ruler_y_to_canvas_y(self, y_ruler: float) -> float:
        return y_ruler + self._scroll_y

    # -----------------------------------------------------------------------
    # Painting
    # -----------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        width = float(self.width())
        height = float(self.height())
        page_t = self.page_top_ruler()
        page_b = self.page_bottom_ruler()
        text_t = self.text_top_ruler()
        text_b = self.text_bottom_ruler()

        # 1. Background outside page (workspace neutral gray)
        painter.fillRect(self.rect(), QColor(140, 140, 140))

        # 2. Page Margins Background (soft blue-gray)
        if page_b > 0 and page_t < height:
            clamped_page_t = max(0.0, page_t)
            clamped_page_h = min(height, page_b) - clamped_page_t
            painter.fillRect(
                QRectF(2.0, clamped_page_t, width - 4.0, clamped_page_h), COLOR_RULER_BG_MARGIN
            )

        # 3. Text Column Background (pure white)
        if text_b > 0 and text_t < height:
            clamped_text_t = max(0.0, text_t)
            clamped_text_h = max(0.0, min(height, text_b) - clamped_text_t)
            painter.fillRect(
                QRectF(2.0, clamped_text_t, width - 4.0, clamped_text_h), COLOR_RULER_BG_PAGE
            )

        # 4. Ruler Border Lines
        painter.setPen(QPen(COLOR_RULER_BORDER, 1.0))
        painter.drawLine(QPointF(1.0, 0), QPointF(1.0, height))
        painter.drawLine(QPointF(width - 1.0, 0), QPointF(width - 1.0, height))

        # 5. Draw Scale Ticks and Numbers
        self._paint_ticks_and_numbers(painter, page_t, page_b, text_t, width)

        # 6. Draw Margin Dividers
        painter.setPen(QPen(QColor(100, 100, 100), 1.0))
        if 0 <= text_t <= height:
            painter.drawLine(
                QPointF(2.0, round(text_t) + 0.5), QPointF(width - 2.0, round(text_t) + 0.5)
            )
        if 0 <= text_b <= height:
            painter.drawLine(
                QPointF(2.0, round(text_b) + 0.5), QPointF(width - 2.0, round(text_b) + 0.5)
            )

    def _paint_ticks_and_numbers(
        self,
        painter: QPainter,
        page_t: float,
        page_b: float,
        text_t: float,
        width: float,
    ) -> None:
        """Render vertical major/minor ticks and numeric labels measured from top margin."""
        px_pt = self.px_per_pt()
        if self._unit == RulerUnit.CM:
            unit_pt = PT_PER_CM
            subs = 4
        elif self._unit == RulerUnit.PT:
            unit_pt = 72.0
            subs = 6
        else:
            unit_pt = PT_PER_INCH
            subs = 8

        step_px = (unit_pt / subs) * px_pt
        if step_px < 2.0:
            return

        font = QFont("Tahoma", 7)
        font.setStyleHint(QFont.StyleHint.SansSerif)
        painter.setFont(font)
        painter.setPen(QPen(COLOR_RULER_TICK, 1.0))

        k_min = math.ceil((max(0.0, page_t) - text_t) / step_px)
        k_max = math.floor((min(float(self.height()), page_b) - text_t) / step_px)

        for k in range(k_min, k_max + 1):
            y = round(text_t + k * step_px) + 0.5
            if k % subs == 0:
                n = abs(k // subs)
                if n != 0:
                    painter.save()
                    painter.setPen(QPen(COLOR_RULER_TEXT))
                    # Draw rotated number or centered number
                    painter.translate(width / 2.0 + 2.0, y)
                    painter.rotate(-90.0)
                    painter.drawText(
                        QRectF(-12.0, -8.0, 24.0, 16.0), Qt.AlignmentFlag.AlignCenter, str(n)
                    )
                    painter.restore()
                painter.setPen(QPen(COLOR_RULER_TICK, 1.0))
                painter.drawLine(QPointF(width - 8.0, y), QPointF(width - 3.0, y))
            else:
                tick_len = 5.0 if k % (subs // 2) == 0 else 2.5
                painter.setPen(QPen(COLOR_RULER_TICK, 1.0))
                painter.drawLine(QPointF(width - 3.0 - tick_len, y), QPointF(width - 3.0, y))

    # -----------------------------------------------------------------------
    # Mouse Interaction
    # -----------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        y = float(event.position().y())
        text_t = self.text_top_ruler()
        text_b = self.text_bottom_ruler()

        if abs(y - text_t) <= 4.0:
            self._drag_kind = "top"
            self._drag_start_y = y
            self.guide_line_requested.emit(self.ruler_y_to_canvas_y(y), False)
            event.accept()
            return
        elif abs(y - text_b) <= 4.0:
            self._drag_kind = "bottom"
            self._drag_start_y = y
            self.guide_line_requested.emit(self.ruler_y_to_canvas_y(y), False)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        y = float(event.position().y())
        text_t = self.text_top_ruler()
        text_b = self.text_bottom_ruler()

        if abs(y - text_t) <= 4.0 or abs(y - text_b) <= 4.0:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        if not self._drag_kind:
            super().mouseMoveEvent(event)
            return

        alt_pressed = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        raw_pt = self.ruler_y_to_pt(y)
        snapped_pt = snap_to_grid(raw_pt, self._unit, disable_snap=alt_pressed)
        guide_y = self.text_top_ruler() + snapped_pt * self.px_per_pt()

        self.guide_line_requested.emit(self.ruler_y_to_canvas_y(guide_y), False)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if not self._drag_kind:
            super().mouseReleaseEvent(event)
            return

        self.guide_line_cleared.emit()
        kind = self._drag_kind
        self._drag_kind = None

        y = float(event.position().y())
        dy_pt = (y - self._drag_start_y) / self.px_per_pt()

        if self._active_sect:
            if kind == "top":
                self._active_sect.mt = round(max(18.0, self._active_sect.mt + dy_pt), 2)
                self.margin_changed.emit("top", self._active_sect.mt)
            elif kind == "bottom":
                self._active_sect.mb = round(max(18.0, self._active_sect.mb - dy_pt), 2)
                self.margin_changed.emit("bottom", self._active_sect.mb)

        if self._active_canvas:
            self._active_canvas.controller.repaginate_and_refresh()
            self.update_geometry_from_canvas()

        self.update()
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.page_setup_requested.emit()
        event.accept()

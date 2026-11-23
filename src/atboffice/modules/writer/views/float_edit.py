"""On-canvas selection, moving and resizing of floating pictures and shapes (Quire).

Page float boxes are in page points; the canvas maps a viewport point to
``(page_index, point_on_page)`` with ``viewport_to_doc_coords``. A drag edits the
object's ``float_pr`` offsets (move) or ``width``/``height`` (resize) and relays out.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen

from atboffice.modules.writer.models.drawing import AnchorHandle, drag_handle_resize

HANDLE_PT = 3.5  # half size of a sizing handle, in points
_HANDLES = (
    AnchorHandle.NW, AnchorHandle.N, AnchorHandle.NE, AnchorHandle.E,
    AnchorHandle.SE, AnchorHandle.S, AnchorHandle.SW, AnchorHandle.W,
)
_CURSORS = {
    "nw": Qt.CursorShape.SizeFDiagCursor, "se": Qt.CursorShape.SizeFDiagCursor,
    "ne": Qt.CursorShape.SizeBDiagCursor, "sw": Qt.CursorShape.SizeBDiagCursor,
    "n": Qt.CursorShape.SizeVerCursor, "s": Qt.CursorShape.SizeVerCursor,
    "e": Qt.CursorShape.SizeHorCursor, "w": Qt.CursorShape.SizeHorCursor,
}


@dataclass
class FloatDrag:
    page_index: int
    item: Any
    handle: str | None  # None = move
    start: QPointF  # page points
    box: tuple[float, float, float, float]  # x, y, w, h at press
    current: QPointF | None = None


def handle_points(x: float, y: float, w: float, h: float) -> dict[str, QPointF]:
    return {
        "nw": QPointF(x, y), "n": QPointF(x + w / 2, y), "ne": QPointF(x + w, y),
        "e": QPointF(x + w, y + h / 2), "se": QPointF(x + w, y + h),
        "s": QPointF(x + w / 2, y + h), "sw": QPointF(x, y + h), "w": QPointF(x, y + h / 2),
    }


def float_at(page: Any, pt: QPointF) -> Any | None:
    """The top-most float box on ``page`` containing ``pt`` (page points)."""
    boxes = [fb for fb in getattr(page, "float_boxes", []) if fb.item is not None]
    # Foreground boxes paint last, so they are hit first; behind-text boxes come after.
    for fb in sorted(boxes, key=lambda b: (not b.behind, b.z_index), reverse=True):
        if QRectF(fb.x, fb.y, fb.w, fb.h).contains(pt):
            return fb
    return None


def box_for_item(page: Any, item: Any) -> Any | None:
    for fb in getattr(page, "float_boxes", []):
        if fb.item is item:
            return fb
    return None


def handle_at(fb: Any, pt: QPointF, tolerance: float) -> str | None:
    for name, hp in handle_points(fb.x, fb.y, fb.w, fb.h).items():
        if abs(hp.x() - pt.x()) <= tolerance and abs(hp.y() - pt.y()) <= tolerance:
            return name
    return None


def cursor_for(handle: str | None) -> Qt.CursorShape:
    return _CURSORS.get(handle or "", Qt.CursorShape.SizeAllCursor)


def preview_box(drag: FloatDrag) -> tuple[float, float, float, float]:
    """Rubber-band rectangle (page points) for the drag in progress."""
    x, y, w, h = drag.box
    if drag.current is None:
        return drag.box
    dx = drag.current.x() - drag.start.x()
    dy = drag.current.y() - drag.start.y()
    if drag.handle is None:
        return x + dx, y + dy, w, h
    if "e" in drag.handle:
        w += dx
    if "w" in drag.handle:
        x, w = x + dx, w - dx
    if "s" in drag.handle:
        h += dy
    if "n" in drag.handle:
        y, h = y + dy, h - dy
    w, h = max(2.0, w), max(2.0, h)
    return x, y, w, h


def apply_move(item: Any, fb_x: float, fb_y: float, dx: float, dy: float) -> None:
    """Move a floating object by (dx, dy) points, keeping its anchor relation.

    Aligned (left/center/…), percentage and character-relative horizontal positions
    become absolute page offsets, like Word does once you drag an aligned picture.
    """
    fp = item.float_pr
    if fp is None:
        return
    h = fp.pos_h
    if h.align or h.percent is not None or h.rel == "character":
        h.rel, h.align, h.percent = "page", None, None
        h.offset = round(fb_x + dx, 2)
    else:
        h.offset = round(h.offset + dx, 2)
    v = fp.pos_v
    if v.align or v.percent is not None or v.rel == "line":
        v.rel, v.align, v.percent = "page", None, None
        v.offset = round(fb_y + dy, 2)
    else:
        v.offset = round(v.offset + dy, 2)


def apply_drag(drag: FloatDrag, end: QPointF, lock_aspect: bool = False) -> bool:
    """Commit ``drag`` ending at ``end`` (page points). True when the object changed."""
    dx = end.x() - drag.start.x()
    dy = end.y() - drag.start.y()
    if abs(dx) < 0.5 and abs(dy) < 0.5:
        return False
    item = drag.item
    if drag.handle is None:
        apply_move(item, drag.box[0], drag.box[1], dx, dy)
    else:
        drag_handle_resize(item, AnchorHandle(drag.handle), dx, dy, lock_aspect=lock_aspect)
    return True


def paint_selection(
    painter: QPainter, page_rect_vp: QRectF, to_px: Any, box: tuple[float, float, float, float],
    dashed: bool = False,
) -> None:
    """Selection frame with eight sizing handles (Word 2003 style)."""
    x, y, w, h = box
    rect = QRectF(page_rect_vp.left() + to_px(x), page_rect_vp.top() + to_px(y),
                  to_px(w), to_px(h))
    painter.save()
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(0, 0, 0), 1.0,
                        Qt.PenStyle.DashLine if dashed else Qt.PenStyle.SolidLine))
    painter.drawRect(rect)
    if not dashed:
        s = 3.5
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        for hp in handle_points(rect.x(), rect.y(), rect.width(), rect.height()).values():
            painter.drawRect(QRectF(hp.x() - s, hp.y() - s, 2 * s, 2 * s))
    painter.restore()

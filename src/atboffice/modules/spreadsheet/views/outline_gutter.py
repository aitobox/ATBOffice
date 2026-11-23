"""Outline gutter beside the grid headers: level buttons (1, 2, 3 …) and +/- buttons."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication, QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from atboffice.modules.spreadsheet.models import outline

STEP = 14  # px per outline level
BUTTON = 11


def safe_tr(text: str) -> str:
    return QCoreApplication.translate("OutlineGutter", text)


class OutlineGutter(QWidget):
    """Painted in the GridViewport's viewport margins, so grid geometry is unchanged."""

    def __init__(self, grid: Any) -> None:
        super().__init__(grid)
        self.grid = grid
        self.setMouseTracking(False)

    # ---------------------------------------------------------------- geometry
    def sizes(self) -> tuple[int, int]:
        """(left gutter width, top gutter height) in widget pixels (0 when no outline)."""
        sheet = self.grid.model
        rows = outline.max_level(sheet, "row")
        cols = outline.max_level(sheet, "col")
        return (rows + 1) * STEP + 4 if rows else 0, (cols + 1) * STEP + 4 if cols else 0

    def _row_y(self, r: int) -> float:
        g = self.grid
        top = g.viewportMargins().top()
        return top + (g.col_header_height + g.geometry_mapper.row_pos(r)
                      - g.verticalScrollBar().value()) * g.zoom

    def _col_x(self, c: int) -> float:
        g = self.grid
        left = g.viewportMargins().left()
        return left + (g.row_header_width + g.geometry_mapper.col_pos(c)
                       - g.horizontalScrollBar().value()) * g.zoom

    def buttons(self) -> list[tuple[QRect, str, Any]]:
        """Clickable buttons: (rect, kind, payload) with kind "level-row", "level-col",
        "toggle-row" or "toggle-col"."""
        sheet = self.grid.model
        gw, gh = self.sizes()
        out: list[tuple[QRect, str, Any]] = []
        row_levels = outline.max_level(sheet, "row")
        col_levels = outline.max_level(sheet, "col")
        for level in range(1, row_levels + 2 if row_levels else 1):
            out.append((QRect((level - 1) * STEP + 2, gh + 2, BUTTON, BUTTON), "level-row", level))
        for level in range(1, col_levels + 2 if col_levels else 1):
            out.append((QRect(gw + 2, (level - 1) * STEP + 2, BUTTON, BUTTON), "level-col", level))
        for grp in outline.groups(sheet, "row"):
            y0, y1 = self._row_y(grp.summary), self._row_y(grp.summary + 1)
            yc = int((y0 + y1) / 2)
            out.append((QRect((grp.level - 1) * STEP + 2, yc - BUTTON // 2, BUTTON, BUTTON),
                        "toggle-row", grp))
        for grp in outline.groups(sheet, "col"):
            x0, x1 = self._col_x(grp.summary), self._col_x(grp.summary + 1)
            xc = int((x0 + x1) / 2)
            out.append((QRect(xc - BUTTON // 2, (grp.level - 1) * STEP + 2, BUTTON, BUTTON),
                        "toggle-col", grp))
        return out

    def relayout(self) -> None:
        """Resize to cover the grid and reserve margins (called after outline changes)."""
        gw, gh = self.sizes()
        self.grid.setViewportMargins(gw, gh, 0, 0)
        self.setGeometry(0, 0, self.grid.width(), self.grid.height())
        self.setVisible(bool(gw or gh))
        self.lower()
        self.update()

    # ---------------------------------------------------------------- painting
    def paintEvent(self, event: Any) -> None:
        sheet = self.grid.model
        gw, gh = self.sizes()
        p = QPainter(self)
        p.fillRect(QRect(0, 0, gw, self.height()), QColor("#F4F4F4"))
        p.fillRect(QRect(0, 0, self.width(), gh), QColor("#F4F4F4"))
        line = QPen(QColor("#333333"), 1)
        p.setPen(line)
        clip_top = gh + self.grid.col_header_height * self.grid.zoom
        clip_left = gw + self.grid.row_header_width * self.grid.zoom
        for grp in outline.groups(sheet, "row"):
            if outline.is_collapsed(sheet, "row", grp):
                continue
            x = (grp.level - 1) * STEP + 2 + BUTTON // 2
            y0, y1 = self._row_y(grp.start), self._row_y(grp.end + 1)
            if y1 > clip_top:
                p.drawLine(QPoint(x, int(max(y0, clip_top))), QPoint(x, int(y1)))
        for grp in outline.groups(sheet, "col"):
            if outline.is_collapsed(sheet, "col", grp):
                continue
            y = (grp.level - 1) * STEP + 2 + BUTTON // 2
            x0, x1 = self._col_x(grp.start), self._col_x(grp.end + 1)
            if x1 > clip_left:
                p.drawLine(QPoint(int(max(x0, clip_left)), y), QPoint(int(x1), y))
        font = QFont("Arial")
        font.setPixelSize(9)
        p.setFont(font)
        for rect, kind, payload in self.buttons():
            if kind.startswith("toggle"):
                axis = kind.split("-")[1]
                edge = clip_top if axis == "row" else clip_left
                pos = rect.top() if axis == "row" else rect.left()
                if pos < edge:
                    continue
                label = "+" if outline.is_collapsed(sheet, axis, payload) else "−"
            else:
                label = str(payload)
            p.fillRect(rect, QColor("#FFFFFF"))
            p.setPen(QPen(QColor("#7F7F7F"), 1))
            p.drawRect(rect)
            p.setPen(QColor("#000000"))
            p.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), label)
        p.end()

    # ---------------------------------------------------------------- input
    def click(self, pos: QPoint) -> bool:
        """Handle a click at ``pos`` (widget coordinates); True when a button was hit."""
        sheet = self.grid.model
        for rect, kind, payload in self.buttons():
            if not rect.adjusted(-2, -2, 2, 2).contains(pos):
                continue
            if kind == "level-row":
                outline.show_level(sheet, "row", payload)
            elif kind == "level-col":
                outline.show_level(sheet, "col", payload)
            else:
                axis = kind.split("-")[1]
                outline.set_collapsed(sheet, axis, payload,
                                      not outline.is_collapsed(sheet, axis, payload))
            self.grid.outline_changed()
            return True
        return False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.click(event.position().toPoint()):
            event.accept()
            return
        super().mousePressEvent(event)

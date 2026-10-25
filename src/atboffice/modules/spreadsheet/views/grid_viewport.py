"""Virtualized custom-painted spreadsheet grid viewport based on QAbstractScrollArea."""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Final

from PySide6.QtCore import QCoreApplication, QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QContextMenuEvent,
    QFont,
    QFontMetrics,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import QAbstractScrollArea, QMenu, QWidget

from atboffice.modules.spreadsheet.calc.references import col_name
from atboffice.modules.spreadsheet.models.selection_model import (
    SelectionModel,
    SelectionRange,
)
from atboffice.modules.spreadsheet.models.sheet_model import (
    SheetDataModel,
)
from atboffice.modules.spreadsheet.views.autofill import AutoFillEngine

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.views.editor_controller import (
        EditorController,
    )


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("GridViewport", text)


class HitZone(Enum):
    NONE = auto()
    CORNER = auto()
    COL_HEADER = auto()
    ROW_HEADER = auto()
    CELL = auto()
    COL_RESIZE = auto()
    ROW_RESIZE = auto()
    FILL_HANDLE = auto()


class HitResult:
    """Result of hit testing mouse position."""

    def __init__(
        self,
        zone: HitZone,
        row: int | None = None,
        col: int | None = None,
        pos: int | None = None,
    ) -> None:
        self.zone = zone
        self.row = row
        self.col = col
        self.pos = pos


class GridViewport(QAbstractScrollArea):
    """High-performance virtualized 2D grid viewport for ATBOffice Ledger.

    Renders hundreds of thousands of cells at 60 FPS using double-buffered QPainter,
    drawing only the cells within the current visible viewport rectangle.
    """

    cell_selected = Signal(int, int)
    cell_double_clicked = Signal(int, int)

    # Classic Office / Luna color palette
    COLOR_GRIDLINE: Final[QColor] = QColor(208, 215, 229)
    COLOR_HDR_BG: Final[QColor] = QColor(236, 233, 216)
    COLOR_HDR_SEL_BG: Final[QColor] = QColor(254, 216, 126)
    COLOR_HDR_BORDER: Final[QColor] = QColor(158, 182, 206)
    COLOR_HDR_TEXT: Final[QColor] = QColor(0, 0, 0)
    COLOR_SELECTION: Final[QColor] = QColor(49, 74, 160, 45)
    COLOR_ACTIVE_BORDER: Final[QColor] = QColor(33, 66, 131)
    COLOR_FILL_HANDLE: Final[QColor] = QColor(0, 0, 0)

    def __init__(
        self,
        model: SheetDataModel | None = None,
        selection: SelectionModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.model = model if model is not None else SheetDataModel()
        self.selection = selection if selection is not None else SelectionModel()
        self.geometry_mapper = self.model.geometry
        self.editor_controller: EditorController | None = None
        self._point_anchor: tuple[int, int] | None = None

        self.row_header_width: int = 46
        self.col_header_height: int = 22

        # Interaction drag state
        self._drag_mode: HitZone = HitZone.NONE
        self._resize_index: int = -1
        self._resize_start_pos: int = 0
        self._resize_orig_size: int = 0
        self._fill_preview_range: SelectionRange | None = None
        self._fill_start_src: SelectionRange | None = None
        self._fill_ctrl_pressed: bool = False

        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.horizontalScrollBar().valueChanged.connect(self._on_scroll)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

        self._update_scrollbars()
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        """Update localized UI text and trigger repaint."""
        self.viewport().update()

    def _on_scroll(self, _: int) -> None:
        if self.editor_controller is not None:
            self.editor_controller.reposition_editor()
        self.viewport().update()

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        self._update_scrollbars()
        if self.editor_controller is not None:
            self.editor_controller.reposition_editor()

    def _update_scrollbars(self) -> None:
        """Synchronize Qt scrollbars with virtualized sheet dimensions."""
        vw = max(1, self.viewport().width() - self.row_header_width)
        vh = max(1, self.viewport().height() - self.col_header_height)

        # Allow scrolling beyond used data by 30 rows / 10 cols
        max_vis_r = min(self.geometry_mapper.max_rows - 1, 1000)
        max_vis_c = min(self.geometry_mapper.max_cols - 1, 100)

        total_h = self.geometry_mapper.row_pos(max_vis_r)
        total_w = self.geometry_mapper.col_pos(max_vis_c)

        self.horizontalScrollBar().setRange(0, max(0, total_w - vw))
        self.horizontalScrollBar().setPageStep(vw)
        self.verticalScrollBar().setRange(0, max(0, total_h - vh))
        self.verticalScrollBar().setPageStep(vh)

    def hit_test(self, x: int, y: int) -> HitResult:
        """Determine hit zone and target coordinates under mouse position (x, y)."""
        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()

        # 1. Corner box
        if x < self.row_header_width and y < self.col_header_height:
            return HitResult(HitZone.CORNER)

        # 2. Column Header area
        if y < self.col_header_height:
            sheet_x = scroll_x + (x - self.row_header_width)
            col = self.geometry_mapper.find_col_at(sheet_x)
            col_end = self.geometry_mapper.col_pos(col) + self.geometry_mapper.col_size(col)
            # Check resize boundary (+/- 3px)
            if abs(sheet_x - col_end) <= 3:
                return HitResult(HitZone.COL_RESIZE, col=col, pos=x)
            if col > 0 and abs(sheet_x - self.geometry_mapper.col_pos(col)) <= 3:
                return HitResult(HitZone.COL_RESIZE, col=col - 1, pos=x)
            return HitResult(HitZone.COL_HEADER, col=col)

        # 3. Row Header area
        if x < self.row_header_width:
            sheet_y = scroll_y + (y - self.col_header_height)
            row = self.geometry_mapper.find_row_at(sheet_y)
            row_end = self.geometry_mapper.row_pos(row) + self.geometry_mapper.row_size(row)
            if abs(sheet_y - row_end) <= 2:
                return HitResult(HitZone.ROW_RESIZE, row=row, pos=y)
            if row > 0 and abs(sheet_y - self.geometry_mapper.row_pos(row)) <= 2:
                return HitResult(HitZone.ROW_RESIZE, row=row - 1, pos=y)
            return HitResult(HitZone.ROW_HEADER, row=row)

        # 4. AutoFill Handle area (active when single selection range)
        if len(self.selection.ranges) == 1:
            pr = self.selection.primary_range
            fx = (
                self.row_header_width
                + self.geometry_mapper.col_pos(pr.max_c + 1)
                - scroll_x
            )
            fy = (
                self.col_header_height
                + self.geometry_mapper.row_pos(pr.max_r + 1)
                - scroll_y
            )
            if abs(x - fx) <= 5 and abs(y - fy) <= 5:
                return HitResult(HitZone.FILL_HANDLE, row=pr.max_r, col=pr.max_c)

        # 5. Cell area
        sheet_x = scroll_x + (x - self.row_header_width)
        sheet_y = scroll_y + (y - self.col_header_height)
        row = self.geometry_mapper.find_row_at(sheet_y)
        col = self.geometry_mapper.find_col_at(sheet_x)
        return HitResult(HitZone.CELL, row=row, col=col)

    def cell_at_pos(self, x: int, y: int) -> tuple[int, int] | None:
        """Return (row, col) cell index at widget coordinates, or None if in headers."""
        hit = self.hit_test(x, y)
        if hit.zone == HitZone.CELL and hit.row is not None and hit.col is not None:
            return (hit.row, hit.col)
        return None

    def auto_fit_column(self, col: int) -> None:
        """Auto-fit column width to the widest content cell in the column."""
        fm = QFontMetrics(self.font())
        max_width = 30  # Minimum column width

        # Measure width of cells in column
        for (r, c), cell in self.model.cells.items():
            if c == col and cell.value is not None:
                text = self.model.get_formatted_text(r, c)
                w = fm.horizontalAdvance(text) + 12
                if w > max_width:
                    max_width = w

        self.geometry_mapper.set_col_width(col, min(500, max_width))
        self._update_scrollbars()
        self.viewport().update()

    def calculate_overflow_span(
        self, r: int, c: int, text_width: int, col_width: int
    ) -> int:
        """Calculate how many consecutive empty neighbor columns text can overflow into."""
        if text_width <= col_width - 6:
            return 1

        accumulated = col_width
        span = 1
        curr_c = c + 1
        while accumulated < text_width + 6 and curr_c < self.geometry_mapper.max_cols:
            if not self.model.is_empty(r, curr_c):
                break
            accumulated += self.geometry_mapper.col_size(curr_c)
            span += 1
            curr_c += 1
            if span > 50:
                break

        return span

    def reveal(self, r: int, c: int) -> None:
        """Ensure cell (r, c) is visible in the viewport by scrolling if needed."""
        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()
        vw = max(1, self.viewport().width() - self.row_header_width)
        vh = max(1, self.viewport().height() - self.col_header_height)

        cell_top = self.geometry_mapper.row_pos(r)
        cell_bottom = cell_top + self.geometry_mapper.row_size(r)
        cell_left = self.geometry_mapper.col_pos(c)
        cell_right = cell_left + self.geometry_mapper.col_size(c)

        if cell_top < scroll_y:
            self.verticalScrollBar().setValue(cell_top)
        elif cell_bottom > scroll_y + vh:
            self.verticalScrollBar().setValue(cell_bottom - vh)

        if cell_left < scroll_x:
            self.horizontalScrollBar().setValue(cell_left)
        elif cell_right > scroll_x + vw:
            self.horizontalScrollBar().setValue(cell_right - vw)

    # -------------------------------------------------------------------------
    # Painting Subsystem
    # -------------------------------------------------------------------------
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()
        vw = self.viewport().width()
        vh = self.viewport().height()

        # Background
        painter.fillRect(0, 0, vw, vh, Qt.GlobalColor.white)

        # 1. Determine visible rows and columns
        start_row = self.geometry_mapper.find_row_at(scroll_y)
        end_row = self.geometry_mapper.find_row_at(scroll_y + vh)
        start_col = self.geometry_mapper.find_col_at(scroll_x)
        end_col = self.geometry_mapper.find_col_at(scroll_x + vw)

        # Cell area clip rect
        cell_clip = QRect(
            self.row_header_width,
            self.col_header_height,
            vw - self.row_header_width,
            vh - self.col_header_height,
        )

        # 2. Draw Selection Overlays
        painter.save()
        painter.setClipRect(cell_clip)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.COLOR_SELECTION))

        for rg in self.selection.ranges:
            if rg.max_r < start_row or rg.min_r > end_row:
                continue
            if rg.max_c < start_col or rg.min_c > end_col:
                continue
            x1 = (
                self.row_header_width
                + self.geometry_mapper.col_pos(rg.min_c)
                - scroll_x
            )
            y1 = (
                self.col_header_height
                + self.geometry_mapper.row_pos(rg.min_r)
                - scroll_y
            )
            x2 = (
                self.row_header_width
                + self.geometry_mapper.col_pos(rg.max_c + 1)
                - scroll_x
            )
            y2 = (
                self.col_header_height
                + self.geometry_mapper.row_pos(rg.max_r + 1)
                - scroll_y
            )
            painter.drawRect(QRect(x1, y1, x2 - x1, y2 - y1))
        painter.restore()

        # 2b. Draw AutoFill Drag Preview Rectangle
        if self._fill_preview_range is not None:
            painter.save()
            painter.setClipRect(cell_clip)
            pr = self._fill_preview_range
            px1 = (
                self.row_header_width
                + self.geometry_mapper.col_pos(pr.min_c)
                - scroll_x
            )
            py1 = (
                self.col_header_height
                + self.geometry_mapper.row_pos(pr.min_r)
                - scroll_y
            )
            px2 = (
                self.row_header_width
                + self.geometry_mapper.col_pos(pr.max_c + 1)
                - scroll_x
            )
            py2 = (
                self.col_header_height
                + self.geometry_mapper.row_pos(pr.max_r + 1)
                - scroll_y
            )
            dash_pen = QPen(QColor(128, 128, 128), 2, Qt.PenStyle.DashLine)
            painter.setPen(dash_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRect(px1, py1, px2 - px1, py2 - py1))
            painter.restore()

        # 3. Draw Gridlines
        painter.save()
        painter.setClipRect(cell_clip)
        painter.setPen(QPen(self.COLOR_GRIDLINE, 1))

        # Vertical gridlines
        for c in range(start_col, end_col + 2):
            x = (
                self.row_header_width
                + self.geometry_mapper.col_pos(c)
                - scroll_x
            )
            painter.drawLine(x, self.col_header_height, x, vh)

        # Horizontal gridlines
        for r in range(start_row, end_row + 2):
            y = (
                self.col_header_height
                + self.geometry_mapper.row_pos(r)
                - scroll_y
            )
            painter.drawLine(self.row_header_width, y, vw, y)
        painter.restore()

        # 4. Draw Cell Contents (with right-overflow)
        painter.save()
        painter.setClipRect(cell_clip)
        fm = QFontMetrics(self.font())

        for r in range(start_row, end_row + 1):
            row_y = (
                self.col_header_height
                + self.geometry_mapper.row_pos(r)
                - scroll_y
            )
            row_h = self.geometry_mapper.row_size(r)
            if row_h <= 0:
                continue

            for c in range(start_col, end_col + 1):
                cell = self.model.get_cell(r, c)
                if cell is None:
                    continue

                col_x = (
                    self.row_header_width
                    + self.geometry_mapper.col_pos(c)
                    - scroll_x
                )
                col_w = self.geometry_mapper.col_size(c)
                if col_w <= 0:
                    continue

                cell_rect = QRect(col_x, row_y, col_w, row_h)
                # Background fill & patterns
                if cell.bg_color or cell.pattern:
                    painter.save()
                    painter.setClipRect(cell_rect)
                    if cell.bg_color:
                        painter.fillRect(cell_rect, QColor(cell.bg_color))
                    if cell.pattern:
                        from atboffice.modules.spreadsheet.dialogs.pattern_defs import (
                            create_pattern_brush,
                        )

                        brush = create_pattern_brush(
                            cell.pattern,
                            cell.pattern_color or "#000000",
                            cell.bg_color or "#FFFFFF",
                        )
                        painter.fillRect(cell_rect, brush)
                    painter.restore()

                # Cell borders
                if any(
                    [
                        cell.border_top,
                        cell.border_bottom,
                        cell.border_left,
                        cell.border_right,
                    ]
                ):
                    painter.save()
                    if cell.border_top and cell.border_top.style != "none":
                        col = (
                            QColor(cell.border_top.color)
                            if cell.border_top.color
                            else Qt.GlobalColor.black
                        )
                        painter.setPen(
                            QPen(
                                col,
                                2
                                if cell.border_top.style in ("medium", "thick")
                                else 1,
                            )
                        )
                        painter.drawLine(col_x, row_y, col_x + col_w, row_y)
                    if (
                        cell.border_bottom
                        and cell.border_bottom.style != "none"
                    ):
                        col = (
                            QColor(cell.border_bottom.color)
                            if cell.border_bottom.color
                            else Qt.GlobalColor.black
                        )
                        painter.setPen(
                            QPen(
                                col,
                                2
                                if cell.border_bottom.style
                                in ("medium", "thick")
                                else 1,
                            )
                        )
                        painter.drawLine(
                            col_x, row_y + row_h, col_x + col_w, row_y + row_h
                        )
                    if cell.border_left and cell.border_left.style != "none":
                        col = (
                            QColor(cell.border_left.color)
                            if cell.border_left.color
                            else Qt.GlobalColor.black
                        )
                        painter.setPen(
                            QPen(
                                col,
                                2
                                if cell.border_left.style
                                in ("medium", "thick")
                                else 1,
                            )
                        )
                        painter.drawLine(col_x, row_y, col_x, row_y + row_h)
                    if cell.border_right and cell.border_right.style != "none":
                        col = (
                            QColor(cell.border_right.color)
                            if cell.border_right.color
                            else Qt.GlobalColor.black
                        )
                        painter.setPen(
                            QPen(
                                col,
                                2
                                if cell.border_right.style
                                in ("medium", "thick")
                                else 1,
                            )
                        )
                        painter.drawLine(
                            col_x + col_w, row_y, col_x + col_w, row_y + row_h
                        )
                    painter.restore()

                if cell.value is None or cell.value == "":
                    continue

                text = self.model.get_formatted_text(r, c)
                text_w = fm.horizontalAdvance(text)

                # Right-overflow calculation
                span = self.calculate_overflow_span(r, c, text_w, col_w)
                span_w = sum(
                    self.geometry_mapper.col_size(c + i) for i in range(span)
                )

                painter.save()
                # Clip cell area
                painter.setClipRect(QRect(col_x, row_y, span_w - 1, row_h - 1))

                # Font & color
                font = QFont(cell.font_family, cell.font_size)
                font.setBold(cell.bold)
                font.setItalic(cell.italic)
                font.setUnderline(cell.underline)
                painter.setFont(font)

                text_color = (
                    QColor(cell.fg_color)
                    if cell.fg_color
                    else Qt.GlobalColor.black
                )
                painter.setPen(text_color)

                # Alignment
                align_flag = (
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                )
                if cell.align_h == "center":
                    align_flag = (
                        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter
                    )
                elif cell.align_h == "right":
                    align_flag = (
                        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
                    )

                text_rect = QRect(col_x + 3, row_y, span_w - 6, row_h)
                painter.drawText(text_rect, align_flag, text)
                painter.restore()

        painter.restore()

        # 5. Draw Active Cell 2px Border & AutoFill Handle
        painter.save()
        painter.setClipRect(cell_clip)
        ar, ac = self.selection.active_cell
        if start_row <= ar <= end_row and start_col <= ac <= end_col:
            ax = (
                self.row_header_width
                + self.geometry_mapper.col_pos(ac)
                - scroll_x
            )
            ay = (
                self.col_header_height
                + self.geometry_mapper.row_pos(ar)
                - scroll_y
            )
            aw = self.geometry_mapper.col_size(ac)
            ah = self.geometry_mapper.row_size(ar)

            painter.setPen(QPen(self.COLOR_ACTIVE_BORDER, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRect(ax, ay, aw, ah))

            # AutoFill handle square at bottom-right of active range
            pr = self.selection.primary_range
            fx = (
                self.row_header_width
                + self.geometry_mapper.col_pos(pr.max_c + 1)
                - scroll_x
                - 3
            )
            fy = (
                self.col_header_height
                + self.geometry_mapper.row_pos(pr.max_r + 1)
                - scroll_y
                - 3
            )
            painter.fillRect(fx - 1, fy - 1, 7, 7, Qt.GlobalColor.white)
            painter.fillRect(fx, fy, 5, 5, self.COLOR_FILL_HANDLE)
        painter.restore()

        # 5.5 Draw Reference Highlights (if in formula editing / point mode)
        if (
            self.editor_controller is not None
            and self.editor_controller.highlights
        ):
            painter.save()
            painter.setClipRect(cell_clip)
            for hl in self.editor_controller.highlights:
                hx = (
                    self.row_header_width
                    + self.geometry_mapper.col_pos(hl.c1)
                    - scroll_x
                )
                hy = (
                    self.col_header_height
                    + self.geometry_mapper.row_pos(hl.r1)
                    - scroll_y
                )
                hw = sum(
                    self.geometry_mapper.col_size(c)
                    for c in range(hl.c1, hl.c2 + 1)
                )
                hh = sum(
                    self.geometry_mapper.row_size(r)
                    for r in range(hl.r1, hl.r2 + 1)
                )

                painter.setPen(QPen(hl.color, 2, Qt.PenStyle.SolidLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(QRect(hx, hy, hw, hh))

                # Corner handles
                for cx, cy in [
                    (hx, hy),
                    (hx + hw - 4, hy),
                    (hx, hy + hh - 4),
                    (hx + hw - 4, hy + hh - 4),
                ]:
                    painter.fillRect(cx, cy, 4, 4, hl.color)
            painter.restore()

        # 6. Draw Fixed Headers (Column Headers, Row Headers, Corner)
        self._paint_headers(
            painter, start_row, end_row, start_col, end_col, scroll_x, scroll_y, vw, vh
        )

    def _paint_headers(
        self,
        painter: QPainter,
        start_row: int,
        end_row: int,
        start_col: int,
        end_col: int,
        scroll_x: int,
        scroll_y: int,
        vw: int,
        vh: int,
    ) -> None:
        """Render column headers, row headers, and corner box."""
        # A. Top-Left Corner Box
        painter.fillRect(
            0,
            0,
            self.row_header_width,
            self.col_header_height,
            self.COLOR_HDR_BG,
        )
        painter.setPen(QPen(self.COLOR_HDR_BORDER, 1))
        painter.drawRect(
            0, 0, self.row_header_width, self.col_header_height
        )

        # Draw diagonal triangle in corner box
        painter.setBrush(QBrush(QColor(160, 160, 160)))
        corner_poly = [
            QPoint(self.row_header_width - 8, self.col_header_height - 3),
            QPoint(self.row_header_width - 3, self.col_header_height - 3),
            QPoint(self.row_header_width - 3, self.col_header_height - 8),
        ]
        painter.drawPolygon(corner_poly)

        # B. Column Headers (A, B, C...)
        painter.save()
        painter.setClipRect(
            QRect(
                self.row_header_width,
                0,
                vw - self.row_header_width,
                self.col_header_height,
            )
        )
        for c in range(start_col, end_col + 1):
            cx = (
                self.row_header_width
                + self.geometry_mapper.col_pos(c)
                - scroll_x
            )
            cw = self.geometry_mapper.col_size(c)
            if cw <= 0:
                continue

            is_sel = self.selection.is_col_selected(c)
            bg = self.COLOR_HDR_SEL_BG if is_sel else self.COLOR_HDR_BG
            painter.fillRect(cx, 0, cw, self.col_header_height, bg)

            painter.setPen(QPen(self.COLOR_HDR_BORDER, 1))
            painter.drawLine(
                cx + cw, 0, cx + cw, self.col_header_height
            )
            painter.drawLine(
                cx,
                self.col_header_height - 1,
                cx + cw,
                self.col_header_height - 1,
            )

            # Header text
            painter.setPen(self.COLOR_HDR_TEXT)
            painter.drawText(
                QRect(cx, 0, cw, self.col_header_height),
                Qt.AlignmentFlag.AlignCenter,
                col_name(c),
            )
        painter.restore()

        # C. Row Headers (1, 2, 3...)
        painter.save()
        painter.setClipRect(
            QRect(
                0,
                self.col_header_height,
                self.row_header_width,
                vh - self.col_header_height,
            )
        )
        for r in range(start_row, end_row + 1):
            ry = (
                self.col_header_height
                + self.geometry_mapper.row_pos(r)
                - scroll_y
            )
            rh = self.geometry_mapper.row_size(r)
            if rh <= 0:
                continue

            is_sel = self.selection.is_row_selected(r)
            bg = self.COLOR_HDR_SEL_BG if is_sel else self.COLOR_HDR_BG
            painter.fillRect(0, ry, self.row_header_width, rh, bg)

            painter.setPen(QPen(self.COLOR_HDR_BORDER, 1))
            painter.drawLine(
                0, ry + rh, self.row_header_width, ry + rh
            )
            painter.drawLine(
                self.row_header_width - 1,
                ry,
                self.row_header_width - 1,
                ry + rh,
            )

            # Header text (1-based row number)
            painter.setPen(self.COLOR_HDR_TEXT)
            painter.drawText(
                QRect(0, ry, self.row_header_width - 4, rh),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                str(r + 1),
            )
        painter.restore()

    # -------------------------------------------------------------------------
    # Mouse Interaction Subsystem
    # -------------------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        x = event.position().x()
        y = event.position().y()
        hit = self.hit_test(int(x), int(y))
        modifiers = event.modifiers()

        if hit.zone == HitZone.CORNER:
            self.selection.select_all()
            self.viewport().update()

        elif hit.zone == HitZone.COL_RESIZE:
            self._drag_mode = HitZone.COL_RESIZE
            self._resize_index = hit.col if hit.col is not None else -1
            self._resize_start_pos = int(x)
            self._resize_orig_size = self.geometry_mapper.col_size(self._resize_index)

        elif hit.zone == HitZone.ROW_RESIZE:
            self._drag_mode = HitZone.ROW_RESIZE
            self._resize_index = hit.row if hit.row is not None else -1
            self._resize_start_pos = int(y)
            self._resize_orig_size = self.geometry_mapper.row_size(self._resize_index)

        elif hit.zone == HitZone.COL_HEADER and hit.col is not None:
            self._drag_mode = HitZone.COL_HEADER
            self.selection.select_cols(hit.col, hit.col)
            self.viewport().update()

        elif hit.zone == HitZone.ROW_HEADER and hit.row is not None:
            self._drag_mode = HitZone.ROW_HEADER
            self.selection.select_rows(hit.row, hit.row)
            self.viewport().update()

        elif hit.zone == HitZone.FILL_HANDLE:
            self._drag_mode = HitZone.FILL_HANDLE
            self._fill_start_src = self.selection.primary_range
            self._fill_preview_range = self._fill_start_src
            self._fill_ctrl_pressed = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
            self.viewport().update()

        elif hit.zone == HitZone.CELL and hit.row is not None and hit.col is not None:
            if (
                self.editor_controller is not None
                and self.editor_controller.is_active
                and self.editor_controller.mode.name.lower() == "point"
            ):
                self._point_anchor = (hit.row, hit.col)
                self._drag_mode = HitZone.CELL
                self.editor_controller.point_at(
                    hit.row, hit.col, hit.row, hit.col
                )
                self.reveal(hit.row, hit.col)
                self.viewport().update()
                return

            self._drag_mode = HitZone.CELL
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self.selection.add_range(
                    SelectionRange(hit.row, hit.col, hit.row, hit.col)
                )
            elif modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.selection.extend_to(hit.row, hit.col)
            else:
                self.selection.select_cell(hit.row, hit.col)
            self.cell_selected.emit(hit.row, hit.col)
            self.reveal(hit.row, hit.col)
            self.viewport().update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        x = int(event.position().x())
        y = int(event.position().y())

        # Update cursor when hovering
        if self._drag_mode == HitZone.NONE:
            hit = self.hit_test(x, y)
            if hit.zone == HitZone.FILL_HANDLE:
                self.viewport().setCursor(Qt.CursorShape.CrossCursor)
            elif hit.zone == HitZone.COL_RESIZE:
                self.viewport().setCursor(Qt.CursorShape.SplitHCursor)
            elif hit.zone == HitZone.ROW_RESIZE:
                self.viewport().setCursor(Qt.CursorShape.SplitVCursor)
            elif hit.zone in (HitZone.COL_HEADER, HitZone.ROW_HEADER):
                self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            return

        # Handle active drag
        if self._drag_mode == HitZone.FILL_HANDLE:
            self._fill_ctrl_pressed = bool(
                event.modifiers() & Qt.KeyboardModifier.ControlModifier
            )
            hit = self.hit_test(x, y)
            if (
                hit.row is not None
                and hit.col is not None
                and self._fill_start_src is not None
            ):
                dest, is_shrink = AutoFillEngine.determine_destination(
                    self._fill_start_src, hit.row, hit.col
                )
                self._fill_preview_range = dest
                self.reveal(hit.row, hit.col)
                self.viewport().update()

        elif self._drag_mode == HitZone.COL_RESIZE:
            delta = x - self._resize_start_pos
            new_w = max(5, self._resize_orig_size + delta)
            self.geometry_mapper.set_col_width(self._resize_index, new_w)
            self._update_scrollbars()
            self.viewport().update()

        elif self._drag_mode == HitZone.ROW_RESIZE:
            delta = y - self._resize_start_pos
            new_h = max(5, self._resize_orig_size + delta)
            self.geometry_mapper.set_row_height(self._resize_index, new_h)
            self._update_scrollbars()
            self.viewport().update()

        elif self._drag_mode == HitZone.CELL:
            hit = self.hit_test(x, y)
            if hit.row is not None and hit.col is not None:
                if (
                    self.editor_controller is not None
                    and self.editor_controller.is_active
                    and self.editor_controller.mode.name.lower() == "point"
                    and self._point_anchor is not None
                ):
                    ar, ac = self._point_anchor
                    r1, r2 = min(ar, hit.row), max(ar, hit.row)
                    c1, c2 = min(ac, hit.col), max(ac, hit.col)
                    self.editor_controller.point_at(r1, c1, r2, c2)
                    self.reveal(hit.row, hit.col)
                    self.viewport().update()
                    return

                self.selection.extend_to(hit.row, hit.col)
                self.reveal(hit.row, hit.col)
                self.viewport().update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_mode == HitZone.FILL_HANDLE:
            if self._fill_start_src is not None and self._fill_preview_range is not None:
                src = self._fill_start_src
                dest = self._fill_preview_range
                ctrl = self._fill_ctrl_pressed or bool(
                    event.modifiers() & Qt.KeyboardModifier.ControlModifier
                )
                AutoFillEngine.auto_fill(
                    self.model,
                    src,
                    dest,
                    mode="auto",
                    ctrl_pressed=ctrl,
                )
                self.selection.select_cell(dest.min_r, dest.min_c)
                self.selection.extend_to(dest.max_r, dest.max_c)
                self._fill_start_src = None
                self._fill_preview_range = None

        self._drag_mode = HitZone.NONE
        self._resize_index = -1
        self._point_anchor = None
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self.viewport().update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        x = int(event.position().x())
        y = int(event.position().y())
        hit = self.hit_test(x, y)

        if hit.zone == HitZone.COL_RESIZE and hit.col is not None:
            self.auto_fit_column(hit.col)
        elif hit.zone == HitZone.CELL and hit.row is not None and hit.col is not None:
            self.cell_double_clicked.emit(hit.row, hit.col)
        else:
            super().mouseDoubleClickEvent(event)

    # -------------------------------------------------------------------------
    # Keyboard Navigation Subsystem
    # -------------------------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        modifiers = event.modifiers()
        r, c = self.selection.active_cell

        # Ctrl+1 / Cmd+1 to open Format Cells dialog
        if (
            modifiers
            & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        ) and key == Qt.Key.Key_1:
            self.open_format_cells_dialog()
            return

        # F2 to start editing
        if key == Qt.Key.Key_F2:
            if (
                self.editor_controller is not None
                and not self.editor_controller.is_active
            ):
                self.editor_controller.begin_edit(r, c)
                return

        # Delete / Backspace to clear selection
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if (
                self.editor_controller is not None
                and not self.editor_controller.is_active
            ):
                for rg in self.selection.ranges:
                    for rr in range(rg.min_r, rg.max_r + 1):
                        for cc in range(rg.min_c, rg.max_c + 1):
                            cell = self.model.get_cell(rr, cc)
                            if cell is not None:
                                cell.value = None
                                cell.formula = None
                self.viewport().update()
                return

        # Printable character starts typing in-cell
        text = event.text()
        if (
            text
            and text.isprintable()
            and not (
                modifiers
                & (
                    Qt.KeyboardModifier.ControlModifier
                    | Qt.KeyboardModifier.AltModifier
                )
            )
        ):
            if (
                self.editor_controller is not None
                and not self.editor_controller.is_active
            ):
                self.editor_controller.begin_edit(r, c, initial_text=text)
                return

        # Ctrl+A Select All
        if key == Qt.Key.Key_A and (
            modifiers & Qt.KeyboardModifier.ControlModifier
        ):
            self.selection.select_all()
            self.viewport().update()
            return

        # Arrow navigation
        dr, dc = 0, 0
        if key == Qt.Key.Key_Up:
            dr = -1
        elif key == Qt.Key.Key_Down or key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            dr = 1
        elif key == Qt.Key.Key_Left:
            dc = -1
        elif key == Qt.Key.Key_Right or key == Qt.Key.Key_Tab:
            dc = 1

        if dr != 0 or dc != 0:
            target_r = max(0, min(self.geometry_mapper.max_rows - 1, r + dr))
            target_c = max(0, min(self.geometry_mapper.max_cols - 1, c + dc))

            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.selection.extend_to(target_r, target_c)
            else:
                self.selection.select_cell(target_r, target_c)

            self.reveal(target_r, target_c)
            self.cell_selected.emit(target_r, target_c)
            self.viewport().update()
            return

        super().keyPressEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Right-click context menu offering cell formatting and clipboard operations."""
        menu = QMenu(self)
        action_fmt = menu.addAction(safe_tr("设置单元格格式(&F)…"))
        action_fmt.setShortcut("Ctrl+1")
        action_fmt.triggered.connect(lambda: self.open_format_cells_dialog())
        menu.exec(event.globalPos())

    def open_format_cells_dialog(self, initial_tab: int = 0) -> None:
        """Open the classic 6-tab Format Cells dialog for the active selection."""
        from atboffice.modules.spreadsheet.dialogs.format_cells import (
            FormatCellsDialog,
        )

        r, c = self.selection.active_cell
        target = self.model.get_cell(r, c)
        dlg = FormatCellsDialog(
            target_cell=target,
            model=self.model,
            selection=self.selection,
            initial_tab=initial_tab,
            parent=self,
        )
        if dlg.exec():
            self.viewport().update()
            # If top-level window has set_modified, flag it
            top = self.window()
            if hasattr(top, "set_modified"):
                top.set_modified(True)

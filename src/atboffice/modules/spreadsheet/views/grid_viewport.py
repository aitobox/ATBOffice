"""Virtualized custom-painted spreadsheet grid viewport based on QAbstractScrollArea."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Final

from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QCloseEvent,
    QColor,
    QContextMenuEvent,
    QFocusEvent,
    QFont,
    QFontMetrics,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QInputDialog,
    QMenu,
    QMessageBox,
    QToolTip,
    QWidget,
)

from atboffice.modules.spreadsheet.calc.parser import parse, to_text
from atboffice.modules.spreadsheet.calc.references import (
    adjust_move,
    cell_name,
    col_name,
    map_ast,
    range_name,
    ref_err,
    translate,
)
from atboffice.modules.spreadsheet.calc.tokens import CellRefNode
from atboffice.modules.spreadsheet.models.conditional_format import (
    evaluate_cf_for_cell,
)
from atboffice.modules.spreadsheet.models.selection_model import (
    SelectionModel,
    SelectionRange,
)
from atboffice.modules.spreadsheet.models.sheet_model import (
    CellComment,
    CellData,
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
    FILTER_BUTTON = auto()
    BORDER = auto()


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


@dataclass
class DragSnapshot:
    """Snapshot of grid state prior to initiating a drag interaction."""

    zone: HitZone
    sheet_index: int
    selection_snapshot: dict[str, Any]
    resize_index: int = -1
    resize_orig_size: int = 0
    resize_orig_sizes: dict[int, int] | None = None
    fill_start_src: SelectionRange | None = None
    move_start_src: SelectionRange | None = None
    move_grab_cell: tuple[int, int] | None = None


class GridViewport(QAbstractScrollArea):
    """High-performance virtualized 2D grid viewport for ATBOffice Ledger.

    Renders hundreds of thousands of cells at 60 FPS using double-buffered QPainter,
    drawing only the cells within the current visible viewport rectangle.
    """

    cell_selected = Signal(int, int)
    cell_double_clicked = Signal(int, int)
    view_mode_changed = Signal(str)

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
        self.object_layer: Any | None = None
        self._internal_clipboard: dict[str, Any] | None = None

        self.row_header_width: int = 46
        self.col_header_height: int = 22

        # Interaction drag state
        self._drag_mode: HitZone = HitZone.NONE
        self._drag_start_pos: QPoint | None = None
        self._drag_moved: bool = False
        self._drag_threshold: int = 3
        self._drag_snapshot: DragSnapshot | None = None
        self._last_mouse_pos: QPoint = QPoint(0, 0)
        self._auto_scroll_timer: QTimer | None = None
        self._auto_scroll_delta: tuple[int, int] = (0, 0)
        self._swallow_secondary_button: bool = False

        self._resize_index: int = -1
        self._resize_start_pos: int = 0
        self._resize_orig_size: int = 0
        self._resize_targets: list[int] = []
        self._resize_orig_sizes: dict[int, int] = {}
        self._resize_preview_pos: int | None = None
        self._resize_preview_size: int = 0
        self._header_drag_anchor: int = -1
        self._last_modifiers: Qt.KeyboardModifiers = Qt.KeyboardModifier.NoModifier
        self._fill_preview_range: SelectionRange | None = None
        self._fill_start_src: SelectionRange | None = None
        self._fill_ctrl_pressed: bool = False
        self._move_src_range: SelectionRange | None = None
        self._move_grab_cell: tuple[int, int] | None = None
        self._move_preview_range: SelectionRange | None = None
        self._move_ctrl_pressed: bool = False
        self._undo_stack: list[dict[str, Any]] = []
        self._redo_stack: list[dict[str, Any]] = []
        self._dv_dropdown_rect: QRect | None = None
        self._format_painter_window: Any | None = None
        self._view_mode: str = "normal"  # "normal" | "page_break"
        self._page_break_welcome_shown: bool = False

        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.viewport().installEventFilter(self)

        self.horizontalScrollBar().valueChanged.connect(self._on_scroll)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

        self._update_scrollbars()
        self.retranslate_ui()

    @property
    def view_mode(self) -> str:
        """Current view mode ('normal' or 'page_break')."""
        return self._view_mode

    def set_view_mode(self, mode: str, prompt_welcome: bool = True) -> None:
        """Switch view mode between 'normal' and 'page_break'."""
        if mode not in ("normal", "page_break"):
            mode = "normal"
        if self._view_mode != mode:
            self._view_mode = mode
            if mode == "page_break" and prompt_welcome and not self._page_break_welcome_shown:
                self.show_page_break_welcome_dialog()
            self.view_mode_changed.emit(self._view_mode)
            self.viewport().update()

    def show_page_break_welcome_dialog(self) -> None:
        """Show classic Excel 2003 'Welcome to Page Break Preview' dialog."""
        self._page_break_welcome_shown = True
        QMessageBox.information(
            self,
            safe_tr("Ledger"),
            safe_tr("欢迎使用分页符预览。\n\n可以通过用鼠标拖动分页符来调整其位置。"),
            QMessageBox.StandardButton.Ok,
        )

    @property
    def is_dragging(self) -> bool:
        """Whether a mouse drag interaction is actively in progress."""
        return self._drag_mode != HitZone.NONE

    @property
    def has_drag_moved(self) -> bool:
        """Whether the pointer has moved beyond the 3px threshold during drag."""
        return self._drag_moved

    @property
    def has_autofill_preview(self) -> bool:
        """Whether an active autofill preview rectangle is being displayed."""
        return (
            self._fill_preview_range is not None
            and self._fill_preview_range != self._fill_start_src
        )

    @property
    def has_move_preview(self) -> bool:
        """Whether an active selection border move/copy preview rectangle is being displayed."""
        return (
            self._move_preview_range is not None
            and self._move_preview_range != self._move_src_range
        )

    @property
    def is_auto_scrolling(self) -> bool:
        """Whether the boundary auto-scroll timer is currently active."""
        return (
            self._auto_scroll_timer is not None
            and self._auto_scroll_timer.isActive()
        )

    @property
    def freeze_rows(self) -> int:
        """Number of frozen rows pinned at the top of the grid."""
        return getattr(self.model, "freeze_rows", 0)

    @property
    def freeze_cols(self) -> int:
        """Number of frozen columns pinned at the left of the grid."""
        return getattr(self.model, "freeze_cols", 0)

    def set_freeze_panes(self, rows: int, cols: int) -> None:
        """Set freeze panes for rows and columns."""
        if hasattr(self.model, "freeze_rows"):
            self.model.freeze_rows = max(0, rows)
            self.model.freeze_cols = max(0, cols)
        self._update_scrollbars()
        self.viewport().update()

    def cols_for_resize(self, col: int) -> list[int]:
        """If col is in a whole-columns selection, return all selected columns; otherwise [col]."""
        for rg in self.selection.ranges:
            if (
                rg.min_r == 0
                and rg.max_r >= self.geometry_mapper.max_rows - 1
                and rg.min_c <= col <= rg.max_c
            ):
                cols: list[int] = []
                for x in self.selection.ranges:
                    if x.min_r == 0 and x.max_r >= self.geometry_mapper.max_rows - 1:
                        cols.extend(range(x.min_c, x.max_c + 1))
                return sorted(list(set(cols)))
        return [col]

    def rows_for_resize(self, row: int) -> list[int]:
        """If row is in a whole-rows selection, return all selected rows; otherwise [row]."""
        for rg in self.selection.ranges:
            if (
                rg.min_c == 0
                and rg.max_c >= self.geometry_mapper.max_cols - 1
                and rg.min_r <= row <= rg.max_r
            ):
                rows: list[int] = []
                for x in self.selection.ranges:
                    if x.min_c == 0 and x.max_c >= self.geometry_mapper.max_cols - 1:
                        rows.extend(range(x.min_r, x.max_r + 1))
                return sorted(list(set(rows)))
        return [row]

    def _get_fill_handle_rect(self) -> QRect | None:
        """Return the visible QRect for the autofill handle, or None if not applicable."""
        if len(self.selection.ranges) != 1:
            return None
        pr = self.selection.primary_range
        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()
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
        return QRect(fx - 4, fy - 4, 9, 9)

    def set_model_and_selection(
        self, model: SheetDataModel, selection: SelectionModel
    ) -> None:
        """Switch active SheetDataModel and SelectionModel."""
        self.cancel_drag(why="api")
        self.model = model
        self.selection = selection
        self.geometry_mapper = model.geometry
        self._update_scrollbars()
        self.viewport().update()

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

        # 4. AutoFill Handle & Selection Border area (active when single selection range)
        if len(self.selection.ranges) == 1:
            pr = self.selection.primary_range
            is_editing = (
                self.editor_controller is not None
                and self.editor_controller.is_active
            )
            is_whole_rows = (
                pr.min_c == 0 and pr.max_c >= self.geometry_mapper.max_cols - 1
            )
            is_whole_cols = (
                pr.min_r == 0 and pr.max_r >= self.geometry_mapper.max_rows - 1
            )

            bx1 = (
                self.row_header_width
                + self.geometry_mapper.col_pos(pr.min_c)
                - scroll_x
            )
            bx2 = (
                self.row_header_width
                + self.geometry_mapper.col_pos(pr.max_c + 1)
                - scroll_x
            )
            by1 = (
                self.col_header_height
                + self.geometry_mapper.row_pos(pr.min_r)
                - scroll_y
            )
            by2 = (
                self.col_header_height
                + self.geometry_mapper.row_pos(pr.max_r + 1)
                - scroll_y
            )

            # AutoFill Handle has priority (+/- 5px at bottom-right)
            if abs(x - bx2) <= 5 and abs(y - by2) <= 5:
                return HitResult(HitZone.FILL_HANDLE, row=pr.max_r, col=pr.max_c)

            # Selection Border (+/- 2px along perimeter)
            if not is_editing and not is_whole_rows and not is_whole_cols:
                on_v = (abs(x - bx1) <= 2 or abs(x - bx2) <= 2) and (by1 - 2 <= y <= by2 + 2)
                on_h = (abs(y - by1) <= 2 or abs(y - by2) <= 2) and (bx1 - 2 <= x <= bx2 + 2)
                if on_v or on_h:
                    sheet_x = max(0, scroll_x + (x - self.row_header_width))
                    sheet_y = max(0, scroll_y + (y - self.col_header_height))
                    hit_r = self.geometry_mapper.find_row_at(sheet_y)
                    hit_c = self.geometry_mapper.find_col_at(sheet_x)
                    return HitResult(HitZone.BORDER, row=hit_r, col=hit_c)

        # 4.5 AutoFilter Button area
        if getattr(self.model, "auto_filter", None) is not None:
            af = self.model.auto_filter
            r1 = af.r1
            row_y = (
                self.col_header_height
                + self.geometry_mapper.row_pos(r1)
                - scroll_y
            )
            row_h = self.geometry_mapper.row_size(r1)
            btn_size = min(16, max(12, row_h - 2))
            if row_y <= y <= row_y + row_h:
                for c in range(af.c1, af.c2 + 1):
                    col_x = (
                        self.row_header_width
                        + self.geometry_mapper.col_pos(c)
                        - scroll_x
                    )
                    col_w = self.geometry_mapper.col_size(c)
                    bx = col_x + col_w - btn_size - 1
                    by = row_y + row_h - btn_size - 1
                    if bx <= x <= bx + btn_size and by <= y <= by + btn_size:
                        return HitResult(HitZone.FILTER_BUTTON, row=r1, col=c)

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

    def cell_rect(self, r: int, c: int) -> QRect:
        """Return the visible QRect coordinates for cell (r, c) within the viewport."""
        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()
        x = self.geometry_mapper.col_pos(c) - scroll_x + self.row_header_width
        y = self.geometry_mapper.row_pos(r) - scroll_y + self.col_header_height
        w = self.geometry_mapper.col_size(c)
        h = self.geometry_mapper.row_size(r)
        return QRect(x, y, w, h)

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

        # 2c. Draw Selection Border Drag Preview Rectangle
        if (
            self._move_preview_range is not None
            and self._move_preview_range != self._move_src_range
        ):
            painter.save()
            painter.setClipRect(cell_clip)
            pr = self._move_preview_range
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
            move_pen = QPen(self.COLOR_ACTIVE_BORDER, 2, Qt.PenStyle.DashLine)
            painter.setPen(move_pen)
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
                cf_res = evaluate_cf_for_cell(self.model, r, c)
                bg_col = cf_res.bg_color if (cf_res and cf_res.bg_color) else cell.bg_color

                # Background fill & patterns
                if bg_col or cell.pattern:
                    painter.save()
                    painter.setClipRect(cell_rect)
                    if bg_col:
                        painter.fillRect(cell_rect, QColor(bg_col))
                    if cell.pattern:
                        from atboffice.modules.spreadsheet.dialogs.pattern_defs import (
                            create_pattern_brush,
                        )

                        brush = create_pattern_brush(
                            cell.pattern,
                            cell.pattern_color or "#000000",
                            bg_col or "#FFFFFF",
                        )
                        painter.fillRect(cell_rect, brush)
                    painter.restore()

                # Data bar overlay
                if cf_res and cf_res.data_bar:
                    painter.save()
                    painter.setClipRect(cell_rect)
                    bar_frac = max(0.0, min(1.0, float(cf_res.data_bar.get("frac", 0.0))))
                    bar_color = QColor(str(cf_res.data_bar.get("color", "#638EC6")))
                    bar_w = int((col_w - 2) * bar_frac)
                    if bar_w > 0:
                        painter.fillRect(QRect(col_x + 1, row_y + 1, bar_w, row_h - 2), bar_color)
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
                is_bold = cf_res.bold if (cf_res and cf_res.bold is not None) else cell.bold
                is_italic = cf_res.italic if (cf_res and cf_res.italic is not None) else cell.italic
                font.setBold(is_bold)
                font.setItalic(is_italic)
                font.setUnderline(cell.underline)
                painter.setFont(font)

                text_col_str = cf_res.fg_color if (cf_res and cf_res.fg_color) else cell.fg_color
                text_color = (
                    QColor(text_col_str)
                    if text_col_str
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

            # Dropdown arrow indicator if active cell has list validation
            active_dv = self.model.get_validation_at(ar, ac)
            if (
                active_dv is not None
                and active_dv.type == "list"
                and active_dv.show_dropdown
            ):
                btn_w = 16
                btn_h = ah - 2
                btn_x = ax + aw - btn_w - 1
                btn_y = ay + 1
                self._dv_dropdown_rect = QRect(btn_x, btn_y, btn_w, btn_h)
                painter.fillRect(self._dv_dropdown_rect, QColor(236, 233, 216))
                painter.setPen(QPen(QColor(158, 182, 206), 1))
                painter.drawRect(self._dv_dropdown_rect)
                painter.setPen(QPen(Qt.GlobalColor.black, 1))
                mx = btn_x + btn_w // 2
                my = btn_y + btn_h // 2
                painter.drawLine(mx - 3, my - 1, mx + 3, my - 1)
                painter.drawLine(mx - 2, my, mx + 2, my)
                painter.drawLine(mx - 1, my + 1, mx + 1, my + 1)
            else:
                self._dv_dropdown_rect = None
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

        # 5.6 Draw AutoFilter Buttons
        if getattr(self.model, "auto_filter", None) is not None:
            af = self.model.auto_filter
            r1 = af.r1
            if start_row <= r1 <= end_row:
                painter.save()
                painter.setClipRect(cell_clip)
                row_y = (
                    self.col_header_height
                    + self.geometry_mapper.row_pos(r1)
                    - scroll_y
                )
                row_h = self.geometry_mapper.row_size(r1)
                btn_size = min(16, max(12, row_h - 2))

                for c in range(max(start_col, af.c1), min(end_col, af.c2) + 1):
                    col_x = (
                        self.row_header_width
                        + self.geometry_mapper.col_pos(c)
                        - scroll_x
                    )
                    col_w = self.geometry_mapper.col_size(c)
                    if col_w <= btn_size:
                        continue

                    bx = col_x + col_w - btn_size - 1
                    by = row_y + row_h - btn_size - 1

                    # Draw Office 2003 bevel button
                    painter.fillRect(bx, by, btn_size, btn_size, QColor(236, 233, 216))
                    painter.setPen(QPen(QColor(128, 128, 128), 1))
                    painter.drawRect(bx, by, btn_size - 1, btn_size - 1)
                    # 1px top/left highlight
                    painter.setPen(QPen(Qt.GlobalColor.white, 1))
                    painter.drawLine(bx + 1, by + 1, bx + btn_size - 2, by + 1)
                    painter.drawLine(bx + 1, by + 1, bx + 1, by + btn_size - 2)

                    # Downward arrow triangle
                    col_offset = c - af.c1
                    has_active_crit = (
                        col_offset in af.cols and af.cols[col_offset].has_criteria()
                    )
                    arrow_color = (
                        QColor(0, 0, 255) if has_active_crit else QColor(0, 0, 0)
                    )
                    painter.setBrush(QBrush(arrow_color))
                    painter.setPen(QPen(arrow_color, 1))

                    cx = bx + btn_size // 2
                    cy = by + btn_size // 2
                    arrow_poly = [
                        QPoint(cx - 3, cy - 1),
                        QPoint(cx + 3, cy - 1),
                        QPoint(cx, cy + 2),
                    ]
                    painter.drawPolygon(arrow_poly)

                painter.restore()

        # 5.7 Draw Invalid Data Validation Circles (red ellipses)
        circles = getattr(self.model, "invalid_circles", [])
        if circles:
            painter.save()
            painter.setClipRect(cell_clip)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            circle_pen = QPen(QColor(255, 0, 0), 1.5)
            painter.setPen(circle_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            for cr, cc in circles:
                if cr < start_row or cr > end_row or cc < start_col or cc > end_col:
                    continue
                cx = (
                    self.row_header_width
                    + self.geometry_mapper.col_pos(cc)
                    - scroll_x
                )
                cy = (
                    self.col_header_height
                    + self.geometry_mapper.row_pos(cr)
                    - scroll_y
                )
                cw = self.geometry_mapper.col_size(cc)
                ch = self.geometry_mapper.row_size(cr)
                if cw <= 0 or ch <= 0:
                    continue
                painter.drawEllipse(QRectF(cx - 3, cy - 2, cw + 6, ch + 4))
            painter.restore()

        # 5.8 Draw Comment Red Triangle Indicators
        comments = getattr(self.model, "comments", {})
        if comments:
            painter.save()
            painter.setClipRect(cell_clip)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(255, 0, 0)))
            s = 6
            for cr, cc in comments.keys():
                if cr < start_row or cr > end_row or cc < start_col or cc > end_col:
                    continue
                cx = (
                    self.row_header_width
                    + self.geometry_mapper.col_pos(cc)
                    - scroll_x
                )
                cy = (
                    self.col_header_height
                    + self.geometry_mapper.row_pos(cr)
                    - scroll_y
                )
                cw = self.geometry_mapper.col_size(cc)
                ch = self.geometry_mapper.row_size(cr)
                if cw <= 0 or ch <= 0:
                    continue
                right = cx + cw
                poly = [
                    QPoint(right - s, cy),
                    QPoint(right, cy),
                    QPoint(right, cy + s),
                ]
                painter.drawPolygon(poly)
            painter.restore()

        # 5.9 Draw Visible Comments Callouts
        show_all = getattr(self.model, "show_all_comments", False)
        if comments:
            painter.save()
            painter.setClipRect(cell_clip)
            for (cr, cc), cm in comments.items():
                if not (cm.visible or show_all):
                    continue
                if cr < start_row or cr > end_row or cc < start_col or cc > end_col:
                    continue
                cx = (
                    self.row_header_width
                    + self.geometry_mapper.col_pos(cc)
                    - scroll_x
                )
                cy = (
                    self.col_header_height
                    + self.geometry_mapper.row_pos(cr)
                    - scroll_y
                )
                cw = self.geometry_mapper.col_size(cc)
                ch = self.geometry_mapper.row_size(cr)
                if cw <= 0 or ch <= 0:
                    continue

                bx = cx + cw + 12
                by = max(self.col_header_height + 2, cy - 6)
                bw = 140
                bh = 65

                # Connecting line from cell top-right to note top-left
                painter.setPen(QPen(QColor(0, 0, 0), 1))
                painter.drawLine(cx + cw, cy, bx, by + 6)

                # Yellow note box
                painter.fillRect(bx, by, bw, bh, QColor(255, 255, 225))
                painter.setPen(QPen(QColor(128, 128, 128), 1))
                painter.drawRect(bx, by, bw, bh)

                # Text inside note
                painter.setPen(QPen(QColor(0, 0, 0), 1))
                note_font = QFont(self.font())
                note_font.setPointSize(8)
                painter.setFont(note_font)
                text_rect = QRect(bx + 4, by + 4, bw - 8, bh - 8)
                display_text = f"{cm.author}:\n{cm.text}" if cm.author else cm.text
                painter.drawText(
                    text_rect,
                    Qt.AlignmentFlag.AlignTop
                    | Qt.AlignmentFlag.AlignLeft
                    | Qt.TextFlag.TextWordWrap,
                    display_text,
                )
            painter.restore()

        # 5.10 Draw Audit Tracer Arrows
        self._paint_audit_arrows(painter, cell_clip, scroll_x, scroll_y)

        # 5.11 Draw Freeze Panes Split Lines
        if self.freeze_rows > 0:
            frozen_y = (
                self.col_header_height
                + self.geometry_mapper.row_pos(self.freeze_rows)
            )
            painter.save()
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.drawLine(self.row_header_width, frozen_y, vw, frozen_y)
            painter.restore()

        if self.freeze_cols > 0:
            frozen_x = (
                self.row_header_width
                + self.geometry_mapper.col_pos(self.freeze_cols)
            )
            painter.save()
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.drawLine(frozen_x, self.col_header_height, frozen_x, vh)
            painter.restore()

        # 5.12 Draw Page Break Preview overlay & watermarks if active
        self._paint_page_break_preview(
            painter, cell_clip, scroll_x, scroll_y, vw, vh
        )

        # 6. Draw Fixed Headers (Column Headers, Row Headers, Corner)
        self._paint_headers(
            painter, start_row, end_row, start_col, end_col, scroll_x, scroll_y, vw, vh
        )

        # 7. Draw Resize Guide Line (on top of headers and grid)
        if (
            self._drag_mode == HitZone.COL_RESIZE
            and self._resize_preview_pos is not None
        ):
            painter.save()
            guide_pen = QPen(QColor(0, 0, 0), 1, Qt.PenStyle.DashLine)
            painter.setPen(guide_pen)
            painter.drawLine(self._resize_preview_pos, 0, self._resize_preview_pos, vh)
            painter.restore()
        elif (
            self._drag_mode == HitZone.ROW_RESIZE
            and self._resize_preview_pos is not None
        ):
            painter.save()
            guide_pen = QPen(QColor(0, 0, 0), 1, Qt.PenStyle.DashLine)
            painter.setPen(guide_pen)
            painter.drawLine(0, self._resize_preview_pos, vw, self._resize_preview_pos)
            painter.restore()

    def _paint_page_break_preview(
        self,
        painter: QPainter,
        cell_clip: QRect,
        scroll_x: int,
        scroll_y: int,
        vw: int,
        vh: int,
    ) -> None:
        """Render Excel 2003 Page Break Preview mode."""
        if self._view_mode != "page_break":
            return

        used_rows = [r for (r, c) in self.model.cells.keys()]
        used_cols = [c for (r, c) in self.model.cells.keys()]
        max_r = max(used_rows) if used_rows else 0
        max_c = max(used_cols) if used_cols else 0

        rows_per_page = 45
        cols_per_page = 8

        total_rows = max(rows_per_page, max_r + 1)
        total_cols = max(cols_per_page, max_c + 1)

        page_rows = math.ceil(total_rows / rows_per_page) * rows_per_page
        page_cols = math.ceil(total_cols / cols_per_page) * cols_per_page

        print_x1 = self.row_header_width + self.geometry_mapper.col_pos(0) - scroll_x
        print_y1 = self.col_header_height + self.geometry_mapper.row_pos(0) - scroll_y
        print_x2 = self.row_header_width + self.geometry_mapper.col_pos(page_cols) - scroll_x
        print_y2 = self.col_header_height + self.geometry_mapper.row_pos(page_rows) - scroll_y
        total_print_rect = QRect(print_x1, print_y1, print_x2 - print_x1, print_y2 - print_y1)

        painter.save()
        painter.setClipRect(cell_clip)

        # 1. Dim outside background with gray overlay
        gray_color = QColor(160, 160, 160, 150)
        if total_print_rect.intersects(cell_clip):
            if total_print_rect.left() > cell_clip.left():
                w = total_print_rect.left() - cell_clip.left()
                painter.fillRect(
                    QRect(cell_clip.left(), cell_clip.top(), w, cell_clip.height()),
                    gray_color,
                )
            if total_print_rect.right() < cell_clip.right():
                w = cell_clip.right() - total_print_rect.right()
                painter.fillRect(
                    QRect(total_print_rect.right() + 1, cell_clip.top(), w, cell_clip.height()),
                    gray_color,
                )
            if total_print_rect.top() > cell_clip.top():
                x = max(cell_clip.left(), total_print_rect.left())
                w = min(cell_clip.width(), total_print_rect.width())
                h = total_print_rect.top() - cell_clip.top()
                painter.fillRect(QRect(x, cell_clip.top(), w, h), gray_color)
            if total_print_rect.bottom() < cell_clip.bottom():
                x = max(cell_clip.left(), total_print_rect.left())
                w = min(cell_clip.width(), total_print_rect.width())
                h = cell_clip.bottom() - total_print_rect.bottom()
                painter.fillRect(QRect(x, total_print_rect.bottom() + 1, w, h), gray_color)
        else:
            painter.fillRect(cell_clip, gray_color)

        # 2. Draw Page Watermarks and internal dashed lines
        num_pages_y = page_rows // rows_per_page
        num_pages_x = page_cols // cols_per_page
        page_num = 1

        watermark_font = QFont("Arial", 46, QFont.Weight.Bold)
        watermark_color = QColor(160, 160, 160, 130)

        for py in range(num_pages_y):
            r_start = py * rows_per_page
            r_end = (py + 1) * rows_per_page
            for px in range(num_pages_x):
                c_start = px * cols_per_page
                c_end = (px + 1) * cols_per_page

                pg_x1 = self.row_header_width + self.geometry_mapper.col_pos(c_start) - scroll_x
                pg_y1 = self.col_header_height + self.geometry_mapper.row_pos(r_start) - scroll_y
                pg_x2 = self.row_header_width + self.geometry_mapper.col_pos(c_end) - scroll_x
                pg_y2 = self.col_header_height + self.geometry_mapper.row_pos(r_end) - scroll_y
                pg_rect = QRect(pg_x1, pg_y1, pg_x2 - pg_x1, pg_y2 - pg_y1)

                if pg_rect.intersects(cell_clip):
                    painter.setFont(watermark_font)
                    painter.setPen(QPen(watermark_color))
                    painter.drawText(pg_rect, Qt.AlignmentFlag.AlignCenter, f"Page {page_num}")

                    # Internal dashed break lines
                    if px > 0:
                        dash_pen = QPen(QColor(0, 0, 255), 1, Qt.PenStyle.DashLine)
                        painter.setPen(dash_pen)
                        painter.drawLine(pg_x1, pg_y1, pg_x1, pg_y2)
                    if py > 0:
                        dash_pen = QPen(QColor(0, 0, 255), 1, Qt.PenStyle.DashLine)
                        painter.setPen(dash_pen)
                        painter.drawLine(pg_x1, pg_y1, pg_x2, pg_y1)

                page_num += 1

        # 3. Outer boundary: bold solid blue border
        outer_pen = QPen(QColor(0, 0, 255), 2, Qt.PenStyle.SolidLine)
        painter.setPen(outer_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(total_print_rect)

        painter.restore()

    def _paint_audit_arrows(
        self,
        painter: QPainter,
        clip_rect: QRect,
        scroll_x: int,
        scroll_y: int,
    ) -> None:
        """Render formula auditing tracer arrows connecting precedents and dependents."""
        arrows = getattr(self.model, "audit_arrows", [])
        if not arrows:
            return

        painter.save()
        painter.setClipRect(clip_rect)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        cur_sheet = getattr(self.model, "name", "Sheet1")

        def cell_center(r: int, c: int) -> QPointF:
            cx = (
                self.row_header_width
                + self.geometry_mapper.col_pos(c)
                - scroll_x
            )
            cy = (
                self.col_header_height
                + self.geometry_mapper.row_pos(r)
                - scroll_y
            )
            cw = self.geometry_mapper.col_size(c)
            ch = self.geometry_mapper.row_size(r)
            return QPointF(cx + cw / 2.0, cy + ch / 2.0)

        def draw_arrow_head(p_from: QPointF, p_to: QPointF, color: QColor) -> None:
            angle = math.atan2(p_to.y() - p_from.y(), p_to.x() - p_from.x())
            arrow_len = 8.0
            arrow_angle = math.pi / 6.0
            p1 = QPointF(
                p_to.x() - arrow_len * math.cos(angle - arrow_angle),
                p_to.y() - arrow_len * math.sin(angle - arrow_angle),
            )
            p2 = QPointF(
                p_to.x() - arrow_len * math.cos(angle + arrow_angle),
                p_to.y() - arrow_len * math.sin(angle + arrow_angle),
            )
            poly = QPolygonF([p_to, p1, p2])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawPolygon(poly)

        for a in arrows:
            col = QColor(255, 0, 0) if a.is_error else QColor(0, 0, 255)
            pen = QPen(col, 1.5)

            # Case 1: Intra-sheet: both on current sheet
            if a.from_sheet == cur_sheet and a.to_sheet == cur_sheet:
                p_to = cell_center(a.to_r, a.to_c)
                p_from = cell_center(a.from_r1, a.from_c1)

                if a.is_range:
                    r_min = min(a.from_r1, a.from_r2)
                    r_max = max(a.from_r1, a.from_r2)
                    c_min = min(a.from_c1, a.from_c2)
                    c_max = max(a.from_c1, a.from_c2)
                    x1 = self.row_header_width + self.geometry_mapper.col_pos(c_min) - scroll_x
                    y1 = self.col_header_height + self.geometry_mapper.row_pos(r_min) - scroll_y
                    x2 = (
                        self.row_header_width
                        + self.geometry_mapper.col_pos(c_max)
                        + self.geometry_mapper.col_size(c_max)
                        - scroll_x
                    )
                    y2 = (
                        self.col_header_height
                        + self.geometry_mapper.row_pos(r_max)
                        + self.geometry_mapper.row_size(r_max)
                        - scroll_y
                    )
                    painter.setPen(pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRect(QRectF(x1, y1, x2 - x1, y2 - y1))

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(col))
                painter.drawEllipse(p_from, 3.0, 3.0)

                painter.setPen(pen)
                painter.drawLine(p_from, p_to)
                draw_arrow_head(p_from, p_to, col)

            # Case 2: Cross-sheet incoming: from another sheet into current sheet
            elif a.to_sheet == cur_sheet and a.from_sheet != cur_sheet:
                p_to = cell_center(a.to_r, a.to_c)
                p_origin = QPointF(p_to.x() - 40.0, p_to.y() - 30.0)

                dash_pen = QPen(QColor(0, 0, 0), 1.2, Qt.PenStyle.DashLine)
                painter.setPen(dash_pen)
                painter.drawLine(p_origin, p_to)
                draw_arrow_head(p_origin, p_to, QColor(0, 0, 0))

                sheet_rect = QRectF(p_to.x() - 52.0, p_to.y() - 40.0, 14.0, 11.0)
                painter.setPen(QPen(QColor(0, 0, 0), 1.0))
                painter.setBrush(QBrush(QColor(255, 255, 255)))
                painter.drawRect(sheet_rect)
                painter.drawLine(
                    QPointF(sheet_rect.left() + 2, sheet_rect.top() + 3),
                    QPointF(sheet_rect.right() - 2, sheet_rect.top() + 3),
                )
                painter.drawLine(
                    QPointF(sheet_rect.left() + 2, sheet_rect.top() + 6),
                    QPointF(sheet_rect.right() - 2, sheet_rect.top() + 6),
                )

            # Case 3: Cross-sheet outgoing: from current sheet to another sheet
            elif a.from_sheet == cur_sheet and a.to_sheet != cur_sheet:
                p_from = cell_center(a.from_r1, a.from_c1)
                p_dest = QPointF(p_from.x() + 40.0, p_from.y() + 30.0)

                dash_pen = QPen(QColor(0, 0, 0), 1.2, Qt.PenStyle.DashLine)
                painter.setPen(dash_pen)
                painter.drawLine(p_from, p_dest)
                draw_arrow_head(p_from, p_dest, QColor(0, 0, 0))

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(col))
                painter.drawEllipse(p_from, 3.0, 3.0)

                sheet_rect = QRectF(p_dest.x() + 2.0, p_dest.y() - 5.0, 14.0, 11.0)
                painter.setPen(QPen(QColor(0, 0, 0), 1.0))
                painter.setBrush(QBrush(QColor(255, 255, 255)))
                painter.drawRect(sheet_rect)
                painter.drawLine(
                    QPointF(sheet_rect.left() + 2, sheet_rect.top() + 3),
                    QPointF(sheet_rect.right() - 2, sheet_rect.top() + 3),
                )
                painter.drawLine(
                    QPointF(sheet_rect.left() + 2, sheet_rect.top() + 6),
                    QPointF(sheet_rect.right() - 2, sheet_rect.top() + 6),
                )

        painter.restore()

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
    # Mouse Interaction Subsystem & Drag Lifecycle
    # -------------------------------------------------------------------------
    def _start_auto_scroll(self, dr: int, dc: int) -> None:
        """Start or update periodic auto-scrolling when dragging near viewport edges."""
        if dr == 0 and dc == 0:
            self._stop_auto_scroll()
            return
        if self._auto_scroll_timer is None:
            self._auto_scroll_timer = QTimer(self)
            self._auto_scroll_timer.setInterval(60)
            self._auto_scroll_timer.timeout.connect(self._on_auto_scroll_tick)
        self._auto_scroll_delta = (dr, dc)
        if not self._auto_scroll_timer.isActive():
            self._auto_scroll_timer.start()

    def _stop_auto_scroll(self) -> None:
        """Stop periodic auto-scrolling."""
        if self._auto_scroll_timer is not None and self._auto_scroll_timer.isActive():
            self._auto_scroll_timer.stop()
        self._auto_scroll_delta = (0, 0)

    def _on_auto_scroll_tick(self) -> None:
        """Handle auto-scroll timer tick: scroll viewport and update drag."""
        dr, dc = self._auto_scroll_delta
        if (dr == 0 and dc == 0) or self._drag_mode == HitZone.NONE:
            self._stop_auto_scroll()
            return

        if dr != 0:
            vs = self.verticalScrollBar()
            cur_y = vs.value()
            cur_r = self.geometry_mapper.find_row_at(cur_y)
            step = 1 if dr > 0 else -1
            target_r = cur_r + step
            while (
                0 <= target_r < self.geometry_mapper.max_rows
                and self.geometry_mapper.row_size(target_r) == 0
            ):
                target_r += step
            target_r = max(0, min(self.geometry_mapper.max_rows - 1, target_r))
            new_y = self.geometry_mapper.row_pos(target_r)
            if new_y == cur_y:
                new_y = max(0, min(vs.maximum(), cur_y + dr * 24))
            vs.setValue(new_y)

        if dc != 0:
            hs = self.horizontalScrollBar()
            cur_x = hs.value()
            cur_c = self.geometry_mapper.find_col_at(cur_x)
            step = 1 if dc > 0 else -1
            target_c = cur_c + step
            while (
                0 <= target_c < self.geometry_mapper.max_cols
                and self.geometry_mapper.col_size(target_c) == 0
            ):
                target_c += step
            target_c = max(0, min(self.geometry_mapper.max_cols - 1, target_c))
            new_x = self.geometry_mapper.col_pos(target_c)
            if new_x == cur_x:
                new_x = max(0, min(hs.maximum(), cur_x + dc * 64))
            hs.setValue(new_x)

        # Update drag destination after scrolling
        self._process_drag_at(
            self._last_mouse_pos.x(),
            self._last_mouse_pos.y(),
            self._last_modifiers,
        )
        self.viewport().update()

    def set_format_painter_armed(self, win: Any) -> None:
        """Arm or disarm format painter mode."""
        self._format_painter_window = win
        if win is not None:
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def cancel_drag(self, why: str = "api") -> None:
        """Cancel an in-progress drag operation and restore pre-drag state."""
        if self._drag_mode == HitZone.NONE and self._drag_snapshot is None:
            return

        self._stop_auto_scroll()

        snap = self._drag_snapshot
        if snap is not None:
            if snap.zone in (
                HitZone.CELL,
                HitZone.COL_HEADER,
                HitZone.ROW_HEADER,
                HitZone.CORNER,
            ):
                current_sheet = getattr(self.model, "active_sheet_index", 0)
                if current_sheet == snap.sheet_index:
                    self.selection.restore_snapshot(snap.selection_snapshot)
            elif snap.zone == HitZone.COL_RESIZE:
                if self._resize_orig_sizes:
                    for c, sz in self._resize_orig_sizes.items():
                        self.geometry_mapper.set_col_width(c, sz)
                elif snap.resize_orig_sizes:
                    for c, sz in snap.resize_orig_sizes.items():
                        self.geometry_mapper.set_col_width(c, sz)
                elif snap.resize_index >= 0:
                    self.geometry_mapper.set_col_width(
                        snap.resize_index, snap.resize_orig_size
                    )
                self._update_scrollbars()
            elif snap.zone == HitZone.ROW_RESIZE:
                if self._resize_orig_sizes:
                    for r, sz in self._resize_orig_sizes.items():
                        self.geometry_mapper.set_row_height(r, sz)
                elif snap.resize_orig_sizes:
                    for r, sz in snap.resize_orig_sizes.items():
                        self.geometry_mapper.set_row_height(r, sz)
                elif snap.resize_index >= 0:
                    self.geometry_mapper.set_row_height(
                        snap.resize_index, snap.resize_orig_size
                    )
                self._update_scrollbars()
            elif snap.zone == HitZone.FILL_HANDLE:
                self._fill_start_src = None
                self._fill_preview_range = None
                QToolTip.hideText()
            elif snap.zone == HitZone.BORDER:
                self._move_src_range = None
                self._move_grab_cell = None
                self._move_preview_range = None
                self._move_ctrl_pressed = False
                QToolTip.hideText()
                current_sheet = getattr(self.model, "active_sheet_index", 0)
                if current_sheet == snap.sheet_index:
                    self.selection.restore_snapshot(snap.selection_snapshot)

            if (
                self.editor_controller is not None
                and self.editor_controller.is_active
                and hasattr(self.editor_controller, "point_cancel")
            ):
                self.editor_controller.point_cancel()

        if why == "button":
            self._swallow_secondary_button = True

        self._drag_mode = HitZone.NONE
        self._drag_moved = False
        self._drag_start_pos = None
        self._drag_snapshot = None
        self._resize_index = -1
        self._resize_targets = []
        self._resize_orig_sizes = {}
        self._resize_preview_pos = None
        self._resize_preview_size = 0
        self._header_drag_anchor = -1
        QToolTip.hideText()
        self._point_anchor = None
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self.viewport().update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # If already dragging with another button and secondary button pressed, cancel
        if self._drag_mode != HitZone.NONE:
            if event.button() != Qt.MouseButton.LeftButton:
                self.cancel_drag(why="button")
                event.accept()
                return

        if event.button() == Qt.MouseButton.RightButton:
            # 1. Right click commits active editor first
            if self.editor_controller is not None and self.editor_controller.is_active:
                if not self.editor_controller.commit():
                    event.accept()
                    return

            x = event.position().x()
            y = event.position().y()
            hit = self.hit_test(int(x), int(y))

            if hit.zone == HitZone.CELL and hit.row is not None and hit.col is not None:
                if not self.selection.is_selected(hit.row, hit.col):
                    self.selection.select_cell(hit.row, hit.col)
            elif hit.zone == HitZone.COL_HEADER and hit.col is not None:
                pr = self.selection.primary_range
                is_whole_cols = (
                    pr.min_r == 0 and pr.max_r == self.selection.max_rows - 1
                )
                if not (is_whole_cols and pr.min_c <= hit.col <= pr.max_c):
                    self.selection.select_cols(hit.col, hit.col)
            elif hit.zone == HitZone.ROW_HEADER and hit.row is not None:
                pr = self.selection.primary_range
                is_whole_rows = (
                    pr.min_c == 0 and pr.max_c == self.selection.max_cols - 1
                )
                if not (is_whole_rows and pr.min_r <= hit.row <= pr.max_r):
                    self.selection.select_rows(hit.row, hit.row)
            elif hit.zone == HitZone.CORNER:
                self.selection.select_all()

            self.viewport().update()
            super().mousePressEvent(event)
            return

        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        x = event.position().x()
        y = event.position().y()

        # Check click on List Validation dropdown arrow button
        if (
            self._dv_dropdown_rect is not None
            and self._dv_dropdown_rect.contains(int(x), int(y))
        ):
            self._open_dv_dropdown()
            return

        hit = self.hit_test(int(x), int(y))
        modifiers = event.modifiers()

        self._drag_start_pos = QPoint(int(x), int(y))
        self._last_mouse_pos = QPoint(int(x), int(y))
        self._drag_moved = False

        if hit.zone == HitZone.CORNER:
            self._drag_mode = HitZone.CORNER
            self._drag_snapshot = DragSnapshot(
                zone=HitZone.CORNER,
                sheet_index=getattr(self.model, "active_sheet_index", 0),
                selection_snapshot=self.selection.snapshot(),
            )
            self.selection.select_all()
            self.viewport().update()

        elif hit.zone == HitZone.COL_RESIZE:
            self._drag_mode = HitZone.COL_RESIZE
            self._resize_index = hit.col if hit.col is not None else -1
            self._resize_start_pos = int(x)
            cols = self.cols_for_resize(self._resize_index)
            self._resize_targets = cols
            self._resize_orig_sizes = {c: self.geometry_mapper.col_size(c) for c in cols}
            self._resize_orig_size = self.geometry_mapper.col_size(self._resize_index)
            self._resize_preview_size = self._resize_orig_size
            self._resize_preview_pos = int(x)
            self._drag_snapshot = DragSnapshot(
                zone=HitZone.COL_RESIZE,
                sheet_index=getattr(self.model, "active_sheet_index", 0),
                selection_snapshot=self.selection.snapshot(),
                resize_index=self._resize_index,
                resize_orig_size=self._resize_orig_size,
                resize_orig_sizes=dict(self._resize_orig_sizes),
            )

        elif hit.zone == HitZone.ROW_RESIZE:
            self._drag_mode = HitZone.ROW_RESIZE
            self._resize_index = hit.row if hit.row is not None else -1
            self._resize_start_pos = int(y)
            rows = self.rows_for_resize(self._resize_index)
            self._resize_targets = rows
            self._resize_orig_sizes = {r: self.geometry_mapper.row_size(r) for r in rows}
            self._resize_orig_size = self.geometry_mapper.row_size(self._resize_index)
            self._resize_preview_size = self._resize_orig_size
            self._resize_preview_pos = int(y)
            self._drag_snapshot = DragSnapshot(
                zone=HitZone.ROW_RESIZE,
                sheet_index=getattr(self.model, "active_sheet_index", 0),
                selection_snapshot=self.selection.snapshot(),
                resize_index=self._resize_index,
                resize_orig_size=self._resize_orig_size,
                resize_orig_sizes=dict(self._resize_orig_sizes),
            )

        elif hit.zone == HitZone.COL_HEADER and hit.col is not None:
            self._drag_mode = HitZone.COL_HEADER
            self._header_drag_anchor = hit.col
            self._drag_snapshot = DragSnapshot(
                zone=HitZone.COL_HEADER,
                sheet_index=getattr(self.model, "active_sheet_index", 0),
                selection_snapshot=self.selection.snapshot(),
            )
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                anchor_c = (
                    self.selection.anchor_cell[1]
                    if self.selection.anchor_cell is not None
                    else hit.col
                )
                self.selection.select_cols(min(anchor_c, hit.col), max(anchor_c, hit.col))
            elif modifiers & (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier
            ):
                self.selection.add_range(
                    SelectionRange(0, hit.col, self.geometry_mapper.max_rows - 1, hit.col)
                )
            else:
                self.selection.select_cols(hit.col, hit.col)
            self.viewport().update()

        elif hit.zone == HitZone.ROW_HEADER and hit.row is not None:
            self._drag_mode = HitZone.ROW_HEADER
            self._header_drag_anchor = hit.row
            self._drag_snapshot = DragSnapshot(
                zone=HitZone.ROW_HEADER,
                sheet_index=getattr(self.model, "active_sheet_index", 0),
                selection_snapshot=self.selection.snapshot(),
            )
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                anchor_r = (
                    self.selection.anchor_cell[0]
                    if self.selection.anchor_cell is not None
                    else hit.row
                )
                self.selection.select_rows(min(anchor_r, hit.row), max(anchor_r, hit.row))
            elif modifiers & (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier
            ):
                self.selection.add_range(
                    SelectionRange(hit.row, 0, hit.row, self.geometry_mapper.max_cols - 1)
                )
            else:
                self.selection.select_rows(hit.row, hit.row)
            self.viewport().update()

        elif hit.zone == HitZone.FILL_HANDLE:
            self._drag_mode = HitZone.FILL_HANDLE
            self._fill_start_src = self.selection.primary_range
            self._fill_preview_range = self._fill_start_src
            self._fill_ctrl_pressed = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
            self._drag_snapshot = DragSnapshot(
                zone=HitZone.FILL_HANDLE,
                sheet_index=getattr(self.model, "active_sheet_index", 0),
                selection_snapshot=self.selection.snapshot(),
                fill_start_src=self._fill_start_src,
            )
            self.viewport().update()

        elif hit.zone == HitZone.BORDER:
            if self.editor_controller is not None and self.editor_controller.is_active:
                if not self.editor_controller.commit():
                    return
            self._drag_mode = HitZone.BORDER
            self._move_src_range = self.selection.primary_range
            self._move_grab_cell = (
                hit.row if hit.row is not None else self._move_src_range.min_r,
                hit.col if hit.col is not None else self._move_src_range.min_c,
            )
            self._move_preview_range = self._move_src_range
            self._move_ctrl_pressed = bool(
                modifiers
                & (
                    Qt.KeyboardModifier.ControlModifier
                    | Qt.KeyboardModifier.MetaModifier
                )
            )
            self._drag_snapshot = DragSnapshot(
                zone=HitZone.BORDER,
                sheet_index=getattr(self.model, "active_sheet_index", 0),
                selection_snapshot=self.selection.snapshot(),
                move_start_src=self._move_src_range,
                move_grab_cell=self._move_grab_cell,
            )
            self.viewport().setCursor(Qt.CursorShape.SizeAllCursor)
            self.viewport().update()

        elif hit.zone == HitZone.FILTER_BUTTON and hit.col is not None:
            self._open_filter_dropdown(hit.col)
            return

        elif hit.zone == HitZone.CELL and hit.row is not None and hit.col is not None:
            self._drag_snapshot = DragSnapshot(
                zone=HitZone.CELL,
                sheet_index=getattr(self.model, "active_sheet_index", 0),
                selection_snapshot=self.selection.snapshot(),
            )
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
        self._last_mouse_pos = QPoint(x, y)

        # Update cursor when hovering
        if self._drag_mode == HitZone.NONE:
            hit = self.hit_test(x, y)
            if hit.zone == HitZone.FILL_HANDLE:
                self.viewport().setCursor(Qt.CursorShape.CrossCursor)
            elif hit.zone == HitZone.BORDER:
                self.viewport().setCursor(Qt.CursorShape.SizeAllCursor)
            elif hit.zone == HitZone.COL_RESIZE:
                self.viewport().setCursor(Qt.CursorShape.SplitHCursor)
            elif hit.zone == HitZone.ROW_RESIZE:
                self.viewport().setCursor(Qt.CursorShape.SplitVCursor)
            elif hit.zone in (HitZone.COL_HEADER, HitZone.ROW_HEADER):
                self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

            # Check comment tooltip hover
            if hit.row is not None and hit.col is not None:
                cm = (
                    self.model.get_comment(hit.row, hit.col)
                    if hasattr(self.model, "get_comment")
                    else None
                )
                if cm:
                    tip_text = (
                        f"{cm.author}:\n{cm.text}" if cm.author else cm.text
                    )
                    QToolTip.showText(
                        event.globalPosition().toPoint(),
                        tip_text,
                        self.viewport(),
                    )
                else:
                    QToolTip.hideText()
            else:
                QToolTip.hideText()
            return

        # 1. Lost capture check: left button not pressed while in drag mode
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            self.cancel_drag(why="lost")
            return

        # 2. Check 3px threshold
        if not self._drag_moved:
            if self._drag_start_pos is not None:
                dx = x - self._drag_start_pos.x()
                dy = y - self._drag_start_pos.y()
                if math.hypot(dx, dy) < self._drag_threshold:
                    return
                self._drag_moved = True

        # 3. Auto-scroll boundary check
        vw = self.viewport().width()
        vh = self.viewport().height()

        fz_r_h = (
            self.geometry_mapper.row_pos(self.freeze_rows)
            if self.freeze_rows > 0
            else 0
        )
        fz_c_w = (
            self.geometry_mapper.col_pos(self.freeze_cols)
            if self.freeze_cols > 0
            else 0
        )

        scroll_top = self.col_header_height + fz_r_h
        scroll_left = self.row_header_width + fz_c_w

        drag_from = self._drag_start_pos or QPoint(x, y)
        in_rows = drag_from.y() >= scroll_top
        in_cols = drag_from.x() >= scroll_left

        curr_sy = self.verticalScrollBar().value()
        curr_sx = self.horizontalScrollBar().value()

        dr = 0
        dc = 0
        if y > vh - 4:
            dr = 1
        elif y < scroll_top and in_rows and curr_sy > 0:
            dr = -1

        if x > vw - 4:
            dc = 1
        elif x < scroll_left and in_cols and curr_sx > 0:
            dc = -1

        if dr != 0 or dc != 0:
            self._start_auto_scroll(dr, dc)
        else:
            self._stop_auto_scroll()

        self._last_modifiers = event.modifiers()
        # 4. Process drag move
        self._process_drag_at(x, y, event.modifiers())

    def _process_drag_at(
        self,
        x: int,
        y: int,
        modifiers: Qt.KeyboardModifiers = Qt.KeyboardModifier.NoModifier,
    ) -> None:
        """Handle active drag update at (x, y)."""
        if self._drag_mode == HitZone.FILL_HANDLE:
            self._fill_ctrl_pressed = bool(
                modifiers & Qt.KeyboardModifier.ControlModifier
            )
            hit = self.hit_test(x, y)
            row = hit.row
            col = hit.col
            if row is None:
                sheet_y = max(
                    0, self.verticalScrollBar().value() + (y - self.col_header_height)
                )
                row = self.geometry_mapper.find_row_at(sheet_y)
            if col is None:
                sheet_x = max(
                    0, self.horizontalScrollBar().value() + (x - self.row_header_width)
                )
                col = self.geometry_mapper.find_col_at(sheet_x)

            if self._fill_start_src is not None:
                dest, is_shrink = AutoFillEngine.determine_destination(
                    self._fill_start_src, row, col
                )
                self._fill_preview_range = dest
                tip = range_name(
                    {
                        "r1": dest.min_r,
                        "c1": dest.min_c,
                        "r2": dest.max_r,
                        "c2": dest.max_c,
                    }
                )
                QToolTip.showText(
                    self.viewport().mapToGlobal(QPoint(x + 14, y + 18)),
                    tip,
                    self.viewport(),
                )
                self.reveal(row, col)
                self.viewport().update()

        elif self._drag_mode == HitZone.COL_RESIZE:
            delta = x - self._resize_start_pos
            base_w = self._resize_orig_sizes.get(
                self._resize_index, self._resize_orig_size
            )
            new_w = max(0, base_w + delta)
            self._resize_preview_size = new_w
            self._resize_preview_pos = x
            for c in self._resize_targets:
                self.geometry_mapper.set_col_width(c, new_w)
            self._update_scrollbars()
            tip = safe_tr("宽度: {0} 像素").format(new_w)
            QToolTip.showText(
                self.viewport().mapToGlobal(QPoint(x + 14, 18)),
                tip,
                self.viewport(),
            )
            self.viewport().update()

        elif self._drag_mode == HitZone.ROW_RESIZE:
            delta = y - self._resize_start_pos
            base_h = self._resize_orig_sizes.get(
                self._resize_index, self._resize_orig_size
            )
            new_h = max(0, base_h + delta)
            self._resize_preview_size = new_h
            self._resize_preview_pos = y
            for r in self._resize_targets:
                self.geometry_mapper.set_row_height(r, new_h)
            self._update_scrollbars()
            tip = safe_tr("高度: {0} 像素").format(new_h)
            QToolTip.showText(
                self.viewport().mapToGlobal(QPoint(14, y + 18)),
                tip,
                self.viewport(),
            )
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

        elif self._drag_mode == HitZone.COL_HEADER:
            hit = self.hit_test(x, y)
            target_c = hit.col
            if target_c is None:
                sheet_x = max(
                    0, self.horizontalScrollBar().value() + (x - self.row_header_width)
                )
                target_c = self.geometry_mapper.find_col_at(sheet_x)
            orig_c = (
                self._header_drag_anchor
                if self._header_drag_anchor >= 0
                else (
                    self._drag_snapshot.selection_snapshot.get(
                        "anchor_cell", (0, target_c)
                    )[1]
                    if self._drag_snapshot is not None
                    else target_c
                )
            )
            self.selection.select_cols(orig_c, target_c)
            self.reveal(0, target_c)
            self.viewport().update()

        elif self._drag_mode == HitZone.ROW_HEADER:
            hit = self.hit_test(x, y)
            target_r = hit.row
            if target_r is None:
                sheet_y = max(
                    0, self.verticalScrollBar().value() + (y - self.col_header_height)
                )
                target_r = self.geometry_mapper.find_row_at(sheet_y)
            orig_r = (
                self._header_drag_anchor
                if self._header_drag_anchor >= 0
                else (
                    self._drag_snapshot.selection_snapshot.get(
                        "anchor_cell", (target_r, 0)
                    )[0]
                    if self._drag_snapshot is not None
                    else target_r
                )
            )
            self.selection.select_rows(orig_r, target_r)
            self.reveal(target_r, 0)
            self.viewport().update()

        elif self._drag_mode == HitZone.BORDER:
            self._move_ctrl_pressed = bool(
                modifiers
                & (
                    Qt.KeyboardModifier.ControlModifier
                    | Qt.KeyboardModifier.MetaModifier
                )
            )
            sheet_x = max(
                0, self.horizontalScrollBar().value() + (x - self.row_header_width)
            )
            sheet_y = max(
                0, self.verticalScrollBar().value() + (y - self.col_header_height)
            )
            curr_r = self.geometry_mapper.find_row_at(sheet_y)
            curr_c = self.geometry_mapper.find_col_at(sheet_x)

            if self._move_src_range is not None:
                grab_r, grab_c = (
                    self._move_grab_cell
                    if self._move_grab_cell
                    else (self._move_src_range.min_r, self._move_src_range.min_c)
                )
                dr = curr_r - grab_r
                dc = curr_c - grab_c

                src = self._move_src_range
                h = src.max_r - src.min_r
                w = src.max_c - src.min_c
                to_r1 = max(0, min(self.geometry_mapper.max_rows - 1 - h, src.min_r + dr))
                to_c1 = max(0, min(self.geometry_mapper.max_cols - 1 - w, src.min_c + dc))
                to_r2 = to_r1 + h
                to_c2 = to_c1 + w

                self._move_preview_range = SelectionRange(to_r1, to_c1, to_r2, to_c2)
                tip = range_name({"r1": to_r1, "c1": to_c1, "r2": to_r2, "c2": to_c2})
                QToolTip.showText(
                    self.viewport().mapToGlobal(QPoint(x + 14, y + 18)),
                    tip,
                    self.viewport(),
                )
                self.reveal(to_r1, to_c1)
                self.viewport().update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._stop_auto_scroll()
        if self._drag_mode == HitZone.FILL_HANDLE:
            QToolTip.hideText()
            if (
                self._drag_moved
                and self._fill_start_src is not None
                and self._fill_preview_range is not None
            ):
                src = self._fill_start_src
                dest = self._fill_preview_range
                ctrl = self._fill_ctrl_pressed or bool(
                    event.modifiers() & Qt.KeyboardModifier.ControlModifier
                )
                single = (src.min_r == src.max_r and src.min_c == src.max_c)
                fill_mode = (
                    "linear" if (ctrl and single) else ("copy" if ctrl else "auto")
                )

                before_cells = {k: v.clone() for k, v in self.model.cells.items()}
                before_merges = list(self.model.merges)
                before_comments = (
                    {
                        k: CellComment(**v.__dict__)
                        for k, v in self.model.comments.items()
                    }
                    if hasattr(self.model, "comments")
                    else {}
                )
                before_sel = self.selection.snapshot()

                AutoFillEngine.auto_fill(
                    self.model,
                    src,
                    dest,
                    mode=fill_mode,
                    ctrl_pressed=ctrl,
                )
                self.selection.select_cell(dest.min_r, dest.min_c)
                self.selection.extend_to(dest.max_r, dest.max_c)

                after_cells = {k: v.clone() for k, v in self.model.cells.items()}
                after_merges = list(self.model.merges)
                after_comments = (
                    {
                        k: CellComment(**v.__dict__)
                        for k, v in self.model.comments.items()
                    }
                    if hasattr(self.model, "comments")
                    else {}
                )
                after_sel = self.selection.snapshot()

                self._undo_stack.append(
                    {
                        "action": "autofill",
                        "before_cells": before_cells,
                        "before_merges": before_merges,
                        "before_comments": before_comments,
                        "before_sel": before_sel,
                        "after_cells": after_cells,
                        "after_merges": after_merges,
                        "after_comments": after_comments,
                        "after_sel": after_sel,
                    }
                )
                self._redo_stack.clear()
            self._fill_start_src = None
            self._fill_preview_range = None

        elif self._drag_mode == HitZone.COL_RESIZE:
            QToolTip.hideText()
            if self._drag_moved and self._resize_targets:
                new_w = self._resize_preview_size
                before_sizes = dict(self._resize_orig_sizes)
                after_sizes = {c: new_w for c in self._resize_targets}
                for c in self._resize_targets:
                    self.geometry_mapper.set_col_width(c, new_w)
                self._undo_stack.append(
                    {
                        "action": "col_resize",
                        "targets": list(self._resize_targets),
                        "before_sizes": before_sizes,
                        "after_sizes": after_sizes,
                    }
                )
                self._redo_stack.clear()
                self._update_scrollbars()
            self._resize_targets = []
            self._resize_orig_sizes = {}
            self._resize_preview_pos = None
            self._resize_preview_size = 0

        elif self._drag_mode == HitZone.ROW_RESIZE:
            QToolTip.hideText()
            if self._drag_moved and self._resize_targets:
                new_h = self._resize_preview_size
                before_sizes = dict(self._resize_orig_sizes)
                after_sizes = {r: new_h for r in self._resize_targets}
                for r in self._resize_targets:
                    self.geometry_mapper.set_row_height(r, new_h)
                self._undo_stack.append(
                    {
                        "action": "row_resize",
                        "targets": list(self._resize_targets),
                        "before_sizes": before_sizes,
                        "after_sizes": after_sizes,
                    }
                )
                self._redo_stack.clear()
                self._update_scrollbars()
            self._resize_targets = []
            self._resize_orig_sizes = {}
            self._resize_preview_pos = None
            self._resize_preview_size = 0

        elif self._drag_mode == HitZone.BORDER:
            QToolTip.hideText()
            if (
                self._drag_moved
                and self._move_src_range is not None
                and self._move_preview_range is not None
            ):
                src = self._move_src_range
                to = self._move_preview_range
                ctrl = self._move_ctrl_pressed or bool(
                    event.modifiers()
                    & (
                        Qt.KeyboardModifier.ControlModifier
                        | Qt.KeyboardModifier.MetaModifier
                    )
                )
                self.move_range(src, to, copy=ctrl)
            self._move_src_range = None
            self._move_grab_cell = None
            self._move_preview_range = None
            self._move_ctrl_pressed = False

        if getattr(self, "_format_painter_window", None) is not None:
            pr = self.selection.primary_range
            self._format_painter_window.apply_format_painter_to_range(
                pr.min_r, pr.min_c, pr.max_r, pr.max_c
            )

        self._drag_mode = HitZone.NONE
        self._drag_moved = False
        self._drag_start_pos = None
        self._drag_snapshot = None
        self._resize_index = -1
        self._header_drag_anchor = -1
        self._point_anchor = None
        if getattr(self, "_format_painter_window", None) is not None:
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self.viewport().update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        x = int(event.position().x())
        y = int(event.position().y())
        hit = self.hit_test(x, y)

        if hit.zone == HitZone.COL_RESIZE and hit.col is not None:
            self.auto_fit_column(hit.col)
        elif hit.zone == HitZone.BORDER and len(self.selection.ranges) == 1:
            pr = self.selection.primary_range
            sx = self.horizontalScrollBar().value()
            sy = self.verticalScrollBar().value()
            bx1 = (
                self.row_header_width
                + self.geometry_mapper.col_pos(pr.min_c)
                - sx
            )
            bx2 = (
                self.row_header_width
                + self.geometry_mapper.col_pos(pr.max_c + 1)
                - sx
            )
            by1 = (
                self.col_header_height
                + self.geometry_mapper.row_pos(pr.min_r)
                - sy
            )
            by2 = (
                self.col_header_height
                + self.geometry_mapper.row_pos(pr.max_r + 1)
                - sy
            )
            d_top = abs(y - by1)
            d_bottom = abs(y - by2)
            d_left = abs(x - bx1)
            d_right = abs(x - bx2)
            min_d = min(d_top, d_bottom, d_left, d_right)
            if min_d == d_top:
                self.move_to_edge(-1, 0)
            elif min_d == d_bottom:
                self.move_to_edge(1, 0)
            elif min_d == d_left:
                self.move_to_edge(0, -1)
            else:
                self.move_to_edge(0, 1)
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

        # Esc cancels active drag or armed format painter
        if key == Qt.Key.Key_Escape:
            if getattr(self, "_format_painter_window", None) is not None:
                self._format_painter_window._cancel_format_painter()
                event.accept()
                return
            if self._drag_mode != HitZone.NONE:
                self.cancel_drag(why="esc")
                event.accept()
                return

        # Shift+F10 to trigger shortcut context menu
        if (
            key == Qt.Key.Key_F10
            and bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        ):
            self.open_context_menu(reason=QContextMenuEvent.Reason.Keyboard)
            return

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

        # Alt+Down to open List Validation dropdown
        if key == Qt.Key.Key_Down and (modifiers & Qt.KeyboardModifier.AltModifier):
            if self._dv_dropdown_rect is not None:
                self._open_dv_dropdown()
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

    def _open_dv_dropdown(self) -> None:
        """Open the List Data Validation dropdown popup for the active cell."""
        ar, ac = self.selection.active_cell
        dv = self.model.get_validation_at(ar, ac)
        if dv is None or dv.type != "list":
            return
        from atboffice.modules.spreadsheet.models.validation import get_list_items

        items = get_list_items(self.model, dv, ar, ac)
        if not items:
            return

        menu = QMenu(self)
        for item in items:
            action = menu.addAction(str(item))

            def on_triggered(checked: bool = False, val=item) -> None:
                self.model.set_cell_value(ar, ac, val)
                if (
                    self.editor_controller is not None
                    and self.editor_controller.formula_bar is not None
                ):
                    self.editor_controller.formula_bar.set_cell_value(val)
                self.viewport().update()

            action.triggered.connect(on_triggered)

        if self._dv_dropdown_rect is not None:
            pt = self.viewport().mapToGlobal(self._dv_dropdown_rect.bottomLeft())
            menu.exec(pt)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Right-click context menu dispatcher."""
        if self._swallow_secondary_button:
            self._swallow_secondary_button = False
            event.accept()
            return

        # If in-cell editor is active and cannot commit, don't open context menu
        if self.editor_controller is not None and self.editor_controller.is_active:
            if not self.editor_controller.commit():
                event.accept()
                return

        self.open_context_menu(
            global_pos=event.globalPos(),
            pos=event.pos(),
            reason=event.reason(),
        )

    def focusOutEvent(self, event: QFocusEvent) -> None:
        """Handle viewport focus loss by cancelling any in-progress drag."""
        if self._drag_mode != HitZone.NONE:
            self.cancel_drag(why="blur")
        super().focusOutEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Filter events on child viewport to capture focus loss during drags."""
        if watched == self.viewport() and event.type() == QEvent.Type.FocusOut:
            if self._drag_mode != HitZone.NONE:
                self.cancel_drag(why="blur")
        return super().eventFilter(watched, event)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Clean up drag resources, auto-scroll timers, and active state on widget close."""
        self.cancel_drag(why="close")
        super().closeEvent(event)

    def open_context_menu(
        self,
        global_pos: QPoint | None = None,
        pos: QPoint | None = None,
        reason: QContextMenuEvent.Reason = QContextMenuEvent.Reason.Mouse,
    ) -> None:
        """Open context menu according to hit target (object, header, cell) and reason."""
        # 1. Object menu if object selected
        if (
            self.object_layer is not None
            and getattr(self.object_layer, "selected_object", None) is not None
        ):
            menu = self._build_object_menu(self.object_layer.selected_object)
            if global_pos is None:
                global_pos = self.viewport().mapToGlobal(QPoint(100, 100))
            menu.exec(global_pos)
            return

        # 2. Keyboard trigger (Shift+F10)
        if reason == QContextMenuEvent.Reason.Keyboard or pos is None:
            ar, ac = self.selection.active_cell
            c_rect = self.cell_rect(ar, ac)
            global_pos = self.viewport().mapToGlobal(c_rect.center())
            hit = HitResult(HitZone.CELL, row=ar, col=ac)
        else:
            hit = self.hit_test(pos.x(), pos.y())

        # 3. Build appropriate menu based on hit target and selection
        pr = self.selection.primary_range
        is_whole_cols = (
            pr.min_r == 0 and pr.max_r == self.selection.max_rows - 1
        )
        is_whole_rows = (
            pr.min_c == 0 and pr.max_c == self.selection.max_cols - 1
        )

        if hit.zone == HitZone.COL_HEADER or (
            is_whole_cols
            and hit.zone != HitZone.ROW_HEADER
            and hit.zone != HitZone.CELL
        ):
            col = hit.col if hit.col is not None else pr.min_c
            menu = self._build_col_header_menu(col)
        elif hit.zone == HitZone.ROW_HEADER or is_whole_rows:
            row = hit.row if hit.row is not None else pr.min_r
            menu = self._build_row_header_menu(row)
        else:
            r = hit.row if hit.row is not None else pr.min_r
            c = hit.col if hit.col is not None else pr.min_c
            menu = self._build_cell_menu(r, c)

        if global_pos is None:
            local_p = pos if pos is not None else QPoint(0, 0)
            global_pos = self.viewport().mapToGlobal(local_p)

        menu.exec(global_pos)

    def _build_col_header_menu(self, col: int) -> QMenu:
        """Build Luna-styled context menu for column headers."""
        menu = QMenu(self)
        act_cut = menu.addAction(safe_tr("剪切(&T)"))
        act_cut.setShortcut("Ctrl+X")
        act_cut.triggered.connect(self.cut)

        act_copy = menu.addAction(safe_tr("复制(&C)"))
        act_copy.setShortcut("Ctrl+C")
        act_copy.triggered.connect(self.copy)

        act_paste = menu.addAction(safe_tr("粘贴(&P)"))
        act_paste.setShortcut("Ctrl+V")
        act_paste.triggered.connect(self.paste)

        act_ps = menu.addAction(safe_tr("选择性粘贴(&S)…"))
        act_ps.triggered.connect(self.paste_special)

        menu.addSeparator()

        act_ins = menu.addAction(safe_tr("插入(&I)"))
        act_ins.triggered.connect(self.insert_selected_cols)

        act_del = menu.addAction(safe_tr("删除(&D)"))
        act_del.triggered.connect(self.delete_selected_cols)

        act_clear = menu.addAction(safe_tr("清除内容(&N)"))
        act_clear.setShortcut("Del")
        act_clear.triggered.connect(self.clear_contents)

        menu.addSeparator()

        act_fmt = menu.addAction(safe_tr("设置单元格格式(&F)…"))
        act_fmt.setShortcut("Ctrl+1")
        act_fmt.triggered.connect(lambda: self.open_format_cells_dialog())

        act_cw = menu.addAction(safe_tr("列宽(&C)…"))
        act_cw.triggered.connect(self.set_col_width_dialog)

        act_autofit_col = menu.addAction(safe_tr("最适合的列宽(&A)"))
        act_autofit_col.triggered.connect(self.autofit_selected_cols)

        act_std_cw = menu.addAction(safe_tr("标准列宽(&S)…"))
        act_std_cw.triggered.connect(self.set_standard_col_width_dialog)

        act_hide = menu.addAction(safe_tr("隐藏(&H)"))
        act_hide.setShortcut("Ctrl+0")
        act_hide.triggered.connect(self.hide_selected_cols)

        act_unhide = menu.addAction(safe_tr("取消隐藏(&U)"))
        act_unhide.setShortcut("Ctrl+Shift+)")
        act_unhide.triggered.connect(self.unhide_selected_cols)

        return menu

    def _build_row_header_menu(self, row: int) -> QMenu:
        """Build Luna-styled context menu for row headers."""
        menu = QMenu(self)
        act_cut = menu.addAction(safe_tr("剪切(&T)"))
        act_cut.setShortcut("Ctrl+X")
        act_cut.triggered.connect(self.cut)

        act_copy = menu.addAction(safe_tr("复制(&C)"))
        act_copy.setShortcut("Ctrl+C")
        act_copy.triggered.connect(self.copy)

        act_paste = menu.addAction(safe_tr("粘贴(&P)"))
        act_paste.setShortcut("Ctrl+V")
        act_paste.triggered.connect(self.paste)

        act_ps = menu.addAction(safe_tr("选择性粘贴(&S)…"))
        act_ps.triggered.connect(self.paste_special)

        menu.addSeparator()

        act_ins = menu.addAction(safe_tr("插入(&I)"))
        act_ins.triggered.connect(self.insert_selected_rows)

        act_del = menu.addAction(safe_tr("删除(&D)"))
        act_del.triggered.connect(self.delete_selected_rows)

        act_clear = menu.addAction(safe_tr("清除内容(&N)"))
        act_clear.setShortcut("Del")
        act_clear.triggered.connect(self.clear_contents)

        menu.addSeparator()

        act_fmt = menu.addAction(safe_tr("设置单元格格式(&F)…"))
        act_fmt.setShortcut("Ctrl+1")
        act_fmt.triggered.connect(lambda: self.open_format_cells_dialog())

        act_rh = menu.addAction(safe_tr("行高(&R)…"))
        act_rh.triggered.connect(self.set_row_height_dialog)

        act_autofit_row = menu.addAction(safe_tr("最适合的行高(&A)"))
        act_autofit_row.triggered.connect(self.autofit_selected_rows)

        act_hide = menu.addAction(safe_tr("隐藏(&H)"))
        act_hide.setShortcut("Ctrl+9")
        act_hide.triggered.connect(self.hide_selected_rows)

        act_unhide = menu.addAction(safe_tr("取消隐藏(&U)"))
        act_unhide.setShortcut("Ctrl+Shift+(")
        act_unhide.triggered.connect(self.unhide_selected_rows)

        return menu

    def _build_cell_menu(self, r: int, c: int) -> QMenu:
        """Build Luna-styled context menu for worksheet cells."""
        menu = QMenu(self)
        act_cut = menu.addAction(safe_tr("剪切(&T)"))
        act_cut.setShortcut("Ctrl+X")
        act_cut.triggered.connect(self.cut)

        act_copy = menu.addAction(safe_tr("复制(&C)"))
        act_copy.setShortcut("Ctrl+C")
        act_copy.triggered.connect(self.copy)

        act_paste = menu.addAction(safe_tr("粘贴(&P)"))
        act_paste.setShortcut("Ctrl+V")
        act_paste.triggered.connect(self.paste)

        act_ps = menu.addAction(safe_tr("选择性粘贴(&S)…"))
        act_ps.triggered.connect(self.paste_special)

        menu.addSeparator()

        act_ins = menu.addAction(safe_tr("插入(&I)…"))
        act_ins.setShortcut("Ctrl+Shift++")
        act_ins.triggered.connect(self.insert_cells_dialog)

        act_del = menu.addAction(safe_tr("删除(&D)…"))
        act_del.setShortcut("Ctrl+-")
        act_del.triggered.connect(self.delete_cells_dialog)

        act_clear = menu.addAction(safe_tr("清除内容(&N)"))
        act_clear.setShortcut("Del")
        act_clear.triggered.connect(self.clear_contents)

        menu.addSeparator()

        # Comment actions
        cm = self.model.get_comment(r, c)
        if cm is not None:
            act_edit_cm = menu.addAction(safe_tr("编辑批注(&M)"))
            act_edit_cm.setShortcut("Shift+F2")
            act_edit_cm.triggered.connect(lambda: self.edit_comment(r, c))

            act_del_cm = menu.addAction(safe_tr("删除批注(&M)"))
            act_del_cm.triggered.connect(lambda: self.delete_comment(r, c))

            act_show_cm = menu.addAction(safe_tr("显示/隐藏批注(&O)"))
            act_show_cm.triggered.connect(lambda: self.toggle_comment_visibility(r, c))
        else:
            act_ins_cm = menu.addAction(safe_tr("插入批注(&M)"))
            act_ins_cm.setShortcut("Shift+F2")
            act_ins_cm.triggered.connect(lambda: self.insert_comment(r, c))

        menu.addSeparator()

        act_fmt = menu.addAction(safe_tr("设置单元格格式(&F)…"))
        act_fmt.setShortcut("Ctrl+1")
        act_fmt.triggered.connect(lambda: self.open_format_cells_dialog())

        act_pick = menu.addAction(safe_tr("从下拉列表中选择(&K)…"))
        act_pick.setShortcut("Alt+Down")
        act_pick.triggered.connect(self.pick_list)

        act_watch = menu.addAction(safe_tr("添加监视(&W)"))
        act_watch.triggered.connect(lambda: self.add_watch(r, c))

        menu.addSeparator()

        # Table / List conditional branch
        tbl = self.table_at(r, c)
        if tbl is not None:
            list_menu = menu.addMenu(safe_tr("列表(&L)"))
            act_tot = list_menu.addAction(safe_tr("汇总行(&T)"))
            act_tot.triggered.connect(lambda: self.toggle_total_row(tbl))
            act_conv = list_menu.addAction(safe_tr("转换为区域(&R)"))
            act_conv.triggered.connect(lambda: self.convert_table_to_range(tbl))
        else:
            act_create_list = menu.addAction(safe_tr("创建列表(&L)…"))
            act_create_list.setShortcut("Ctrl+L")
            act_create_list.triggered.connect(self.create_list)

        menu.addSeparator()

        # Hyperlink actions
        has_link = self._has_hyperlink(r, c)
        if has_link:
            act_edit_hl = menu.addAction(safe_tr("编辑超链接(&H)…"))
            act_edit_hl.triggered.connect(lambda: self.edit_hyperlink(r, c))

            act_open_hl = menu.addAction(safe_tr("打开超链接(&O)"))
            act_open_hl.triggered.connect(lambda: self.open_hyperlink(r, c))

            act_rem_hl = menu.addAction(safe_tr("删除超链接(&R)"))
            act_rem_hl.triggered.connect(lambda: self.remove_hyperlink(r, c))
        else:
            act_ins_hl = menu.addAction(safe_tr("超链接(&I)…"))
            act_ins_hl.setShortcut("Ctrl+K")
            act_ins_hl.triggered.connect(lambda: self.insert_hyperlink(r, c))

        return menu

    def _build_object_menu(self, obj: Any) -> QMenu:
        """Build context menu for floating objects (shapes, pictures, charts)."""
        menu = QMenu(self)
        act_cut = menu.addAction(safe_tr("剪切(&T)"))
        act_cut.triggered.connect(self.cut)

        act_copy = menu.addAction(safe_tr("复制(&C)"))
        act_copy.triggered.connect(self.copy)

        act_paste = menu.addAction(safe_tr("粘贴(&P)"))
        act_paste.triggered.connect(self.paste)

        act_del = menu.addAction(safe_tr("删除(&D)"))
        act_del.triggered.connect(self.clear_contents)

        menu.addSeparator()

        kind = getattr(obj, "kind", None)
        if kind == "chart":
            act_chart_type = menu.addAction(safe_tr("图表类型(&Y)…"))
            act_chart_type.triggered.connect(lambda: self.open_chart_type_dialog(obj))
            act_chart_opts = menu.addAction(safe_tr("图表选项(&O)…"))
            act_chart_opts.triggered.connect(lambda: self.open_chart_options_dialog(obj))
            menu.addSeparator()
        elif kind == "shape":
            act_edit_txt = menu.addAction(safe_tr("编辑文字(&X)"))
            act_edit_txt.triggered.connect(lambda: self.edit_object_text(obj))
            menu.addSeparator()

        order_menu = menu.addMenu(safe_tr("叠放次序(&R)"))
        if self.object_layer is not None:
            order_menu.addAction(
                safe_tr("置于顶层(&T)"),
                lambda: self.object_layer.bring_to_front(obj),
            )
            order_menu.addAction(
                safe_tr("置于底层(&K)"),
                lambda: self.object_layer.send_to_back(obj),
            )
            order_menu.addAction(
                safe_tr("上移一层(&F)"),
                lambda: self.object_layer.bring_forward(obj),
            )
            order_menu.addAction(
                safe_tr("下移一层(&B)"),
                lambda: self.object_layer.send_backward(obj),
            )

        menu.addSeparator()

        fmt_label = safe_tr("设置对象格式(&O)…")
        if kind == "image":
            fmt_label = safe_tr("设置图片格式(&O)…")
        elif kind == "chart":
            fmt_label = safe_tr("设置图表区域格式(&O)…")
        elif kind == "shape" and getattr(obj, "tx_box", False):
            fmt_label = safe_tr("设置文本框格式(&O)…")
        elif kind == "shape":
            fmt_label = safe_tr("设置自选图形格式(&O)…")

        act_fmt = menu.addAction(fmt_label)
        act_fmt.triggered.connect(lambda: self.open_format_object_dialog(obj))

        return menu

    # -------------------------------------------------------------------------
    # Context Menu Actions & Guard Protection
    # -------------------------------------------------------------------------
    def guard_protect(
        self, allow_key: str | None = None, cell_edit: bool = False
    ) -> bool:
        """Check worksheet protection and alert if mutation is restricted."""
        if getattr(self.model, "protected", False):
            QMessageBox.information(
                self,
                safe_tr("工作表受保护"),
                safe_tr(
                    "您试图更改的单元格位于受保护的工作表中。\n"
                    "若要修改受保护的单元格，请先撤消工作表保护。"
                ),
            )
            return True

        protection = getattr(self.model, "protection", None)
        if not protection or not protection.get("enabled", False):
            return False

        attrs = protection.get("attrs", {})
        if allow_key and attrs.get(allow_key) == "0":
            return False

        if cell_edit:
            locked = False
            for rg in self.selection.ranges:
                for r in range(rg.min_r, min(rg.max_r + 1, rg.min_r + 500)):
                    for c in range(rg.min_c, min(rg.max_c + 1, rg.min_c + 100)):
                        cell = self.model.get_cell(r, c)
                        if cell is None or getattr(cell, "locked", True):
                            locked = True
                            break
                    if locked:
                        break
            if not locked:
                return False

        QMessageBox.warning(
            self,
            safe_tr("工作表受保护"),
            safe_tr(
                "您试图更改的单元格或图表受保护，因而是只读的。\n\n"
                "若要修改受保护的单元格或图表，请先使用“撤消工作表保护”命令（在“工具”菜单的“保护”子菜单中）。"
            ),
        )
        return True

    def cut(self) -> None:
        """Cut selection to clipboard."""
        if self.guard_protect(cell_edit=True):
            return
        if (
            self.object_layer is not None
            and getattr(self.object_layer, "selected_object", None) is not None
        ):
            self.object_layer.copy_selected()
            self.object_layer.delete_selected()
            return

        self.copy()
        if self._internal_clipboard is not None:
            self._internal_clipboard["is_cut"] = True

    def copy(self) -> None:
        """Copy selection to clipboard using sparse boundaries."""
        if (
            self.object_layer is not None
            and getattr(self.object_layer, "selected_object", None) is not None
        ):
            self.object_layer.copy_selected()
            return

        pr = self.selection.primary_range
        # Calculate sparse bounds to prevent 10^6 iteration on whole column/row selection
        max_alloc_r = max(
            (r for (r, c) in self.model.cells.keys() if pr.min_c <= c <= pr.max_c),
            default=pr.min_r,
        )
        max_alloc_c = max(
            (c for (r, c) in self.model.cells.keys() if pr.min_r <= r <= pr.max_r),
            default=pr.min_c,
        )

        eff_max_r = min(pr.max_r, max(pr.min_r, max_alloc_r))
        eff_max_c = min(pr.max_c, max(pr.min_c, max_alloc_c))
        eff_range = SelectionRange(pr.min_r, pr.min_c, eff_max_r, eff_max_c)

        lines: list[str] = []
        for r in range(eff_range.min_r, eff_range.max_r + 1):
            row_vals: list[str] = []
            for c in range(eff_range.min_c, eff_range.max_c + 1):
                val = self.model.get_cell_value(r, c)
                row_vals.append("" if val is None else str(val))
            lines.append("\t".join(row_vals))
        tsv = "\n".join(lines)
        QApplication.clipboard().setText(tsv)

        col_widths = {
            c - pr.min_c: self.geometry_mapper.col_size(c)
            for c in range(eff_range.min_c, eff_range.max_c + 1)
        }

        self._internal_clipboard = {
            "range": pr,
            "effective_range": eff_range,
            "h": eff_range.max_r - eff_range.min_r + 1,
            "w": eff_range.max_c - eff_range.min_c + 1,
            "col_widths": col_widths,
            "cells": {
                (r - pr.min_r, c - pr.min_c): (
                    self.model.get_cell(r, c).clone()
                    if self.model.get_cell(r, c)
                    else None
                )
                for r in range(eff_range.min_r, eff_range.max_r + 1)
                for c in range(eff_range.min_c, eff_range.max_c + 1)
            },
            "is_cut": False,
        }

    def _snapshot_state(self) -> dict[str, Any]:
        """Capture cell, merge, comment, and selection snapshot for undo."""
        before_cells = {k: v.clone() for k, v in self.model.cells.items()}
        before_merges = list(self.model.merges)
        before_comments = (
            {k: CellComment(**v.__dict__) for k, v in self.model.comments.items()}
            if hasattr(self.model, "comments")
            else {}
        )
        before_sel = self.selection.snapshot()
        return {
            "before_cells": before_cells,
            "before_merges": before_merges,
            "before_comments": before_comments,
            "before_sel": before_sel,
        }

    def _commit_undo(self, before_state: dict[str, Any], action: str = "edit") -> None:
        """Record state transition in undo stack and flag document dirty."""
        after_cells = {k: v.clone() for k, v in self.model.cells.items()}
        after_merges = list(self.model.merges)
        after_comments = (
            {k: CellComment(**v.__dict__) for k, v in self.model.comments.items()}
            if hasattr(self.model, "comments")
            else {}
        )
        after_sel = self.selection.snapshot()
        entry = {
            **before_state,
            "after_cells": after_cells,
            "after_merges": after_merges,
            "after_comments": after_comments,
            "after_sel": after_sel,
            "action": action,
        }
        self._undo_stack.append(entry)
        self._redo_stack.clear()
        self.mark_dirty()
        self.viewport().update()

    def mark_dirty(self) -> None:
        """Mark workbook as modified."""
        win = self.window()
        if hasattr(win, "set_dirty"):
            win.set_dirty(True)
        elif hasattr(win, "set_modified"):
            win.set_modified(True)
        elif hasattr(self, "workbook") and self.workbook:
            self.workbook.dirty = True

    def table_at(self, r: int, c: int) -> Any | None:
        """Check if cell (r, c) is part of a list/table."""
        for t in getattr(self.model, "tables", []):
            if hasattr(t, "range"):
                r1, c1, r2, c2 = t.range
            elif isinstance(t, dict):
                r1, c1 = t.get("r1", 0), t.get("c1", 0)
                r2, c2 = t.get("r2", 0), t.get("c2", 0)
            else:
                continue
            if r1 <= r <= r2 and c1 <= c <= c2:
                return t

        af = getattr(self.model, "auto_filter", None)
        if af is not None:
            r1, c1 = getattr(af, "min_r", 0), getattr(af, "min_c", 0)
            r2, c2 = getattr(af, "max_r", 0), getattr(af, "max_c", 0)
            if r1 <= r <= r2 and c1 <= c <= c2:
                return af

        win = self.window()
        if getattr(win, "_total_row_active", False):
            total_r = getattr(win, "_total_row_r", None)
            c1, c2 = getattr(win, "_total_row_cols", (0, 0))
            if total_r is not None and r <= total_r and c1 <= c <= c2:
                return {"r1": 0, "c1": c1, "r2": total_r, "c2": c2}

        return None

    def create_list(self) -> None:
        """Create a list/table from current selection."""
        pr = self.selection.primary_range
        if not hasattr(self.model, "tables"):
            self.model.tables = []
        table_info = {
            "name": f"Table{len(self.model.tables) + 1}",
            "r1": pr.min_r,
            "c1": pr.min_c,
            "r2": pr.max_r,
            "c2": pr.max_c,
            "has_headers": True,
            "totalRow": False,
        }
        self.model.tables.append(table_info)
        self.toggle_auto_filter()
        self.mark_dirty()
        self.viewport().update()

    def toggle_total_row(self, target_table: dict | None = None) -> None:
        """Toggle total row on the active table/list."""
        win = self.window()
        if win is not self and hasattr(win, "toggle_total_row"):
            win.toggle_total_row()
        tbl = target_table or (self.table_at(*self.selection.active_cell) if hasattr(self, "table_at") else None)
        if tbl is not None:
            tbl["totalRow"] = not tbl.get("totalRow", False)
        self.mark_dirty()
        self.viewport().update()

    def convert_table_to_range(self, target_table: dict | None = None) -> None:
        """Convert list/table back to normal range."""
        win = self.window()
        if win is not self and hasattr(win, "convert_table_to_range"):
            win.convert_table_to_range()
        if hasattr(self.model, "tables"):
            if target_table is not None and target_table in self.model.tables:
                self.model.tables.remove(target_table)
            else:
                pr = self.selection.primary_range
                self.model.tables = [
                    t
                    for t in self.model.tables
                    if not (
                        t.get("r1", 0) <= pr.min_r
                        and t.get("r2", 0) >= pr.max_r
                        and t.get("c1", 0) <= pr.min_c
                        and t.get("c2", 0) >= pr.max_c
                    )
                ]
        self.mark_dirty()
        self.viewport().update()

    def open_chart_type_dialog(self, obj: Any) -> None:
        """Open chart type selector for chart object."""
        win = self.window()
        if win is not self and hasattr(win, "chart_wizard"):
            win.chart_wizard()
        else:
            from atboffice.modules.spreadsheet.dialogs.chart_wizard import (
                ChartWizardDialog,
            )

            dlg = ChartWizardDialog(parent=self)
            dlg.exec()

    def open_chart_options_dialog(self, obj: Any) -> None:
        """Open chart wizard / options for chart object."""
        self.open_chart_type_dialog(obj)

    def edit_object_text(self, obj: Any) -> None:
        """Begin editing text inside shape/textbox."""
        if self.object_layer is not None and hasattr(
            self.object_layer, "start_text_editing"
        ):
            self.object_layer.start_text_editing(obj)

    def paste(self) -> None:
        """Paste clipboard content to active cell with undo support."""
        if self.guard_protect(cell_edit=True):
            return
        if (
            self.object_layer is not None
            and getattr(self.object_layer, "selected_object", None) is not None
        ):
            self.object_layer.paste()
            return

        before_state = self._snapshot_state()
        ar, ac = self.selection.active_cell
        if self._internal_clipboard:
            cells_data = self._internal_clipboard.get("cells", {})
            is_cut = self._internal_clipboard.get("is_cut", False)
            src_range = self._internal_clipboard.get("range")
            for (dr, dc), cell_copy in cells_data.items():
                target_r, target_c = ar + dr, ac + dc
                if cell_copy is not None:
                    cloned = cell_copy.clone()
                    if cloned.formula and src_range is not None:
                        shift_r = target_r - (src_range.min_r + dr)
                        shift_c = target_c - (src_range.min_c + dc)
                        cloned.formula = translate(cloned.formula, shift_r, shift_c)
                    self.model.set_cell(target_r, target_c, cloned)
                else:
                    self.model.set_cell(target_r, target_c, CellData())
            if is_cut and src_range:
                for r in range(src_range.min_r, src_range.max_r + 1):
                    for c in range(src_range.min_c, src_range.max_c + 1):
                        tr = ar + (r - src_range.min_r)
                        tc = ac + (c - src_range.min_c)
                        if not (
                            src_range.min_r <= tr <= src_range.max_r
                            and src_range.min_c <= tc <= src_range.max_c
                        ):
                            self.model.set_cell(r, c, CellData())
                self._internal_clipboard = None
        else:
            text = QApplication.clipboard().text()
            if text:
                rows = text.splitlines()
                for dr, row_str in enumerate(rows):
                    cols = row_str.split("\t")
                    for dc, cell_str in enumerate(cols):
                        val: Any = cell_str
                        try:
                            if "." in cell_str:
                                val = float(cell_str)
                            else:
                                val = int(cell_str)
                        except ValueError:
                            pass
                        self.model.set_cell_value(ar + dr, ac + dc, val)
        self._commit_undo(before_state, action="paste")

    def paste_special(self, options: dict[str, Any] | None = None) -> None:
        """Paste values / special options from clipboard with real business transformations."""
        if self.guard_protect(cell_edit=True):
            return

        if options is None:
            from atboffice.modules.spreadsheet.dialogs.paste_special_dialog import (
                PasteSpecialDialog,
            )

            dlg = PasteSpecialDialog(self)
            if not dlg.exec():
                return
            options = dlg.options

        # Ensure internal clipboard or fallback to parsed clipboard text
        if not self._internal_clipboard:
            text = QApplication.clipboard().text()
            if not text:
                return
            rows = text.splitlines()
            cells = {}
            for dr, row_str in enumerate(rows):
                for dc, cell_str in enumerate(row_str.split("\t")):
                    val: Any = cell_str
                    try:
                        if "." in cell_str:
                            val = float(cell_str)
                        else:
                            val = int(cell_str)
                    except ValueError:
                        pass
                    cells[(dr, dc)] = CellData(value=val)
            h = len(rows)
            w = max((len(r.split("\t")) for r in rows), default=1)
            self._internal_clipboard = {
                "range": SelectionRange(0, 0, h - 1, w - 1),
                "effective_range": SelectionRange(0, 0, h - 1, w - 1),
                "h": h,
                "w": w,
                "col_widths": {},
                "cells": cells,
                "is_cut": False,
            }

        before_state = self._snapshot_state()

        src_h = self._internal_clipboard.get("h", 1)
        src_w = self._internal_clipboard.get("w", 1)
        src_cells = self._internal_clipboard.get("cells", {})
        src_range = self._internal_clipboard.get("range", SelectionRange(0, 0, 0, 0))
        col_widths = self._internal_clipboard.get("col_widths", {})

        transpose = bool(options.get("transpose", False))
        skip_blanks = bool(options.get("skip_blanks", False))
        what = options.get("what") or options.get("type") or "all"
        op = options.get("op") or options.get("operation") or "none"
        is_link = bool(
            options.get("link", False)
            or options.get("type") == "paste_link"
            or options.get("what") == "paste_link"
        )

        dest_h = src_w if transpose else src_h
        dest_w = src_h if transpose else src_w
        ar, ac = self.selection.active_cell

        # Special case: Column widths only
        if what == "colWidths":
            for j in range(dest_w):
                src_j = j if not transpose else 0
                width = col_widths.get(src_j)
                if width is not None:
                    self.geometry_mapper.set_col_width(ac + j, width)
                    self.model.geometry.set_col_width(ac + j, width)
            self._commit_undo(before_state, action="paste_special")
            return

        take_val = what in ("all", "values", "valuesNF")
        take_formula = what in ("all", "formulas", "noBorders", "formulasNF")
        take_format = what in ("all", "formats", "noBorders")
        take_nf = what in ("formulasNF", "valuesNF")

        for dr in range(dest_h):
            for dc in range(dest_w):
                si, sj = (dc, dr) if transpose else (dr, dc)
                src_cell = src_cells.get((si, sj))
                target_r = ar + dr
                target_c = ac + dc

                if skip_blanks and (
                    src_cell is None
                    or (
                        (src_cell.value is None or src_cell.value == "")
                        and not src_cell.formula
                    )
                ):
                    continue

                curr_cell = self.model.get_cell(target_r, target_c)
                new_cell = curr_cell.clone() if curr_cell else CellData()

                if is_link:
                    src_abs_r = src_range.min_r + si
                    src_abs_c = src_range.min_c + sj
                    sheet_name = getattr(self.model, "name", "")
                    sheet_ref = f"{sheet_name}!" if sheet_name else ""
                    new_cell.formula = f"={sheet_ref}{cell_name(src_abs_r, src_abs_c, False, False)}"
                    new_cell.value = None
                    self.model.set_cell(target_r, target_c, new_cell)
                    continue

                if what == "comments":
                    src_abs_r = src_range.min_r + si
                    src_abs_c = src_range.min_c + sj
                    cm = self.model.get_comment(src_abs_r, src_abs_c)
                    if cm:
                        self.model.set_comment(
                            target_r, target_c, cm.text, cm.author, cm.visible
                        )
                    continue

                if what == "validation":
                    src_abs_r = src_range.min_r + si
                    src_abs_c = src_range.min_c + sj
                    dv = self.model.get_validation_at(src_abs_r, src_abs_c)
                    if dv and hasattr(self.model, "add_data_validation"):
                        self.model.add_data_validation(dv)
                    continue

                if take_val or take_formula:
                    src_v = src_cell.value if src_cell else None
                    src_f = src_cell.formula if (src_cell and take_formula) else None

                    if src_f is not None:
                        shift_r = target_r - (src_range.min_r + si)
                        shift_c = target_c - (src_range.min_c + sj)
                        src_f = translate(src_f, shift_r, shift_c)

                    if op and op != "none":
                        cur_v = curr_cell.value if curr_cell else None
                        base_num = cur_v if isinstance(cur_v, (int, float)) else 0
                        val_num = src_v if isinstance(src_v, (int, float)) else 0
                        if op == "add":
                            src_v = base_num + val_num
                        elif op in ("sub", "subtract"):
                            src_v = base_num - val_num
                        elif op in ("mul", "multiply"):
                            src_v = base_num * val_num
                        elif op in ("div", "divide"):
                            src_v = "#DIV/0!" if val_num == 0 else base_num / val_num
                        src_f = None

                    new_cell.value = src_v
                    new_cell.formula = src_f

                if take_format and src_cell is not None:
                    new_cell.font_family = src_cell.font_family
                    new_cell.font_size = src_cell.font_size
                    new_cell.bold = src_cell.bold
                    new_cell.italic = src_cell.italic
                    new_cell.underline = src_cell.underline
                    new_cell.fg_color = src_cell.fg_color
                    new_cell.bg_color = src_cell.bg_color
                    new_cell.align_h = src_cell.align_h
                    new_cell.align_v = src_cell.align_v
                    new_cell.format_code = src_cell.format_code
                    if what != "noBorders":
                        new_cell.border_top = src_cell.border_top
                        new_cell.border_bottom = src_cell.border_bottom
                        new_cell.border_left = src_cell.border_left
                        new_cell.border_right = src_cell.border_right

                if take_nf and src_cell is not None:
                    new_cell.format_code = src_cell.format_code

                self.model.set_cell(target_r, target_c, new_cell)

        self._commit_undo(before_state, action="paste_special")

    def clear_contents(self) -> None:
        """Clear values and formulas in the current selection with sparse optimization."""
        if self.guard_protect(cell_edit=True):
            return
        if (
            self.object_layer is not None
            and getattr(self.object_layer, "selected_object", None) is not None
        ):
            self.object_layer.delete_selected()
            return

        before_state = self._snapshot_state()

        for rg in self.selection.ranges:
            total_cells = (rg.max_r - rg.min_r + 1) * (rg.max_c - rg.min_c + 1)
            if total_cells > len(self.model.cells):
                for (r, c), cell in list(self.model.cells.items()):
                    if rg.contains(r, c):
                        cell.value = None
                        cell.formula = None
            else:
                for r in range(rg.min_r, rg.max_r + 1):
                    for c in range(rg.min_c, rg.max_c + 1):
                        cell = self.model.get_cell(r, c)
                        if cell is not None:
                            cell.value = None
                            cell.formula = None

        self._commit_undo(before_state, action="clear_contents")

    def _holds_data(
        self,
        to_range: SelectionRange,
        except_range: SelectionRange | None = None,
    ) -> bool:
        """Check if any cell in to_range outside except_range holds a value or formula."""
        for r in range(to_range.min_r, to_range.max_r + 1):
            for c in range(to_range.min_c, to_range.max_c + 1):
                if except_range is not None and except_range.contains(r, c):
                    continue
                cell = self.model.get_cell(r, c)
                if cell is not None and (cell.value is not None or cell.formula is not None):
                    return True
        return False

    def move_to_edge(self, dr: int, dc: int) -> None:
        """Jump selection to data region boundary in direction (dr, dc).

        Matches Excel/VibeOffice double-click parity.
        """
        r, c = self.selection.active_cell
        max_r = self.geometry_mapper.max_rows - 1
        max_c = self.geometry_mapper.max_cols - 1

        curr_cell = self.model.get_cell(r, c)
        curr_has_data = curr_cell is not None and (
            curr_cell.value is not None or curr_cell.formula is not None
        )

        nr, nc = r, c
        while 0 <= nr + dr <= max_r and 0 <= nc + dc <= max_c:
            nxt = self.model.get_cell(nr + dr, nc + dc)
            nxt_has_data = nxt is not None and (
                nxt.value is not None or nxt.formula is not None
            )
            if curr_has_data and not nxt_has_data:
                break
            if not curr_has_data and nxt_has_data:
                nr += dr
                nc += dc
                break
            nr += dr
            nc += dc

        self.selection.select_cell(nr, nc)
        self.reveal(nr, nc)
        self.cell_selected.emit(nr, nc)
        self.viewport().update()

    def move_range(
        self,
        src: SelectionRange,
        to: SelectionRange,
        copy: bool = False,
    ) -> bool:
        """Move or copy cell range src to to.

        Handles formulas, merges, comments, confirmation, and undo.
        """
        if self.guard_protect(cell_edit=True):
            return False

        if (
            src.min_r == to.min_r
            and src.min_c == to.min_c
            and src.max_r == to.max_r
            and src.max_c == to.max_c
        ):
            return True

        # Overwrite confirmation check
        except_rg = None if copy else src
        if self._holds_data(to, except_rg):
            ret = QMessageBox.question(
                self,
                safe_tr("ATBOffice Ledger"),
                safe_tr("是否替换目标单元格内容？"),
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if ret != QMessageBox.StandardButton.Ok:
                return False

        # Snapshot state for undo/redo
        before_cells = {k: v.clone() for k, v in self.model.cells.items()}
        before_merges = list(self.model.merges)
        before_comments = (
            {k: CellComment(**v.__dict__) for k, v in self.model.comments.items()}
            if hasattr(self.model, "comments")
            else {}
        )
        before_sel = self.selection.snapshot()

        dr = to.min_r - src.min_r
        dc = to.min_c - src.min_c

        # Snapshot source cells
        src_cells: dict[tuple[int, int], CellData | None] = {}
        for r in range(src.min_r, src.max_r + 1):
            for c in range(src.min_c, src.max_c + 1):
                cl = self.model.get_cell(r, c)
                src_cells[(r - src.min_r, c - src.min_c)] = cl.clone() if cl else None

        # Snapshot source merges
        src_merges: list[tuple[int, int, int, int]] = [
            (
                m[0] - src.min_r,
                m[1] - src.min_c,
                m[2] - src.min_r,
                m[3] - src.min_c,
            )
            for m in self.model.merges
            if (
                m[0] >= src.min_r
                and m[2] <= src.max_r
                and m[1] >= src.min_c
                and m[3] <= src.max_c
            )
        ]

        # Snapshot source comments
        src_comments: dict[tuple[int, int], Any] = {}
        if hasattr(self.model, "comments"):
            for (r, c), cm in self.model.comments.items():
                if src.min_r <= r <= src.max_r and src.min_c <= c <= src.max_c:
                    src_comments[(r - src.min_r, c - src.min_c)] = cm

        if copy:
            # Remove merges overlapping destination
            self.model.merges = [
                m
                for m in self.model.merges
                if not (
                    max(m[0], to.min_r) <= min(m[2], to.max_r)
                    and max(m[1], to.min_c) <= min(m[3], to.max_c)
                )
            ]
            # Write cells to destination with translated formulas
            for (dr_i, dc_j), cell in src_cells.items():
                tr = to.min_r + dr_i
                tc = to.min_c + dc_j
                if cell is not None:
                    new_cell = cell.clone()
                    if new_cell.formula:
                        new_cell.formula = translate(new_cell.formula, dr, dc)
                    self.model.set_cell(tr, tc, new_cell)
                else:
                    self.model.set_cell(tr, tc, CellData())
            # Replicate merges
            for sm in src_merges:
                self.model.merges.append(
                    (
                        to.min_r + sm[0],
                        to.min_c + sm[1],
                        to.min_r + sm[2],
                        to.min_c + sm[3],
                    )
                )
            # Replicate comments
            if hasattr(self.model, "set_comment"):
                for (dr_i, dc_j), cm in src_comments.items():
                    self.model.set_comment(
                        to.min_r + dr_i,
                        to.min_c + dc_j,
                        text=cm.text,
                        author=cm.author,
                        visible=cm.visible,
                    )

        else:
            # Move
            sheet_name = getattr(self.model, "sheet_name", "Sheet1")
            src_dict = {
                "r1": src.min_r,
                "c1": src.min_c,
                "r2": src.max_r,
                "c2": src.max_c,
                "sheet": sheet_name,
            }

            # Update external formulas pointing to moved source or overwritten destination
            for (r, c), cell in list(self.model.cells.items()):
                if src.min_r <= r <= src.max_r and src.min_c <= c <= src.max_c:
                    continue
                if cell and cell.formula:
                    try:
                        ast = parse(cell.formula)
                        # Check if formula references overwritten cells in destination
                        def mapper_dest(n):
                            if isinstance(n, CellRefNode):
                                if (
                                    to.min_r <= n.r <= to.max_r
                                    and to.min_c <= n.c <= to.max_c
                                    and not (
                                        src.min_r <= n.r <= src.max_r
                                        and src.min_c <= n.c <= src.max_c
                                    )
                                ):
                                    return ref_err(n)
                            return None

                        ast_dest = map_ast(ast, mapper_dest)
                        if ast_dest is not None:
                            ast = ast_dest

                        new_ast, ch = adjust_move(
                            ast, src_dict, dr, dc, home=sheet_name, to_sheet=sheet_name
                        )
                        pref = "=" if cell.formula.startswith("=") else ""
                        cell.formula = pref + to_text(new_ast)
                    except Exception:
                        pass

            # Clear source cells that do not overlap destination
            for r in range(src.min_r, src.max_r + 1):
                for c in range(src.min_c, src.max_c + 1):
                    if not (to.min_r <= r <= to.max_r and to.min_c <= c <= to.max_c):
                        self.model.set_cell(r, c, CellData())

            # Write moved cells to destination
            for (dr_i, dc_j), cell in src_cells.items():
                tr = to.min_r + dr_i
                tc = to.min_c + dc_j
                if cell is not None:
                    new_cell = cell.clone()
                    if new_cell.formula:
                        try:
                            ast = parse(new_cell.formula)
                            new_ast, ch = adjust_move(
                                ast, src_dict, dr, dc, home=sheet_name, to_sheet=sheet_name
                            )
                            pref = "=" if new_cell.formula.startswith("=") else ""
                            new_cell.formula = pref + to_text(new_ast)
                        except Exception:
                            pass
                    self.model.set_cell(tr, tc, new_cell)
                else:
                    self.model.set_cell(tr, tc, CellData())

            # Remove source merges and destination overwritten merges
            self.model.merges = [
                m
                for m in self.model.merges
                if not (
                    (
                        m[0] >= src.min_r
                        and m[2] <= src.max_r
                        and m[1] >= src.min_c
                        and m[3] <= src.max_c
                    )
                    or (
                        max(m[0], to.min_r) <= min(m[2], to.max_r)
                        and max(m[1], to.min_c) <= min(m[3], to.max_c)
                    )
                )
            ]
            for sm in src_merges:
                self.model.merges.append(
                    (
                        to.min_r + sm[0],
                        to.min_c + sm[1],
                        to.min_r + sm[2],
                        to.min_c + sm[3],
                    )
                )

            # Move comments
            if hasattr(self.model, "comments"):
                for r in range(src.min_r, src.max_r + 1):
                    for c in range(src.min_c, src.max_c + 1):
                        if (r, c) in self.model.comments:
                            del self.model.comments[(r, c)]
                for (dr_i, dc_j), cm in src_comments.items():
                    self.model.set_comment(
                        to.min_r + dr_i,
                        to.min_c + dc_j,
                        text=cm.text,
                        author=cm.author,
                        visible=cm.visible,
                    )

        # Update selection
        self.selection.select_cell(to.min_r, to.min_c)
        self.selection.extend_to(to.max_r, to.max_c)

        # Record in undo stack
        after_cells = {k: v.clone() for k, v in self.model.cells.items()}
        after_merges = list(self.model.merges)
        after_comments = (
            {k: CellComment(**v.__dict__) for k, v in self.model.comments.items()}
            if hasattr(self.model, "comments")
            else {}
        )
        after_sel = self.selection.snapshot()

        self._undo_stack.append(
            {
                "before_cells": before_cells,
                "before_merges": before_merges,
                "before_comments": before_comments,
                "before_sel": before_sel,
                "after_cells": after_cells,
                "after_merges": after_merges,
                "after_comments": after_comments,
                "after_sel": after_sel,
            }
        )
        self._redo_stack.clear()
        self.viewport().update()
        return True

    def undo(self) -> None:
        """Undo the last spreadsheet edit operation."""
        if not self._undo_stack:
            return
        cmd = self._undo_stack.pop()
        self._redo_stack.append(cmd)
        action = cmd.get("action")
        if action == "col_resize":
            for c, sz in cmd["before_sizes"].items():
                self.geometry_mapper.set_col_width(c, sz)
            self._update_scrollbars()
            self.viewport().update()
            return
        if action == "row_resize":
            for r, sz in cmd["before_sizes"].items():
                self.geometry_mapper.set_row_height(r, sz)
            self._update_scrollbars()
            self.viewport().update()
            return

        self.model.cells = {k: v.clone() for k, v in cmd["before_cells"].items()}
        self.model.merges = list(cmd["before_merges"])
        if hasattr(self.model, "links") and "before_links" in cmd:
            self.model.links = [
                dict(lk) if isinstance(lk, dict) else lk for lk in cmd["before_links"]
            ]
        if hasattr(self.model, "comments") and "before_comments" in cmd:
            self.model.comments = {
                k: CellComment(**v.__dict__) for k, v in cmd["before_comments"].items()
            }
        if action == "total_row":
            win = self.window()
            if hasattr(win, "_total_row_active"):
                win._total_row_active = not cmd.get("active", True)
                if hasattr(win, "action_registry"):
                    win.action_registry.set_checked("totalRow", win._total_row_active)
        self.selection.restore_snapshot(cmd["before_sel"])
        self.viewport().update()

    def redo(self) -> None:
        """Redo the last undone spreadsheet edit operation."""
        if not self._redo_stack:
            return
        cmd = self._redo_stack.pop()
        self._undo_stack.append(cmd)
        action = cmd.get("action")
        if action == "col_resize":
            for c, sz in cmd["after_sizes"].items():
                self.geometry_mapper.set_col_width(c, sz)
            self._update_scrollbars()
            self.viewport().update()
            return
        if action == "row_resize":
            for r, sz in cmd["after_sizes"].items():
                self.geometry_mapper.set_row_height(r, sz)
            self._update_scrollbars()
            self.viewport().update()
            return

        self.model.cells = {k: v.clone() for k, v in cmd["after_cells"].items()}
        self.model.merges = list(cmd["after_merges"])
        if hasattr(self.model, "links") and "after_links" in cmd:
            self.model.links = [
                dict(lk) if isinstance(lk, dict) else lk for lk in cmd["after_links"]
            ]
        if hasattr(self.model, "comments") and "after_comments" in cmd:
            self.model.comments = {
                k: CellComment(**v.__dict__) for k, v in cmd["after_comments"].items()
            }
        if action == "total_row":
            win = self.window()
            if hasattr(win, "_total_row_active"):
                win._total_row_active = cmd.get("active", True)
                if hasattr(win, "action_registry"):
                    win.action_registry.set_checked("totalRow", win._total_row_active)
        self.selection.restore_snapshot(cmd["after_sel"])
        self.viewport().update()

    def insert_selected_cols(self) -> None:
        """Insert columns to the left of the current selection."""
        if self.guard_protect("insertColumns"):
            return
        pr = self.selection.primary_range
        c1, c2 = pr.min_c, pr.max_c
        count = c2 - c1 + 1
        new_cells: dict[tuple[int, int], CellData] = {}
        for (r, c), cell in self.model.cells.items():
            if c >= c1:
                new_cells[(r, c + count)] = cell
            else:
                new_cells[(r, c)] = cell
        self.model.cells = new_cells
        new_merges: list[tuple[int, int, int, int]] = []
        for mr1, mc1, mr2, mc2 in self.model.merges:
            if mc1 >= c1:
                new_merges.append((mr1, mc1 + count, mr2, mc2 + count))
            elif mc2 >= c1:
                new_merges.append((mr1, mc1, mr2, mc2 + count))
            else:
                new_merges.append((mr1, mc1, mr2, mc2))
        self.model.merges = new_merges
        self.viewport().update()

    def delete_selected_cols(self) -> None:
        """Delete columns in the current selection."""
        if self.guard_protect("deleteColumns"):
            return
        pr = self.selection.primary_range
        c1, c2 = pr.min_c, pr.max_c
        count = c2 - c1 + 1
        new_cells: dict[tuple[int, int], CellData] = {}
        for (r, c), cell in self.model.cells.items():
            if c1 <= c <= c2:
                continue
            elif c > c2:
                new_cells[(r, c - count)] = cell
            else:
                new_cells[(r, c)] = cell
        self.model.cells = new_cells
        new_merges: list[tuple[int, int, int, int]] = []
        for mr1, mc1, mr2, mc2 in self.model.merges:
            if mc1 > c2:
                new_merges.append((mr1, mc1 - count, mr2, mc2 - count))
            elif mc2 < c1:
                new_merges.append((mr1, mc1, mr2, mc2))
        self.model.merges = new_merges
        self.viewport().update()

    def insert_selected_rows(self) -> None:
        """Insert rows above the current selection."""
        if self.guard_protect("insertRows"):
            return
        pr = self.selection.primary_range
        r1, r2 = pr.min_r, pr.max_r
        count = r2 - r1 + 1
        new_cells: dict[tuple[int, int], CellData] = {}
        for (r, c), cell in self.model.cells.items():
            if r >= r1:
                new_cells[(r + count, c)] = cell
            else:
                new_cells[(r, c)] = cell
        self.model.cells = new_cells
        new_merges: list[tuple[int, int, int, int]] = []
        for mr1, mc1, mr2, mc2 in self.model.merges:
            if mr1 >= r1:
                new_merges.append((mr1 + count, mc1, mr2 + count, mc2))
            elif mr2 >= r1:
                new_merges.append((mr1, mc1, mr2 + count, mc2))
            else:
                new_merges.append((mr1, mc1, mr2, mc2))
        self.model.merges = new_merges
        self.viewport().update()

    def delete_selected_rows(self) -> None:
        """Delete rows in the current selection."""
        if self.guard_protect("deleteRows"):
            return
        pr = self.selection.primary_range
        r1, r2 = pr.min_r, pr.max_r
        count = r2 - r1 + 1
        new_cells: dict[tuple[int, int], CellData] = {}
        for (r, c), cell in self.model.cells.items():
            if r1 <= r <= r2:
                continue
            elif r > r2:
                new_cells[(r - count, c)] = cell
            else:
                new_cells[(r, c)] = cell
        self.model.cells = new_cells
        new_merges: list[tuple[int, int, int, int]] = []
        for mr1, mc1, mr2, mc2 in self.model.merges:
            if mr1 > r2:
                new_merges.append((mr1 - count, mc1, mr2 - count, mc2))
            elif mr2 < r1:
                new_merges.append((mr1, mc1, mr2, mc2))
        self.model.merges = new_merges
        self.viewport().update()

    def set_col_width_dialog(self) -> None:
        """Show dialog to set column width for selected columns."""
        if self.guard_protect("formatColumns"):
            return
        pr = self.selection.primary_range
        curr = self.geometry_mapper.col_size(pr.min_c)
        val, ok = QInputDialog.getInt(
            self,
            safe_tr("列宽"),
            safe_tr("列宽(&C):"),
            curr,
            0,
            1000,
        )
        if ok:
            for c in range(pr.min_c, pr.max_c + 1):
                self.geometry_mapper.set_col_width(c, val)
            self._update_scrollbars()
            self.viewport().update()

    def set_row_height_dialog(self) -> None:
        """Show dialog to set row height for selected rows."""
        if self.guard_protect("formatRows"):
            return
        pr = self.selection.primary_range
        curr = self.geometry_mapper.row_size(pr.min_r)
        val, ok = QInputDialog.getInt(
            self,
            safe_tr("行高"),
            safe_tr("行高(&R):"),
            curr,
            0,
            409,
        )
        if ok:
            for r in range(pr.min_r, pr.max_r + 1):
                self.geometry_mapper.set_row_height(r, val)
            self._update_scrollbars()
            self.viewport().update()

    def autofit_selected_rows(self) -> None:
        """Autofit row heights for selected rows based on cell contents."""
        if self.guard_protect("formatRows"):
            return
        pr = self.selection.primary_range
        fm = QFontMetrics(self.font())
        default_h = 20
        for r in range(pr.min_r, pr.max_r + 1):
            max_h = default_h
            for c in range(min(100, self.selection.max_cols)):
                cell = self.model.get_cell(r, c)
                if cell is not None and cell.value is not None and str(cell.value) != "":
                    lines = str(cell.value).split("\n")
                    needed_h = max(default_h, len(lines) * (fm.height() + 4) + 4)
                    if needed_h > max_h:
                        max_h = min(needed_h, 409)
            self.geometry_mapper.set_row_height(r, max_h)
        self._update_scrollbars()
        self.viewport().update()

    def autofit_selected_cols(self) -> None:
        """Autofit column widths for selected columns based on cell contents."""
        if self.guard_protect("formatColumns"):
            return
        pr = self.selection.primary_range
        fm = QFontMetrics(self.font())
        min_w = 40
        for c in range(pr.min_c, pr.max_c + 1):
            max_w = min_w
            for r in range(min(500, self.selection.max_rows)):
                cell = self.model.get_cell(r, c)
                if cell is not None and cell.value is not None and str(cell.value) != "":
                    val_str = str(getattr(cell, "formatted_value", None) or cell.value)
                    w = fm.horizontalAdvance(val_str) + 16
                    if w > max_w:
                        max_w = min(w, 500)
            self.geometry_mapper.set_col_width(c, max_w)
        self._update_scrollbars()
        self.viewport().update()

    def set_standard_col_width_dialog(self) -> None:
        """Show dialog to set standard column width."""
        if self.guard_protect("formatColumns"):
            return
        curr = 72
        val, ok = QInputDialog.getInt(
            self,
            safe_tr("标准列宽"),
            safe_tr("标准列宽(&S):"),
            curr,
            0,
            1000,
        )
        if ok:
            pr = self.selection.primary_range
            for c in range(pr.min_c, pr.max_c + 1):
                self.geometry_mapper.set_col_width(c, val)
            self._update_scrollbars()
            self.viewport().update()

    def hide_selected_cols(self) -> None:
        """Hide columns in current selection."""
        if self.guard_protect("formatColumns"):
            return
        pr = self.selection.primary_range
        for c in range(pr.min_c, pr.max_c + 1):
            self.geometry_mapper.hidden_cols.add(c)
        self._update_scrollbars()
        self.viewport().update()

    def unhide_selected_cols(self) -> None:
        """Unhide columns in and around current selection."""
        if self.guard_protect("formatColumns"):
            return
        pr = self.selection.primary_range
        start = max(0, pr.min_c - 1)
        end = min(self.selection.max_cols - 1, pr.max_c + 1)
        for c in range(start, end + 1):
            self.geometry_mapper.hidden_cols.discard(c)
        self._update_scrollbars()
        self.viewport().update()

    def hide_selected_rows(self) -> None:
        """Hide rows in current selection."""
        if self.guard_protect("formatRows"):
            return
        pr = self.selection.primary_range
        for r in range(pr.min_r, pr.max_r + 1):
            self.geometry_mapper.hidden_rows.add(r)
        self._update_scrollbars()
        self.viewport().update()

    def unhide_selected_rows(self) -> None:
        """Unhide rows in and around current selection."""
        if self.guard_protect("formatRows"):
            return
        pr = self.selection.primary_range
        start = max(0, pr.min_r - 1)
        end = min(self.selection.max_rows - 1, pr.max_r + 1)
        for r in range(start, end + 1):
            self.geometry_mapper.hidden_rows.discard(r)
        self._update_scrollbars()
        self.viewport().update()

    def insert_cells_dialog(self) -> None:
        """Insert cells shifting down in current column span."""
        if self.guard_protect("insertRows"):
            return
        pr = self.selection.primary_range
        count = pr.max_r - pr.min_r + 1
        new_cells: dict[tuple[int, int], CellData] = {}
        for (r, c), cell in self.model.cells.items():
            if pr.min_c <= c <= pr.max_c and r >= pr.min_r:
                new_cells[(r + count, c)] = cell
            else:
                new_cells[(r, c)] = cell
        self.model.cells = new_cells
        self.viewport().update()

    def delete_cells_dialog(self) -> None:
        """Delete cells shifting up in current column span."""
        if self.guard_protect("deleteRows"):
            return
        pr = self.selection.primary_range
        count = pr.max_r - pr.min_r + 1
        new_cells: dict[tuple[int, int], CellData] = {}
        for (r, c), cell in self.model.cells.items():
            if pr.min_c <= c <= pr.max_c:
                if pr.min_r <= r <= pr.max_r:
                    continue
                elif r > pr.max_r:
                    new_cells[(r - count, c)] = cell
                else:
                    new_cells[(r, c)] = cell
            else:
                new_cells[(r, c)] = cell
        self.model.cells = new_cells
        self.viewport().update()

    def insert_comment(self, r: int, c: int) -> None:
        """Insert a comment on cell (r, c)."""
        if self.guard_protect(cell_edit=True):
            return
        text, ok = QInputDialog.getMultiLineText(
            self, safe_tr("插入批注"), safe_tr("批注内容:"), ""
        )
        if ok and text:
            self.model.set_comment(r, c, text, visible=True)
            self.viewport().update()

    def edit_comment(self, r: int, c: int) -> None:
        """Edit existing comment on cell (r, c)."""
        if self.guard_protect(cell_edit=True):
            return
        cm = self.model.get_comment(r, c)
        curr = cm.text if cm else ""
        text, ok = QInputDialog.getMultiLineText(
            self, safe_tr("编辑批注"), safe_tr("批注内容:"), curr
        )
        if ok:
            self.model.set_comment(r, c, text, visible=True)
            self.viewport().update()

    def delete_comment(self, r: int, c: int) -> None:
        """Delete comment on cell (r, c)."""
        if self.guard_protect(cell_edit=True):
            return
        self.model.delete_comment(r, c)
        self.viewport().update()

    def toggle_comment_visibility(self, r: int, c: int) -> None:
        """Toggle comment visibility on cell (r, c)."""
        cm = self.model.get_comment(r, c)
        if cm:
            cm.visible = not cm.visible
            self.viewport().update()

    def pick_list(self) -> None:
        """Show dropdown validation or distinct column items for active cell."""
        if self._dv_dropdown_rect is not None:
            self._open_dv_dropdown()
            return

        ar, ac = self.selection.active_cell
        distinct_vals: list[str] = []
        seen: set[str] = set()
        for r in range(max(0, ar - 100), min(self.selection.max_rows, ar + 100)):
            if r == ar:
                continue
            v = self.model.get_cell_value(r, ac)
            if v is not None and str(v).strip() and str(v) not in seen:
                seen.add(str(v))
                distinct_vals.append(str(v))
        distinct_vals.sort()
        if distinct_vals:
            menu = QMenu(self)
            for item in distinct_vals:
                def on_sel(val=item) -> None:
                    self.model.set_cell_value(ar, ac, val)
                    self.viewport().update()

                menu.addAction(item, on_sel)
            rect = self.cell_rect(ar, ac)
            menu.exec(self.viewport().mapToGlobal(rect.bottomLeft()))

    def add_watch(self, r: int, c: int) -> None:
        """Add cell to Watch Window dialog."""
        win = self.window()
        if hasattr(win, "show_watch_window"):
            win.show_watch_window(True)

    def _has_hyperlink(self, r: int, c: int) -> bool:
        """Check whether cell (r, c) contains a hyperlink."""
        links = getattr(self.model, "links", [])
        from atboffice.modules.spreadsheet.calc.references import cell_name

        cname = cell_name(r, c)
        for link_item in links:
            if isinstance(link_item, dict) and (
                link_item.get("ref") == cname
                or (link_item.get("r") == r and link_item.get("c") == c)
            ):
                return True
        return False

    def insert_hyperlink(self, r: int, c: int) -> None:
        """Insert hyperlink into cell (r, c)."""
        win = self.window()
        if hasattr(win, "insert_hyperlink"):
            win.insert_hyperlink()
        else:
            url, ok = QInputDialog.getText(
                self, safe_tr("插入超链接"), safe_tr("地址(&E):")
            )
            if ok and url:
                links = getattr(self.model, "links", [])
                links.append({"r": r, "c": c, "target": url})
                self.viewport().update()

    def edit_hyperlink(self, r: int, c: int) -> None:
        """Edit hyperlink in cell (r, c)."""
        self.insert_hyperlink(r, c)

    def open_hyperlink(self, r: int, c: int) -> None:
        """Open hyperlink in cell (r, c)."""
        links = getattr(self.model, "links", [])
        from atboffice.modules.spreadsheet.calc.references import cell_name

        cname = cell_name(r, c)
        target = None
        for link_item in links:
            if isinstance(link_item, dict) and (
                link_item.get("ref") == cname
                or (link_item.get("r") == r and link_item.get("c") == c)
            ):
                target = link_item.get("target")
                break
        if target:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            QDesktopServices.openUrl(QUrl(target))

    def remove_hyperlink(self, r: int, c: int) -> None:
        """Remove hyperlink from cell (r, c)."""
        links = getattr(self.model, "links", [])
        from atboffice.modules.spreadsheet.calc.references import cell_name

        cname = cell_name(r, c)
        self.model.links = [
            link_item
            for link_item in links
            if not (
                isinstance(link_item, dict)
                and (
                    link_item.get("ref") == cname
                    or (link_item.get("r") == r and link_item.get("c") == c)
                )
            )
        ]
        self.viewport().update()

    def open_format_object_dialog(self, obj: Any) -> None:
        """Open formatting dialog for the selected floating object."""
        win = self.window()
        if hasattr(win, "format_object"):
            win.format_object()

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

    def _open_filter_dropdown(self, col: int) -> None:
        """Open the AutoFilter dropdown popup for the specified column."""
        if getattr(self.model, "auto_filter", None) is None:
            return
        af = self.model.auto_filter
        from atboffice.modules.spreadsheet.models.filter_model import (
            apply_auto_filter,
            clear_auto_filter,
            sort_sheet_range,
        )
        from atboffice.modules.spreadsheet.views.filter_dropdown import (
            FilterDropdown,
        )

        dropdown = FilterDropdown(self.model, af, col, self.viewport())

        def on_applied(crit: Any) -> None:
            col_offset = col - af.c1
            af.cols[col_offset] = crit
            apply_auto_filter(self.model, af)
            self._update_scrollbars()
            self.viewport().update()

        def on_cleared() -> None:
            col_offset = col - af.c1
            clear_auto_filter(self.model, af, col_offset)
            self._update_scrollbars()
            self.viewport().update()

        def on_sort(desc: bool) -> None:
            sort_sheet_range(
                self.model,
                af.r1,
                af.c1,
                af.r2,
                af.c2,
                [(col, desc)],
                has_header=True,
            )
            self.viewport().update()

        dropdown.filter_applied.connect(on_applied)
        dropdown.filter_cleared.connect(on_cleared)
        dropdown.sort_requested.connect(on_sort)

        # Position popup directly under the cell
        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()
        col_x = (
            self.row_header_width
            + self.geometry_mapper.col_pos(col)
            - scroll_x
        )
        row_y = (
            self.col_header_height
            + self.geometry_mapper.row_pos(af.r1)
            - scroll_y
        )
        row_h = self.geometry_mapper.row_size(af.r1)
        global_pos = self.viewport().mapToGlobal(QPoint(col_x, row_y + row_h))
        dropdown.move(global_pos)
        dropdown.show()

    def toggle_auto_filter(self) -> None:
        """Toggle AutoFilter on current selection or surrounding data range."""
        from atboffice.modules.spreadsheet.models.filter_model import (
            AutoFilter,
            clear_auto_filter,
        )

        if getattr(self.model, "auto_filter", None) is not None:
            clear_auto_filter(self.model, self.model.auto_filter)
            self.model.auto_filter = None
            self._update_scrollbars()
            self.viewport().update()
            return

        # Determine range from current selection
        pr = self.selection.primary_range
        r1, c1, r2, c2 = pr.min_r, pr.min_c, pr.max_r, pr.max_c
        if r1 == r2 and c1 == c2:
            # Single cell selected: expand to bounding box of active cells
            min_r, min_c, max_r, max_c = r1, c1, r2, c2
            for (cr, cc), cell in self.model.cells.items():
                if cell.value is not None and cell.value != "":
                    min_r = min(min_r, cr)
                    max_r = max(max_r, cr)
                    min_c = min(min_c, cc)
                    max_c = max(max_c, cc)
            r1, c1, r2, c2 = min_r, min_c, max_r, max_c

        af = AutoFilter(r1=r1, c1=c1, r2=r2, c2=c2)
        self.model.auto_filter = af
        self.viewport().update()

    def open_sort_dialog(self) -> None:
        """Open SortDialog for current selection or surrounding data range."""
        pr = self.selection.primary_range
        r1, c1, r2, c2 = pr.min_r, pr.min_c, pr.max_r, pr.max_c
        if r1 == r2 and c1 == c2:
            min_r, min_c, max_r, max_c = r1, c1, r2, c2
            for (cr, cc), cell in self.model.cells.items():
                if cell.value is not None and cell.value != "":
                    min_r = min(min_r, cr)
                    max_r = max(max_r, cr)
                    min_c = min(min_c, cc)
                    max_c = max(max_c, cc)
            r1, c1, r2, c2 = min_r, min_c, max_r, max_c

        from atboffice.modules.spreadsheet.dialogs.sort_dialog import SortDialog
        from atboffice.modules.spreadsheet.models.filter_model import (
            sort_sheet_range,
        )

        dlg = SortDialog(self.model, r1, c1, r2, c2, self)
        if dlg.exec() == SortDialog.DialogCode.Accepted:
            keys = dlg.get_sort_keys()
            if keys:
                sort_sheet_range(
                    self.model,
                    r1,
                    c1,
                    r2,
                    c2,
                    keys,
                    has_header=dlg.has_header(),
                    case_sensitive=dlg.is_case_sensitive(),
                )
                self.viewport().update()

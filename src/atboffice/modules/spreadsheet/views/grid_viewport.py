"""Virtualized custom-painted spreadsheet grid viewport based on QAbstractScrollArea."""

from __future__ import annotations

import logging
import math
import weakref
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Final

from PySide6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QRect,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QContextMenuEvent,
    QFocusEvent,
    QFont,
    QKeyEvent,
)
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QMessageBox,
    QToolTip,
    QWidget,
)

from atboffice.core.fault_guard import guard_qt_event
from atboffice.core.i18n import safe_tr
from atboffice.core.undo import UndoService
from atboffice.modules.spreadsheet.models.selection_model import (
    SelectionModel,
    SelectionRange,
)
from atboffice.modules.spreadsheet.models.sheet_model import (
    CellComment,
    CellData,
    SheetDataModel,
)

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.views.editor_controller import (
        EditorController,
    )
from atboffice.modules.spreadsheet.views.grid_cell_commands import GridCellCommandsMixin
from atboffice.modules.spreadsheet.views.grid_clipboard import GridClipboardMixin
from atboffice.modules.spreadsheet.views.grid_data_commands import GridDataMixin
from atboffice.modules.spreadsheet.views.grid_menus import GridMenuMixin
from atboffice.modules.spreadsheet.views.grid_mouse import GridMouseMixin
from atboffice.modules.spreadsheet.views.grid_paint import GridPaintMixin
from atboffice.modules.spreadsheet.views.grid_paint_overlays import GridOverlayPaintMixin
from atboffice.modules.spreadsheet.views.grid_types import (  # noqa: F401  re-exported
    DragSnapshot,
    HitResult,
    HitZone,
    _copy_comments,
    _copy_links,
    cell_delta,
    page_bounds,
)

logger = logging.getLogger(__name__)


class GridViewport(
    GridOverlayPaintMixin,
    GridPaintMixin,
    GridMouseMixin,
    GridMenuMixin,
    GridClipboardMixin,
    GridDataMixin,
    GridCellCommandsMixin,
    QAbstractScrollArea,
):
    """High-performance virtualized 2D grid viewport for ATBOffice Ledger.

    Renders hundreds of thousands of cells at 60 FPS using double-buffered QPainter,
    drawing only the cells within the current visible viewport rectangle.
    """

    cell_selected = Signal(int, int)
    cell_double_clicked = Signal(int, int)
    header_dimensions_changed = Signal(int, int)
    view_mode_changed = Signal(str)
    pivot_refresh_requested = Signal(object)
    pivot_field_list_requested = Signal(object)
    pivot_selection_changed = Signal(object)
    zoom_changed = Signal(float)

    # Classic Office / Luna color palette
    # Colours follow ledger/js/render.js COL (Excel 2007-style headers and grid).
    COLOR_GRIDLINE: Final[QColor] = QColor("#C0C0C0")
    COLOR_HDR_BG: Final[QColor] = QColor("#E4ECF7")
    COLOR_HDR_TOP: Final[QColor] = QColor("#FFFFFF")
    COLOR_HDR_SEL_BG: Final[QColor] = QColor("#F8C55E")
    COLOR_HDR_SEL_TOP: Final[QColor] = QColor("#FFE7A2")
    COLOR_HDR_BORDER: Final[QColor] = QColor("#9EB6CE")
    COLOR_HDR_SEL_BORDER: Final[QColor] = QColor("#D7A43C")
    COLOR_HDR_TEXT: Final[QColor] = QColor(0, 0, 0)
    COLOR_SELECTION: Final[QColor] = QColor(49, 74, 160, 51)
    COLOR_ACTIVE_BORDER: Final[QColor] = QColor("#000000")
    # Header geometry minimums (logical px), as in render.js RD.frame.
    MIN_ROW_HEADER_WIDTH: Final[int] = 25
    MIN_COL_HEADER_HEIGHT: Final[int] = 17
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

        # Recomputed from the visible rows by update_header_dimensions().
        self.row_header_width: int = self.MIN_ROW_HEADER_WIDTH
        self.col_header_height: int = max(
            self.MIN_COL_HEADER_HEIGHT, int(self.geometry_mapper.default_row_height)
        )

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
        # Undo / redo history of the whole workbook; entries remember their sheet.
        self.history = UndoService(self)
        self._edit_depth = 0
        self._dv_dropdown_rect: QRect | None = None
        self._format_painter_window: Any | None = None
        self._view_mode: str = "normal"  # "normal" | "page_break"
        self._page_break_welcome_shown: bool = False
        self._zoom: float = 1.0
        self._page_break_drag: dict[str, Any] | None = None
        self._view_state_applied: weakref.WeakSet[SheetDataModel] = weakref.WeakSet()
        self._hover_comment_cell: tuple[int, int] | None = None
        self.last_status_message: str = ""
        self._updating_scrollbars: bool = False

        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.viewport().installEventFilter(self)

        from atboffice.ui.styles.luna_2003 import grid_scrollbar_stylesheet

        self.setStyleSheet(grid_scrollbar_stylesheet())

        self.horizontalScrollBar().valueChanged.connect(self._on_scroll)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

        self._update_scrollbars()
        self._apply_sheet_view_state()
        self.retranslate_ui()

    @property
    def hover_comment_cell(self) -> tuple[int, int] | None:
        """Active hovered comment cell coordinates (row, col) or None."""
        return self._hover_comment_cell

    def show_comment_hover(self, r: int, c: int) -> None:
        """Explicitly set or clear comment hover on cell (r, c)."""
        if r < 0 or c < 0:
            new_hover = None
        else:
            cm = self.model.get_comment(r, c) if hasattr(self.model, "get_comment") else None
            new_hover = (r, c) if cm is not None else None
        if self._hover_comment_cell != new_hover:
            self._hover_comment_cell = new_hover
            self.viewport().update()

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
        return self._auto_scroll_timer is not None and self._auto_scroll_timer.isActive()

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
        fx = self.row_header_width + self.geometry_mapper.col_pos(pr.max_c + 1) - scroll_x
        fy = self.col_header_height + self.geometry_mapper.row_pos(pr.max_r + 1) - scroll_y
        return QRect(fx - 4, fy - 4, 9, 9)

    @property
    def zoom(self) -> float:
        """Current view zoom factor (1.0 = 100%)."""
        return getattr(self, "_zoom", 1.0)

    def set_zoom(self, zoom: float) -> None:
        """Set the sheet's view zoom (1.0 = 100%, clamped to 10%..400%).

        Like ledger/js/grid.js ``G.setZoom`` the zoom belongs to the sheet: it is
        stored in ``model.extra["zoom"]`` / ``view_state.zoom_scale`` so a sheet
        keeps its own zoom across tab switches and is saved as ``zoomScale``.
        """
        pct = max(10, min(400, round(float(zoom) * 100)))
        # A drag measured at the old zoom is meaningless at the new one.
        self.cancel_drag(why="api")
        self._zoom = pct / 100.0
        model = self.model
        extra = getattr(model, "extra", None)
        if isinstance(extra, dict) and extra.get("zoom", 100) != pct:
            if pct == 100:
                extra.pop("zoom", None)
            else:
                extra["zoom"] = pct
            vs = getattr(model, "view_state", None)
            if vs is not None:
                vs.zoom_scale = None if pct == 100 else pct
        if self.object_layer is not None and hasattr(self.object_layer, "set_zoom"):
            self.object_layer.set_zoom(self._zoom)
        if self.editor_controller is not None:
            self.editor_controller.reposition_editor()
        self._update_scrollbars()
        self.viewport().update()
        self.zoom_changed.emit(self._zoom)

    # ---- zoom coordinate mapping ------------------------------------------
    # Every grid computation (cell_rect, hit_test, scroll values, header sizes)
    # works in unzoomed "grid" pixels; the paint path scales the painter by the
    # zoom (render.js multiplies the same geometry by ``z``) and mouse input is
    # divided by it, so only the boundary to real widget pixels needs mapping.

    def _view_size(self) -> tuple[int, int]:
        """Viewport width/height in grid (unzoomed) pixels."""
        vp = self.viewport()
        z = self.zoom
        return math.ceil(vp.width() / z), math.ceil(vp.height() / z)

    def map_from_device(self, x: float, y: float) -> tuple[int, int]:
        """Map a viewport (widget pixel) point to grid coordinates."""
        z = self.zoom
        return math.floor(x / z), math.floor(y / z)

    def map_to_device(self, point: QPoint) -> QPoint:
        """Map a grid-coordinate point to viewport (widget pixel) coordinates."""
        z = self.zoom
        return QPoint(round(point.x() * z), round(point.y() * z))

    def map_rect_to_device(self, rect: QRect) -> QRect:
        """Map a grid-coordinate rect to viewport (widget pixel) coordinates."""
        z = self.zoom
        x1, y1 = round(rect.x() * z), round(rect.y() * z)
        x2 = round((rect.x() + rect.width()) * z)
        y2 = round((rect.y() + rect.height()) * z)
        return QRect(x1, y1, x2 - x1, y2 - y1)

    def device_cell_rect(self, r: int, c: int) -> QRect:
        """Viewport (widget pixel) rect of cell (r, c) at the current zoom."""
        return self.map_rect_to_device(self.cell_rect(r, c))

    def _global_pos(self, point: QPoint) -> QPoint:
        """Screen position of a grid-coordinate point."""
        return self.viewport().mapToGlobal(self.map_to_device(point))

    def clear_undo_stack(self) -> None:
        """Clear all undo and redo history and reset transient interaction states."""
        self.history.clear()
        self._reset_transient_state()

    def _reset_transient_state(self) -> None:
        """Drop drag previews and the internal clipboard (another sheet is shown)."""
        self._internal_clipboard = None
        self._fill_preview_range = None
        self._move_preview_range = None
        self._move_src_range = None
        self._drag_snapshot = None
        self._dv_dropdown_rect = None

    def set_model_and_selection(self, model: SheetDataModel, selection: SelectionModel) -> None:
        """Switch active SheetDataModel and SelectionModel."""
        self.cancel_drag(why="api")
        # The history is kept: each entry switches back to its own sheet.
        self._reset_transient_state()
        # Hover state refers to the previous sheet's cells; never carry it over.
        self._hover_comment_cell = None
        QToolTip.hideText()
        self.model = model
        self.selection = selection
        self.geometry_mapper = model.geometry
        self.update_header_dimensions()
        self._apply_sheet_view_state()
        self._update_scrollbars()
        self._relayout_outline_gutter()
        self.viewport().update()

    # ---- outline grouping gutter -----------------------------------------------
    def _relayout_outline_gutter(self) -> None:
        from atboffice.modules.spreadsheet.models import outline

        has = bool(outline.levels(self.model, "row") or outline.levels(self.model, "col"))
        gutter = getattr(self, "outline_gutter", None)
        if gutter is None:
            if not has:
                return
            from atboffice.modules.spreadsheet.views.outline_gutter import OutlineGutter

            gutter = self.outline_gutter = OutlineGutter(self)
        gutter.relayout()

    def outline_changed(self) -> None:
        """Call after grouping changes or a group was expanded / collapsed."""
        self._relayout_outline_gutter()
        self._update_scrollbars()
        self.mark_dirty()
        self.viewport().update()

    @property
    def show_grid_lines(self) -> bool:
        """Whether cell gridlines are painted for the current sheet (``showGridLines``)."""
        vs = getattr(self.model, "view_state", None)
        return vs.show_grid_lines if vs is not None else True

    def _apply_sheet_view_state(self) -> None:
        """Apply the sheet's saved zoom; on first display also its view mode and scroll origin."""
        model = self.model
        zoom_pct: Any = 100
        if hasattr(model, "extra") and "zoom" in model.extra:
            zoom_pct = model.extra["zoom"]
        try:
            self.set_zoom(float(zoom_pct) / 100.0)
        except (TypeError, ValueError):
            self.set_zoom(1.0)
        vs = getattr(model, "view_state", None)
        if vs is None or model in self._view_state_applied:
            return
        self._view_state_applied.add(model)
        mode = "page_break" if vs.view == "pageBreakPreview" else "normal"
        self.set_view_mode(mode, prompt_welcome=False)
        top_left = vs.top_left_rc()
        if top_left is None:
            return
        r, c = top_left
        fz_r, fz_c = self.freeze_rows, self.freeze_cols
        fz_h = self.geometry_mapper.row_pos(fz_r) if fz_r > 0 else 0
        fz_w = self.geometry_mapper.col_pos(fz_c) if fz_c > 0 else 0
        target_y = max(0, self.geometry_mapper.row_pos(r) - fz_h) if r >= fz_r else 0
        target_x = max(0, self.geometry_mapper.col_pos(c) - fz_w) if c >= fz_c else 0
        view_w, view_h = self._view_size()
        vw = max(1, view_w - self.row_header_width)
        vh = max(1, view_h - self.col_header_height)
        self._update_scrollbars(min_bottom=target_y + vh, min_right=target_x + vw)
        self._updating_scrollbars = True
        try:
            if r >= fz_r:
                self.verticalScrollBar().setValue(target_y)
            if c >= fz_c:
                self.horizontalScrollBar().setValue(target_x)
        finally:
            self._updating_scrollbars = False

    def retranslate_ui(self) -> None:
        """Update localized UI text and trigger repaint."""
        self.viewport().update()

    def _on_scroll(self, _: int) -> None:
        if self.editor_controller is not None:
            self.editor_controller.reposition_editor()
        if not getattr(self, "_updating_scrollbars", False):
            self._update_scrollbars()
        self.viewport().update()
        gutter = getattr(self, "outline_gutter", None)
        if gutter is not None:
            gutter.update()

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        gutter = getattr(self, "outline_gutter", None)
        if gutter is not None:
            gutter.relayout()
        self._update_scrollbars()
        if self.editor_controller is not None:
            self.editor_controller.reposition_editor()

    def _used_scroll_extent(self) -> tuple[int, int]:
        """Return (bottom_y, right_x) grid coordinates for used cells, merges, and drawings."""
        model = self.model
        geo = self.geometry_mapper
        cells = getattr(model, "cells", None) or {}
        max_r = 0
        max_c = 0
        for r, c in cells:
            if r > max_r:
                max_r = r
            if c > max_c:
                max_c = c
        for m in getattr(model, "merges", None) or ():
            try:
                _r1, _c1, r2, c2 = self._normalize_merge(m)
            except (TypeError, ValueError):
                continue
            max_r = max(max_r, r2)
            max_c = max(max_c, c2)

        extra_h = 0
        extra_w = 0
        for d in getattr(model, "drawings", None) or ():
            anchor = getattr(d, "anchor_type", None)
            anchor_val = getattr(anchor, "value", anchor)
            abs_rect = getattr(d, "abs_rect", None)
            if anchor_val == "absolute":
                if abs_rect is not None and len(abs_rect) >= 4:
                    extra_w = max(extra_w, int(abs_rect[0]) + int(abs_rect[2]))
                    extra_h = max(extra_h, int(abs_rect[1]) + int(abs_rect[3]))
            elif anchor_val == "oneCell":
                from_pt = getattr(d, "from_point", None)
                if from_pt is not None:
                    fr = max(0, min(geo.max_rows - 1, int(getattr(from_pt, "row", 0))))
                    fc = max(0, min(geo.max_cols - 1, int(getattr(from_pt, "col", 0))))
                    w_px = int(abs_rect[2]) if abs_rect is not None and len(abs_rect) >= 4 else 0
                    h_px = int(abs_rect[3]) if abs_rect is not None and len(abs_rect) >= 4 else 0
                    row_off = int(getattr(from_pt, "row_off", 0))
                    col_off = int(getattr(from_pt, "col_off", 0))
                    extra_h = max(extra_h, geo.row_pos(fr) + row_off + h_px)
                    extra_w = max(extra_w, geo.col_pos(fc) + col_off + w_px)
            else:
                to_pt = getattr(d, "to_point", None)
                if to_pt is not None:
                    max_r = max(max_r, int(getattr(to_pt, "row", 0)))
                    max_c = max(max_c, int(getattr(to_pt, "col", 0)))

        r_idx = min(geo.max_rows - 1, max(0, max_r + 1))
        c_idx = min(geo.max_cols - 1, max(0, max_c + 1))
        return (
            max(geo.row_pos(r_idx), extra_h),
            max(geo.col_pos(c_idx), extra_w),
        )

    def _update_scrollbars(self, min_bottom: int = 0, min_right: int = 0) -> None:
        """Synchronize Qt scrollbars with used sheet extent plus one viewport page."""
        view_w, view_h = self._view_size()
        vw = max(1, view_w - self.row_header_width)
        vh = max(1, view_h - self.col_header_height)

        used_h, used_w = self._used_scroll_extent()
        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()

        max_total_h = self.geometry_mapper.row_pos(self.geometry_mapper.max_rows - 1)
        max_total_w = self.geometry_mapper.col_pos(self.geometry_mapper.max_cols - 1)

        total_h = min(max_total_h, max(used_h, scroll_y + vh, min_bottom) + vh)
        total_w = min(max_total_w, max(used_w, scroll_x + vw, min_right) + vw)

        self._updating_scrollbars = True
        try:
            self.horizontalScrollBar().setRange(0, max(0, total_w - vw))
            self.horizontalScrollBar().setPageStep(vw)
            self.verticalScrollBar().setRange(0, max(0, total_h - vh))
            self.verticalScrollBar().setPageStep(vh)
        finally:
            self._updating_scrollbars = False

    def hit_test(self, x: int, y: int) -> HitResult:
        """Determine hit zone and target under grid point (x, y).

        (x, y) are grid (unzoomed) coordinates; mouse handlers map widget
        pixels with :meth:`map_from_device`.  Grab tolerances are kept
        constant in screen pixels, as in ledger/js/grid.js ``zone()``.
        """
        z = self.zoom
        tol2, tol3, tol5 = 2 / z, 3 / z, 5 / z
        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()

        fz_r = self.freeze_rows
        fz_c = self.freeze_cols
        fz_r_h = self.geometry_mapper.row_pos(fz_r) if fz_r > 0 else 0
        fz_c_w = self.geometry_mapper.col_pos(fz_c) if fz_c > 0 else 0

        # 1. Corner box
        if x < self.row_header_width and y < self.col_header_height:
            return HitResult(HitZone.CORNER)

        # 2. Column Header area
        if y < self.col_header_height:
            x_rel = x - self.row_header_width
            if fz_c > 0 and x_rel < fz_c_w:
                sheet_x = x_rel
            else:
                sheet_x = scroll_x + x_rel
            col = self.geometry_mapper.find_col_at(sheet_x)
            col_end = self.geometry_mapper.col_pos(col) + self.geometry_mapper.col_size(col)
            # Check resize boundary (+/- 3px)
            if abs(sheet_x - col_end) <= tol3:
                return HitResult(HitZone.COL_RESIZE, col=col, pos=x)
            if col > 0 and abs(sheet_x - self.geometry_mapper.col_pos(col)) <= tol3:
                return HitResult(HitZone.COL_RESIZE, col=col - 1, pos=x)
            return HitResult(HitZone.COL_HEADER, col=col)

        # 3. Row Header area
        if x < self.row_header_width:
            y_rel = y - self.col_header_height
            if fz_r > 0 and y_rel < fz_r_h:
                sheet_y = y_rel
            else:
                sheet_y = scroll_y + y_rel
            row = self.geometry_mapper.find_row_at(sheet_y)
            row_end = self.geometry_mapper.row_pos(row) + self.geometry_mapper.row_size(row)
            if abs(sheet_y - row_end) <= tol2:
                return HitResult(HitZone.ROW_RESIZE, row=row, pos=y)
            if row > 0 and abs(sheet_y - self.geometry_mapper.row_pos(row)) <= tol2:
                return HitResult(HitZone.ROW_RESIZE, row=row - 1, pos=y)
            return HitResult(HitZone.ROW_HEADER, row=row)

        # 4. AutoFill Handle & Selection Border area (active when single selection range)
        if len(self.selection.ranges) == 1:
            pr = self.selection.primary_range
            is_editing = self.editor_controller is not None and self.editor_controller.is_active
            is_whole_rows = pr.min_c == 0 and pr.max_c >= self.geometry_mapper.max_cols - 1
            is_whole_cols = pr.min_r == 0 and pr.max_r >= self.geometry_mapper.max_rows - 1

            r_tl = self.cell_rect(pr.min_r, pr.min_c)
            r_br = self.cell_rect(pr.max_r, pr.max_c)
            bx1 = r_tl.left()
            by1 = r_tl.top()
            bx2 = r_br.right() + 1
            by2 = r_br.bottom() + 1

            # AutoFill Handle has priority (+/- 5px at bottom-right)
            if abs(x - bx2) <= tol5 and abs(y - by2) <= tol5:
                return HitResult(HitZone.FILL_HANDLE, row=pr.max_r, col=pr.max_c)

            # Selection Border (+/- 2px along perimeter)
            if not is_editing and not is_whole_rows and not is_whole_cols:
                on_v = (abs(x - bx1) <= tol2 or abs(x - bx2) <= tol2) and (
                    by1 - tol2 <= y <= by2 + tol2
                )
                on_h = (abs(y - by1) <= tol2 or abs(y - by2) <= tol2) and (
                    bx1 - tol2 <= x <= bx2 + tol2
                )
                if on_v or on_h:
                    x_rel = x - self.row_header_width
                    y_rel = y - self.col_header_height
                    sx = x_rel if (fz_c > 0 and x_rel < fz_c_w) else max(0, scroll_x + x_rel)
                    sy = y_rel if (fz_r > 0 and y_rel < fz_r_h) else max(0, scroll_y + y_rel)
                    hit_r = self.geometry_mapper.find_row_at(sy)
                    hit_c = self.geometry_mapper.find_col_at(sx)
                    return HitResult(HitZone.BORDER, row=hit_r, col=hit_c)

        # 4.5 AutoFilter Button area
        af = getattr(self.model, "auto_filter", None)
        if af is not None and hasattr(af, "r1") and hasattr(af, "c1") and hasattr(af, "c2"):
            r1 = af.r1
            r_af_top = self.cell_rect(r1, af.c1)
            row_y = r_af_top.top()
            row_h = self.geometry_mapper.row_size(r1)
            btn_size = min(16, max(12, row_h - 2))
            if row_y <= y <= row_y + row_h:
                for c in range(af.c1, af.c2 + 1):
                    c_cell_rect = self.cell_rect(r1, c)
                    col_x = c_cell_rect.left()
                    col_w = c_cell_rect.width()
                    bx = col_x + col_w - btn_size - 1
                    by = row_y + row_h - btn_size - 1
                    if bx <= x <= bx + btn_size and by <= y <= by + btn_size:
                        return HitResult(HitZone.FILTER_BUTTON, row=r1, col=c)

        # 4.6 PivotTable Filter Dropdown Button area
        for report in getattr(self.model, "pivot_reports", []):
            meta = getattr(report, "meta", None)
            if meta is None:
                continue
            for r_cell, c_cell in getattr(meta, "filter_dropdown_cells", {}):
                c_rect = self.cell_rect(r_cell, c_cell)
                if not c_rect.isValid():
                    continue
                btn_size = min(16, max(12, c_rect.height() - 2))
                bx = c_rect.left() + c_rect.width() - btn_size - 1
                by = c_rect.top() + c_rect.height() - btn_size - 1
                if bx <= x <= bx + btn_size and by <= y <= by + btn_size:
                    return HitResult(HitZone.PIVOT_FILTER_BUTTON, row=r_cell, col=c_cell)

        # 5. Cell area
        x_rel = x - self.row_header_width
        y_rel = y - self.col_header_height
        if fz_c > 0 and x_rel < fz_c_w:
            sheet_x = x_rel
        else:
            sheet_x = scroll_x + x_rel

        if fz_r > 0 and y_rel < fz_r_h:
            sheet_y = y_rel
        else:
            sheet_y = scroll_y + y_rel

        row = self.geometry_mapper.find_row_at(sheet_y)
        col = self.geometry_mapper.find_col_at(sheet_x)
        return HitResult(HitZone.CELL, row=row, col=col)

    def cell_at_pos(self, x: int, y: int) -> tuple[int, int] | None:
        """Return (row, col) cell index at widget coordinates, or None if in headers."""
        hit = self.hit_test(x, y)
        if hit.zone == HitZone.CELL and hit.row is not None and hit.col is not None:
            return (hit.row, hit.col)
        return None

    @staticmethod
    def _normalize_unwrapped_text(text: str, wrap_text: bool) -> str:
        """Replace line breaks with spaces when wrap_text is disabled (Excel behavior)."""
        if wrap_text:
            return text
        if "\n" not in text and "\r" not in text:
            return text
        return text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")

    @staticmethod
    def _normalize_merge(m: Any) -> tuple[int, int, int, int]:
        """Normalize a merge entry (4-tuple or SelectionRange) to (r1, c1, r2, c2)."""
        if hasattr(m, "min_r"):
            return (int(m.min_r), int(m.min_c), int(m.max_r), int(m.max_c))
        r1, c1, r2, c2 = m
        return (
            min(int(r1), int(r2)),
            min(int(c1), int(c2)),
            max(int(r1), int(r2)),
            max(int(c1), int(c2)),
        )

    def _is_merged_cell(self, r: int, c: int) -> bool:
        """Return True if (r, c) lies inside any merged region on the sheet."""
        for m in getattr(self.model, "merges", []):
            r1, c1, r2, c2 = self._normalize_merge(m)
            if r1 <= r <= r2 and c1 <= c <= c2:
                return True
        return False

    def _is_empty_for_spill(
        self,
        r: int,
        c: int,
        merge_by_cell: dict[tuple[int, int], tuple[int, int, int, int]] | None = None,
    ) -> bool:
        """Return True if neighbor cell (r, c) can accept spilled text."""
        if c < 0 or c >= self.geometry_mapper.max_cols:
            return False
        if merge_by_cell is not None:
            if (r, c) in merge_by_cell:
                return False
        elif self._is_merged_cell(r, c):
            return False
        return self.model.is_empty(r, c)

    def _measure_rich_runs_width(self, cell: CellData) -> float:
        """Measure total horizontal width of rich text runs."""
        runs = cell.rich_runs or []
        if not runs:
            return 0.0

        max_line_w = 0.0
        curr_line_w = 0.0

        for r in runs:
            fam = r.font_family or cell.font_family or "Arial"
            sz = r.font_size if r.font_size is not None else (cell.font_size or 10)
            if r.vert_align in ("subscript", "superscript"):
                sz = max(1.0, sz * 0.7)

            rf = QFont(fam, int(sz) if isinstance(sz, int) else round(sz))
            if isinstance(sz, float):
                rf.setPointSizeF(sz * self._print_font_factor)
            rf.setBold(r.bold if r.bold is not None else cell.bold)
            rf.setItalic(r.italic if r.italic is not None else cell.italic)
            rfm = self._fm(rf)

            run_text = self._normalize_unwrapped_text(r.text, cell.wrap_text)
            parts = run_text.split("\n")
            for idx, part in enumerate(parts):
                if idx > 0:
                    if curr_line_w > max_line_w:
                        max_line_w = curr_line_w
                    curr_line_w = 0.0
                curr_line_w += rfm.horizontalAdvance(part)

        if curr_line_w > max_line_w:
            max_line_w = curr_line_w

        return max_line_w

    def auto_fit_column(self, col: int) -> None:
        """Auto-fit column width to the widest content cell in the column."""
        max_width = 30  # Minimum column width

        # Measure width of cells in column
        for (r, c), cell in self.model.cells.items():
            disp_val = (
                cell.get_display_value() if hasattr(cell, "get_display_value") else cell.value
            )
            if c == col and disp_val is not None:
                if cell.rich_runs:
                    w = self._measure_rich_runs_width(cell) + 12
                else:
                    text = self.model.get_formatted_text(r, c)
                    cell_font = QFont(
                        cell.font_family or self.font().family(),
                        cell.font_size or 10,
                    )
                    cell_font.setBold(cell.bold)
                    cell_font.setItalic(cell.italic)
                    w = self._fm(cell_font).horizontalAdvance(text) + 12
                if w > max_width:
                    max_width = int(w)

        self.geometry_mapper.set_col_width(col, min(500, max_width))
        self._update_scrollbars()
        self.viewport().update()

    def calculate_overflow_span(self, r: int, c: int, text_width: int, col_width: int) -> int:
        """Calculate how many consecutive empty neighbor columns text can overflow right."""
        _, right_c = self.calculate_spill_bounds(r, c, text_width, col_width, eff_h="left")
        return right_c - c + 1

    def calculate_spill_bounds(
        self,
        r: int,
        c: int,
        text_width: float,
        col_width: int,
        eff_h: str,
        indent_px: int = 0,
        min_col: int = 0,
        max_col: int | None = None,
        merge_by_cell: dict[tuple[int, int], tuple[int, int, int, int]] | None = None,
    ) -> tuple[int, int]:
        """Calculate inclusive (left_col, right_col) spill bounds for unwrapped text."""
        avail = col_width - 6 - indent_px
        if text_width <= avail:
            return (c, c)

        upper_col = (
            self.geometry_mapper.max_cols - 1
            if max_col is None
            else min(max_col, self.geometry_mapper.max_cols - 1)
        )
        lower_col = max(0, min_col)
        left_c = c
        right_c = c

        if eff_h in ("left", "general"):
            accumulated = col_width
            curr_c = c + 1
            steps = 0
            while (
                accumulated < text_width + 6 + indent_px
                and curr_c <= upper_col
                and steps < 200
                and self._is_empty_for_spill(r, curr_c, merge_by_cell)
            ):
                accumulated += self.geometry_mapper.col_size(curr_c)
                right_c = curr_c
                curr_c += 1
                steps += 1
        elif eff_h == "right":
            accumulated = col_width
            curr_c = c - 1
            steps = 0
            while (
                accumulated < text_width + 6 + indent_px
                and curr_c >= lower_col
                and steps < 200
                and self._is_empty_for_spill(r, curr_c, merge_by_cell)
            ):
                accumulated += self.geometry_mapper.col_size(curr_c)
                left_c = curr_c
                curr_c -= 1
                steps += 1
        elif eff_h in ("center", "centerContinuous"):
            need = max(0.0, (text_width - max(0, col_width - 6)) / 2.0)
            extra_r = 0
            curr_c = c + 1
            steps = 0
            while (
                extra_r < need + 3
                and curr_c <= upper_col
                and steps < 200
                and self._is_empty_for_spill(r, curr_c, merge_by_cell)
            ):
                extra_r += self.geometry_mapper.col_size(curr_c)
                right_c = curr_c
                curr_c += 1
                steps += 1

            extra_l = 0
            curr_c = c - 1
            steps = 0
            while (
                extra_l < need + 3
                and curr_c >= lower_col
                and steps < 200
                and self._is_empty_for_spill(r, curr_c, merge_by_cell)
            ):
                extra_l += self.geometry_mapper.col_size(curr_c)
                left_c = curr_c
                curr_c -= 1
                steps += 1

        return (left_c, right_c)

    def reveal(self, r: int, c: int) -> None:
        """Ensure cell (r, c) is visible in the viewport by scrolling if needed."""
        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()
        view_w, view_h = self._view_size()
        vw = max(1, view_w - self.row_header_width)
        vh = max(1, view_h - self.col_header_height)

        fz_r = self.freeze_rows
        fz_c = self.freeze_cols
        fz_r_h = self.geometry_mapper.row_pos(fz_r) if fz_r > 0 else 0
        fz_c_w = self.geometry_mapper.col_pos(fz_c) if fz_c > 0 else 0

        cell_top = self.geometry_mapper.row_pos(r)
        cell_bottom = cell_top + self.geometry_mapper.row_size(r)
        cell_left = self.geometry_mapper.col_pos(c)
        cell_right = cell_left + self.geometry_mapper.col_size(c)

        self._update_scrollbars(
            min_bottom=cell_bottom
            if (fz_r == 0 or r >= fz_r) and cell_bottom > self.verticalScrollBar().maximum() + vh
            else 0,
            min_right=cell_right
            if (fz_c == 0 or c >= fz_c) and cell_right > self.horizontalScrollBar().maximum() + vw
            else 0,
        )
        self._updating_scrollbars = True
        try:
            if fz_r > 0 and r < fz_r:
                # Pinned row: already visible at the top
                pass
            else:
                if cell_top < scroll_y + fz_r_h:
                    self.verticalScrollBar().setValue(max(0, cell_top - fz_r_h))
                elif cell_bottom > scroll_y + vh:
                    self.verticalScrollBar().setValue(cell_bottom - vh)

            if fz_c > 0 and c < fz_c:
                # Pinned column: already visible at the left
                pass
            else:
                if cell_left < scroll_x + fz_c_w:
                    self.horizontalScrollBar().setValue(max(0, cell_left - fz_c_w))
                elif cell_right > scroll_x + vw:
                    self.horizontalScrollBar().setValue(cell_right - vw)
        finally:
            self._updating_scrollbars = False
        self._update_scrollbars()

    def cell_rect(self, r: int, c: int) -> QRect:
        """Return the visible QRect coordinates for cell (r, c) within the viewport."""
        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()
        if self.freeze_cols > 0 and c < self.freeze_cols:
            x = self.row_header_width + self.geometry_mapper.col_pos(c)
        else:
            x = self.row_header_width + self.geometry_mapper.col_pos(c) - scroll_x

        if self.freeze_rows > 0 and r < self.freeze_rows:
            y = self.col_header_height + self.geometry_mapper.row_pos(r)
        else:
            y = self.col_header_height + self.geometry_mapper.row_pos(r) - scroll_y

        w = self.geometry_mapper.col_size(c)
        h = self.geometry_mapper.row_size(r)
        return QRect(x, y, w, h)

    # ---- printing -----------------------------------------------------------
    _printing: bool = False
    _print_gridlines: bool = False
    _print_font_factor: float = 1.0
    _print_device: Any = None

    _COMMENT_NOTE_BG = QColor(0xFF, 0xFF, 0xE1)
    _COMMENT_GAP = 14

    # -------------------------------------------------------------------------
    # Keyboard Navigation Subsystem
    # -------------------------------------------------------------------------
    @guard_qt_event("spreadsheet_grid", "key_press")
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
        if key == Qt.Key.Key_F10 and bool(modifiers & Qt.KeyboardModifier.ShiftModifier):
            self.open_context_menu(reason=QContextMenuEvent.Reason.Keyboard)
            return

        # Ctrl+1 / Cmd+1 to open Format Cells dialog
        if (
            modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)
        ) and key == Qt.Key.Key_1:
            self.open_format_cells_dialog()
            return

        # Ctrl+Alt+V / Cmd+Alt+V to open Paste Special dialog
        if (
            (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))
            and bool(modifiers & Qt.KeyboardModifier.AltModifier)
            and key == Qt.Key.Key_V
        ):
            self.paste_special()
            return

        # F2 to start editing
        if key == Qt.Key.Key_F2:
            if self.editor_controller is not None and not self.editor_controller.is_active:
                self.editor_controller.begin_edit(r, c)
                return

        # Alt+Down to open List Validation dropdown
        if key == Qt.Key.Key_Down and (modifiers & Qt.KeyboardModifier.AltModifier):
            if self._dv_dropdown_rect is not None:
                self._open_dv_dropdown()
                return

        # Delete / Backspace to clear selection
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self.editor_controller is not None and not self.editor_controller.is_active:
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
                modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
            )
        ):
            if self.editor_controller is not None and not self.editor_controller.is_active:
                self.editor_controller.begin_edit(r, c, initial_text=text)
                return

        # Ctrl+A Select All
        if key == Qt.Key.Key_A and (modifiers & Qt.KeyboardModifier.ControlModifier):
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

    # -------------------------------------------------------------------------
    # Context Menu Actions & Guard Protection
    # -------------------------------------------------------------------------
    def guard_protect(self, allow_key: str | None = None, cell_edit: bool = False) -> bool:
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

    # -------------------------------------------------------------------------
    # Undo / redo
    # -------------------------------------------------------------------------

    def selection_scope(self, margin: int = 1) -> list[SelectionRange]:
        """The selected ranges grown by ``margin`` cells (borders reach neighbours)."""
        return [
            SelectionRange(
                max(0, rg.min_r - margin),
                max(0, rg.min_c - margin),
                rg.max_r + margin,
                rg.max_c + margin,
            )
            for rg in self.selection.ranges
        ]

    @contextmanager
    def undoable_edit(
        self,
        action: str = "edit",
        *,
        scope: str | list[SelectionRange] = "sheet",
        label: str | None = None,
    ) -> Iterator[None]:
        """Record every change made inside the block as one undo step.

        ``scope`` is ``"sheet"`` (any cell may change), ``"selection"`` (only the
        selected cells and their neighbours) or explicit ranges. Edits nest: an
        inner edit is part of the outer step.
        """
        if self._edit_depth or not self.history.is_recording:
            self._edit_depth += 1
            try:
                yield
            finally:
                self._edit_depth -= 1
            return
        if scope == "selection":
            ranges: list[SelectionRange] | None = self.selection_scope()
        elif scope == "sheet":
            ranges = None
        else:
            ranges = list(scope)
        before = self._snapshot_state(ranges)
        self._edit_depth += 1
        try:
            with self.history.paused():
                yield
        finally:
            self._edit_depth -= 1
        self._commit_undo(before, action, label)

    def _snapshot_state(
        self, scope: list[SelectionRange] | SelectionRange | None = None
    ) -> dict[str, Any]:
        """Capture the state an edit may change, for :meth:`_commit_undo`.

        ``scope`` limits the cells copied to the ranges the edit touches; with
        None every cell of the sheet is copied. Merges, comments and links are
        small and always copied.
        """
        if isinstance(scope, SelectionRange):
            scope = [scope]
        scope = [SelectionRange(rg.r1, rg.c1, rg.r2, rg.c2) for rg in scope] if scope else None
        model = self.model
        return {
            "sheet": model,
            "scope": scope,
            "before_cells": self._clone_cells(scope, model),
            "before_merges": list(model.merges),
            "before_comments": _copy_comments(model),
            "before_links": _copy_links(model),
            "before_sel": self.selection.snapshot(),
        }

    def _commit_undo(
        self, before_state: dict[str, Any], action: str = "edit", label: str | None = None
    ) -> bool:
        """Record the change since ``before_state`` as one undo step (changed cells only).

        Returns False, and records nothing, when nothing changed.
        """
        model = before_state.get("sheet") or self.model
        after_cells = self._clone_cells(before_state.get("scope"), model)
        entry: dict[str, Any] = {"action": action, "sheet": model}
        if label:
            entry["label"] = label
        delta_before, delta_after = cell_delta(before_state["before_cells"], after_cells)
        changed = bool(delta_before or delta_after)
        if changed:
            entry["before_delta_cells"] = delta_before
            entry["after_delta_cells"] = delta_after
        for key, now in (
            ("merges", list(model.merges)),
            ("comments", _copy_comments(model)),
            ("links", _copy_links(model)),
        ):
            was = before_state.get(f"before_{key}")
            if was is not None and was != now:
                entry[f"before_{key}"] = was
                entry[f"after_{key}"] = now
                changed = True
        if not changed:
            return False
        entry["before_sel"] = before_state.get("before_sel")
        entry["after_sel"] = self.selection.snapshot()
        self._record_entry(entry)
        self.mark_dirty()
        self.viewport().update()
        return True

    def _record_entry(self, entry: dict[str, Any]) -> None:
        """Push an already-applied change described by ``entry`` onto the history.

        Entries holding whole-sheet ``before_cells`` / ``after_cells`` copies are
        reduced to the cells that changed before they are stored.
        """
        from atboffice.ui.components.undo_history import entry_label

        entry.setdefault("sheet", self.model)
        if "before_cells" in entry and "after_cells" in entry:
            delta_before, delta_after = cell_delta(
                entry.pop("before_cells"), entry.pop("after_cells")
            )
            entry["before_delta_cells"] = delta_before
            entry["after_delta_cells"] = delta_after
            for key in ("merges", "comments", "links"):
                if entry.get(f"before_{key}") == entry.get(f"after_{key}"):
                    entry.pop(f"before_{key}", None)
                    entry.pop(f"after_{key}", None)
        self.history.record(
            entry_label(entry),
            lambda: self._apply_entry(entry, undo=True),
            lambda: self._apply_entry(entry, undo=False),
            data=entry,
        )

    def mark_dirty(self) -> None:
        """Mark workbook as modified."""
        win = self.window()
        if hasattr(win, "set_dirty"):
            win.set_dirty(True)
        elif hasattr(win, "set_modified"):
            win.set_modified(True)
        elif hasattr(self, "workbook") and self.workbook:
            self.workbook.dirty = True

    # -------------------------------------------------------------------------
    # PivotTable Integration (Detection, Rendering, Refresh & Filter Dropdowns)
    # -------------------------------------------------------------------------

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
            nxt_has_data = nxt is not None and (nxt.value is not None or nxt.formula is not None)
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

    def undo(self) -> bool:
        """Undo the last spreadsheet edit operation."""
        return self.history.undo()

    def redo(self) -> bool:
        """Redo the last undone spreadsheet edit operation."""
        return self.history.redo()

    def _activate_sheet(self, sheet: Any) -> None:
        """Show ``sheet`` before one of its edits is undone or redone."""
        if sheet is None or sheet is self.model:
            return
        wb = self._resolve_workbook()
        if wb is None or not hasattr(wb, "sheet_index"):
            return
        idx = wb.sheet_index(sheet)
        if idx >= 0:
            wb.set_active_sheet_index(idx)

    def _recalculate(self) -> None:
        if hasattr(self.model, "recalculate"):
            self.model.recalculate()
        elif getattr(self, "workbook", None) is not None and hasattr(self.workbook, "recalculate"):
            self.workbook.recalculate()

    def _apply_entry(self, cmd: dict[str, Any], *, undo: bool) -> None:
        """Move the model to the ``before`` (undo) or ``after`` (redo) side of ``cmd``."""
        side = "before" if undo else "after"
        self._activate_sheet(cmd.get("sheet"))
        action = cmd.get("action")
        if action == "filter":
            from atboffice.modules.spreadsheet.models.filter_model import (
                ColumnFilter,
                apply_auto_filter,
            )

            af = cmd["af"]
            af.cols = {
                c: ColumnFilter(**(vars(cf) if hasattr(cf, "__dict__") else cf))
                if isinstance(cf, ColumnFilter)
                else cf
                for c, cf in cmd[f"{side}_cols"].items()
            }
            apply_auto_filter(self.model, af)
            self._update_filter_status(af)
            self._update_scrollbars()
            self.viewport().update()
            return
        if action in ("col_resize", "row_resize"):
            setter = (
                self.geometry_mapper.set_col_width
                if action == "col_resize"
                else self.geometry_mapper.set_row_height
            )
            for idx, size in cmd[f"{side}_sizes"].items():
                setter(idx, size)
            self._update_scrollbars()
            self.viewport().update()
            return

        cells = cmd.get(f"{side}_delta_cells")
        if cells is not None:
            for key, cell in cells.items():
                if cell is None:
                    self.model.cells.pop(key, None)
                else:
                    self.model.cells[key] = cell.clone()
        if f"{side}_merges" in cmd:
            self.model.merges = list(cmd[f"{side}_merges"])
        if hasattr(self.model, "links") and f"{side}_links" in cmd:
            self.model.links = [
                dict(lk) if isinstance(lk, dict) else lk for lk in cmd[f"{side}_links"]
            ]
        if hasattr(self.model, "comments") and f"{side}_comments" in cmd:
            self.model.comments = {
                k: CellComment(**v.__dict__) for k, v in cmd[f"{side}_comments"].items()
            }
        if action == "total_row":
            win = self.window()
            if hasattr(win, "_total_row_active"):
                active = cmd.get("active", True)
                win._total_row_active = (not active) if undo else active
                if hasattr(win, "action_registry"):
                    win.action_registry.set_checked("totalRow", win._total_row_active)
        if cmd.get(f"{side}_sel"):
            self.selection.restore_snapshot(cmd[f"{side}_sel"])
        if cells:
            self._recalculate()
        self.mark_dirty()
        self.viewport().update()

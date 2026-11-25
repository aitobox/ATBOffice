"""Mouse handling for the spreadsheet grid: selection, drags, auto-scroll, page breaks."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import (
    QPoint,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QToolTip,
)

from atboffice.core.i18n import safe_tr
from atboffice.modules.spreadsheet.calc.references import (
    range_name,
)
from atboffice.modules.spreadsheet.models.selection_model import (
    SelectionRange,
)
from atboffice.modules.spreadsheet.views.autofill import AutoFillEngine
from atboffice.platform.cursors import get_safe_cursor

if TYPE_CHECKING:
    pass
from atboffice.modules.spreadsheet.views.grid_types import (
    DragSnapshot,
    HitZone,
)


class GridMouseMixin:
    """Handles clicks, drags (move, fill, resize, page breaks) and auto-scroll."""

    def page_break_bounds(self) -> tuple[list[int], list[int]]:
        """Page start indices (+ end) for rows and columns, from the sheet's page setup."""
        from atboffice.modules.spreadsheet.printing.layout import paginate
        from atboffice.modules.spreadsheet.printing.setup import get_print_setup

        layout = paginate(self.model, get_print_setup(self.model))
        rows = sorted({p.rows[0] for p in layout.pages})
        cols = sorted({p.cols[0] for p in layout.pages})
        last_r = max(p.rows[1] for p in layout.pages) + 1
        last_c = max(p.cols[1] for p in layout.pages) + 1
        return rows + [last_r], cols + [last_c]

    def _page_break_hit(self, x: int, y: int) -> dict[str, Any] | None:
        """A page break line (row or column) within 3 px of grid point (x, y)."""
        if self._view_mode != "page_break":
            return None
        rows, cols = self.page_break_bounds()
        sx, sy = self.horizontalScrollBar().value(), self.verticalScrollBar().value()
        geo = self.geometry_mapper
        for idx in rows[1:-1]:
            if abs(self.col_header_height + geo.row_pos(idx) - sy - y) <= 3:
                return {"axis": "row", "index": idx, "target": idx}
        for idx in cols[1:-1]:
            if abs(self.row_header_width + geo.col_pos(idx) - sx - x) <= 3:
                return {"axis": "col", "index": idx, "target": idx}
        return None

    def _page_break_drag_to(self, x: int, y: int) -> None:
        drag = self._page_break_drag
        sx, sy = self.horizontalScrollBar().value(), self.verticalScrollBar().value()
        if drag["axis"] == "row":
            idx = self.geometry_mapper.find_row_at(max(0, y - self.col_header_height + sy))
            pos = self.geometry_mapper.row_pos(idx)
            nxt = self.geometry_mapper.row_pos(idx + 1)
            if y - self.col_header_height + sy > (pos + nxt) / 2:
                idx += 1
        else:
            idx = self.geometry_mapper.find_col_at(max(0, x - self.row_header_width + sx))
            pos = self.geometry_mapper.col_pos(idx)
            nxt = self.geometry_mapper.col_pos(idx + 1)
            if x - self.row_header_width + sx > (pos + nxt) / 2:
                idx += 1
        drag["target"] = max(1, idx)
        self.viewport().update()

    def finish_page_break_drag(self) -> bool:
        """Turn the dragged line into a manual break (moving it if it was manual)."""
        drag = getattr(self, "_page_break_drag", None)
        self._page_break_drag = None
        if drag is None or drag.get("target") is None:
            return False
        vs = self.model.view_state
        attr = "row_breaks" if drag["axis"] == "row" else "col_breaks"
        breaks = [b for b in getattr(vs, attr) if b != drag["index"]]
        if drag["target"] not in breaks:
            breaks.append(drag["target"])
        setattr(vs, attr, sorted(breaks))
        self.mark_dirty()
        self.viewport().update()
        return drag["target"] != drag["index"]

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
                    self.geometry_mapper.set_col_width(snap.resize_index, snap.resize_orig_size)
                self._update_scrollbars()
            elif snap.zone == HitZone.ROW_RESIZE:
                if self._resize_orig_sizes:
                    for r, sz in self._resize_orig_sizes.items():
                        self.geometry_mapper.set_row_height(r, sz)
                elif snap.resize_orig_sizes:
                    for r, sz in snap.resize_orig_sizes.items():
                        self.geometry_mapper.set_row_height(r, sz)
                elif snap.resize_index >= 0:
                    self.geometry_mapper.set_row_height(snap.resize_index, snap.resize_orig_size)
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
        if event.button() == Qt.MouseButton.LeftButton and self._view_mode == "page_break":
            gx, gy = self.map_from_device(event.position().x(), event.position().y())
            hit = self._page_break_hit(gx, gy)
            if hit is not None:
                self._page_break_drag = hit
                event.accept()
                return
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

            x, y = self.map_from_device(event.position().x(), event.position().y())
            hit = self.hit_test(x, y)

            if hit.zone == HitZone.CELL and hit.row is not None and hit.col is not None:
                if not self.selection.is_selected(hit.row, hit.col):
                    self.selection.select_cell(hit.row, hit.col)
            elif hit.zone == HitZone.COL_HEADER and hit.col is not None:
                pr = self.selection.primary_range
                is_whole_cols = pr.min_r == 0 and pr.max_r == self.selection.max_rows - 1
                if not (is_whole_cols and pr.min_c <= hit.col <= pr.max_c):
                    self.selection.select_cols(hit.col, hit.col)
            elif hit.zone == HitZone.ROW_HEADER and hit.row is not None:
                pr = self.selection.primary_range
                is_whole_rows = pr.min_c == 0 and pr.max_c == self.selection.max_cols - 1
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

        x, y = self.map_from_device(event.position().x(), event.position().y())

        # Check click on List Validation dropdown arrow button
        if self._dv_dropdown_rect is not None and self._dv_dropdown_rect.contains(int(x), int(y)):
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
            if self.editor_controller is not None and self.editor_controller.is_active:
                if not self.editor_controller.commit():
                    return
            self._drag_mode = HitZone.FILL_HANDLE
            self._fill_start_src = self.selection.primary_range
            self._fill_preview_range = self._fill_start_src
            self._fill_ctrl_pressed = bool(
                modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)
            )
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
                modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)
            )
            self._drag_snapshot = DragSnapshot(
                zone=HitZone.BORDER,
                sheet_index=getattr(self.model, "active_sheet_index", 0),
                selection_snapshot=self.selection.snapshot(),
                move_start_src=self._move_src_range,
                move_grab_cell=self._move_grab_cell,
            )
            self.viewport().setCursor(get_safe_cursor(Qt.CursorShape.SizeAllCursor))
            self.viewport().update()

        elif hit.zone == HitZone.FILTER_BUTTON and hit.col is not None:
            self._open_filter_dropdown(hit.col)
            return

        elif (
            hit.zone == HitZone.PIVOT_FILTER_BUTTON and hit.row is not None and hit.col is not None
        ):
            self._open_pivot_filter_dropdown(hit.row, hit.col)
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
                self.editor_controller.point_at(hit.row, hit.col, hit.row, hit.col)
                self.reveal(hit.row, hit.col)
                self.viewport().update()
                return

            self._drag_mode = HitZone.CELL
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self.selection.add_range(SelectionRange(hit.row, hit.col, hit.row, hit.col))
            elif modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.selection.extend_to(hit.row, hit.col)
            else:
                self.selection.select_cell(hit.row, hit.col)
            self.cell_selected.emit(hit.row, hit.col)
            self.pivot_selection_changed.emit(self.pivot_table_at(hit.row, hit.col))
            self.reveal(hit.row, hit.col)
            self.viewport().update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if getattr(self, "_page_break_drag", None) is not None:
            gx, gy = self.map_from_device(event.position().x(), event.position().y())
            self._page_break_drag_to(gx, gy)
            event.accept()
            return
        if self._view_mode == "page_break" and not event.buttons():
            gx, gy = self.map_from_device(event.position().x(), event.position().y())
            hit = self._page_break_hit(gx, gy)
            if hit is not None:
                self.viewport().setCursor(
                    Qt.CursorShape.SizeVerCursor
                    if hit["axis"] == "row"
                    else Qt.CursorShape.SizeHorCursor
                )
        if self.model is None or self.selection is None:
            event.ignore()
            return
        x, y = self.map_from_device(event.position().x(), event.position().y())
        self._last_mouse_pos = QPoint(x, y)

        # Update cursor when hovering
        if self._drag_mode == HitZone.NONE:
            hit = self.hit_test(x, y)
            if hit.zone == HitZone.FILL_HANDLE:
                self.viewport().setCursor(Qt.CursorShape.CrossCursor)
            elif hit.zone == HitZone.BORDER:
                self.viewport().setCursor(get_safe_cursor(Qt.CursorShape.SizeAllCursor))
            elif hit.zone == HitZone.COL_RESIZE:
                self.viewport().setCursor(Qt.CursorShape.SplitHCursor)
            elif hit.zone == HitZone.ROW_RESIZE:
                self.viewport().setCursor(Qt.CursorShape.SplitVCursor)
            elif hit.zone in (HitZone.COL_HEADER, HitZone.ROW_HEADER):
                self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

            # Check comment tooltip hover and callout card
            if hit.row is not None and hit.col is not None:
                cm = (
                    self.model.get_comment(hit.row, hit.col)
                    if hasattr(self.model, "get_comment")
                    else None
                )
                new_hover = (hit.row, hit.col) if cm is not None else None
                # The painted callout shows the note; a system tooltip would
                # duplicate it in the (possibly dark) platform palette.
                QToolTip.hideText()
            else:
                new_hover = None
                QToolTip.hideText()

            if self._hover_comment_cell != new_hover:
                self._hover_comment_cell = new_hover
                self.viewport().update()
            return

        # 1. Lost capture check: left button not pressed while in drag mode
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            self.cancel_drag(why="lost")
            return

        # 2. A drag without a recorded origin is stale (e.g. interrupted by a sheet switch).
        if self._drag_start_pos is None and not self._drag_moved:
            self.cancel_drag(why="lost")
            return

        # 3px threshold
        if not self._drag_moved:
            if self._drag_start_pos is not None:
                dx = x - self._drag_start_pos.x()
                dy = y - self._drag_start_pos.y()
                if math.hypot(dx, dy) < self._drag_threshold:
                    return
                self._drag_moved = True

        # 3. Auto-scroll boundary check
        vw, vh = self._view_size()

        fz_r_h = self.geometry_mapper.row_pos(self.freeze_rows) if self.freeze_rows > 0 else 0
        fz_c_w = self.geometry_mapper.col_pos(self.freeze_cols) if self.freeze_cols > 0 else 0

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
                modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)
            )
            hit = self.hit_test(x, y)
            row = hit.row
            col = hit.col
            if row is None:
                sheet_y = max(0, self.verticalScrollBar().value() + (y - self.col_header_height))
                row = self.geometry_mapper.find_row_at(sheet_y)
            if col is None:
                sheet_x = max(0, self.horizontalScrollBar().value() + (x - self.row_header_width))
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
                    self.viewport().mapToGlobal(self.map_to_device(QPoint(x, y)) + QPoint(14, 18)),
                    tip,
                    self.viewport(),
                )
                self.reveal(row, col)
                self.viewport().update()

        elif self._drag_mode == HitZone.COL_RESIZE:
            delta = x - self._resize_start_pos
            base_w = self._resize_orig_sizes.get(self._resize_index, self._resize_orig_size)
            new_w = max(0, base_w + delta)
            self._resize_preview_size = new_w
            self._resize_preview_pos = x
            for c in self._resize_targets:
                self.geometry_mapper.set_col_width(c, new_w)
            self._update_scrollbars()
            tip = safe_tr("宽度: {0} 像素").format(new_w)
            QToolTip.showText(
                self.viewport().mapToGlobal(self.map_to_device(QPoint(x, 0)) + QPoint(14, 18)),
                tip,
                self.viewport(),
            )
            self.viewport().update()

        elif self._drag_mode == HitZone.ROW_RESIZE:
            delta = y - self._resize_start_pos
            base_h = self._resize_orig_sizes.get(self._resize_index, self._resize_orig_size)
            new_h = max(0, base_h + delta)
            self._resize_preview_size = new_h
            self._resize_preview_pos = y
            for r in self._resize_targets:
                self.geometry_mapper.set_row_height(r, new_h)
            self._update_scrollbars()
            tip = safe_tr("高度: {0} 像素").format(new_h)
            QToolTip.showText(
                self.viewport().mapToGlobal(self.map_to_device(QPoint(0, y)) + QPoint(14, 18)),
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
                sheet_x = max(0, self.horizontalScrollBar().value() + (x - self.row_header_width))
                target_c = self.geometry_mapper.find_col_at(sheet_x)
            orig_c = (
                self._header_drag_anchor
                if self._header_drag_anchor >= 0
                else (
                    self._drag_snapshot.selection_snapshot.get("anchor_cell", (0, target_c))[1]
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
                sheet_y = max(0, self.verticalScrollBar().value() + (y - self.col_header_height))
                target_r = self.geometry_mapper.find_row_at(sheet_y)
            orig_r = (
                self._header_drag_anchor
                if self._header_drag_anchor >= 0
                else (
                    self._drag_snapshot.selection_snapshot.get("anchor_cell", (target_r, 0))[0]
                    if self._drag_snapshot is not None
                    else target_r
                )
            )
            self.selection.select_rows(orig_r, target_r)
            self.reveal(target_r, 0)
            self.viewport().update()

        elif self._drag_mode == HitZone.BORDER:
            self._move_ctrl_pressed = bool(
                modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)
            )
            sheet_x = max(0, self.horizontalScrollBar().value() + (x - self.row_header_width))
            sheet_y = max(0, self.verticalScrollBar().value() + (y - self.col_header_height))
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
                    self.viewport().mapToGlobal(self.map_to_device(QPoint(x, y)) + QPoint(14, 18)),
                    tip,
                    self.viewport(),
                )
                self.reveal(to_r1, to_c1)
                self.viewport().update()

    def leaveEvent(self, event: Any) -> None:
        """Clear comment hover callout when mouse leaves the viewport."""
        if self._hover_comment_cell is not None:
            self._hover_comment_cell = None
            self.viewport().update()
        if event is not None:
            super().leaveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if getattr(self, "_page_break_drag", None) is not None:
            self.finish_page_break_drag()
            event.accept()
            return
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

                # Check worksheet protection before applying changes
                if self.guard_protect(cell_edit=True):
                    self._fill_start_src = None
                    self._fill_preview_range = None
                    self._drag_mode = HitZone.NONE
                    self._drag_moved = False
                    self.viewport().update()
                    return

                ctrl = self._fill_ctrl_pressed or bool(
                    event.modifiers()
                    & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)
                )
                single = src.min_r == src.max_r and src.min_c == src.max_c
                fill_mode = "linear" if (ctrl and single) else ("copy" if ctrl else "auto")

                # Capture sparse delta bounding box (prevents whole-sheet memory spike)
                min_r = min(src.min_r, dest.min_r)
                max_r = max(src.max_r, dest.max_r)
                min_c = min(src.min_c, dest.min_c)
                max_c = max(src.max_c, dest.max_c)
                affected_coords = [
                    (r, c) for r in range(min_r, max_r + 1) for c in range(min_c, max_c + 1)
                ]
                before_delta = {
                    (r, c): (
                        self.model.get_cell(r, c).clone() if self.model.get_cell(r, c) else None
                    )
                    for (r, c) in affected_coords
                }
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

                after_delta = {
                    (r, c): (
                        self.model.get_cell(r, c).clone() if self.model.get_cell(r, c) else None
                    )
                    for (r, c) in affected_coords
                }
                after_sel = self.selection.snapshot()

                self._record_entry(
                    {
                        "action": "autofill",
                        "affected_coords": affected_coords,
                        "before_delta_cells": before_delta,
                        "after_delta_cells": after_delta,
                        "before_sel": before_sel,
                        "after_sel": after_sel,
                    }
                )
                self.mark_dirty()
                if hasattr(self.model, "recalculate"):
                    self.model.recalculate()
                elif (
                    hasattr(self, "workbook")
                    and self.workbook
                    and hasattr(self.workbook, "recalculate")
                ):
                    self.workbook.recalculate()
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
                self._record_entry(
                    {
                        "action": "col_resize",
                        "targets": list(self._resize_targets),
                        "before_sizes": before_sizes,
                        "after_sizes": after_sizes,
                    }
                )
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
                self._record_entry(
                    {
                        "action": "row_resize",
                        "targets": list(self._resize_targets),
                        "before_sizes": before_sizes,
                        "after_sizes": after_sizes,
                    }
                )
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
                    & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)
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
        x, y = self.map_from_device(event.position().x(), event.position().y())
        hit = self.hit_test(x, y)

        if hit.zone == HitZone.COL_RESIZE and hit.col is not None:
            self.auto_fit_column(hit.col)
        elif hit.zone == HitZone.FILL_HANDLE:
            self.fill_down_to_data()
        elif hit.zone == HitZone.BORDER and len(self.selection.ranges) == 1:
            pr = self.selection.primary_range
            sx = self.horizontalScrollBar().value()
            sy = self.verticalScrollBar().value()
            bx1 = self.row_header_width + self.geometry_mapper.col_pos(pr.min_c) - sx
            bx2 = self.row_header_width + self.geometry_mapper.col_pos(pr.max_c + 1) - sx
            by1 = self.col_header_height + self.geometry_mapper.row_pos(pr.min_r) - sy
            by2 = self.col_header_height + self.geometry_mapper.row_pos(pr.max_r + 1) - sy
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

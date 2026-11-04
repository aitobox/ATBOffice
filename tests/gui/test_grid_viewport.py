"""GUI tests for virtualized GridViewport."""

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.models.selection_model import (
    SelectionRange,
)
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport, HitZone
from atboffice.platform.cursors import get_safe_cursor


@pytest.fixture
def viewport(qapp: QApplication) -> GridViewport:
    model = SheetDataModel()
    vp = GridViewport(model=model)
    vp.resize(800, 600)
    return vp


class TestGridViewportInitialization:
    def test_init_and_retranslate(self, viewport: GridViewport) -> None:
        assert viewport.model is not None
        assert viewport.selection is not None
        assert viewport.geometry_mapper is not None
        viewport.retranslate_ui()


class TestCoordinateAndHitTesting:
    def test_hit_corner(self, viewport: GridViewport) -> None:
        # Corner box is 0..row_header_width, 0..col_header_height
        res = viewport.hit_test(10, 10)
        assert res.zone == HitZone.CORNER

    def test_hit_col_header(self, viewport: GridViewport) -> None:
        # Above col_header_height, right of row_header_width
        x = viewport.row_header_width + 20
        y = 10
        res = viewport.hit_test(x, y)
        assert res.zone == HitZone.COL_HEADER
        assert res.col == 0

    def test_hit_col_resize(self, viewport: GridViewport) -> None:
        # Right border of column 0
        w0 = viewport.geometry_mapper.col_size(0)
        border_x = viewport.row_header_width + w0
        res = viewport.hit_test(border_x, 10)
        assert res.zone == HitZone.COL_RESIZE
        assert res.col == 0

    def test_hit_row_header(self, viewport: GridViewport) -> None:
        # Left of row_header_width, below col_header_height
        x = 10
        y = viewport.col_header_height + 10
        res = viewport.hit_test(x, y)
        assert res.zone == HitZone.ROW_HEADER
        assert res.row == 0

    def test_hit_cell(self, viewport: GridViewport) -> None:
        x = viewport.row_header_width + 10
        y = viewport.col_header_height + 10
        res = viewport.hit_test(x, y)
        assert res.zone == HitZone.CELL
        assert (res.row, res.col) == (0, 0)


class TestMouseSelectionInteractions:
    def test_click_select_cell(self, viewport: GridViewport) -> None:
        x = viewport.row_header_width + 100
        y = viewport.col_header_height + 50
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(x, y),
            QPointF(x, y),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(event)
        target_cell = viewport.cell_at_pos(x, y)
        assert viewport.selection.active_cell == target_cell

    def test_click_col_header_selects_column(self, viewport: GridViewport) -> None:
        x = viewport.row_header_width + 20
        y = 10
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(x, y),
            QPointF(x, y),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(event)
        assert viewport.selection.is_col_selected(0)
        assert viewport.selection.ranges[0].min_c == 0
        assert viewport.selection.ranges[0].max_c == 0

    def test_click_row_header_selects_row(self, viewport: GridViewport) -> None:
        x = 10
        y = viewport.col_header_height + 10
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(x, y),
            QPointF(x, y),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(event)
        assert viewport.selection.is_row_selected(0)
        assert viewport.selection.ranges[0].min_r == 0
        assert viewport.selection.ranges[0].max_r == 0

    def test_click_corner_selects_all(self, viewport: GridViewport) -> None:
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(5, 5),
            QPointF(5, 5),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(event)
        assert viewport.selection.ranges[0].min_r == 0
        assert viewport.selection.ranges[0].min_c == 0
        assert viewport.selection.is_selected(100, 50)


class TestColumnAutoFitAndResize:
    def test_resize_column(self, viewport: GridViewport) -> None:
        viewport.geometry_mapper.set_col_width(0, 120)
        assert viewport.geometry_mapper.col_size(0) == 120

    def test_autofit_column(self, viewport: GridViewport) -> None:
        viewport.model.set_cell(
            0, 0, CellData(value="Super Long Text Content That Requires Wider Column")
        )
        orig_w = viewport.geometry_mapper.col_size(0)
        viewport.auto_fit_column(0)
        new_w = viewport.geometry_mapper.col_size(0)
        assert new_w > orig_w


class TestTextRightOverflow:
    def test_overflow_calculation_empty_neighbor(self, viewport: GridViewport) -> None:
        # Cell (0, 0) has long text, cell (0, 1) is empty
        viewport.model.set_cell(
            0, 0, CellData(value="Very long text overflowing into empty neighbors")
        )
        # Check right overflow column span
        span = viewport.calculate_overflow_span(0, 0, text_width=180, col_width=64)
        assert span >= 2  # can overflow into column 1 and beyond

    def test_overflow_blocked_by_occupied_neighbor(self, viewport: GridViewport) -> None:
        viewport.model.set_cell(0, 0, CellData(value="Very long text"))
        viewport.model.set_cell(0, 1, CellData(value="Blocked!"))
        span = viewport.calculate_overflow_span(0, 0, text_width=180, col_width=64)
        assert span == 1  # Strictly blocked to column 0


class TestKeyboardNavigation:
    def test_arrow_keys(self, viewport: GridViewport) -> None:
        viewport.selection.select_cell(0, 0)
        event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Down,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.keyPressEvent(event)
        assert viewport.selection.active_cell == (1, 0)

        event_right = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Right,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.keyPressEvent(event_right)
        assert viewport.selection.active_cell == (1, 1)

    def test_ctrl_a_select_all(self, viewport: GridViewport) -> None:
        viewport.selection.select_cell(2, 2)
        event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_A,
            Qt.KeyboardModifier.ControlModifier,
        )
        viewport.keyPressEvent(event)
        assert viewport.selection.is_selected(0, 0)
        assert viewport.selection.is_selected(999, 100)


class TestDragLifecycleAndCancellation:
    def test_drag_threshold_3px(self, viewport: GridViewport) -> None:
        viewport.selection.select_cell(1, 1)
        r1_rect = viewport.cell_rect(1, 1)
        start_x = r1_rect.center().x()
        start_y = r1_rect.center().y()

        # Mouse press
        press_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(start_x, start_y),
            QPointF(start_x, start_y),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(press_event)
        assert viewport.is_dragging
        assert not viewport.has_drag_moved

        # Micro-move 1px: distance < 3px
        move_1px = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(start_x + 1, start_y + 1),
            QPointF(start_x + 1, start_y + 1),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move_1px)
        assert not viewport.has_drag_moved
        # Selection should still be single cell (1, 1)
        assert viewport.selection.primary_range.min_r == 1
        assert viewport.selection.primary_range.max_r == 1

        # Move 10px to cell (2, 2): distance >= 3px
        r2_rect = viewport.cell_rect(2, 2)
        move_dest = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(r2_rect.center().x(), r2_rect.center().y()),
            QPointF(r2_rect.center().x(), r2_rect.center().y()),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move_dest)
        assert viewport.has_drag_moved
        assert viewport.selection.primary_range.max_r == 2
        assert viewport.selection.primary_range.max_c == 2

    def test_drag_cancel_escape(self, viewport: GridViewport) -> None:
        viewport.selection.select_cell(1, 1)
        r1_rect = viewport.cell_rect(1, 1)
        r3_rect = viewport.cell_rect(3, 3)

        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(r1_rect.center().x(), r1_rect.center().y()),
            QPointF(r1_rect.center().x(), r1_rect.center().y()),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(press)

        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(r3_rect.center().x(), r3_rect.center().y()),
            QPointF(r3_rect.center().x(), r3_rect.center().y()),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move)
        assert viewport.selection.primary_range.max_r == 3

        # Press Escape key
        esc_event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.keyPressEvent(esc_event)

        assert not viewport.is_dragging
        # Selection must be restored to (1, 1)
        pr = viewport.selection.primary_range
        assert (pr.min_r, pr.min_c, pr.max_r, pr.max_c) == (1, 1, 1, 1)

    def test_drag_cancel_focus_out(self, viewport: GridViewport) -> None:
        from PySide6.QtGui import QFocusEvent

        viewport.selection.select_cell(1, 1)
        r1_rect = viewport.cell_rect(1, 1)
        r3_rect = viewport.cell_rect(3, 3)

        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(r1_rect.center().x(), r1_rect.center().y()),
            QPointF(r1_rect.center().x(), r1_rect.center().y()),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(press)

        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(r3_rect.center().x(), r3_rect.center().y()),
            QPointF(r3_rect.center().x(), r3_rect.center().y()),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move)
        assert viewport.is_dragging

        # Focus out
        focus_event = QFocusEvent(QFocusEvent.Type.FocusOut)
        viewport.focusOutEvent(focus_event)

        assert not viewport.is_dragging
        pr = viewport.selection.primary_range
        assert (pr.min_r, pr.min_c, pr.max_r, pr.max_c) == (1, 1, 1, 1)

    def test_drag_cancel_second_button(self, viewport: GridViewport) -> None:
        from PySide6.QtGui import QContextMenuEvent

        viewport.selection.select_cell(1, 1)
        r1_rect = viewport.cell_rect(1, 1)
        r3_rect = viewport.cell_rect(3, 3)

        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(r1_rect.center().x(), r1_rect.center().y()),
            QPointF(r1_rect.center().x(), r1_rect.center().y()),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(press)

        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(r3_rect.center().x(), r3_rect.center().y()),
            QPointF(r3_rect.center().x(), r3_rect.center().y()),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move)

        # Right click while left dragging
        right_press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(r3_rect.center().x(), r3_rect.center().y()),
            QPointF(r3_rect.center().x(), r3_rect.center().y()),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(right_press)

        assert not viewport.is_dragging
        pr = viewport.selection.primary_range
        assert (pr.min_r, pr.min_c, pr.max_r, pr.max_c) == (1, 1, 1, 1)

        # Context menu event should be swallowed
        menu_event = QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse,
            r3_rect.center(),
            viewport.viewport().mapToGlobal(r3_rect.center()),
        )
        viewport.contextMenuEvent(menu_event)
        # Should be accepted and swallowed (no crash, flag cleared)
        assert menu_event.isAccepted()

    def test_drag_cancel_lost_capture(self, viewport: GridViewport) -> None:
        viewport.selection.select_cell(1, 1)
        r1_rect = viewport.cell_rect(1, 1)
        r2_rect = viewport.cell_rect(2, 2)

        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(r1_rect.center().x(), r1_rect.center().y()),
            QPointF(r1_rect.center().x(), r1_rect.center().y()),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(press)

        # Move without LeftButton held (lost release/capture)
        move_lost = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(r2_rect.center().x(), r2_rect.center().y()),
            QPointF(r2_rect.center().x(), r2_rect.center().y()),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,  # No button held
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move_lost)

        assert not viewport.is_dragging
        pr = viewport.selection.primary_range
        assert (pr.min_r, pr.min_c, pr.max_r, pr.max_c) == (1, 1, 1, 1)

    def test_drag_cancel_resize(self, viewport: GridViewport) -> None:
        orig_w = viewport.geometry_mapper.col_size(0)
        col_end_x = viewport.row_header_width + orig_w

        # Press on col resize boundary
        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(col_end_x, 10),
            QPointF(col_end_x, 10),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(press)
        assert viewport.is_dragging

        # Move to resize
        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(col_end_x + 50, 10),
            QPointF(col_end_x + 50, 10),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move)
        assert viewport.geometry_mapper.col_size(0) == orig_w + 50

        # Press Escape
        esc_event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.keyPressEvent(esc_event)

        assert not viewport.is_dragging
        # Size restored
        assert viewport.geometry_mapper.col_size(0) == orig_w

    def test_drag_cancel_autofill(self, viewport: GridViewport) -> None:
        viewport.model.set_cell(1, 1, CellData(value=10))
        viewport.model.set_cell(2, 1, CellData(value=None))
        viewport.selection.select_cell(1, 1)

        # Find fill handle pos
        fh_rect = viewport._get_fill_handle_rect()
        assert fh_rect is not None

        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(fh_rect.center().x(), fh_rect.center().y()),
            QPointF(fh_rect.center().x(), fh_rect.center().y()),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(press)
        assert viewport.is_dragging

        # Move to row 3
        r3_rect = viewport.cell_rect(3, 1)
        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(r3_rect.center().x(), r3_rect.center().y()),
            QPointF(r3_rect.center().x(), r3_rect.center().y()),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move)
        assert viewport.has_autofill_preview

        # Cancel via Escape
        esc_event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.keyPressEvent(esc_event)

        assert not viewport.is_dragging
        assert not viewport.has_autofill_preview
        # Cells below must remain uncommitted
        c2 = viewport.model.get_cell(2, 1)
        assert c2 is None or c2.value is None
        c3 = viewport.model.get_cell(3, 1)
        assert c3 is None or c3.value is None

    def test_drag_autoscroll_timer_cleanup(self, viewport: GridViewport) -> None:
        viewport.selection.select_cell(1, 1)
        r1_rect = viewport.cell_rect(1, 1)

        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(r1_rect.center().x(), r1_rect.center().y()),
            QPointF(r1_rect.center().x(), r1_rect.center().y()),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(press)

        # Move past bottom edge of viewport
        vp_h = viewport.viewport().height()
        move_outside = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(r1_rect.center().x(), vp_h + 50),
            QPointF(r1_rect.center().x(), vp_h + 50),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move_outside)

        assert viewport.is_auto_scrolling

        # Release mouse
        release = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(r1_rect.center().x(), vp_h + 50),
            QPointF(r1_rect.center().x(), vp_h + 50),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseReleaseEvent(release)

        assert not viewport.is_dragging
        assert not viewport.is_auto_scrolling

    def test_right_click_does_not_drag(self, viewport: GridViewport) -> None:
        r1_rect = viewport.cell_rect(1, 1)

        right_press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(r1_rect.center().x(), r1_rect.center().y()),
            QPointF(r1_rect.center().x(), r1_rect.center().y()),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(right_press)

        assert not viewport.is_dragging

        # Move with right button held
        right_move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(r1_rect.center().x() + 50, r1_rect.center().y() + 50),
            QPointF(r1_rect.center().x() + 50, r1_rect.center().y() + 50),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(right_move)

        assert not viewport.is_dragging


class TestSelectionBorderDragAndDrop:
    """Parity tests for Ledger selection border dragging, moving, and copying."""

    def test_border_hit_test(self, viewport: GridViewport) -> None:
        viewport.selection.select_cell(1, 1)
        viewport.selection.extend_to(3, 3)  # B2:D4

        pr = viewport.selection.primary_range
        sx = viewport.horizontalScrollBar().value()
        sy = viewport.verticalScrollBar().value()
        x1 = viewport.row_header_width + viewport.geometry_mapper.col_pos(pr.min_c) - sx
        x2 = viewport.row_header_width + viewport.geometry_mapper.col_pos(pr.max_c + 1) - sx
        y1 = viewport.col_header_height + viewport.geometry_mapper.row_pos(pr.min_r) - sy
        y2 = viewport.col_header_height + viewport.geometry_mapper.row_pos(pr.max_r + 1) - sy

        mid_x = (x1 + x2) // 2
        mid_y = (y1 + y2) // 2

        # Top border
        hit_top = viewport.hit_test(mid_x, y1)
        assert hit_top.zone == HitZone.BORDER

        # Bottom border (away from bottom-right fill handle)
        hit_bottom = viewport.hit_test(x1 + 10, y2)
        assert hit_bottom.zone == HitZone.BORDER

        # Left border
        hit_left = viewport.hit_test(x1, mid_y)
        assert hit_left.zone == HitZone.BORDER

        # Right border
        hit_right = viewport.hit_test(x2, mid_y)
        assert hit_right.zone == HitZone.BORDER

        # Fill handle at (x2, y2)
        hit_fill = viewport.hit_test(x2, y2)
        assert hit_fill.zone == HitZone.FILL_HANDLE

        # Cell interior
        hit_interior = viewport.hit_test(mid_x, mid_y)
        assert hit_interior.zone == HitZone.CELL

        # Cursor update on hover
        hover_event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(mid_x, y1),
            QPointF(mid_x, y1),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(hover_event)
        assert viewport.viewport().cursor().shape() == get_safe_cursor(Qt.CursorShape.SizeAllCursor)

    def test_border_drag_preview_and_esc_cancel(self, viewport: GridViewport) -> None:
        viewport.selection.select_cell(1, 1)
        viewport.selection.extend_to(2, 2)  # B2:C3

        pr = viewport.selection.primary_range
        sx = viewport.horizontalScrollBar().value()
        sy = viewport.verticalScrollBar().value()
        x1 = viewport.row_header_width + viewport.geometry_mapper.col_pos(pr.min_c) - sx
        y1 = viewport.col_header_height + viewport.geometry_mapper.row_pos(pr.min_r) - sy
        grab_x = x1 + 10

        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(grab_x, y1),
            QPointF(grab_x, y1),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(press)
        assert viewport.is_dragging
        assert viewport._drag_mode == HitZone.BORDER

        # Move > 3px threshold
        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(grab_x + 50, y1 + 50),
            QPointF(grab_x + 50, y1 + 50),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move)
        assert viewport.has_drag_moved
        assert viewport.has_move_preview

        # Esc key cancels drag
        esc_event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.keyPressEvent(esc_event)
        assert not viewport.is_dragging
        assert not viewport.has_move_preview
        assert viewport.selection.primary_range == pr

    def test_border_move_empty_destination(self, viewport: GridViewport) -> None:
        viewport.model.set_cell_value(1, 1, "Hello")
        viewport.model.set_cell_value(1, 2, 123)
        viewport.selection.select_cell(1, 1)
        viewport.selection.extend_to(1, 2)  # B2:C2

        pr = viewport.selection.primary_range
        sx = viewport.horizontalScrollBar().value()
        sy = viewport.verticalScrollBar().value()
        x1 = viewport.row_header_width + viewport.geometry_mapper.col_pos(pr.min_c) - sx
        y1 = viewport.col_header_height + viewport.geometry_mapper.row_pos(pr.min_r) - sy
        grab_x = x1 + 10

        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(grab_x, y1),
            QPointF(grab_x, y1),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(press)

        # Target cell D4 (row 3, col 3)
        dest_rect = viewport.cell_rect(3, 3)
        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(dest_rect.center().x(), dest_rect.center().y()),
            QPointF(dest_rect.center().x(), dest_rect.center().y()),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move)

        release = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(dest_rect.center().x(), dest_rect.center().y()),
            QPointF(dest_rect.center().x(), dest_rect.center().y()),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseReleaseEvent(release)

        # Source cells cleared
        assert viewport.model.get_cell_value(1, 1) is None
        assert viewport.model.get_cell_value(1, 2) is None

        # Destination cells populated
        assert viewport.model.get_cell_value(3, 3) == "Hello"
        assert viewport.model.get_cell_value(3, 4) == 123

        # Selection updated
        new_pr = viewport.selection.primary_range
        assert (new_pr.min_r, new_pr.min_c, new_pr.max_r, new_pr.max_c) == (3, 3, 3, 4)

    def test_border_move_overlapping(self, viewport: GridViewport) -> None:
        viewport.model.set_cell_value(0, 0, 10)
        viewport.model.set_cell_value(1, 0, 20)
        viewport.selection.select_cell(0, 0)
        viewport.selection.extend_to(1, 0)  # A1:A2

        # Move A1:A2 down by 1 row to A2:A3
        dest = viewport.selection.primary_range
        target = viewport.selection.primary_range.__class__(1, 0, 2, 0)
        viewport.move_range(dest, target, copy=False)

        assert viewport.model.get_cell_value(0, 0) is None
        assert viewport.model.get_cell_value(1, 0) == 10
        assert viewport.model.get_cell_value(2, 0) == 20

    def test_border_copy_ctrl(self, viewport: GridViewport) -> None:
        viewport.model.set_cell_value(0, 0, 42)
        viewport.selection.select_cell(0, 0)

        pr = viewport.selection.primary_range
        sx = viewport.horizontalScrollBar().value()
        sy = viewport.verticalScrollBar().value()
        x1 = viewport.row_header_width + viewport.geometry_mapper.col_pos(pr.min_c) - sx
        y1 = viewport.col_header_height + viewport.geometry_mapper.row_pos(pr.min_r) - sy

        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(x1, y1),
            QPointF(x1, y1),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.ControlModifier,
        )
        viewport.mousePressEvent(press)

        dest_rect = viewport.cell_rect(0, 1)
        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(dest_rect.center().x(), dest_rect.center().y()),
            QPointF(dest_rect.center().x(), dest_rect.center().y()),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.ControlModifier,
        )
        viewport.mouseMoveEvent(move)

        release = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(dest_rect.center().x(), dest_rect.center().y()),
            QPointF(dest_rect.center().x(), dest_rect.center().y()),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.ControlModifier,
        )
        viewport.mouseReleaseEvent(release)

        # Both source and destination retain values in copy mode
        assert viewport.model.get_cell_value(0, 0) == 42
        assert viewport.model.get_cell_value(0, 1) == 42

    def test_border_overwrite_confirmation(
        self, viewport: GridViewport, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from PySide6.QtWidgets import QMessageBox

        viewport.model.set_cell_value(0, 0, "Source")
        viewport.model.set_cell_value(0, 1, "Existing")
        viewport.selection.select_cell(0, 0)

        # 1. Cancel confirmation -> no change
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Cancel,
        )

        dest_rect = viewport.cell_rect(0, 1)
        pr = viewport.selection.primary_range
        sx = viewport.horizontalScrollBar().value()
        sy = viewport.verticalScrollBar().value()
        x1 = viewport.row_header_width + viewport.geometry_mapper.col_pos(pr.min_c) - sx
        y1 = viewport.col_header_height + viewport.geometry_mapper.row_pos(pr.min_r) - sy

        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(x1, y1),
            QPointF(x1, y1),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(press)

        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(dest_rect.center().x(), dest_rect.center().y()),
            QPointF(dest_rect.center().x(), dest_rect.center().y()),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move)

        release = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(dest_rect.center().x(), dest_rect.center().y()),
            QPointF(dest_rect.center().x(), dest_rect.center().y()),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseReleaseEvent(release)

        assert viewport.model.get_cell_value(0, 0) == "Source"
        assert viewport.model.get_cell_value(0, 1) == "Existing"

        # 2. Accept confirmation -> overwritten
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
        )

        viewport.mousePressEvent(press)
        viewport.mouseMoveEvent(move)
        viewport.mouseReleaseEvent(release)

        assert viewport.model.get_cell_value(0, 0) is None
        assert viewport.model.get_cell_value(0, 1) == "Source"

    def test_border_move_formulas(self, viewport: GridViewport) -> None:
        viewport.model.set_cell_value(0, 0, 10)
        c_b1 = CellData(value=20, formula="=A1*2")
        viewport.model.set_cell(0, 1, c_b1)
        c_c1 = CellData(value=15, formula="=A1+5")
        viewport.model.set_cell(0, 2, c_c1)

        viewport.selection.select_cell(0, 0)
        viewport.selection.extend_to(0, 1)  # A1:B1

        # Move A1:B1 down to A2:B2 (row 1)
        src = viewport.selection.primary_range
        to = src.__class__(1, 0, 1, 1)
        viewport.move_range(src, to, copy=False)

        # Internal formula in B2 should now point to A2
        cell_b2 = viewport.model.get_cell(1, 1)
        assert cell_b2 is not None
        assert cell_b2.formula is not None
        assert "A2" in cell_b2.formula

        # External formula in C1 referencing moved A1 should follow to A2
        cell_c1 = viewport.model.get_cell(0, 2)
        assert cell_c1 is not None
        assert cell_c1.formula is not None
        assert "A2" in cell_c1.formula

    def test_border_move_merged_cells(self, viewport: GridViewport) -> None:
        viewport.model.set_cell_value(0, 0, "Header")
        viewport.model.merges.append((0, 0, 0, 1))  # Merge A1:B1
        viewport.selection.select_cell(0, 0)
        viewport.selection.extend_to(0, 1)

        src = viewport.selection.primary_range
        to = src.__class__(2, 2, 2, 3)  # Move to C3:D3
        viewport.move_range(src, to, copy=False)

        assert (0, 0, 0, 1) not in viewport.model.merges
        assert (2, 2, 2, 3) in viewport.model.merges
        assert viewport.model.get_cell_value(2, 2) == "Header"

    def test_border_undo_redo(self, viewport: GridViewport) -> None:
        viewport.model.set_cell_value(0, 0, "A")
        viewport.model.set_cell_value(1, 0, "B")
        viewport.selection.select_cell(0, 0)
        viewport.selection.extend_to(1, 0)  # A1:A2

        src = viewport.selection.primary_range
        to = src.__class__(0, 2, 1, 2)  # C1:C2
        viewport.move_range(src, to, copy=False)

        assert viewport.model.get_cell_value(0, 0) is None
        assert viewport.model.get_cell_value(1, 0) is None
        assert viewport.model.get_cell_value(0, 2) == "A"
        assert viewport.model.get_cell_value(1, 2) == "B"

        # Undo
        viewport.undo()
        assert viewport.model.get_cell_value(0, 0) == "A"
        assert viewport.model.get_cell_value(1, 0) == "B"
        assert viewport.model.get_cell_value(0, 2) is None
        assert viewport.model.get_cell_value(1, 2) is None

        # Redo
        viewport.redo()
        assert viewport.model.get_cell_value(0, 0) is None
        assert viewport.model.get_cell_value(1, 0) is None
        assert viewport.model.get_cell_value(0, 2) == "A"
        assert viewport.model.get_cell_value(1, 2) == "B"

    def test_border_protection_blocks_move(
        self, viewport: GridViewport, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from PySide6.QtWidgets import QMessageBox
        monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

        viewport.model.set_cell_value(0, 0, 999)
        viewport.model.protected = True
        viewport.selection.select_cell(0, 0)

        src = viewport.selection.primary_range
        to = src.__class__(1, 1, 1, 1)
        viewport.move_range(src, to, copy=False)

        # Not moved because sheet is protected
        assert viewport.model.get_cell_value(0, 0) == 999
        assert viewport.model.get_cell_value(1, 1) is None


class TestAutoFillInteractionsAndUndoRedo:
    def test_autofill_drag_down_and_undo_redo(self, viewport: GridViewport) -> None:
        viewport.model.set_cell(0, 0, CellData(value=10))
        viewport.model.set_cell(1, 0, CellData(value=20))
        viewport.selection.select_cell(0, 0)
        viewport.selection.extend_to(1, 0)  # A1:A2

        handle_rect = viewport._get_fill_handle_rect()
        assert handle_rect is not None
        hx, hy = handle_rect.center().x(), handle_rect.center().y()

        # 1. Press on fill handle
        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(hx, hy),
            QPointF(hx, hy),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(press)
        assert viewport.is_dragging
        assert viewport._drag_mode == HitZone.FILL_HANDLE

        # 2. Drag down to cell (3, 0) -> A4
        c3_rect = viewport.cell_rect(3, 0)
        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(c3_rect.center().x(), c3_rect.center().y()),
            QPointF(c3_rect.center().x(), c3_rect.center().y()),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move)
        assert viewport.has_drag_moved
        assert viewport.has_autofill_preview
        assert viewport._fill_preview_range == SelectionRange(0, 0, 3, 0)

        # 3. Release mouse to commit autofill
        release = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(c3_rect.center().x(), c3_rect.center().y()),
            QPointF(c3_rect.center().x(), c3_rect.center().y()),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseReleaseEvent(release)
        assert not viewport.is_dragging
        assert viewport.model.get_cell_value(2, 0) == 30
        assert viewport.model.get_cell_value(3, 0) == 40
        assert viewport.selection.primary_range == SelectionRange(0, 0, 3, 0)

        # 4. Undo restores pre-fill state
        viewport.undo()
        assert viewport.model.get_cell_value(0, 0) == 10
        assert viewport.model.get_cell_value(1, 0) == 20
        assert viewport.model.get_cell_value(2, 0) is None
        assert viewport.model.get_cell_value(3, 0) is None
        assert viewport.selection.primary_range == SelectionRange(0, 0, 1, 0)

        # 5. Redo re-applies fill
        viewport.redo()
        assert viewport.model.get_cell_value(2, 0) == 30
        assert viewport.model.get_cell_value(3, 0) == 40

    def test_autofill_shrink_and_undo_redo(self, viewport: GridViewport) -> None:
        viewport.model.set_cell(0, 0, CellData(value="Row 1"))
        viewport.model.set_cell(1, 0, CellData(value="Row 2"))
        viewport.model.set_cell(2, 0, CellData(value="Row 3"))
        viewport.selection.select_cell(0, 0)
        viewport.selection.extend_to(2, 0)  # A1:A3

        handle_rect = viewport._get_fill_handle_rect()
        assert handle_rect is not None
        hx, hy = handle_rect.center().x(), handle_rect.center().y()

        # Press on fill handle
        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(hx, hy),
            QPointF(hx, hy),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(press)

        # Shrink upward to row 0
        c0_rect = viewport.cell_rect(0, 0)
        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(c0_rect.center().x(), c0_rect.center().y()),
            QPointF(c0_rect.center().x(), c0_rect.center().y()),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move)
        assert viewport.has_autofill_preview
        assert viewport._fill_preview_range == SelectionRange(0, 0, 0, 0)

        release = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(c0_rect.center().x(), c0_rect.center().y()),
            QPointF(c0_rect.center().x(), c0_rect.center().y()),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseReleaseEvent(release)

        # Contracted cells are cleared
        assert viewport.model.get_cell_value(0, 0) == "Row 1"
        assert viewport.model.get_cell_value(1, 0) is None
        assert viewport.model.get_cell_value(2, 0) is None
        assert viewport.selection.primary_range == SelectionRange(0, 0, 0, 0)

        # Undo restores contracted cells
        viewport.undo()
        assert viewport.model.get_cell_value(1, 0) == "Row 2"
        assert viewport.model.get_cell_value(2, 0) == "Row 3"

        # Redo re-clears contracted cells
        viewport.redo()
        assert viewport.model.get_cell_value(1, 0) is None
        assert viewport.model.get_cell_value(2, 0) is None

    def test_autofill_cancel_leaves_cells_untouched(self, viewport: GridViewport) -> None:
        viewport.model.set_cell(0, 0, CellData(value=100))
        viewport.selection.select_cell(0, 0)

        handle_rect = viewport._get_fill_handle_rect()
        assert handle_rect is not None
        hx, hy = handle_rect.center().x(), handle_rect.center().y()

        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(hx, hy),
            QPointF(hx, hy),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(press)

        c2_rect = viewport.cell_rect(2, 0)
        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(c2_rect.center().x(), c2_rect.center().y()),
            QPointF(c2_rect.center().x(), c2_rect.center().y()),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move)

        # Cancel drag via Escape key
        esc = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        viewport.keyPressEvent(esc)

        assert not viewport.is_dragging
        assert not viewport.has_autofill_preview
        assert viewport.model.get_cell_value(1, 0) is None
        assert viewport.model.get_cell_value(2, 0) is None


class TestHeaderDragSelectionAdvanced:
    def test_col_header_drag_multiple_cols(self, viewport: GridViewport) -> None:
        # Press on col header 1
        x1 = viewport.row_header_width + viewport.geometry_mapper.col_pos(1) + 10
        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(x1, 10),
            QPointF(x1, 10),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(press)
        assert viewport.is_dragging
        assert viewport._drag_mode == HitZone.COL_HEADER
        assert viewport.selection.primary_range.min_c == 1
        assert viewport.selection.primary_range.max_c == 1

        # Drag across to col header 3
        x3 = viewport.row_header_width + viewport.geometry_mapper.col_pos(3) + 10
        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(x3, 10),
            QPointF(x3, 10),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move)
        assert viewport.selection.primary_range.min_c == 1
        assert viewport.selection.primary_range.max_c == 3

        release = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(x3, 10),
            QPointF(x3, 10),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseReleaseEvent(release)
        assert not viewport.is_dragging
        assert viewport.selection.primary_range.min_c == 1
        assert viewport.selection.primary_range.max_c == 3

    def test_col_header_shift_and_ctrl_selection(self, viewport: GridViewport) -> None:
        # Click col 1
        x1 = viewport.row_header_width + viewport.geometry_mapper.col_pos(1) + 10
        press1 = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(x1, 10),
            QPointF(x1, 10),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(press1)
        assert viewport.selection.primary_range.min_c == 1
        assert viewport.selection.primary_range.max_c == 1

        # Shift-click col 3 -> extends 1..3
        x3 = viewport.row_header_width + viewport.geometry_mapper.col_pos(3) + 10
        press3 = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(x3, 10),
            QPointF(x3, 10),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.ShiftModifier,
        )
        viewport.mousePressEvent(press3)
        assert viewport.selection.primary_range.min_c == 1
        assert viewport.selection.primary_range.max_c == 3

        # Ctrl-click col 5 -> adds col 5 as second range
        x5 = viewport.row_header_width + viewport.geometry_mapper.col_pos(5) + 10
        press5 = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(x5, 10),
            QPointF(x5, 10),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.ControlModifier,
        )
        viewport.mousePressEvent(press5)
        assert len(viewport.selection.ranges) == 2
        assert viewport.selection.ranges[1].min_c == 5
        assert viewport.selection.ranges[1].max_c == 5

    def test_row_header_drag_multiple_rows(self, viewport: GridViewport) -> None:
        y1 = viewport.col_header_height + viewport.geometry_mapper.row_pos(1) + 5
        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(10, y1),
            QPointF(10, y1),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(press)
        assert viewport.selection.primary_range.min_r == 1
        assert viewport.selection.primary_range.max_r == 1

        y4 = viewport.col_header_height + viewport.geometry_mapper.row_pos(4) + 5
        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(10, y4),
            QPointF(10, y4),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move)
        assert viewport.selection.primary_range.min_r == 1
        assert viewport.selection.primary_range.max_r == 4


class TestColumnRowResizeBatchAndUndoRedo:
    def test_batch_col_resize_selected_columns(self, viewport: GridViewport) -> None:
        # Select columns 1..3 (B:D)
        viewport.selection.select_cols(1, 3)
        orig_w1 = viewport.geometry_mapper.col_size(1)
        orig_w2 = viewport.geometry_mapper.col_size(2)
        orig_w3 = viewport.geometry_mapper.col_size(3)

        # Drag resize border of col 1
        b_x = viewport.row_header_width + viewport.geometry_mapper.col_pos(2)
        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(b_x, 10),
            QPointF(b_x, 10),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(press)
        assert viewport.cols_for_resize(1) == [1, 2, 3]

        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(b_x + 30, 10),
            QPointF(b_x + 30, 10),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move)

        release = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(b_x + 30, 10),
            QPointF(b_x + 30, 10),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseReleaseEvent(release)

        # All selected columns resized to orig + 30
        assert viewport.geometry_mapper.col_size(1) == orig_w1 + 30
        assert viewport.geometry_mapper.col_size(2) == orig_w2 + 30
        assert viewport.geometry_mapper.col_size(3) == orig_w3 + 30

        # Undo restores all columns
        viewport.undo()
        assert viewport.geometry_mapper.col_size(1) == orig_w1
        assert viewport.geometry_mapper.col_size(2) == orig_w2
        assert viewport.geometry_mapper.col_size(3) == orig_w3

        # Redo re-applies resize to all columns
        viewport.redo()
        assert viewport.geometry_mapper.col_size(1) == orig_w1 + 30
        assert viewport.geometry_mapper.col_size(2) == orig_w2 + 30
        assert viewport.geometry_mapper.col_size(3) == orig_w3 + 30

    def test_row_resize_undo_redo(self, viewport: GridViewport) -> None:
        orig_h = viewport.geometry_mapper.row_size(0)
        b_y = viewport.col_header_height + orig_h

        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(10, b_y),
            QPointF(10, b_y),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(press)

        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(10, b_y + 25),
            QPointF(10, b_y + 25),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move)

        release = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(10, b_y + 25),
            QPointF(10, b_y + 25),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseReleaseEvent(release)
        assert viewport.geometry_mapper.row_size(0) == orig_h + 25

        viewport.undo()
        assert viewport.geometry_mapper.row_size(0) == orig_h

        viewport.redo()
        assert viewport.geometry_mapper.row_size(0) == orig_h + 25


class TestEdgeAutoScrollAndFreezePanes:
    def test_freeze_panes_properties_and_split(self, viewport: GridViewport) -> None:
        assert viewport.freeze_rows == 0
        assert viewport.freeze_cols == 0

        viewport.set_freeze_panes(2, 3)
        assert viewport.freeze_rows == 2
        assert viewport.freeze_cols == 3

    def test_edge_scroll_trigger_and_stop(self, viewport: GridViewport) -> None:
        viewport.selection.select_cell(0, 0)
        c0 = viewport.cell_rect(0, 0)

        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(c0.center().x(), c0.center().y()),
            QPointF(c0.center().x(), c0.center().y()),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(press)
        assert viewport.is_dragging

        # Move near bottom edge (height - 1)
        vh = viewport.viewport().height()
        move_edge = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(c0.center().x(), vh - 1),
            QPointF(c0.center().x(), vh - 1),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move_edge)
        assert viewport.is_auto_scrolling

        # Move back inside viewport
        move_back = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(c0.center().x(), vh // 2),
            QPointF(c0.center().x(), vh // 2),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseMoveEvent(move_back)
        assert not viewport.is_auto_scrolling

        # Release stops everything cleanly
        release = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(c0.center().x(), vh // 2),
            QPointF(c0.center().x(), vh // 2),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mouseReleaseEvent(release)
        assert not viewport.is_dragging
        assert not viewport.is_auto_scrolling

    def test_edge_scroll_skips_hidden_rows_and_cols(self, viewport: GridViewport) -> None:
        # Hide rows 1 and 2
        viewport.geometry_mapper.hidden_rows.add(1)
        viewport.geometry_mapper.hidden_rows.add(2)

        # Set scroll delta downwards
        viewport._drag_mode = HitZone.CELL
        viewport._auto_scroll_delta = (1, 0)
        viewport.verticalScrollBar().setValue(0)

        # Trigger tick
        viewport._on_auto_scroll_tick()

        # Should skip rows 1 and 2, jumping directly to row 3 pos
        r3_pos = viewport.geometry_mapper.row_pos(3)
        assert viewport.verticalScrollBar().value() == r3_pos
        viewport._stop_auto_scroll()


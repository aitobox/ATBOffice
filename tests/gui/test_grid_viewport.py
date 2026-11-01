"""GUI tests for virtualized GridViewport."""

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport, HitZone


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


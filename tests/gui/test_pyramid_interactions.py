"""GUI automation test suite for Layer 2 of the Pyramid Regression Suite:
GridViewport selections, In-place EditorController, AutoFill handle drag,
and keyboard navigation shortcuts.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.models.sheet_model import CellData
from atboffice.modules.spreadsheet.view import SpreadsheetView
from atboffice.modules.spreadsheet.views.grid_viewport import HitZone


@pytest.fixture
def view(qtbot: pytest.FixtureRequest, qapp: QApplication) -> SpreadsheetView:
    v = SpreadsheetView()
    qtbot.addWidget(v)
    v.resize(900, 600)
    v.show()
    return v


class TestPyramidGUIInteractions:
    def test_rubberband_mouse_drag_selection(self, view: SpreadsheetView) -> None:
        """Drag mouse across cells to select a rectangular area."""
        grid = view.grid
        # Cell (1, 1) to (3, 3)
        # Offset from row header and col header
        start_x = grid.row_header_width + grid.geometry_mapper.col_pos(1) + 10
        start_y = grid.col_header_height + grid.geometry_mapper.row_pos(1) + 5

        end_x = grid.row_header_width + grid.geometry_mapper.col_pos(3) + 15
        end_y = grid.col_header_height + grid.geometry_mapper.row_pos(3) + 10

        p1 = QPointF(start_x, start_y)
        p2 = QPointF(end_x, end_y)

        # 1. Mouse Press at (1, 1)
        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            p1,
            p1,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        grid.mousePressEvent(press)
        assert grid.selection.active_cell == (1, 1)

        # 2. Mouse Move to (3, 3)
        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            p2,
            p2,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        grid.mouseMoveEvent(move)

        # 3. Mouse Release at (3, 3)
        release = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            p2,
            p2,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        grid.mouseReleaseEvent(release)

        # Verify selection range is (1, 1) to (3, 3)
        sel = grid.selection.ranges[0]
        assert sel.min_r == 1
        assert sel.min_c == 1
        assert sel.max_r == 3
        assert sel.max_c == 3

    def test_double_click_inplace_edit_and_commit(self, view: SpreadsheetView) -> None:
        """Double click cell, type formula, commit with Enter, check calculation."""
        ctrl = view.editor_controller
        assert not ctrl.is_active

        # Double click cell (2, 2) (C3)
        view.grid.cell_double_clicked.emit(2, 2)
        assert ctrl.is_active
        assert ctrl.active_row == 2
        assert ctrl.active_col == 2
        assert not ctrl.in_cell_editor.isHidden()

        # Type formula in the active editor
        ctrl.in_cell_editor.setText("=SUM(15, 25)")
        assert view.formula_bar.text() == "=SUM(15, 25)"

        # Commit edit
        ctrl.commit()
        assert not ctrl.is_active
        assert ctrl.in_cell_editor.isHidden()

        # Verify SheetDataModel cell value and formula
        cell = view.model.get_cell(2, 2)
        assert cell is not None
        assert cell.formula == "SUM(15, 25)"
        assert cell.value == 40.0

    def test_double_click_inplace_edit_and_cancel(self, view: SpreadsheetView) -> None:
        """Double click cell, type, press cancel/Escape, verify rollback."""
        ctrl = view.editor_controller
        view.model.set_cell_value(3, 1, "KeepMe")

        # Double click (3, 1)
        view.grid.cell_double_clicked.emit(3, 1)
        ctrl.in_cell_editor.setText("DiscardMe")

        # Cancel
        ctrl.cancel()
        assert not ctrl.is_active
        assert view.model.get_cell_value(3, 1) == "KeepMe"

    def test_autofill_smart_handle_drag(self, view: SpreadsheetView) -> None:
        """Drag fill handle down to extrapolate linear sequence 10, 20 -> 30, 40."""
        grid = view.grid
        view.model.set_cell(0, 0, CellData(value=10))
        view.model.set_cell(1, 0, CellData(value=20))

        # Select A1:A2
        grid.selection.select_cell(0, 0)
        grid.selection.extend_to(1, 0)

        # Bottom-right handle position for range A1:A2
        handle_x = grid.row_header_width + grid.geometry_mapper.col_pos(1)
        handle_y = grid.col_header_height + grid.geometry_mapper.row_pos(2)

        p_handle = QPointF(handle_x, handle_y)
        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            p_handle,
            p_handle,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        grid.mousePressEvent(press)
        assert grid._drag_mode == HitZone.FILL_HANDLE

        # Drag down to row 3 (offset row 4)
        target_y = grid.col_header_height + grid.geometry_mapper.row_pos(4) - 5
        p_target = QPointF(handle_x, target_y)
        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            p_target,
            p_target,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        grid.mouseMoveEvent(move)

        # Release
        release = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            p_target,
            p_target,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        grid.mouseReleaseEvent(release)

        assert grid._drag_mode == HitZone.NONE
        # A3 (row 2) should be 30, A4 (row 3) should be 40
        assert view.model.get_cell_value(2, 0) == 30
        assert view.model.get_cell_value(3, 0) == 40

    def test_keyboard_navigation_and_delete(self, view: SpreadsheetView) -> None:
        """Test Arrow key navigation, Tab, and Delete key clearing."""
        grid = view.grid
        grid.selection.select_cell(2, 2)

        # Key Down -> (3, 2)
        event_down = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Down,
            Qt.KeyboardModifier.NoModifier,
        )
        grid.keyPressEvent(event_down)
        assert grid.selection.active_cell == (3, 2)

        # Key Right -> (3, 3)
        event_right = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Right,
            Qt.KeyboardModifier.NoModifier,
        )
        grid.keyPressEvent(event_right)
        assert grid.selection.active_cell == (3, 3)

        # Key Up -> (2, 3)
        event_up = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Up,
            Qt.KeyboardModifier.NoModifier,
        )
        grid.keyPressEvent(event_up)
        assert grid.selection.active_cell == (2, 3)

        # Key Left -> (2, 2)
        event_left = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Left,
            Qt.KeyboardModifier.NoModifier,
        )
        grid.keyPressEvent(event_left)
        assert grid.selection.active_cell == (2, 2)

        # Test Delete key clears content
        view.model.set_cell_value(2, 2, "DeleteThis")
        assert view.model.get_cell_value(2, 2) == "DeleteThis"

        event_delete = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Delete,
            Qt.KeyboardModifier.NoModifier,
        )
        grid.keyPressEvent(event_delete)
        assert view.model.get_cell_value(2, 2) is None

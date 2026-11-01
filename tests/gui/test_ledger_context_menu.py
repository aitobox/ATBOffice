"""Tests for Ledger GridViewport right-click selection and context menu system."""

from unittest.mock import patch

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.models.selection_model import SelectionRange
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.spreadsheet.views.editor_controller import EditorController
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport


@pytest.fixture
def viewport(qapp: QApplication) -> GridViewport:
    model = SheetDataModel()
    vp = GridViewport(model=model)
    vp.resize(800, 600)
    # Attach editor controller
    controller = EditorController(
        viewport=vp,
        model=model,
        selection=vp.selection,
        formula_bar=None,
        parent=vp,
    )
    vp.editor_controller = controller
    return vp


def make_right_click(x: float, y: float) -> QMouseEvent:
    return QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(x, y),
        QPointF(x, y),
        Qt.MouseButton.RightButton,
        Qt.MouseButton.RightButton,
        Qt.KeyboardModifier.NoModifier,
    )


class TestRightClickSelection:
    def test_right_click_inside_selection_preserves_selection(
        self, viewport: GridViewport
    ) -> None:
        # Select range (1, 1) to (3, 3)
        viewport.selection.select_cell(1, 1)
        viewport.selection.extend_to(3, 3)
        assert len(viewport.selection.ranges) == 1
        assert viewport.selection.primary_range == SelectionRange(1, 1, 3, 3)

        # Right click at cell (2, 2) which is inside selection
        r_pos = viewport.geometry_mapper.row_pos(2) + viewport.col_header_height + 5
        c_pos = viewport.geometry_mapper.col_pos(2) + viewport.row_header_width + 5
        event = make_right_click(c_pos, r_pos)
        viewport.mousePressEvent(event)

        # Selection should remain (1, 1) to (3, 3)
        assert viewport.selection.primary_range == SelectionRange(1, 1, 3, 3)

    def test_right_click_outside_selection_selects_target_cell(
        self, viewport: GridViewport
    ) -> None:
        # Select range (1, 1) to (3, 3)
        viewport.selection.select_cell(1, 1)
        viewport.selection.extend_to(3, 3)

        # Right click at cell (5, 5) which is outside selection
        r_pos = viewport.geometry_mapper.row_pos(5) + viewport.col_header_height + 5
        c_pos = viewport.geometry_mapper.col_pos(5) + viewport.row_header_width + 5
        event = make_right_click(c_pos, r_pos)
        viewport.mousePressEvent(event)

        # Selection should now only be (5, 5)
        assert viewport.selection.active_cell == (5, 5)
        assert viewport.selection.primary_range == SelectionRange(5, 5, 5, 5)

    def test_right_click_col_header(self, viewport: GridViewport) -> None:
        # Right click column header 2
        c_pos = viewport.geometry_mapper.col_pos(2) + viewport.row_header_width + 5
        r_pos = 10  # in column header
        event = make_right_click(c_pos, r_pos)
        viewport.mousePressEvent(event)

        assert viewport.selection.is_col_selected(2)
        pr = viewport.selection.primary_range
        assert pr.min_c == 2 and pr.max_c == 2
        assert pr.min_r == 0 and pr.max_r == viewport.selection.max_rows - 1

        # Right click column header 2 again, keeps whole column selection
        viewport.mousePressEvent(event)
        assert viewport.selection.is_col_selected(2)

    def test_right_click_row_header(self, viewport: GridViewport) -> None:
        # Right click row header 3
        c_pos = 10  # in row header
        r_pos = viewport.geometry_mapper.row_pos(3) + viewport.col_header_height + 5
        event = make_right_click(c_pos, r_pos)
        viewport.mousePressEvent(event)

        assert viewport.selection.is_row_selected(3)
        pr = viewport.selection.primary_range
        assert pr.min_r == 3 and pr.max_r == 3
        assert pr.min_c == 0 and pr.max_c == viewport.selection.max_cols - 1

        # Right click row header 3 again, keeps whole row selection
        viewport.mousePressEvent(event)
        assert viewport.selection.is_row_selected(3)


class TestRightClickEditorCommitAndAbort:
    def test_right_click_commits_active_editor(self, viewport: GridViewport) -> None:
        viewport.selection.select_cell(0, 0)
        viewport.editor_controller.begin_edit(0, 0)
        viewport.editor_controller.in_cell_editor.setText("42")
        assert viewport.editor_controller.is_active

        # Right click on cell (2, 2)
        r_pos = viewport.geometry_mapper.row_pos(2) + viewport.col_header_height + 5
        c_pos = viewport.geometry_mapper.col_pos(2) + viewport.row_header_width + 5
        event = make_right_click(c_pos, r_pos)
        viewport.mousePressEvent(event)

        # Editor should be committed
        assert not viewport.editor_controller.is_active
        assert viewport.model.get_cell_value(0, 0) == 42
        assert viewport.selection.active_cell == (2, 2)

    def test_right_click_aborts_when_commit_fails(
        self, viewport: GridViewport
    ) -> None:
        viewport.selection.select_cell(0, 0)
        viewport.editor_controller.begin_edit(0, 0)
        assert viewport.editor_controller.is_active

        # Mock commit() returning False
        with patch.object(viewport.editor_controller, "commit", return_value=False):
            r_pos = viewport.geometry_mapper.row_pos(2) + viewport.col_header_height + 5
            c_pos = viewport.geometry_mapper.col_pos(2) + viewport.row_header_width + 5
            event = make_right_click(c_pos, r_pos)
            viewport.mousePressEvent(event)

            # Editor remains active and selection didn't switch to (2, 2)
            assert viewport.editor_controller.is_active
            assert viewport.selection.active_cell == (0, 0)


class TestContextMenuConstruction:
    def test_build_col_header_menu(self, viewport: GridViewport) -> None:
        viewport.selection.select_cols(1, 1)
        menu = viewport._build_col_header_menu(1)
        actions = [a.text() for a in menu.actions() if not a.isSeparator()]
        # Check essential actions exist
        assert any("剪切" in a or "Cut" in a for a in actions)
        assert any("复制" in a or "Copy" in a for a in actions)
        assert any("粘贴" in a or "Paste" in a for a in actions)
        assert any("插入" in a or "Insert" in a for a in actions)
        assert any("删除" in a or "Delete" in a for a in actions)
        assert any("清除内容" in a or "Clear Contents" in a for a in actions)
        assert any("列宽" in a or "Column Width" in a for a in actions)
        assert any("隐藏" in a or "Hide" in a for a in actions)
        assert any("取消隐藏" in a or "Unhide" in a for a in actions)

    def test_build_row_header_menu(self, viewport: GridViewport) -> None:
        viewport.selection.select_rows(2, 2)
        menu = viewport._build_row_header_menu(2)
        actions = [a.text() for a in menu.actions() if not a.isSeparator()]
        assert any("剪切" in a or "Cut" in a for a in actions)
        assert any("复制" in a or "Copy" in a for a in actions)
        assert any("粘贴" in a or "Paste" in a for a in actions)
        assert any("插入" in a or "Insert" in a for a in actions)
        assert any("删除" in a or "Delete" in a for a in actions)
        assert any("清除内容" in a or "Clear Contents" in a for a in actions)
        assert any("行高" in a or "Row Height" in a for a in actions)
        assert any("隐藏" in a or "Hide" in a for a in actions)
        assert any("取消隐藏" in a or "Unhide" in a for a in actions)

    def test_build_cell_menu(self, viewport: GridViewport) -> None:
        viewport.selection.select_cell(1, 1)
        menu = viewport._build_cell_menu(1, 1)
        actions = [a.text() for a in menu.actions() if not a.isSeparator()]
        assert any("剪切" in a or "Cut" in a for a in actions)
        assert any("复制" in a or "Copy" in a for a in actions)
        assert any("粘贴" in a or "Paste" in a for a in actions)
        assert any("清除内容" in a or "Clear Contents" in a for a in actions)
        assert any("设置单元格格式" in a or "Format Cells" in a for a in actions)
        assert any("批注" in a or "Comment" in a for a in actions)
        assert any("超链接" in a or "Hyperlink" in a for a in actions)


class TestKeyboardContextMenuShiftF10:
    def test_shift_f10_triggers_context_menu(self, viewport: GridViewport) -> None:
        viewport.selection.select_cell(2, 3)
        event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_F10,
            Qt.KeyboardModifier.ShiftModifier,
        )
        with patch.object(viewport, "open_context_menu") as mock_open:
            viewport.keyPressEvent(event)
            assert mock_open.called


class TestGuardProtection:
    def test_guard_protect_blocks_locked_cells(self, viewport: GridViewport) -> None:
        viewport.model.protection = {"enabled": True}
        viewport.model.set_cell(1, 1, CellData(value="Protected", locked=True))
        viewport.selection.select_cell(1, 1)

        assert viewport.guard_protect(cell_edit=True) is True

    def test_guard_protect_allows_unlocked_cells(self, viewport: GridViewport) -> None:
        viewport.model.protection = {"enabled": True}
        viewport.model.set_cell(1, 1, CellData(value="Unlocked", locked=False))
        viewport.selection.select_cell(1, 1)

        assert viewport.guard_protect(cell_edit=True) is False

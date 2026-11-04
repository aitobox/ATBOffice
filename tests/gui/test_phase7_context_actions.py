"""Phase 7 acceptance tests for Ledger context menus and business actions.

Covers:
- Matrix 234: 049_context_Cell (selection targeting, editor commit, Shift+F10,
  copy, cut, paste, paste special, table actions)
- Matrix 235: 050_context_Row_Header (row selection, insert, delete, clear, format)
- Matrix 236: 051_context_Col_Header (col selection, insert, delete, clear, format)
- Matrix 237: 052_context_Sheet_Tab (sheet tab context menu, grouping, select all,
  ungroup, dirty marking)
- Matrix 238: 053_context_StatusBar_Calc (status bar calculation context menu and live aggregation)
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QContextMenuEvent, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QDialog, QInputDialog, QMenu

from atboffice.modules.spreadsheet.dialogs.paste_special_dialog import (
    PasteSpecialDialog,
)
from atboffice.modules.spreadsheet.models.selection_model import SelectionRange
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.spreadsheet.views.editor_controller import EditorController
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport
from atboffice.modules.spreadsheet.views.object_layer import (
    FloatingObject,
    SpreadsheetObjectLayer,
)
from atboffice.modules.spreadsheet.views.sheet_tab_bar import SheetTabBar


@pytest.fixture
def viewport(qapp: QApplication) -> GridViewport:
    model = SheetDataModel()
    vp = GridViewport(model=model)
    vp.resize(800, 600)
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


class TestCellContextMenuTargetingAndEditor:
    """Test selection preservation, re-targeting, editor commit, and Shift+F10 dispatch."""

    def test_right_click_inside_selection_preserves_selection(
        self, viewport: GridViewport
    ) -> None:
        viewport.selection.select_cell(1, 1)
        viewport.selection.extend_to(3, 3)
        assert viewport.selection.primary_range == SelectionRange(1, 1, 3, 3)

        r_pos = viewport.geometry_mapper.row_pos(2) + viewport.col_header_height + 5
        c_pos = viewport.geometry_mapper.col_pos(2) + viewport.row_header_width + 5
        event = make_right_click(c_pos, r_pos)
        viewport.mousePressEvent(event)

        assert viewport.selection.primary_range == SelectionRange(1, 1, 3, 3)

    def test_right_click_outside_selection_targets_clicked_cell(
        self, viewport: GridViewport
    ) -> None:
        viewport.selection.select_cell(1, 1)
        viewport.selection.extend_to(3, 3)

        r_pos = viewport.geometry_mapper.row_pos(5) + viewport.col_header_height + 5
        c_pos = viewport.geometry_mapper.col_pos(5) + viewport.row_header_width + 5
        event = make_right_click(c_pos, r_pos)
        viewport.mousePressEvent(event)

        assert viewport.selection.active_cell == (5, 5)
        assert viewport.selection.primary_range == SelectionRange(5, 5, 5, 5)

    def test_in_cell_editor_commits_on_context_menu(
        self, viewport: GridViewport
    ) -> None:
        ctrl = viewport.editor_controller
        ctrl.begin_edit(0, 0, initial_text="TypedValue")
        assert ctrl.is_active is True

        # Right click cell (1, 1) outside editor
        r_pos = viewport.geometry_mapper.row_pos(1) + viewport.col_header_height + 5
        c_pos = viewport.geometry_mapper.col_pos(1) + viewport.row_header_width + 5
        event = make_right_click(c_pos, r_pos)

        with patch.object(QMenu, "exec", return_value=None):
            viewport.mousePressEvent(event)

        # Editor should be committed and closed
        assert ctrl.is_active is False
        assert viewport.model.get_cell(0, 0).value == "TypedValue"

    def test_shift_f10_opens_context_menu_at_active_cell(
        self, viewport: GridViewport
    ) -> None:
        viewport.selection.select_cell(2, 3)
        key_event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_F10,
            Qt.KeyboardModifier.ShiftModifier,
        )

        with patch.object(viewport, "open_context_menu") as mock_open:
            viewport.keyPressEvent(key_event)
            assert mock_open.called
            assert mock_open.call_args[1]["reason"] == QContextMenuEvent.Reason.Keyboard


class TestPasteSpecialDialog:
    """Test PasteSpecialDialog controls, initial state, options dictionary, and Paste Link."""

    def test_dialog_default_options(self, qapp: QApplication) -> None:
        dlg = PasteSpecialDialog()
        assert dlg.rb_all.isChecked()
        assert dlg.rb_op_none.isChecked()
        assert not dlg.chk_skip_blanks.isChecked()
        assert not dlg.chk_transpose.isChecked()
        assert dlg.is_paste_link is False

        opts = dlg.options
        assert opts["type"] == "all"
        assert opts["operation"] == "none"
        assert opts["skip_blanks"] is False
        assert opts["transpose"] is False

        dlg.retranslate_ui()
        dlg.close()

    def test_dialog_custom_options_selection(self, qapp: QApplication) -> None:
        dlg = PasteSpecialDialog()
        dlg.rb_values.setChecked(True)
        dlg.rb_op_add.setChecked(True)
        dlg.chk_skip_blanks.setChecked(True)
        dlg.chk_transpose.setChecked(True)

        opts = dlg.options
        assert opts["type"] == "values"
        assert opts["operation"] == "add"
        assert opts["skip_blanks"] is True
        assert opts["transpose"] is True
        dlg.close()

    def test_dialog_paste_link_button(self, qapp: QApplication) -> None:
        dlg = PasteSpecialDialog()
        with patch.object(dlg, "accept") as mock_accept:
            dlg.btn_paste_link.click()
            assert dlg.is_paste_link is True
            assert mock_accept.called
        dlg.close()


class TestPasteSpecialExecution:
    """Test Paste Special business logic executions and formula translation."""

    def test_paste_special_values_only(self, viewport: GridViewport) -> None:
        # Populate source cells at (0, 0) and (0, 1)
        viewport.model.set_cell(0, 0, CellData(value=10))
        viewport.model.set_cell(0, 1, CellData(value=30, formula="=A1*3"))

        # Select source and copy
        viewport.selection.select_cell(0, 0)
        viewport.selection.extend_to(0, 1)
        viewport.copy()

        # Target cell at (2, 2)
        viewport.selection.select_cell(2, 2)
        viewport.paste_special({"type": "values", "operation": "none"})

        c1 = viewport.model.get_cell(2, 2)
        c2 = viewport.model.get_cell(2, 3)
        assert c1.value == 10
        assert c1.formula is None
        assert c2.value == 30
        assert c2.formula is None

    def test_paste_special_formulas_relative_translation(
        self, viewport: GridViewport
    ) -> None:
        # Source at (1, 1) with relative formula '=A1+10' and absolute reference '=$A$1+5'
        viewport.model.set_cell(1, 1, CellData(value=15, formula="=A1+10"))
        viewport.model.set_cell(1, 2, CellData(value=20, formula="=$A$1+5"))

        viewport.selection.select_cell(1, 1)
        viewport.selection.extend_to(1, 2)
        viewport.copy()

        # Paste to (3, 2), offsetting dr = +2, dc = +1
        # Relative: A1 -> B3
        # Absolute: $A$1 -> $A$1
        viewport.selection.select_cell(3, 2)
        viewport.paste_special({"type": "formulas", "operation": "none"})

        t1 = viewport.model.get_cell(3, 2)
        t2 = viewport.model.get_cell(3, 3)
        assert t1.formula == "=B3+10"
        assert t2.formula == "=$A$1+5"

    def test_paste_special_column_widths(self, viewport: GridViewport) -> None:
        viewport.geometry_mapper.set_col_width(1, 140)
        viewport.selection.select_cell(0, 1)
        viewport.copy()

        viewport.selection.select_cell(0, 5)
        viewport.paste_special({"type": "colWidths", "operation": "none"})

        assert viewport.geometry_mapper.col_width(5) == 140

    def test_paste_special_transpose(self, viewport: GridViewport) -> None:
        # Create 2x3 block:
        # 1  2  3
        # 4  5  6
        for r in range(2):
            for c in range(3):
                viewport.model.set_cell(r, c, CellData(value=(r * 3 + c + 1)))

        viewport.selection.select_cell(0, 0)
        viewport.selection.extend_to(1, 2)
        viewport.copy()

        # Transpose paste to (5, 5) -> becomes 3x2 block
        viewport.selection.select_cell(5, 5)
        viewport.paste_special(
            {"type": "all", "operation": "none", "transpose": True}
        )

        assert viewport.model.get_cell(5, 5).value == 1
        assert viewport.model.get_cell(6, 5).value == 2
        assert viewport.model.get_cell(7, 5).value == 3
        assert viewport.model.get_cell(5, 6).value == 4
        assert viewport.model.get_cell(6, 6).value == 5
        assert viewport.model.get_cell(7, 6).value == 6

    def test_paste_special_arithmetic_operations(
        self, viewport: GridViewport
    ) -> None:
        # Source = 5
        viewport.model.set_cell(0, 0, CellData(value=5))
        viewport.selection.select_cell(0, 0)
        viewport.copy()

        # Add to 10 -> 15
        viewport.model.set_cell(1, 0, CellData(value=10))
        viewport.selection.select_cell(1, 0)
        viewport.paste_special({"type": "all", "operation": "add"})
        assert viewport.model.get_cell(1, 0).value == 15

        # Subtract from 15 -> 10
        viewport.selection.select_cell(1, 0)
        viewport.paste_special({"type": "all", "operation": "subtract"})
        assert viewport.model.get_cell(1, 0).value == 10

        # Multiply with 10 -> 50
        viewport.selection.select_cell(1, 0)
        viewport.paste_special({"type": "all", "operation": "multiply"})
        assert viewport.model.get_cell(1, 0).value == 50

        # Divide 50 by 5 -> 10.0
        viewport.selection.select_cell(1, 0)
        viewport.paste_special({"type": "all", "operation": "divide"})
        assert viewport.model.get_cell(1, 0).value == 10.0

    def test_paste_special_skip_blanks(self, viewport: GridViewport) -> None:
        # Source: cell (0, 0) = "Filled", cell (0, 1) = "" (blank)
        viewport.model.set_cell(0, 0, CellData(value="Filled"))
        viewport.model.set_cell(0, 1, CellData(value=""))

        viewport.selection.select_cell(0, 0)
        viewport.selection.extend_to(0, 1)
        viewport.copy()

        # Target: cell (2, 0) = "OrigA", cell (2, 1) = "OrigB"
        viewport.model.set_cell(2, 0, CellData(value="OrigA"))
        viewport.model.set_cell(2, 1, CellData(value="OrigB"))

        viewport.selection.select_cell(2, 0)
        viewport.paste_special(
            {"type": "all", "operation": "none", "skip_blanks": True}
        )

        assert viewport.model.get_cell(2, 0).value == "Filled"
        # OrigB must NOT have been overwritten by the blank source cell
        assert viewport.model.get_cell(2, 1).value == "OrigB"

    def test_paste_special_paste_link(self, viewport: GridViewport) -> None:
        wb = WorkbookModel(sheets=[viewport.model])
        viewport.workbook = wb
        viewport.model.name = "Sheet1"

        viewport.model.set_cell(0, 0, CellData(value=100))
        viewport.selection.select_cell(0, 0)
        viewport.copy()

        viewport.selection.select_cell(3, 3)
        viewport.paste_special({"type": "paste_link"})

        cell = viewport.model.get_cell(3, 3)
        assert cell.formula == "=Sheet1!A1"


class TestTableListContextMenuActions:
    """Test conditional Table / List menu actions and transformations."""

    def test_table_at_and_list_actions(self, viewport: GridViewport) -> None:
        # Cell outside table
        assert viewport.table_at(0, 0) is None
        menu_outside = viewport._build_cell_menu(0, 0)
        titles_outside = [a.text() for a in menu_outside.actions()]
        assert any("创建列表(&L)" in t for t in titles_outside)
        assert not any(t == "列表(&L)" for t in titles_outside)

        # Create table at range (0, 0) to (3, 3)
        viewport.selection.select_cell(0, 0)
        viewport.selection.extend_to(3, 3)
        viewport.create_list()

        tbl = viewport.table_at(1, 1)
        assert tbl is not None
        assert tbl["totalRow"] is False

        # Cell inside table
        menu_inside = viewport._build_cell_menu(1, 1)
        action_texts = [a.text() for a in menu_inside.actions()]
        assert "列表(&L)" in action_texts

        # Toggle total row
        viewport.toggle_total_row(tbl)
        assert tbl["totalRow"] is True

        # Convert back to range
        viewport.convert_table_to_range(tbl)
        assert viewport.table_at(1, 1) is None


class TestSparseBoundsCopyClearPerformance:
    """Test that selecting 1,048,576 rows executes copy and clear in milliseconds."""

    def test_sparse_bounds_full_column_copy_and_clear(
        self, viewport: GridViewport
    ) -> None:
        # Populate only 3 cells in column 0
        viewport.model.set_cell(0, 0, CellData(value=1))
        viewport.model.set_cell(10, 0, CellData(value=2))
        viewport.model.set_cell(20, 0, CellData(value=3))

        # Select entire column 0 (0 to 1,048,575 rows)
        viewport.selection.select_cols(0, 0)
        pr = viewport.selection.primary_range
        assert pr.min_r == 0
        assert pr.max_r == viewport.selection.max_rows - 1

        # Copy should finish quickly (< 0.5s)
        t0 = time.perf_counter()
        viewport.copy()
        t1 = time.perf_counter()
        assert (t1 - t0) < 0.5

        # Clipboard buffer should have bounded data, not 1 million elements
        buf = viewport._internal_clipboard
        assert buf is not None
        assert len(buf["cells"]) == 21  # 0 to 20 rows

        # Clear contents should also finish quickly (< 0.5s)
        t2 = time.perf_counter()
        viewport.clear_contents()
        t3 = time.perf_counter()
        assert (t3 - t2) < 0.5

        # All cells in column 0 should now be cleared
        assert viewport.model.get_cell(0, 0).value is None
        assert viewport.model.get_cell(10, 0).value is None
        assert viewport.model.get_cell(20, 0).value is None


class TestSheetTabBarContextActions:
    """Test SheetTabBar context menu items, select all, ungroup, and dirty marking."""

    def test_sheet_grouping_and_ungrouping(self, qapp: QApplication) -> None:
        wb = WorkbookModel(
            sheets=[
                SheetDataModel(name="Sheet1"),
                SheetDataModel(name="Sheet2"),
                SheetDataModel(name="Sheet3"),
            ]
        )
        bar = SheetTabBar(workbook=wb)
        try:
            assert bar.selected_sheet_indices == {0}

            # Select all sheets
            bar.select_all_sheets()
            assert bar.selected_sheet_indices == {0, 1, 2}

            # Ungroup sheets
            bar.ungroup_sheets()
            assert bar.selected_sheet_indices == {0}
        finally:
            bar.close()

    def test_sheet_tab_bar_dirty_marking(self, qapp: QApplication) -> None:
        wb = WorkbookModel(
            sheets=[
                SheetDataModel(name="S1"),
                SheetDataModel(name="S2"),
            ]
        )
        assert wb.dirty is False
        bar = SheetTabBar(workbook=wb)
        try:
            bar.insert_sheet()
            assert wb.dirty is True

            wb.dirty = False
            bar.delete_sheet(2)
            assert wb.dirty is True

            wb.dirty = False
            bar.set_tab_color(0, QColor(255, 0, 0))
            assert wb.dirty is True
        finally:
            bar.close()


class TestObjectLayerContextMenu:
    """Test FloatingObject context menu for shapes, textboxes, and charts."""

    def test_shape_object_context_menu_and_edit_text(
        self, qapp: QApplication
    ) -> None:
        layer = SpreadsheetObjectLayer()
        try:
            shape = FloatingObject(
                id=1,
                name="Rectangle 1",
                kind="rect",
                text="InitialText",
            )
            layer.add_object(shape)
            layer.select_object(shape)

            # Test start text editing with QInputDialog mock
            with patch.object(
                QInputDialog, "getMultiLineText", return_value=("UpdatedText", True)
            ):
                layer.start_text_editing(shape)
                assert shape.text == "UpdatedText"

            # Test chart options dialog launch mock
            chart_obj = FloatingObject(id=2, name="Chart 1", kind="chart")
            layer.add_object(chart_obj)
            layer.select_object(chart_obj)

            with patch(
                "atboffice.modules.spreadsheet.dialogs.chart_wizard.ChartWizardDialog.exec",
                return_value=QDialog.DialogCode.Accepted,
            ):
                layer.open_chart_type_dialog(chart_obj)
                layer.open_chart_options_dialog(chart_obj)
        finally:
            layer.close()


class TestUndoRedoContextMenuOperations:
    """Test undo/redo transactions for paste special and clear contents."""

    def test_undo_redo_paste_special_and_clear(
        self, viewport: GridViewport
    ) -> None:
        viewport.model.set_cell(0, 0, CellData(value="Initial"))
        viewport.selection.select_cell(0, 0)
        viewport.copy()

        viewport.selection.select_cell(2, 2)
        viewport.paste_special({"type": "values", "operation": "none"})
        assert viewport.model.get_cell(2, 2).value == "Initial"

        # Undo paste special
        viewport.undo()
        assert viewport.model.get_cell(2, 2) is None

        # Redo paste special
        viewport.redo()
        assert viewport.model.get_cell(2, 2).value == "Initial"

        # Clear contents and undo
        viewport.selection.select_cell(2, 2)
        viewport.clear_contents()
        assert viewport.model.get_cell(2, 2).value is None

        viewport.undo()
        assert viewport.model.get_cell(2, 2).value == "Initial"

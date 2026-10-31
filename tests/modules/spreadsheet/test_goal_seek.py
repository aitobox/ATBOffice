"""Tests for Ledger Goal Seek numerical iterative solver and dialogs."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.calc.goal_seek import (
    GoalSeekParams,
    GoalSeekResult,
    parse_cell_reference,
    solve_goal_seek,
)
from atboffice.modules.spreadsheet.dialogs.goal_seek_dlg import (
    GoalSeekDialog,
    GoalSeekStatusDialog,
)
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestGoalSeekParser:
    """Test cell coordinate string parsing."""

    def test_parse_simple_a1(self):
        sheet, r, c = parse_cell_reference("B5", default_sheet="Sheet1")
        assert sheet == "Sheet1"
        assert r == 4
        assert c == 1

    def test_parse_absolute_reference(self):
        sheet, r, c = parse_cell_reference("$C$10", default_sheet="Sheet1")
        assert sheet == "Sheet1"
        assert r == 9
        assert c == 2

    def test_parse_sheet_qualified_reference(self):
        sheet, r, c = parse_cell_reference("Summary!D2", default_sheet="Sheet1")
        assert sheet == "Summary"
        assert r == 1
        assert c == 3

    def test_parse_quoted_sheet_reference(self):
        sheet, r, c = parse_cell_reference("'Annual Report'!$A$1", default_sheet="Sheet1")
        assert sheet == "Annual Report"
        assert r == 0
        assert c == 0

    def test_parse_invalid_reference(self):
        with pytest.raises(ValueError):
            parse_cell_reference("Invalid!!Cell", default_sheet="Sheet1")
        with pytest.raises(ValueError):
            parse_cell_reference("", default_sheet="Sheet1")


class TestGoalSeekSolver:
    """Test numerical goal seek iterative solver."""

    def test_linear_formula_solve(self):
        # Model: B1 = 5, B2 = "=B1*2 + 10", Goal: 50 -> Expected B1 = 20
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 1, CellData(value=5.0))  # B1
        sh.set_cell(1, 1, CellData(value=20.0, formula="=B1*2 + 10"))  # B2
        wb.recalculate()

        params = GoalSeekParams(
            target_sheet="Sheet1",
            target_row=1,
            target_col=1,
            goal_value=50.0,
            changing_sheet="Sheet1",
            changing_row=0,
            changing_col=1,
        )

        res = solve_goal_seek(wb, params)
        assert res.success is True
        assert abs(res.solution - 20.0) < 0.001
        assert abs(res.current_value - 50.0) < 0.001
        assert res.iterations > 0

        # Verify solver preserved original value in the model during exploration
        assert sh.get_cell_value(0, 1) == 5.0

    def test_quadratic_formula_solve(self):
        # Model: B1 = 1, B2 = "=B1^2 - 16", Goal: 0 -> Expected B1 = 4
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 1, CellData(value=1.0))
        sh.set_cell(1, 1, CellData(value=-15.0, formula="=B1^2 - 16"))
        wb.recalculate()

        params = GoalSeekParams(
            target_sheet="Sheet1",
            target_row=1,
            target_col=1,
            goal_value=0.0,
            changing_sheet="Sheet1",
            changing_row=0,
            changing_col=1,
        )

        res = solve_goal_seek(wb, params)
        assert res.success is True
        assert abs(res.solution - 4.0) < 0.001
        assert abs(res.current_value - 0.0) < 0.001

    def test_initial_value_already_at_goal(self):
        # Model: B1 = 20, B2 = "=B1*2", Goal: 40 -> Already matches
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 1, CellData(value=20.0))
        sh.set_cell(1, 1, CellData(value=40.0, formula="=B1*2"))
        wb.recalculate()

        params = GoalSeekParams(
            target_sheet="Sheet1",
            target_row=1,
            target_col=1,
            goal_value=40.0,
            changing_sheet="Sheet1",
            changing_row=0,
            changing_col=1,
        )

        res = solve_goal_seek(wb, params)
        assert res.success is True
        assert abs(res.solution - 20.0) < 1e-6
        assert res.iterations <= 1

    def test_target_cell_has_no_formula(self):
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 1, CellData(value=10.0))
        sh.set_cell(1, 1, CellData(value=20.0))  # No formula!

        params = GoalSeekParams(
            target_sheet="Sheet1",
            target_row=1,
            target_col=1,
            goal_value=50.0,
            changing_sheet="Sheet1",
            changing_row=0,
            changing_col=1,
        )

        with pytest.raises(ValueError, match="formula"):
            solve_goal_seek(wb, params)

    def test_changing_cell_contains_formula(self):
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 1, CellData(value=10.0, formula="=A1+1"))  # Has formula!
        sh.set_cell(1, 1, CellData(value=20.0, formula="=B1*2"))

        params = GoalSeekParams(
            target_sheet="Sheet1",
            target_row=1,
            target_col=1,
            goal_value=50.0,
            changing_sheet="Sheet1",
            changing_row=0,
            changing_col=1,
        )

        with pytest.raises(ValueError, match="value"):
            solve_goal_seek(wb, params)

    def test_target_and_changing_cells_are_same(self):
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 1, CellData(value=10.0, formula="=1+1"))

        params = GoalSeekParams(
            target_sheet="Sheet1",
            target_row=0,
            target_col=1,
            goal_value=50.0,
            changing_sheet="Sheet1",
            changing_row=0,
            changing_col=1,
        )

        with pytest.raises(ValueError, match="same"):
            solve_goal_seek(wb, params)

    def test_no_dependency_between_cells(self):
        # Target cell formula doesn't depend on changing cell B1: B2 = "=10 + 20" (constant 30)
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 1, CellData(value=1.0))
        sh.set_cell(1, 1, CellData(value=30.0, formula="=10 + 20"))
        wb.recalculate()

        params = GoalSeekParams(
            target_sheet="Sheet1",
            target_row=1,
            target_col=1,
            goal_value=100.0,
            changing_sheet="Sheet1",
            changing_row=0,
            changing_col=1,
            max_iterations=10,
        )

        res = solve_goal_seek(wb, params)
        assert res.success is False
        assert res.iterations <= 10


class TestGoalSeekDialogs:
    """Test GoalSeekDialog and GoalSeekStatusDialog UI classes."""

    def test_goal_seek_dialog_init(self, qapp):
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 1, CellData(value=5.0))
        sh.set_cell(1, 1, CellData(value=15.0, formula="=B1*3"))
        wb.recalculate()

        dlg = GoalSeekDialog(workbook=wb, current_sheet=sh, initial_r=1, initial_c=1)
        assert dlg.edit_target_cell.text() == "$B$2"
        assert dlg.windowTitle() != ""
        dlg.retranslate_ui()
        dlg.close()

    def test_goal_seek_status_dialog_apply_and_cancel(self, qapp):
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 1, CellData(value=5.0))
        sh.set_cell(1, 1, CellData(value=20.0, formula="=B1*2 + 10"))
        wb.recalculate()

        result = GoalSeekResult(
            success=True,
            solution=20.0,
            iterations=5,
            target_value=50.0,
            current_value=50.0,
            error_margin=0.0001,
            initial_value=5.0,
            target_cell_name="$B$2",
            changing_sheet="Sheet1",
            changing_row=0,
            changing_col=1,
        )

        status_dlg = GoalSeekStatusDialog(workbook=wb, result=result)
        assert "$B$2" in status_dlg.lbl_status.text()
        status_dlg.retranslate_ui()

        # Test apply
        status_dlg.apply_solution()
        assert sh.get_cell_value(0, 1) == 20.0

        # Test revert / cancel
        status_dlg.revert_solution()
        assert sh.get_cell_value(0, 1) == 5.0
        status_dlg.close()

    def test_goal_seek_dialog_validation_and_solve(self, qapp, monkeypatch):
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 1, CellData(value=5.0))
        sh.set_cell(1, 1, CellData(value=20.0, formula="=B1*2 + 10"))
        wb.recalculate()

        dlg = GoalSeekDialog(workbook=wb, current_sheet=sh, initial_r=1, initial_c=1)
        dlg.edit_target_cell.setText("$B$2")
        dlg.edit_goal_value.setText("50")
        dlg.edit_changing_cell.setText("$B$1")

        # Mock GoalSeekStatusDialog.exec to accept
        monkeypatch.setattr(
            GoalSeekStatusDialog, "exec", lambda self: GoalSeekStatusDialog.DialogCode.Accepted
        )

        dlg._on_ok_clicked()
        val = sh.get_cell_value(0, 1)
        assert abs(val - 20.0) < 0.001
        dlg.close()

    def test_mac_menu_integration(self, qapp):
        from PySide6.QtWidgets import QMainWindow
        from atboffice.ui.shell.mac_menu import MacMenuBar

        win = QMainWindow()
        menu_bar = MacMenuBar(app_type="ledger", parent=win)
        assert "tools_goal_seek" in menu_bar.action_map
        assert menu_bar.action_map["tools_goal_seek"].isVisible() is True
        menu_bar.retranslate_ui()
        win.close()

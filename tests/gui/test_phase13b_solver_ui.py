"""Headless Qt GUI tests for Phase 13B Ledger Constrained Solver dialogs."""

from __future__ import annotations

import threading
import time
from typing import Any
from unittest.mock import patch

import pytest
from atboffice.modules.spreadsheet.calc.solver import (
    ConstraintReportItem,
    SolverConstraint,
    SolverOptions,
    SolverParams,
    SolverResult,
    load_solver_model,
    save_solver_model,
)
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from atboffice.core.i18n import get_i18n_manager, load_locale
from atboffice.modules.spreadsheet.dialogs.solver_dialog import (
    AddConstraintDialog,
    SolverOptionsDialog,
    SolverParametersDialog,
    SolverResultsDialog,
)
from atboffice.modules.spreadsheet.models.sheet_model import CellData
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel


@pytest.fixture(autouse=True)
def _reset_locale() -> Any:
    mgr = get_i18n_manager()
    mgr.set_locale("zh-CN")
    yield
    mgr.set_locale("zh-CN")


def _make_lp_workbook() -> WorkbookModel:
    """Create a small 2-variable LP workbook: max 3*A1 + 2*B1 s.t. A1+B1<=4, 2*A1+B1<=6."""
    wb = WorkbookModel()
    sheet = wb.sheets[0]
    sheet.set_cell(0, 0, CellData(value=0.0))  # A1
    sheet.set_cell(0, 1, CellData(value=0.0))  # B1
    sheet.set_cell(0, 2, CellData(formula="=3*A1+2*B1"))  # C1 objective
    sheet.set_cell(0, 3, CellData(formula="=A1+B1"))  # D1 <= 4
    sheet.set_cell(0, 4, CellData(formula="=2*A1+B1"))  # E1 <= 6
    wb.recalculate()
    return wb


class TestSolverDialogsLifecycle:
    def test_preload_initial_cell_and_saved_model(self, qapp: QApplication) -> None:
        wb = _make_lp_workbook()
        sheet = wb.sheets[0]

        dlg_default = SolverParametersDialog(wb, sheet, initial_r=0, initial_c=2)
        try:
            assert dlg_default.objective_edit.text() == "$C$1"
            assert dlg_default.radio_max.isChecked()
            assert dlg_default.non_negative_chk.isChecked()
            assert dlg_default.method_combo.currentData() == "simplex_lp"
        finally:
            dlg_default.close()

        saved = SolverParams(
            objective_ref="$C$1",
            goal="value_of",
            target_value=8.5,
            variable_refs="$A$1:$B$1",
            constraints=[
                SolverConstraint("$D$1", "<=", "4"),
                SolverConstraint("$A$1", "int", ""),
            ],
            make_unconstrained_non_negative=False,
            method="grg_nonlinear",
            default_sheet=sheet.name,
            options=SolverOptions(max_iterations=350, precision=1e-5),
        )
        save_solver_model(sheet, saved)

        dlg_loaded = SolverParametersDialog(wb, sheet, initial_r=4, initial_c=4)
        try:
            assert dlg_loaded.objective_edit.text() == "$C$1"
            assert dlg_loaded.radio_value_of.isChecked()
            assert dlg_loaded.target_value_edit.isEnabled()
            assert dlg_loaded.target_value_edit.text() == "8.5"
            assert dlg_loaded.variables_edit.text() == "$A$1:$B$1"
            assert dlg_loaded.constraints_list.count() == 2
            assert not dlg_loaded.non_negative_chk.isChecked()
            assert dlg_loaded.method_combo.currentData() == "grg_nonlinear"
            assert dlg_loaded.build_params().options.max_iterations == 350
        finally:
            dlg_loaded.close()

    def test_save_model_button_persists_to_sheet(self, qapp: QApplication) -> None:
        wb = _make_lp_workbook()
        sheet = wb.sheets[0]
        dlg = SolverParametersDialog(wb, sheet, initial_r=0, initial_c=2)
        try:
            dlg.variables_edit.setText("A1:B1")
            dlg.radio_min.setChecked(True)
            dlg.save_model_btn.click()

            loaded = load_solver_model(sheet)
            assert loaded is not None
            assert loaded.objective_ref == "$C$1"
            assert loaded.variable_refs == "A1:B1"
            assert loaded.goal == "min"
        finally:
            dlg.close()

    def test_add_edit_delete_reset_constraints(self, qapp: QApplication) -> None:
        wb = _make_lp_workbook()
        sheet = wb.sheets[0]
        dlg = SolverParametersDialog(wb, sheet, initial_r=0, initial_c=2)
        try:
            # Add binary constraint <=
            def add_le(sub: AddConstraintDialog) -> int:
                sub.lhs_edit.setText("D1")
                sub.op_combo.setCurrentIndex(sub.op_combo.findData("<="))
                sub.rhs_edit.setText("4")
                sub.ok_btn.click()
                return sub.result()

            with patch.object(AddConstraintDialog, "exec", add_le):
                dlg.add_constraint_btn.click()

            assert dlg.constraints_list.count() == 1
            assert "D1 <= 4" in dlg.constraints_list.item(0).text()

            # Add unary int constraint via add_more button + ok button
            def add_multi(sub: AddConstraintDialog) -> int:
                sub.lhs_edit.setText("A1")
                sub.op_combo.setCurrentIndex(sub.op_combo.findData("int"))
                assert not sub.rhs_edit.isEnabled()
                sub.add_btn.click()

                sub.lhs_edit.setText("E1")
                sub.op_combo.setCurrentIndex(sub.op_combo.findData(">="))
                assert sub.rhs_edit.isEnabled()
                sub.rhs_edit.setText("1")
                sub.ok_btn.click()
                return sub.result()

            with patch.object(AddConstraintDialog, "exec", add_multi):
                dlg.add_constraint_btn.click()

            assert dlg.constraints_list.count() == 3

            # Edit first constraint
            dlg.constraints_list.setCurrentRow(0)
            assert dlg.edit_constraint_btn.isEnabled()
            assert dlg.delete_constraint_btn.isEnabled()

            def edit_first(sub: AddConstraintDialog) -> int:
                assert sub.lhs_edit.text() == "D1"
                sub.op_combo.setCurrentIndex(sub.op_combo.findData("="))
                sub.rhs_edit.setText("4")
                sub.ok_btn.click()
                return sub.result()

            with patch.object(AddConstraintDialog, "exec", edit_first):
                dlg.edit_constraint_btn.click()

            assert "D1 = 4" in dlg.constraints_list.item(0).text()

            # Delete second constraint
            dlg.constraints_list.setCurrentRow(1)
            dlg.delete_constraint_btn.click()
            assert dlg.constraints_list.count() == 2

            # Reset all
            dlg.variables_edit.setText("A1:B1")
            dlg.radio_min.setChecked(True)
            dlg.non_negative_chk.setChecked(False)
            dlg.reset_all_btn.click()

            assert dlg.objective_edit.text() == ""
            assert dlg.variables_edit.text() == ""
            assert dlg.constraints_list.count() == 0
            assert dlg.radio_max.isChecked()
            assert dlg.non_negative_chk.isChecked()
            assert dlg.method_combo.currentData() == "simplex_lp"
        finally:
            dlg.close()

    def test_options_dialog_update_and_defaults(self, qapp: QApplication) -> None:
        wb = _make_lp_workbook()
        dlg = SolverParametersDialog(wb, wb.sheets[0], initial_r=0, initial_c=2)
        try:

            def edit_opts(opt_dlg: SolverOptionsDialog) -> int:
                opt_dlg.max_iter_spin.setValue(500)
                opt_dlg.max_time_spin.setValue(45.0)
                opt_dlg.precision_edit.setText("1e-7")
                opt_dlg.int_opt_spin.setValue(0.05)
                opt_dlg.pop_size_spin.setValue(60)
                opt_dlg.seed_spin.setValue(99)
                opt_dlg.ok_btn.click()
                return opt_dlg.result()

            with patch.object(SolverOptionsDialog, "exec", edit_opts):
                dlg.options_btn.click()

            opts = dlg.build_params().options
            assert opts.max_iterations == 500
            assert opts.max_time_sec == pytest.approx(45.0)
            assert opts.precision == pytest.approx(1e-7)
            assert opts.integer_optimality == pytest.approx(0.05)
            assert opts.population_size == 60
            assert opts.random_seed == 99

            # Standalone invalid precision + restore defaults check
            opt_dlg = SolverOptionsDialog(options=opts)
            try:
                opt_dlg.precision_edit.setText("-0.1")
                with patch.object(QMessageBox, "warning") as mock_warn:
                    opt_dlg.ok_btn.click()
                assert mock_warn.called
                assert opt_dlg.result() == 0

                opt_dlg.defaults_btn.click()
                opt_dlg.ok_btn.click()
                assert opt_dlg.get_options() == SolverOptions()
            finally:
                opt_dlg.close()
        finally:
            dlg.close()

    def test_retranslate_ui_language_switch(self, qapp: QApplication) -> None:
        wb = _make_lp_workbook()
        params_dlg = SolverParametersDialog(wb, wb.sheets[0], initial_r=0, initial_c=2)
        add_dlg = AddConstraintDialog(constraint=SolverConstraint("A1", "bin"))
        opts_dlg = SolverOptionsDialog()
        dummy_res = SolverResult(
            success=True,
            status="optimal",
            message="规划求解已找到最优解。",
            iterations=4,
            objective_ref="C1",
            initial_objective=0.0,
            final_objective=10.0,
            initial_values={"Sheet1!A1": 0.0},
            solution_values={"Sheet1!A1": 2.0},
            constraint_reports=[ConstraintReportItem("D1", "=A1+B1", 4.0, "<=", "4", True, 0.0)],
            elapsed_sec=0.02,
        )
        res_dlg = SolverResultsDialog(dummy_res)
        try:
            assert "规划求解参数" in params_dlg.windowTitle()
            assert "添加约束" in add_dlg.windowTitle()
            assert "规划求解选项" in opts_dlg.windowTitle()
            assert "规划求解结果" in res_dlg.windowTitle()

            load_locale("en")
            qapp.processEvents()

            assert params_dlg.windowTitle() == "Solver Parameters"
            assert params_dlg.solve_btn.text() != "求解(&S)"
            assert params_dlg.close_btn.text() == "Close"
            assert add_dlg.windowTitle() == "Add Constraint"
            assert add_dlg.cancel_btn.text() == "Cancel"
            assert opts_dlg.windowTitle() == "Solver Options"
            assert res_dlg.windowTitle() == "Solver Results"
            assert "Keep Solver Solution" in res_dlg.keep_radio.text().replace("&", "")

            load_locale("zh-CN")
            qapp.processEvents()

            assert params_dlg.windowTitle() == "规划求解参数"
            assert add_dlg.windowTitle() == "添加约束"
            assert opts_dlg.windowTitle() == "规划求解选项"
            assert res_dlg.windowTitle() == "规划求解结果"
        finally:
            for d in (params_dlg, add_dlg, opts_dlg, res_dlg):
                d.close()


class TestSolverExecutionAndResults:
    def _configure_lp_dialog(
        self,
        wb: WorkbookModel,
        callback: Any = None,
    ) -> SolverParametersDialog:
        sheet = wb.sheets[0]
        dlg = SolverParametersDialog(
            wb,
            sheet,
            initial_r=0,
            initial_c=2,
            apply_callback=callback,
        )
        dlg.variables_edit.setText("A1:B1")
        dlg._constraints = [
            SolverConstraint("D1", "<=", "4"),
            SolverConstraint("E1", "<=", "6"),
        ]
        dlg._refresh_constraints_list()
        return dlg

    def _wait_for_worker_done(self, qapp: QApplication, dlg: SolverParametersDialog) -> None:
        deadline = time.monotonic() + 10.0
        while dlg.last_result is None and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.01)
        assert dlg.last_result is not None

    def test_solve_real_lp_keep_and_generate_report(self, qapp: QApplication) -> None:
        wb = _make_lp_workbook()
        sheet = wb.sheets[0]
        callback_calls: list[tuple[SolverParams, SolverResult, bool]] = []

        def on_apply(params: SolverParams, result: SolverResult, keep: bool) -> None:
            callback_calls.append((params, result, keep))
            if keep:
                for ref, val in result.solution_values.items():
                    if ref.endswith("!A1"):
                        sheet.set_cell_value(0, 0, val)
                    elif ref.endswith("!B1"):
                        sheet.set_cell_value(0, 1, val)
                wb.recalculate()

        dlg = self._configure_lp_dialog(wb, callback=on_apply)
        try:

            def accept_keep_with_report(res_dlg: SolverResultsDialog) -> int:
                res_dlg.keep_radio.setChecked(True)
                res_dlg.report_chk.setChecked(True)
                res_dlg.accept()
                return QDialog.DialogCode.Accepted

            with patch.object(SolverResultsDialog, "exec", accept_keep_with_report):
                dlg.solve_btn.click()
                self._wait_for_worker_done(qapp, dlg)
                qapp.processEvents()

            assert dlg.last_result is not None
            assert dlg.last_result.success is True
            assert dlg.last_result.final_objective == pytest.approx(10.0, abs=1e-4)
            assert len(callback_calls) == 1
            assert callback_calls[0][2] is True
            assert dlg.created_report_sheet is not None
            assert wb.get_sheet_by_name(dlg.created_report_sheet) is not None
            assert load_solver_model(sheet) is not None
            assert sheet.get_cell(0, 2).value == pytest.approx(10.0, abs=1e-4)
        finally:
            dlg.close()

    def test_solve_real_lp_restore_original_values(self, qapp: QApplication) -> None:
        wb = _make_lp_workbook()
        sheet = wb.sheets[0]
        sheet.set_cell_value(0, 0, 1.0)
        sheet.set_cell_value(0, 1, 1.0)
        wb.recalculate()
        callback_calls: list[bool] = []

        def on_apply(_params: SolverParams, _result: SolverResult, keep: bool) -> None:
            callback_calls.append(keep)

        dlg = self._configure_lp_dialog(wb, callback=on_apply)
        try:

            def pick_restore(res_dlg: SolverResultsDialog) -> int:
                res_dlg.restore_radio.setChecked(True)
                res_dlg.accept()
                return QDialog.DialogCode.Accepted

            with patch.object(SolverResultsDialog, "exec", pick_restore):
                dlg.solve_btn.click()
                self._wait_for_worker_done(qapp, dlg)
                qapp.processEvents()

            assert dlg.last_result is not None
            assert dlg.last_result.success is True
            assert callback_calls == [False]
            assert sheet.get_cell(0, 0).value == pytest.approx(1.0)
            assert sheet.get_cell(0, 1).value == pytest.approx(1.0)
            assert dlg.created_report_sheet is None
        finally:
            dlg.close()

    def test_background_solve_cancellation_and_cleanup(self, qapp: QApplication) -> None:
        wb = _make_lp_workbook()
        dlg = self._configure_lp_dialog(wb)
        started = threading.Event()

        def slow_solve(
            workbook: WorkbookModel,
            params: SolverParams,
            cancel_check: Any = None,
            progress_cb: Any = None,
        ) -> SolverResult:
            started.set()
            it = 0
            while not (cancel_check and cancel_check()):
                it += 1
                if progress_cb:
                    progress_cb(it, float(it))
                time.sleep(0.01)
            return SolverResult(
                success=False,
                status="cancelled",
                message="规划求解已取消。",
                iterations=it,
                objective_ref=params.objective_ref,
                initial_objective=0.0,
                final_objective=0.0,
                initial_values={},
                solution_values={},
                constraint_reports=[],
                elapsed_sec=0.02,
            )

        try:
            with patch(
                "atboffice.modules.spreadsheet.dialogs.solver_dialog.solve_model",
                side_effect=slow_solve,
            ):
                dlg.solve_btn.click()
                assert started.wait(timeout=2.0)
                qapp.processEvents()
                assert dlg.cancel_btn.isVisible()
                dlg.cancel_btn.click()
                self._wait_for_worker_done(qapp, dlg)
                qapp.processEvents()

            assert dlg.last_result is not None
            assert dlg.last_result.status == "cancelled"
            assert not dlg.cancel_btn.isVisible()
            assert dlg.solve_btn.isEnabled()
        finally:
            dlg.close()

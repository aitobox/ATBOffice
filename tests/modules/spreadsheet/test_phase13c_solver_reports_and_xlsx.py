"""Tests for Phase 13C Solver Sensitivity/Limits reports, multi-report UI, and XLSX persistence."""

from __future__ import annotations

import io
import zipfile
from typing import Any
from unittest.mock import patch

import pytest
from lxml import etree as LET
from PySide6.QtWidgets import QApplication, QDialog

from atboffice.core.i18n import get_i18n_manager, load_locale
from atboffice.modules.spreadsheet.calc.solver import (
    SolverConstraint,
    SolverOptions,
    SolverParams,
    SolverResult,
    apply_solver_solution,
    generate_limits_report,
    generate_sensitivity_report,
    load_solver_model,
    save_solver_model,
    solve_model,
    solver_params_from_defined_names,
    solver_params_to_defined_names,
)
from atboffice.modules.spreadsheet.dialogs.solver_dialog import (
    SolverParametersDialog,
    SolverResultsDialog,
)
from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel


def _make_classic_lp() -> tuple[WorkbookModel, SolverParams]:
    """Max 40*x1 + 30*x2 s.t. x1+x2<=12, 2*x1+x2<=16, x1,x2>=0 -> (4, 8), obj=400."""
    wb = WorkbookModel()
    sh = wb.active_sheet
    sh.set_cell(0, 0, CellData(value=1.0))  # A1 = x1
    sh.set_cell(0, 1, CellData(value=1.0))  # B1 = x2
    sh.set_cell(1, 0, CellData(value=0.0, formula="=40*A1 + 30*B1"))  # A2 obj
    sh.set_cell(2, 0, CellData(value=0.0, formula="=A1 + B1"))  # A3 <= 12
    sh.set_cell(2, 1, CellData(value=0.0, formula="=2*A1 + B1"))  # B3 <= 16
    wb.recalculate()
    params = SolverParams(
        objective_ref="A2",
        goal="max",
        variable_refs="A1:B1",
        constraints=[
            SolverConstraint("A3", "<=", "12"),
            SolverConstraint("B3", "<=", "16"),
        ],
        method="simplex_lp",
        default_sheet=sh.name,
    )
    return wb, params


def _sheet_rows(sheet: SheetDataModel) -> list[list[Any]]:
    if not sheet.cells:
        return []
    max_r = max(r for r, _ in sheet.cells)
    max_c = max(c for _, c in sheet.cells)
    rows: list[list[Any]] = []
    for r in range(max_r + 1):
        row_vals = []
        for c in range(max_c + 1):
            cell = sheet.get_cell(r, c)
            row_vals.append(cell.value if cell is not None else None)
        rows.append(row_vals)
    return rows


class TestSensitivityReport:
    """Test Sensitivity Report generation for LP, Nonlinear, and Evolutionary models."""

    def test_lp_sensitivity_report_values_and_unique_naming(self) -> None:
        wb, params = _make_classic_lp()
        res = solve_model(wb, params)
        assert res.success is True

        # Ensure workbook is untouched before & after report generation
        assert wb.active_sheet.get_cell_value(0, 0) == 1.0
        assert wb.active_sheet.get_cell_value(0, 1) == 1.0

        name1 = generate_sensitivity_report(wb, params, res)
        name2 = generate_sensitivity_report(wb, params, res)
        assert name1 == "Sensitivity Report 1"
        assert name2 == "Sensitivity Report 2"
        assert wb.active_sheet.get_cell_value(0, 0) == 1.0
        assert wb.active_sheet.get_cell_value(0, 1) == 1.0

        rows = _sheet_rows(wb.get_sheet_by_name(name1))
        var_a1 = next(r for r in rows if r and r[0] == "A1")
        var_b1 = next(r for r in rows if r and r[0] == "B1")
        # A1: val=4, rc=0, obj_coeff=40, allow_inc=20, allow_dec=10
        assert var_a1[1] == pytest.approx(4.0)
        assert var_a1[2] == pytest.approx(0.0)
        assert var_a1[3] == pytest.approx(40.0)
        assert var_a1[4] == pytest.approx(20.0)
        assert var_a1[5] == pytest.approx(10.0)
        # B1: val=8, rc=0, obj_coeff=30, allow_inc=10, allow_dec=10
        assert var_b1[1] == pytest.approx(8.0)
        assert var_b1[2] == pytest.approx(0.0)
        assert var_b1[3] == pytest.approx(30.0)
        assert var_b1[4] == pytest.approx(10.0)
        assert var_b1[5] == pytest.approx(10.0)

        con_a3 = next(r for r in rows if r and r[0] == "A3")
        con_b3 = next(r for r in rows if r and r[0] == "B3")
        # A3: val=12, shadow=20, rhs=12, allow_inc=4, allow_dec=4
        assert con_a3[1] == pytest.approx(12.0)
        assert con_a3[2] == pytest.approx(20.0)
        assert con_a3[3] == pytest.approx(12.0)
        assert con_a3[4] == pytest.approx(4.0)
        assert con_a3[5] == pytest.approx(4.0)
        # B3: val=16, shadow=10, rhs=16, allow_inc=8, allow_dec=4
        assert con_b3[1] == pytest.approx(16.0)
        assert con_b3[2] == pytest.approx(10.0)
        assert con_b3[3] == pytest.approx(16.0)
        assert con_b3[4] == pytest.approx(8.0)
        assert con_b3[5] == pytest.approx(4.0)

    def test_lp_sensitivity_non_basic_reduced_cost(self) -> None:
        # Max 3*x1 + 2*x2 s.t. x1 + x2 <= 10 -> x1=10, x2=0, reduced cost(x2) = -1
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 0, CellData(value=0.0))
        sh.set_cell(0, 1, CellData(value=0.0))
        sh.set_cell(1, 0, CellData(value=0.0, formula="=3*A1 + 2*B1"))
        sh.set_cell(2, 0, CellData(value=0.0, formula="=A1 + B1"))
        wb.recalculate()
        params = SolverParams(
            objective_ref="A2",
            goal="max",
            variable_refs="A1:B1",
            constraints=[SolverConstraint("A3", "<=", "10")],
            method="simplex_lp",
        )
        res = solve_model(wb, params)
        assert res.success is True
        name = generate_sensitivity_report(wb, params, res)
        rows = _sheet_rows(wb.get_sheet_by_name(name))
        var_b1 = next(r for r in rows if r and r[0] == "B1")
        assert var_b1[1] == pytest.approx(0.0)
        assert var_b1[2] == pytest.approx(-1.0)
        assert var_b1[3] == pytest.approx(2.0)
        assert var_b1[4] == pytest.approx(1.0)
        assert var_b1[5] >= 1e20

    def test_nonlinear_and_evolutionary_sensitivity_report(self) -> None:
        # Nonlinear: min (x - 3)^2 + (y - 2)^2 s.t. x + y <= 4 -> (2.5, 1.5)
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 0, CellData(value=0.5))
        sh.set_cell(0, 1, CellData(value=0.5))
        sh.set_cell(1, 0, CellData(value=0.0, formula="=(A1 - 3)^2 + (B1 - 2)^2"))
        sh.set_cell(2, 0, CellData(value=0.0, formula="=A1 + B1"))
        wb.recalculate()

        grg_params = SolverParams(
            objective_ref="A2",
            goal="min",
            variable_refs="A1:B1",
            constraints=[SolverConstraint("A3", "<=", "4")],
            method="grg_nonlinear",
        )
        grg_res = solve_model(wb, grg_params)
        assert grg_res.success is True
        s_name = generate_sensitivity_report(wb, grg_params, grg_res)
        rows = _sheet_rows(wb.get_sheet_by_name(s_name))
        var_a1 = next(r for r in rows if r and r[0] == "A1")
        con_a3 = next(r for r in rows if r and r[0] == "A3")
        assert var_a1[1] == pytest.approx(2.5, abs=1e-2)
        assert var_a1[2] == pytest.approx(0.0, abs=1e-2)
        assert con_a3[2] == pytest.approx(-1.0, abs=5e-2)

        # Evolutionary discontinuous + integer
        sh.set_cell(1, 1, CellData(value=0.0, formula="=ABS(A1 - 7) + IF(A1 < 5, 100, 0)"))
        wb.recalculate()
        ea_params = SolverParams(
            objective_ref="B2",
            goal="min",
            variable_refs="A1",
            constraints=[SolverConstraint("A1", "int")],
            method="evolutionary",
            options=SolverOptions(max_iterations=80, population_size=30, random_seed=42),
        )
        ea_res = solve_model(wb, ea_params)
        assert ea_res.success is True
        ea_name = generate_sensitivity_report(wb, ea_params, ea_res)
        assert ea_name == "Sensitivity Report 2"
        assert sh.get_cell_value(0, 0) == 0.5


class TestLimitsReport:
    """Test Limits Report feasible lower/upper limits and objective results."""

    def test_lp_limits_report(self) -> None:
        wb, params = _make_classic_lp()
        res = solve_model(wb, params)
        assert res.success is True

        name1 = generate_limits_report(wb, params, res)
        name2 = generate_limits_report(wb, params, res)
        assert name1 == "Limits Report 1"
        assert name2 == "Limits Report 2"

        rows = _sheet_rows(wb.get_sheet_by_name(name1))
        var_a1 = next(r for r in rows if r and r[0] == "A1")
        var_b1 = next(r for r in rows if r and r[0] == "B1")

        # Holding B1=8: A1 in [0, 4], obj in [240, 400]
        assert var_a1[1] == pytest.approx(4.0)
        assert var_a1[2] == pytest.approx(0.0)
        assert var_a1[3] == pytest.approx(240.0)
        assert var_a1[4] == pytest.approx(4.0)
        assert var_a1[5] == pytest.approx(400.0)

        # Holding A1=4: B1 in [0, 8], obj in [160, 400]
        assert var_b1[1] == pytest.approx(8.0)
        assert var_b1[2] == pytest.approx(0.0)
        assert var_b1[3] == pytest.approx(160.0)
        assert var_b1[4] == pytest.approx(8.0)
        assert var_b1[5] == pytest.approx(400.0)

        # Workbook values still preserved
        assert wb.active_sheet.get_cell_value(0, 0) == 1.0
        assert wb.active_sheet.get_cell_value(0, 1) == 1.0

    def test_nonlinear_limits_report(self) -> None:
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 0, CellData(value=0.5))
        sh.set_cell(0, 1, CellData(value=0.5))
        sh.set_cell(1, 0, CellData(value=0.0, formula="=(A1 - 3)^2 + (B1 - 2)^2"))
        sh.set_cell(2, 0, CellData(value=0.0, formula="=A1 + B1"))
        wb.recalculate()

        params = SolverParams(
            objective_ref="A2",
            goal="min",
            variable_refs="A1:B1",
            constraints=[SolverConstraint("A3", "<=", "4")],
            method="grg_nonlinear",
        )
        res = solve_model(wb, params)
        assert res.success is True
        name = generate_limits_report(wb, params, res)
        rows = _sheet_rows(wb.get_sheet_by_name(name))
        var_a1 = next(r for r in rows if r and r[0] == "A1")
        assert var_a1[2] == pytest.approx(0.0, abs=1e-3)
        assert var_a1[3] == pytest.approx(9.25, abs=5e-2)
        assert var_a1[4] == pytest.approx(2.5, abs=1e-2)
        assert var_a1[5] == pytest.approx(0.5, abs=1e-2)


class TestDefinedNamesAndXlsxRoundTrip:
    """Test solver_* hidden sheet-scoped definedNames and XLSX persistence."""

    def test_defined_names_codec_all_operators_and_options(self) -> None:
        params = SolverParams(
            objective_ref="$D$5",
            goal="value_of",
            target_value=42.5,
            variable_refs="$A$1:$B$2, $C$1",
            constraints=[
                SolverConstraint("$E$1", "<=", "100"),
                SolverConstraint("$E$2", "=", "$F$2"),
                SolverConstraint("$E$3", ">=", "5"),
                SolverConstraint("$A$1:$A$2", "int"),
                SolverConstraint("$B$1", "bin"),
                SolverConstraint("$A$1:$B$2", "dif"),
            ],
            make_unconstrained_non_negative=False,
            method="evolutionary",
            default_sheet="My Sheet",
            options=SolverOptions(
                max_iterations=350,
                max_time_sec=45.5,
                precision=1e-7,
                integer_optimality=0.02,
                population_size=64,
                random_seed=123,
            ),
        )
        entries = solver_params_to_defined_names(params, sheet_idx=2)
        as_map = {(name, idx): val for name, idx, val in entries}
        assert as_map[("solver_opt", 2)] == "'My Sheet'!$D$5"
        assert as_map[("solver_typ", 2)] == "3"
        assert as_map[("solver_val", 2)] == "42.5"
        assert as_map[("solver_num", 2)] == "6"
        assert as_map[("solver_rel1", 2)] == "1"
        assert as_map[("solver_rel2", 2)] == "2"
        assert as_map[("solver_rel3", 2)] == "3"
        assert as_map[("solver_rel4", 2)] == "4"
        assert as_map[("solver_rel5", 2)] == "5"
        assert as_map[("solver_rel6", 2)] == "6"
        assert as_map[("solver_neg", 2)] == "2"
        assert as_map[("solver_eng", 2)] == "3"
        assert as_map[("solver_itr", 2)] == "350"
        assert as_map[("solver_pop", 2)] == "64"
        assert as_map[("solver_sed", 2)] == "123"

        assert solver_params_from_defined_names(entries, sheet_idx=0, sheet_name="Sheet1") is None
        restored = solver_params_from_defined_names(entries, sheet_idx=2, sheet_name="My Sheet")
        assert restored == params

    def test_xlsx_roundtrip_with_initially_empty_defined_names(self) -> None:
        wb = WorkbookModel()
        sh1 = wb.active_sheet
        sh1.set_cell(0, 0, CellData(value=2.0))
        sh1.set_cell(0, 1, CellData(value=3.0))
        sh1.set_cell(1, 0, CellData(value=0.0, formula="=40*A1+30*B1"))
        sh2 = SheetDataModel(name="Second Sheet")
        wb.add_sheet(sheet=sh2)
        sh2.set_cell(0, 0, CellData(value=1.0))
        sh2.set_cell(1, 0, CellData(value=0.0, formula="=A1^2"))
        wb.recalculate()

        assert wb.extra.get("defined_names") is None

        p1 = SolverParams(
            objective_ref="A2",
            goal="max",
            variable_refs="A1:B1",
            constraints=[SolverConstraint("A1", "<=", "10"), SolverConstraint("B1", "int")],
            method="simplex_lp",
            default_sheet=sh1.name,
        )
        p2 = SolverParams(
            objective_ref="$A$2",
            goal="value_of",
            target_value=9.0,
            variable_refs="$A$1",
            constraints=[SolverConstraint("$A$1", ">=", "0")],
            make_unconstrained_non_negative=False,
            method="grg_nonlinear",
            default_sheet=sh2.name,
            options=SolverOptions(max_iterations=150, precision=1e-5),
        )
        save_solver_model(sh1, p1)
        save_solver_model(sh2, p2)

        payload = write_xlsx(wb)

        # Inspect xl/workbook.xml directly
        with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
            wb_xml = LET.fromstring(zf.read("xl/workbook.xml"))
        dn_els = [
            el for el in wb_xml.iter() if el.tag.endswith("}definedName") or el.tag == "definedName"
        ]
        assert any(
            el.get("name") == "solver_opt"
            and el.get("hidden") == "1"
            and el.get("localSheetId") == "0"
            for el in dn_els
        )
        assert any(
            el.get("name") == "solver_opt"
            and el.get("hidden") == "1"
            and el.get("localSheetId") == "1"
            for el in dn_els
        )

        wb_read = read_xlsx(io.BytesIO(payload))
        assert load_solver_model(wb_read.sheets[0]) == p1
        assert load_solver_model(wb_read.sheets[1]) == p2

    def test_xlsx_preserves_user_defined_names_and_in_place_updates(self) -> None:
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 0, CellData(value=1.0))
        sh.set_cell(1, 0, CellData(value=0.0, formula="=2*A1"))
        wb.recalculate()

        wb.extra["defined_names"] = (
            "<definedNames>"
            '<definedName name="Sales">Sheet1!$A$1:$B$3</definedName>'
            '<definedName name="_xlnm.Print_Area" localSheetId="0">Sheet1!$A$1:$D$10</definedName>'
            "</definedNames>"
        )
        p1 = SolverParams(
            objective_ref="A2",
            goal="max",
            variable_refs="A1",
            constraints=[SolverConstraint("A1", "<=", "5")],
            method="simplex_lp",
            default_sheet="Sheet1",
        )
        save_solver_model(sh, p1)

        bytes1 = write_xlsx(wb)
        wb_loaded = read_xlsx(io.BytesIO(bytes1))

        # User defined names preserved verbatim alongside loaded solver_model
        assert "Sales" in (wb_loaded.extra.get("defined_names") or "")
        assert "_xlnm.Print_Area" in (wb_loaded.extra.get("defined_names") or "")
        assert load_solver_model(wb_loaded.sheets[0]) == p1

        # Now update solver model on source-backed workbook and write again (lxml in-place patch)
        p1_updated = SolverParams(
            objective_ref="A2",
            goal="min",
            variable_refs="A1",
            constraints=[SolverConstraint("A1", ">=", "2")],
            method="grg_nonlinear",
            default_sheet="Sheet1",
        )
        save_solver_model(wb_loaded.sheets[0], p1_updated)
        bytes2 = write_xlsx(wb_loaded)

        with zipfile.ZipFile(io.BytesIO(bytes2), "r") as zf:
            wb_xml2 = LET.fromstring(zf.read("xl/workbook.xml"))
        names2 = [
            (el.get("name"), el.get("localSheetId"), el.text or "")
            for el in wb_xml2.iter()
            if el.tag.endswith("}definedName") or el.tag == "definedName"
        ]
        assert ("Sales", None, "Sheet1!$A$1:$B$3") in names2
        assert ("_xlnm.Print_Area", "0", "Sheet1!$A$1:$D$10") in names2
        # Old solver_typ=1 replaced cleanly by solver_typ=2 (no duplicate solver_typ)
        typ_entries = [item for item in names2 if item[0] == "solver_typ"]
        assert typ_entries == [("solver_typ", "0", "2")]

        wb_reloaded = read_xlsx(io.BytesIO(bytes2))
        assert load_solver_model(wb_reloaded.sheets[0]) == p1_updated
        assert "Sales" in (wb_reloaded.extra.get("defined_names") or "")


class TestMultiReportDialog:
    """Test SolverResultsDialog multi-report selection and SolverParametersDialog wiring."""

    def test_results_dialog_multi_report_checkboxes_and_retranslate(
        self, qapp: QApplication
    ) -> None:
        mgr = get_i18n_manager()
        mgr.set_locale("zh-CN")
        dummy = SolverResult(
            success=True,
            status="optimal",
            message="ok",
            iterations=2,
            objective_ref="A2",
            initial_objective=0.0,
            final_objective=10.0,
            initial_values={"A1": 0.0},
            solution_values={"A1": 5.0},
            constraint_reports=[],
            elapsed_sec=0.01,
        )
        dlg = SolverResultsDialog(dummy)
        try:
            assert dlg.report_checkbox is dlg.report_chk
            assert "运算结果" in dlg.report_chk.text()
            assert "灵敏度" in dlg.sensitivity_report_chk.text()
            assert "极限值" in dlg.limits_report_chk.text()

            load_locale("en")
            qapp.processEvents()
            assert dlg.windowTitle() == "Solver Results"
            assert "Answer" in dlg.report_chk.text().replace("&", "")
            load_locale("zh-CN")
            qapp.processEvents()

            dlg.report_chk.setChecked(True)
            dlg.sensitivity_report_chk.setChecked(True)
            dlg.limits_report_chk.setChecked(True)
            dlg.accept()
            assert dlg.generate_report is True
            assert dlg.generate_sensitivity is True
            assert dlg.generate_limits is True
            assert dlg.selected_reports == ["answer", "sensitivity", "limits"]
        finally:
            dlg.close()

    def test_parameters_dialog_generates_all_selected_reports(self, qapp: QApplication) -> None:
        wb, _ = _make_classic_lp()
        sh = wb.active_sheet
        dlg = SolverParametersDialog(wb, sh, initial_r=1, initial_c=0)
        try:
            dlg.variables_edit.setText("A1:B1")
            dlg._constraints = [
                SolverConstraint("A3", "<=", "12"),
                SolverConstraint("B3", "<=", "16"),
            ]
            dlg._refresh_constraints_list()

            def accept_all_reports(res_dlg: SolverResultsDialog) -> int:
                res_dlg.keep_radio.setChecked(True)
                res_dlg.report_chk.setChecked(True)
                res_dlg.sensitivity_report_chk.setChecked(True)
                res_dlg.limits_report_chk.setChecked(True)
                res_dlg.accept()
                return QDialog.DialogCode.Accepted

            with patch.object(SolverResultsDialog, "exec", accept_all_reports):
                dlg.solve_btn.click()
                import time

                deadline = time.monotonic() + 10.0
                while dlg.last_result is None and time.monotonic() < deadline:
                    qapp.processEvents()
                    time.sleep(0.01)
                qapp.processEvents()

            assert dlg.created_report_sheet == "Answer Report 1"
            assert dlg.created_report_sheets == [
                "Answer Report 1",
                "Sensitivity Report 1",
                "Limits Report 1",
            ]
            for name in dlg.created_report_sheets:
                assert wb.get_sheet_by_name(name) is not None
            assert sh.get_cell_value(0, 0) == pytest.approx(4.0, abs=1e-4)
            assert sh.get_cell_value(0, 1) == pytest.approx(8.0, abs=1e-4)
            assert sh.get_cell_value(1, 0) == pytest.approx(400.0, abs=1e-4)

            # Also verify Sensitivity + Limits without Answer sets created_report_sheet cleanly
            apply_solver_solution(wb, {"A1": 1.0, "B1": 1.0})
            dlg2 = SolverParametersDialog(wb, sh, initial_r=1, initial_c=0)
            try:
                dlg2.variables_edit.setText("A1:B1")
                dlg2._constraints = [
                    SolverConstraint("A3", "<=", "12"),
                    SolverConstraint("B3", "<=", "16"),
                ]

                def accept_sens_limits_only(res_dlg: SolverResultsDialog) -> int:
                    res_dlg.keep_radio.setChecked(True)
                    res_dlg.report_chk.setChecked(False)
                    res_dlg.sensitivity_report_chk.setChecked(True)
                    res_dlg.limits_report_chk.setChecked(True)
                    res_dlg.accept()
                    return QDialog.DialogCode.Accepted

                with patch.object(SolverResultsDialog, "exec", accept_sens_limits_only):
                    dlg2.solve_btn.click()
                    deadline = time.monotonic() + 10.0
                    while dlg2.last_result is None and time.monotonic() < deadline:
                        qapp.processEvents()
                        time.sleep(0.01)
                    qapp.processEvents()

                assert dlg2.created_report_sheets == [
                    "Sensitivity Report 2",
                    "Limits Report 2",
                ]
                assert dlg2.created_report_sheet == "Sensitivity Report 2"
            finally:
                dlg2.close()
        finally:
            dlg.close()

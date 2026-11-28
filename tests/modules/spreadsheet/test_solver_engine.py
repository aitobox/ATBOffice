"""Tests for Phase 13B Ledger Constrained Solver engine."""

from __future__ import annotations

import pytest

from atboffice.core.i18n import load_locale
from atboffice.modules.spreadsheet.calc.solver import (
    SolverConstraint,
    SolverOptions,
    SolverParams,
    apply_solver_solution,
    format_cell_ref,
    generate_answer_report,
    load_solver_model,
    parse_cell_list,
    save_solver_model,
    solve_model,
)
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel


class TestCellListAndFormat:
    """Test cell list parsing and cell reference formatting."""

    def test_parse_single_and_ranges_dedup(self):
        coords = parse_cell_list("A1, $B$2:C3, B2, Sheet2!$D$4", default_sheet="Sheet1")
        assert coords == [
            ("Sheet1", 0, 0),
            ("Sheet1", 1, 1),
            ("Sheet1", 1, 2),
            ("Sheet1", 2, 1),
            ("Sheet1", 2, 2),
            ("Sheet2", 3, 3),
        ]

    def test_parse_quoted_sheet_names(self):
        coords = parse_cell_list("'My Sheet'!$A$1:$A$2, 'O''Brien'!B3", default_sheet="Sheet1")
        assert coords == [
            ("My Sheet", 0, 0),
            ("My Sheet", 1, 0),
            ("O'Brien", 2, 1),
        ]

    def test_parse_empty_and_invalid(self):
        assert parse_cell_list("") == []
        with pytest.raises(ValueError):
            parse_cell_list("Bad!!Ref")
        with pytest.raises(ValueError):
            parse_cell_list("Sheet1!A1:Sheet2!B2")

    def test_format_cell_ref(self):
        assert format_cell_ref("Sheet1", 0, 0, default_sheet="Sheet1") == "A1"
        assert format_cell_ref("Sheet2", 1, 2, default_sheet="Sheet1") == "Sheet2!C2"
        assert format_cell_ref("My Sheet", 0, 1, default_sheet="Sheet1") == "'My Sheet'!B1"
        assert format_cell_ref("Sheet1", 0, 0) == "Sheet1!A1"


class TestValidationAndRestoration:
    """Test input validation, cancellation, and workbook restoration guarantees."""

    def test_invalid_objective_and_variables(self):
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 0, CellData(value=5.0))
        sh.set_cell(0, 1, CellData(value=10.0))  # No formula

        # Objective has no formula
        res1 = solve_model(wb, SolverParams(objective_ref="B1", variable_refs="A1"))
        assert res1.success is False
        assert res1.status == "invalid_input"

        # Variable overlaps objective
        sh.set_cell(0, 1, CellData(value=10.0, formula="=A1*2"))
        wb.recalculate()
        res2 = solve_model(wb, SolverParams(objective_ref="B1", variable_refs="B1"))
        assert res2.success is False
        assert res2.status == "invalid_input"

        # Empty variable list
        res3 = solve_model(wb, SolverParams(objective_ref="B1", variable_refs=""))
        assert res3.success is False
        assert res3.status == "invalid_input"

        # Variable cell contains formula
        sh.set_cell(0, 2, CellData(value=1.0, formula="=A1+1"))
        res4 = solve_model(wb, SolverParams(objective_ref="B1", variable_refs="C1"))
        assert res4.success is False
        assert res4.status == "invalid_input"

    def test_circular_reference_rejected(self):
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 0, CellData(value=1.0))
        sh.set_cell(0, 1, CellData(value=0.0, formula="=C1+A1"))
        sh.set_cell(0, 2, CellData(value=0.0, formula="=B1+1"))
        res = solve_model(wb, SolverParams(objective_ref="B1", variable_refs="A1"))
        assert res.success is False
        assert res.status == "invalid_input"

    def test_workbook_restored_on_success_failure_and_cancel(self):
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 0, CellData(value=3.0))  # A1
        # B1 initially empty (not even in sh.cells)
        sh.set_cell(0, 2, CellData(value=0.0, formula="=A1 + B1"))  # C1
        wb.recalculate()
        sh.dirty = False

        # Success run
        res = solve_model(
            wb,
            SolverParams(
                objective_ref="C1",
                goal="max",
                variable_refs="A1, B1",
                constraints=[
                    SolverConstraint("A1", "<=", "10"),
                    SolverConstraint("B1", "<=", "5"),
                ],
                method="simplex_lp",
            ),
        )
        assert res.success is True
        assert abs(res.final_objective - 15.0) < 1e-6
        assert sh.get_cell_value(0, 0) == 3.0
        assert sh.get_cell(0, 1) is None
        assert sh.get_cell_value(0, 2) == 3.0
        assert sh.dirty is False

        # Cancel immediately
        res_cancel = solve_model(
            wb,
            SolverParams(
                objective_ref="C1",
                goal="max",
                variable_refs="A1, B1",
                constraints=[SolverConstraint("A1", "<=", "10")],
                method="evolutionary",
            ),
            cancel_check=lambda: True,
        )
        assert res_cancel.success is False
        assert res_cancel.status == "cancelled"
        assert sh.get_cell_value(0, 0) == 3.0
        assert sh.get_cell(0, 1) is None
        assert sh.dirty is False


class TestSimplexLPAndMILP:
    """Test Two-Phase Simplex LP, nonlinearity rejection, and Branch-and-Bound MILP."""

    def test_lp_maximization(self):
        # Maximize 40*x1 + 30*x2
        # s.t. x1 + x2 <= 12, 2*x1 + x2 <= 16, x1, x2 >= 0
        # Optimal: x1 = 4, x2 = 8, obj = 400
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 0, CellData(value=0.0))  # A1 = x1
        sh.set_cell(0, 1, CellData(value=0.0))  # B1 = x2
        sh.set_cell(1, 0, CellData(value=0.0, formula="=40*A1 + 30*B1"))  # A2 obj
        sh.set_cell(2, 0, CellData(value=0.0, formula="=A1 + B1"))  # A3 c1
        sh.set_cell(2, 1, CellData(value=0.0, formula="=2*A1 + B1"))  # B3 c2
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
        )
        res = solve_model(wb, params)
        assert res.success is True
        assert res.status == "optimal"
        assert abs(res.final_objective - 400.0) < 1e-6
        assert abs(res.solution_values["A1"] - 4.0) < 1e-6
        assert abs(res.solution_values["B1"] - 8.0) < 1e-6
        assert len(res.constraint_reports) == 2
        assert all(cr.binding for cr in res.constraint_reports)

    def test_lp_minimization_with_ge_and_eq_and_free_vars(self):
        # Minimize 2*x1 + 3*x2 s.t. x1 + x2 >= 10, x1 - x2 = 2, x1, x2 >= 0
        # => x1 = 6, x2 = 4, obj = 24
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 0, CellData(value=0.0))
        sh.set_cell(0, 1, CellData(value=0.0))
        sh.set_cell(1, 0, CellData(value=0.0, formula="=2*A1 + 3*B1"))
        sh.set_cell(2, 0, CellData(value=0.0, formula="=A1 + B1"))
        sh.set_cell(2, 1, CellData(value=0.0, formula="=A1 - B1"))
        sh.set_cell(2, 2, CellData(value=10.0))  # C3 = 10 (cell RHS)
        wb.recalculate()

        params = SolverParams(
            objective_ref="A2",
            goal="min",
            variable_refs="A1, B1",
            constraints=[
                SolverConstraint("A3", ">=", "C3"),
                SolverConstraint("B3", "=", "2"),
            ],
            method="simplex_lp",
        )
        res = solve_model(wb, params)
        assert res.success is True
        assert abs(res.final_objective - 24.0) < 1e-6
        assert abs(res.solution_values["A1"] - 6.0) < 1e-6
        assert abs(res.solution_values["B1"] - 4.0) < 1e-6

        # Free (unconstrained sign) variable test:
        # Min x1 s.t. x1 >= -5 (with non-negative disabled) => x1 = -5
        sh.set_cell(1, 1, CellData(value=0.0, formula="=A1"))
        wb.recalculate()
        res_free = solve_model(
            wb,
            SolverParams(
                objective_ref="B2",
                goal="min",
                variable_refs="A1",
                constraints=[SolverConstraint("A1", ">=", "-5")],
                make_unconstrained_non_negative=False,
                method="simplex_lp",
            ),
        )
        assert res_free.success is True
        assert abs(res_free.final_objective - (-5.0)) < 1e-6

    def test_lp_value_of(self):
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 0, CellData(value=1.0))
        sh.set_cell(0, 1, CellData(value=1.0))
        sh.set_cell(1, 0, CellData(value=0.0, formula="=3*A1 + 5*B1"))
        sh.set_cell(2, 0, CellData(value=0.0, formula="=A1 + B1"))
        wb.recalculate()

        res = solve_model(
            wb,
            SolverParams(
                objective_ref="A2",
                goal="value_of",
                target_value=22.0,
                variable_refs="A1:B1",
                constraints=[SolverConstraint("A3", "<=", "6")],
                method="simplex_lp",
            ),
        )
        assert res.success is True
        assert abs(res.final_objective - 22.0) < 1e-5

    def test_lp_infeasible_and_unbounded(self):
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 0, CellData(value=1.0))
        sh.set_cell(1, 0, CellData(value=0.0, formula="=A1*2"))
        wb.recalculate()

        # Infeasible: A1 >= 10 and A1 <= 5
        res_inf = solve_model(
            wb,
            SolverParams(
                objective_ref="A2",
                goal="max",
                variable_refs="A1",
                constraints=[
                    SolverConstraint("A1", ">=", "10"),
                    SolverConstraint("A1", "<=", "5"),
                ],
                method="simplex_lp",
            ),
        )
        assert res_inf.success is False
        assert res_inf.status == "infeasible"

        # Unbounded: max 2*A1 s.t. A1 >= 0
        res_unb = solve_model(
            wb,
            SolverParams(
                objective_ref="A2",
                goal="max",
                variable_refs="A1",
                constraints=[],
                method="simplex_lp",
            ),
        )
        assert res_unb.success is False
        assert res_unb.status == "unbounded"

    def test_lp_rejects_nonlinear_models(self):
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 0, CellData(value=2.0))
        sh.set_cell(0, 1, CellData(value=3.0))
        # Quadratic objective
        sh.set_cell(1, 0, CellData(value=0.0, formula="=A1^2 + B1"))
        # Bilinear constraint
        sh.set_cell(1, 1, CellData(value=0.0, formula="=A1 * B1"))
        sh.set_cell(2, 0, CellData(value=0.0, formula="=A1 + B1"))
        wb.recalculate()

        res_quad = solve_model(
            wb,
            SolverParams(
                objective_ref="A2",
                goal="min",
                variable_refs="A1:B1",
                method="simplex_lp",
            ),
        )
        assert res_quad.success is False
        assert res_quad.status == "non_linear"

        res_bilin = solve_model(
            wb,
            SolverParams(
                objective_ref="A3",
                goal="max",
                variable_refs="A1:B1",
                constraints=[SolverConstraint("B2", "<=", "10")],
                method="simplex_lp",
            ),
        )
        assert res_bilin.success is False
        assert res_bilin.status == "non_linear"

    def test_milp_integer_and_binary_branch_and_bound(self):
        # Classic IP: max 8*x1 + 5*x2 s.t. x1 + x2 <= 6, 9*x1 + 5*x2 <= 45, x1, x2 int >= 0
        # LP relaxation = 41.25 (3.75, 2.25); IP optimal = 40 (5, 0)
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 0, CellData(value=0.0))
        sh.set_cell(0, 1, CellData(value=0.0))
        sh.set_cell(1, 0, CellData(value=0.0, formula="=8*A1 + 5*B1"))
        sh.set_cell(2, 0, CellData(value=0.0, formula="=A1 + B1"))
        sh.set_cell(2, 1, CellData(value=0.0, formula="=9*A1 + 5*B1"))
        wb.recalculate()

        res_ip = solve_model(
            wb,
            SolverParams(
                objective_ref="A2",
                goal="max",
                variable_refs="A1:B1",
                constraints=[
                    SolverConstraint("A3", "<=", "6"),
                    SolverConstraint("B3", "<=", "45"),
                    SolverConstraint("A1:B1", "int"),
                ],
                method="simplex_lp",
                options=SolverOptions(integer_optimality=0.0),
            ),
        )
        assert res_ip.success is True
        assert abs(res_ip.final_objective - 40.0) < 1e-6
        assert abs(res_ip.solution_values["A1"] - 5.0) < 1e-6
        assert abs(res_ip.solution_values["B1"] - 0.0) < 1e-6

        # 0-1 Knapsack with binary constraint:
        # values: 10, 14, 12; weights: 4, 6, 5; cap <= 10 => pick items 1 & 2 (val=24, w=10)
        sh2 = SheetDataModel(name="Knap")
        wb.add_sheet(sheet=sh2)
        for c_idx in range(3):
            sh2.set_cell(0, c_idx, CellData(value=0.0))  # A1:C1 bin
        sh2.set_cell(1, 0, CellData(value=0.0, formula="=10*A1 + 14*B1 + 12*C1"))
        sh2.set_cell(2, 0, CellData(value=0.0, formula="=4*A1 + 6*B1 + 5*C1"))
        wb.recalculate()

        res_bin = solve_model(
            wb,
            SolverParams(
                objective_ref="A2",
                goal="max",
                variable_refs="A1:C1",
                constraints=[
                    SolverConstraint("A3", "<=", "10"),
                    SolverConstraint("A1:C1", "bin"),
                ],
                method="simplex_lp",
                default_sheet="Knap",
                options=SolverOptions(integer_optimality=0.0),
            ),
        )
        assert res_bin.success is True
        assert abs(res_bin.final_objective - 24.0) < 1e-6
        assert abs(res_bin.solution_values["A1"] - 1.0) < 1e-6
        assert abs(res_bin.solution_values["B1"] - 1.0) < 1e-6
        assert abs(res_bin.solution_values["C1"] - 0.0) < 1e-6


class TestGRGNonlinear:
    """Test GRG Nonlinear constrained optimization."""

    def test_grg_constrained_quadratic_min_and_max(self):
        # Min (x - 3)^2 + (y - 2)^2 s.t. x + y <= 4, x, y >= 0 => (2.5, 1.5), obj = 0.5
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 0, CellData(value=0.5))
        sh.set_cell(0, 1, CellData(value=0.5))
        sh.set_cell(1, 0, CellData(value=0.0, formula="=(A1 - 3)^2 + (B1 - 2)^2"))
        sh.set_cell(2, 0, CellData(value=0.0, formula="=A1 + B1"))
        wb.recalculate()

        res_min = solve_model(
            wb,
            SolverParams(
                objective_ref="A2",
                goal="min",
                variable_refs="A1:B1",
                constraints=[SolverConstraint("A3", "<=", "4")],
                method="grg_nonlinear",
            ),
        )
        assert res_min.success is True
        assert abs(res_min.final_objective - 0.5) < 1e-3
        assert abs(res_min.solution_values["A1"] - 2.5) < 1e-2
        assert abs(res_min.solution_values["B1"] - 1.5) < 1e-2

        # Max x * y s.t. 2*x + 2*y = 20 => x=5, y=5, obj=25
        sh.set_cell(1, 1, CellData(value=0.0, formula="=A1 * B1"))
        sh.set_cell(2, 1, CellData(value=0.0, formula="=2*A1 + 2*B1"))
        wb.recalculate()

        res_max = solve_model(
            wb,
            SolverParams(
                objective_ref="B2",
                goal="max",
                variable_refs="A1:B1",
                constraints=[SolverConstraint("B3", "=", "20")],
                method="grg_nonlinear",
            ),
        )
        assert res_max.success is True
        assert abs(res_max.final_objective - 25.0) < 1e-2
        assert abs(res_max.solution_values["A1"] - 5.0) < 1e-1
        assert abs(res_max.solution_values["B1"] - 5.0) < 1e-1

    def test_grg_value_of(self):
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 0, CellData(value=1.0))
        sh.set_cell(1, 0, CellData(value=0.0, formula="=A1^2 + 2*A1"))
        wb.recalculate()

        res = solve_model(
            wb,
            SolverParams(
                objective_ref="A2",
                goal="value_of",
                target_value=15.0,
                variable_refs="A1",
                method="grg_nonlinear",
            ),
        )
        assert res.success is True
        assert abs(res.final_objective - 15.0) < 1e-3
        assert abs(res.solution_values["A1"] - 3.0) < 1e-2


class TestEvolutionarySolver:
    """Test Evolutionary DE solver with discontinuous IF and AllDifferent (dif)."""

    def test_evolutionary_discontinuous_if_and_abs(self):
        # Non-smooth discontinuous step objective:
        # Min ABS(A1 - 7) + IF(A1 < 5, 100, 0) + IF(B1 > 3, (B1 - 3)*2, 10)
        # Optimal at A1 = 7, B1 = 3.0001 -> ~0
        # Or integer version: Min ABS(A1 - 7) + IF(A1 < 5, 100, 0) + ABS(B1 - 4) with A1, B1 int
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 0, CellData(value=1.0))
        sh.set_cell(0, 1, CellData(value=1.0))
        sh.set_cell(
            1,
            0,
            CellData(
                value=0.0,
                formula="=ABS(A1 - 7) + IF(A1 < 5, 100, 0) + ABS(B1 - 4)",
            ),
        )
        wb.recalculate()

        res = solve_model(
            wb,
            SolverParams(
                objective_ref="A2",
                goal="min",
                variable_refs="A1:B1",
                constraints=[SolverConstraint("A1:B1", "int")],
                method="evolutionary",
                options=SolverOptions(max_iterations=120, population_size=36, random_seed=42),
            ),
        )
        assert res.success is True
        assert res.final_objective < 1e-4
        assert abs(res.solution_values["A1"] - 7.0) < 1e-6
        assert abs(res.solution_values["B1"] - 4.0) < 1e-6

    def test_evolutionary_all_different_dif_assignment(self):
        # 3-task assignment with permutation dif on A1:C1 in {1, 2, 3}:
        # Cost if A1=1:10, 2:5, 3:8; B1=1:4, 2:9, 3:7; C1=1:6, 2:3, 3:2
        # Best distinct permutation: A1=2 (5), B1=1 (4), C1=3 (2) -> total cost = 11
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 0, CellData(value=1.0))
        sh.set_cell(0, 1, CellData(value=1.0))
        sh.set_cell(0, 2, CellData(value=1.0))
        sh.set_cell(
            1,
            0,
            CellData(
                value=0.0,
                formula=(
                    "=IF(A1=1,10,IF(A1=2,5,8)) + IF(B1=1,4,IF(B1=2,9,7)) + IF(C1=1,6,IF(C1=2,3,2))"
                ),
            ),
        )
        wb.recalculate()

        res = solve_model(
            wb,
            SolverParams(
                objective_ref="A2",
                goal="min",
                variable_refs="A1:C1",
                constraints=[
                    SolverConstraint("A1:C1", "dif"),
                    SolverConstraint("A1:C1", ">=", "1"),
                    SolverConstraint("A1:C1", "<=", "3"),
                ],
                method="evolutionary",
                options=SolverOptions(max_iterations=80, population_size=30, random_seed=7),
            ),
        )
        assert res.success is True
        vals = [
            round(res.solution_values["A1"]),
            round(res.solution_values["B1"]),
            round(res.solution_values["C1"]),
        ]
        assert sorted(vals) == [1, 2, 3]
        assert abs(res.final_objective - 11.0) < 1e-6
        assert any(cr.op == "dif" and cr.binding for cr in res.constraint_reports)


class TestApplyReportAndPersistence:
    """Test apply_solver_solution, generate_answer_report, and save/load model roundtrip."""

    def test_apply_solution_and_answer_report(self):
        load_locale("zh-CN")
        wb = WorkbookModel()
        sh = wb.active_sheet
        sh.set_cell(0, 0, CellData(value=1.0))
        sh.set_cell(0, 1, CellData(value=1.0))
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

        apply_solver_solution(wb, res.solution_values)
        assert abs(sh.get_cell_value(0, 0) - 10.0) < 1e-6
        assert abs(sh.get_cell_value(0, 1) - 0.0) < 1e-6
        assert abs(sh.get_cell_value(1, 0) - 30.0) < 1e-6

        name1 = generate_answer_report(wb, params, res)
        name2 = generate_answer_report(wb, params, res)
        assert name1 == "Answer Report 1"
        assert name2 == "Answer Report 2"
        rep = wb.get_sheet_by_name(name1)
        assert rep is not None
        # Verify objective, variable, and constraint entries exist on report sheet
        texts = [str(c.value) for c in rep.cells.values() if c.value is not None]
        assert any("A2" in t for t in texts)
        assert any("A1" in t for t in texts)
        assert any("A3" in t for t in texts)

    def test_save_and_load_solver_model_roundtrip(self):
        sh = SheetDataModel(name="ModelSheet")
        assert load_solver_model(sh) is None

        params = SolverParams(
            objective_ref="D5",
            goal="value_of",
            target_value=42.5,
            variable_refs="A1:B2",
            constraints=[
                SolverConstraint("C1:C2", "<=", "100"),
                SolverConstraint("A1:B2", "int"),
            ],
            make_unconstrained_non_negative=False,
            method="grg_nonlinear",
            default_sheet="ModelSheet",
            options=SolverOptions(
                max_iterations=350,
                max_time_sec=45.0,
                precision=1e-7,
                integer_optimality=0.005,
                population_size=60,
                random_seed=99,
            ),
        )
        save_solver_model(sh, params)
        assert "solver_model" in sh.extra

        loaded = load_solver_model(sh)
        assert loaded == params

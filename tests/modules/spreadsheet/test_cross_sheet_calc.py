"""Tests for cross-sheet formula evaluation, SheetReference AST, and DAG cycle detection."""

import pytest

from atboffice.modules.spreadsheet.calc.context import EvalContext
from atboffice.modules.spreadsheet.calc.dag import CellAddress, DependencyGraph
from atboffice.modules.spreadsheet.calc.errors import CYCLE, REF
from atboffice.modules.spreadsheet.calc.evaluator import evaluate
from atboffice.modules.spreadsheet.calc.parser import parse_sheet_reference
from atboffice.modules.spreadsheet.calc.tokens import AreaRefNode, CellRefNode, SheetReference
from atboffice.modules.spreadsheet.models.sheet_model import CellData
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel


class TestSheetReferenceAST:
    """Tests for SheetReference AST node parsing and properties."""

    def test_parse_sheet_reference_simple(self):
        ref = parse_sheet_reference("Sheet2!A1")
        assert ref is not None
        assert isinstance(ref, SheetReference)
        assert ref.sheet_name == "Sheet2"
        assert ref.cell_range == "A1"
        assert ref.r == 0
        assert ref.c == 0
        assert ref.is_range is False

    def test_parse_sheet_reference_quoted_spaces(self):
        ref = parse_sheet_reference("'Q1 Summary'!B5")
        assert ref is not None
        assert ref.sheet_name == "Q1 Summary"
        assert ref.cell_range == "B5"
        assert ref.r == 4
        assert ref.c == 1
        assert ref.is_range is False

    def test_parse_sheet_reference_escaped_quote(self):
        ref = parse_sheet_reference("'O''Reilly'!C3:D10")
        assert ref is not None
        assert ref.sheet_name == "O'Reilly"
        assert ref.cell_range == "C3:D10"
        assert ref.is_range is True
        assert ref.r1 == 2
        assert ref.c1 == 2
        assert ref.r2 == 9
        assert ref.c2 == 3

    def test_parse_sheet_reference_invalid(self):
        assert parse_sheet_reference("A1") is None
        assert parse_sheet_reference("NoExclamationMark") is None
        assert parse_sheet_reference("!A1") is None
        assert parse_sheet_reference("Sheet1!") is None

    def test_cell_node_sheet_reference_property(self):
        node = CellRefNode(r=2, c=3, sheet="Data")
        sheet_ref = node.sheet_reference
        assert sheet_ref is not None
        assert sheet_ref.sheet_name == "Data"
        assert sheet_ref.cell_range == "D3"
        assert sheet_ref.r == 2
        assert sheet_ref.c == 3

        area_node = AreaRefNode(r1=0, c1=0, r2=4, c2=1, sheet="Summary")
        area_ref = area_node.sheet_reference
        assert area_ref is not None
        assert area_ref.sheet_name == "Summary"
        assert area_ref.cell_range == "A1:B5"
        assert area_ref.is_range is True


class TestCrossSheetEvaluation:
    """Tests for cross-sheet formula evaluation with WorkbookModel."""

    @pytest.fixture
    def workbook(self) -> WorkbookModel:
        wb = WorkbookModel()
        s2 = wb.add_sheet("Sheet2")
        s3 = wb.add_sheet("Q1 Summary")
        s4 = wb.add_sheet("O'Reilly")

        # Set values
        s2.set_cell_value(0, 0, 42)  # Sheet2!A1 = 42
        s2.set_cell_value(1, 0, 8)  # Sheet2!A2 = 8
        s2.set_cell_value(2, 0, 10)  # Sheet2!A3 = 10

        s3.set_cell_value(4, 1, 25)  # 'Q1 Summary'!B5 = 25
        s4.set_cell_value(2, 2, 99)  # 'O''Reilly'!C3 = 99

        return wb

    def test_cross_sheet_cell_addition(self, workbook: WorkbookModel):
        res = evaluate("=Sheet2!A1 + 10", workbook=workbook)
        assert res == 52.0

    def test_cross_sheet_quoted_name_multiplication(self, workbook: WorkbookModel):
        res = evaluate("='Q1 Summary'!B5 * 2", workbook=workbook)
        assert res == 50.0

    def test_cross_sheet_escaped_quote_formula(self, workbook: WorkbookModel):
        res = evaluate("='O''Reilly'!C3 + 1", workbook=workbook)
        assert res == 100.0

    def test_cross_sheet_range_aggregation(self, workbook: WorkbookModel):
        res_sum = evaluate("=SUM(Sheet2!A1:A3)", workbook=workbook)
        assert res_sum == 60.0

        res_avg = evaluate("=AVERAGE(Sheet2!A1:A3)", workbook=workbook)
        assert res_avg == 20.0

    def test_nonexistent_sheet_returns_ref_error(self, workbook: WorkbookModel):
        res_cell = evaluate("=NoSuchSheet!A1 + 5", workbook=workbook)
        assert res_cell == REF
        assert str(res_cell) == "#REF!"

        res_range = evaluate("=SUM('Missing Sheet'!A1:B10)", workbook=workbook)
        assert res_range == REF


class TestCycleDetectionAndRecalculation:
    """Tests for circular reference detection, stack overflow prevention, and DAG recalc."""

    def test_direct_two_sheet_cycle_prevention(self):
        # Sheet1!A1 = Sheet2!A1, Sheet2!A1 = Sheet1!A1
        ctx = EvalContext()
        ctx.workbook_data["Sheet1"] = {(0, 0): "=Sheet2!A1"}
        ctx.workbook_data["Sheet2"] = {(0, 0): "=Sheet1!A1"}

        # Must not raise RecursionError and must return CYCLE error
        res1 = evaluate("=Sheet1!A1", ctx)
        assert res1 == CYCLE
        assert str(res1) == "#CYCLE!"

        res2 = evaluate("=Sheet2!A1", ctx)
        assert res2 == CYCLE
        assert str(res2) == "#CYCLE!"

    def test_self_cycle_detection(self):
        ctx = EvalContext()
        ctx.current_sheet = "Sheet1"
        ctx.visiting.add(("sheet1", 0, 0))
        res = evaluate("=A1 + 1", ctx)
        assert res == CYCLE

    def test_multi_hop_cycle_detection(self):
        # Sheet1!A1 -> Sheet2!B2 -> Sheet3!C3 -> Sheet1!A1
        ctx = EvalContext()
        ctx.workbook_data["Sheet1"] = {(0, 0): "=Sheet2!B2"}
        ctx.workbook_data["Sheet2"] = {(1, 1): "=Sheet3!C3"}
        ctx.workbook_data["Sheet3"] = {(2, 2): "=Sheet1!A1"}

        res = evaluate("=Sheet1!A1", ctx)
        assert res == CYCLE

    def test_dag_cycle_report(self):
        graph = DependencyGraph()
        graph.set_cell_formula("Sheet1", 0, 0, "=Sheet2!A1")
        graph.set_cell_formula("Sheet2", 0, 0, "=Sheet1!A1")

        report = graph.detect_cycles()
        assert report.has_cycle is True
        assert CellAddress("Sheet1", 0, 0) in report.circular_cells
        assert CellAddress("Sheet2", 0, 0) in report.circular_cells

    def test_workbook_recalculate_multi_sheet_cascade(self):
        # Sheet1!A1 = 10
        # Sheet2!A1 = =Sheet1!A1 * 2  (20)
        # Sheet3!A1 = =Sheet2!A1 + 5  (25)
        wb = WorkbookModel()
        s1 = wb.active_sheet
        s2 = wb.add_sheet("Sheet2")
        s3 = wb.add_sheet("Sheet3")

        s1.set_cell_value(0, 0, 10)
        s2.set_cell(0, 0, CellData(formula="=Sheet1!A1 * 2"))
        s3.set_cell(0, 0, CellData(formula="=Sheet2!A1 + 5"))

        report = wb.recalculate()
        assert report.has_cycle is False

        assert s2.get_cell_value(0, 0) == 20.0
        assert s3.get_cell_value(0, 0) == 25.0

    def test_workbook_recalculate_with_cycles_sets_cycle_error(self):
        # Sheet1!A1 = =Sheet2!A1
        # Sheet2!A1 = =Sheet1!A1
        # Sheet3!A1 = 100
        wb = WorkbookModel()
        s1 = wb.active_sheet
        s2 = wb.add_sheet("Sheet2")
        s3 = wb.add_sheet("Sheet3")

        s1.set_cell(0, 0, CellData(formula="=Sheet2!A1"))
        s2.set_cell(0, 0, CellData(formula="=Sheet1!A1"))
        s3.set_cell(0, 0, CellData(formula="=50 * 2"))

        report = wb.recalculate()
        assert report.has_cycle is True

        assert s1.get_cell_value(0, 0) == CYCLE
        assert s2.get_cell_value(0, 0) == CYCLE
        assert s3.get_cell_value(0, 0) == 100.0

    def test_incremental_recalculate_cell(self):
        wb = WorkbookModel()
        s1 = wb.active_sheet
        s2 = wb.add_sheet("Sheet2")

        s1.set_cell_value(0, 0, 5)
        s2.set_cell(0, 0, CellData(formula="=Sheet1!A1 * 10"))

        graph = DependencyGraph()
        graph.recalculate(wb)
        assert s2.get_cell_value(0, 0) == 50.0

        # Now change Sheet1!A1 to 7 and recalculate cell
        s1.set_cell_value(0, 0, 7)
        plan = graph.recalculate_cell("Sheet1", 0, 0, wb)
        assert CellAddress("Sheet2", 0, 0) in plan.eval_order
        assert s2.get_cell_value(0, 0) == 70.0

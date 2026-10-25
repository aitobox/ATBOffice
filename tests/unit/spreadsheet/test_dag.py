"""Tests for DAG dependency tracking, three-color cycle detection, and topological sorting."""

from atboffice.modules.spreadsheet.calc.dag import (
    CellAddress,
    CellRange,
    Change,
    DependencyGraph,
    extract_precedents,
)
from atboffice.modules.spreadsheet.calc.parser import parse


class TestCellAddressAndRange:
    def test_cell_address_basics(self):
        addr1 = CellAddress("Sheet1", 0, 0)
        addr2 = CellAddress("Sheet1", 0, 0)
        addr3 = CellAddress("Sheet1", 0, 1)
        addr4 = CellAddress("Sheet2", 0, 0)

        assert addr1 == addr2
        assert hash(addr1) == hash(addr2)
        assert addr1 != addr3
        assert addr1 != addr4
        assert str(addr1) == "Sheet1!A1"
        assert repr(addr1) == "CellAddress(sheet='Sheet1', r=0, c=0)"

    def test_cell_range_basics(self):
        rng = CellRange("Sheet1", 0, 0, 4, 2)  # A1:C5
        assert rng.sheet == "Sheet1"
        assert rng.r1 == 0 and rng.c1 == 0 and rng.r2 == 4 and rng.c2 == 2
        assert rng.contains("Sheet1", 2, 1) is True
        assert rng.contains("Sheet1", 5, 1) is False
        assert rng.contains("Sheet2", 2, 1) is False

        # Intersections
        overlap = CellRange("Sheet1", 3, 1, 6, 3)
        disjoint = CellRange("Sheet1", 5, 0, 7, 2)
        other_sheet = CellRange("Sheet2", 0, 0, 4, 2)

        assert rng.intersects(overlap) is True
        assert rng.intersects(disjoint) is False
        assert rng.intersects(other_sheet) is False


class TestPrecedentExtraction:
    def test_extract_simple_cell_reference(self):
        ast = parse("=A1 * 2 + B2")
        result = extract_precedents(ast, default_sheet="Sheet1")
        assert result.volatile is False
        assert CellAddress("Sheet1", 0, 0) in result.refs  # A1
        assert CellAddress("Sheet1", 1, 1) in result.refs  # B2

    def test_extract_range_reference(self):
        ast = parse("=SUM(A1:B3)")
        result = extract_precedents(ast, default_sheet="Sheet1")
        assert result.volatile is False
        ranges = [r for r in result.refs if isinstance(r, CellRange)]
        assert len(ranges) == 1
        assert ranges[0] == CellRange("Sheet1", 0, 0, 2, 1)

    def test_extract_cross_sheet_reference(self):
        ast = parse("='Summary Report'!C4 + Sheet2!D5:E6")
        result = extract_precedents(ast, default_sheet="Sheet1")
        assert CellAddress("Summary Report", 3, 2) in result.refs
        ranges = [r for r in result.refs if isinstance(r, CellRange)]
        assert any(r == CellRange("Sheet2", 4, 3, 5, 4) for r in ranges)

    def test_extract_volatile_functions(self):
        volatile_formulas = [
            "=NOW()",
            "=TODAY() + 1",
            "=RAND()",
            "=RANDBETWEEN(1, 10)",
            "=OFFSET(A1, 1, 1)",
            '=INDIRECT("A1")',
        ]
        for f in volatile_formulas:
            ast = parse(f)
            result = extract_precedents(ast, default_sheet="Sheet1")
            assert result.volatile is True, f"Formula {f} should be detected as volatile"

    def test_non_volatile_function(self):
        ast = parse("=SUM(A1:A10) + AVERAGE(B1:B10)")
        result = extract_precedents(ast, default_sheet="Sheet1")
        assert result.volatile is False


class TestDependencyGraph:
    def test_direct_cell_dependencies(self):
        dag = DependencyGraph()
        dag.set_cell_formula("Sheet1", 0, 1, "=A1 * 2")  # B1 = A1 * 2
        dag.set_cell_formula("Sheet1", 0, 2, "=B1 + 5")  # C1 = B1 + 5

        a1_deps = dag.get_dependents("Sheet1", 0, 0)
        assert CellAddress("Sheet1", 0, 1) in a1_deps

        b1_deps = dag.get_dependents("Sheet1", 0, 1)
        assert CellAddress("Sheet1", 0, 2) in b1_deps

        c1_deps = dag.get_dependents("Sheet1", 0, 2)
        assert len(c1_deps) == 0

        # Precedents
        b1_precs = dag.get_precedents("Sheet1", 0, 1)
        assert CellAddress("Sheet1", 0, 0) in b1_precs

    def test_range_dependencies_via_column_buckets(self):
        dag = DependencyGraph()
        # C1 = SUM(A1:B5)
        dag.set_cell_formula("Sheet1", 0, 2, "=SUM(A1:B5)")

        # Any cell in A1:B5 should have C1 as dependent
        assert CellAddress("Sheet1", 0, 2) in dag.get_dependents("Sheet1", 0, 0)  # A1
        assert CellAddress("Sheet1", 0, 2) in dag.get_dependents("Sheet1", 4, 1)  # B5
        assert CellAddress("Sheet1", 0, 2) in dag.get_dependents("Sheet1", 2, 0)  # A3

        # Cells outside the range should not trigger C1
        assert CellAddress("Sheet1", 0, 2) not in dag.get_dependents("Sheet1", 5, 0)  # A6
        assert CellAddress("Sheet1", 0, 2) not in dag.get_dependents("Sheet1", 0, 2)  # C1
        assert CellAddress("Sheet1", 0, 2) not in dag.get_dependents("Sheet2", 0, 0)  # Sheet2!A1

    def test_wide_range_dependencies(self):
        dag = DependencyGraph()
        # Row 1 spans columns A to Z (26 columns > 24 threshold)
        dag.set_cell_formula("Sheet1", 1, 0, "=SUM(A1:Z1)")

        # M1 (col 12) should find dependent A2
        assert CellAddress("Sheet1", 1, 0) in dag.get_dependents("Sheet1", 0, 12)
        # AA1 (col 26) should not
        assert CellAddress("Sheet1", 1, 0) not in dag.get_dependents("Sheet1", 0, 26)

    def test_update_and_remove_formula(self):
        dag = DependencyGraph()
        dag.set_cell_formula("Sheet1", 0, 1, "=A1 * 2")
        assert CellAddress("Sheet1", 0, 1) in dag.get_dependents("Sheet1", 0, 0)

        # Update formula to reference D1 instead of A1
        dag.set_cell_formula("Sheet1", 0, 1, "=D1 * 2")
        assert CellAddress("Sheet1", 0, 1) not in dag.get_dependents("Sheet1", 0, 0)
        assert CellAddress("Sheet1", 0, 1) in dag.get_dependents("Sheet1", 0, 3)

        # Remove formula completely
        dag.remove_cell("Sheet1", 0, 1)
        assert CellAddress("Sheet1", 0, 1) not in dag.get_dependents("Sheet1", 0, 3)
        assert len(dag.get_precedents("Sheet1", 0, 1)) == 0


class TestInvalidationAndDirtyPropagation:
    def test_cascading_invalidation(self):
        dag = DependencyGraph()
        # A1 -> B1 -> C1 -> D1
        dag.set_cell_formula("Sheet1", 0, 1, "=A1 + 1")
        dag.set_cell_formula("Sheet1", 0, 2, "=B1 + 1")
        dag.set_cell_formula("Sheet1", 0, 3, "=C1 + 1")

        # Modifying A1
        dirty = dag.invalidate([Change(sheet="Sheet1", r=0, c=0)])
        assert CellAddress("Sheet1", 0, 1) in dirty
        assert CellAddress("Sheet1", 0, 2) in dirty
        assert CellAddress("Sheet1", 0, 3) in dirty

    def test_area_invalidation(self):
        dag = DependencyGraph()
        dag.set_cell_formula("Sheet1", 5, 0, "=SUM(A1:A5)")  # A6 = SUM(A1:A5)
        dag.set_cell_formula("Sheet1", 5, 1, "=SUM(B1:B5)")  # B6 = SUM(B1:B5)

        # Change range A2:A4
        dirty = dag.invalidate([Change(sheet="Sheet1", range=CellRange("Sheet1", 1, 0, 3, 0))])
        assert CellAddress("Sheet1", 5, 0) in dirty
        assert CellAddress("Sheet1", 5, 1) not in dirty

    def test_volatile_cells_automatically_dirtied(self):
        dag = DependencyGraph()
        dag.set_cell_formula("Sheet1", 0, 0, "=NOW()")
        dag.set_cell_formula("Sheet1", 0, 1, "=A1 * 2")
        dag.set_cell_formula("Sheet1", 10, 10, "=X100 + 1")  # unrelated

        # Modifying completely unrelated cell Z100
        dirty = dag.invalidate([Change(sheet="Sheet1", r=99, c=25)])
        assert CellAddress("Sheet1", 0, 0) in dirty
        assert CellAddress("Sheet1", 0, 1) in dirty


class TestCycleDetection:
    def test_acyclic_graph(self):
        dag = DependencyGraph()
        dag.set_cell_formula("Sheet1", 0, 1, "=A1")
        dag.set_cell_formula("Sheet1", 0, 2, "=B1")

        report = dag.detect_cycles()
        assert report.has_cycle is False
        assert len(report.circular_cells) == 0

    def test_self_reference_cycle(self):
        dag = DependencyGraph()
        dag.set_cell_formula("Sheet1", 0, 0, "=A1 + 1")

        report = dag.detect_cycles()
        assert report.has_cycle is True
        assert CellAddress("Sheet1", 0, 0) in report.circular_cells

    def test_two_cell_mutual_cycle(self):
        dag = DependencyGraph()
        dag.set_cell_formula("Sheet1", 0, 0, "=B1")
        dag.set_cell_formula("Sheet1", 0, 1, "=A1")

        report = dag.detect_cycles()
        assert report.has_cycle is True
        assert CellAddress("Sheet1", 0, 0) in report.circular_cells
        assert CellAddress("Sheet1", 0, 1) in report.circular_cells

    def test_three_cell_loop_with_downstream(self):
        dag = DependencyGraph()
        # A1 -> B1 -> C1 -> A1 (cycle)
        # C1 -> D1 (downstream dependent, not in cycle)
        dag.set_cell_formula("Sheet1", 0, 0, "=C1")
        dag.set_cell_formula("Sheet1", 0, 1, "=A1")
        dag.set_cell_formula("Sheet1", 0, 2, "=B1")
        dag.set_cell_formula("Sheet1", 0, 3, "=C1")

        report = dag.detect_cycles()
        assert report.has_cycle is True
        assert report.circular_cells == {
            CellAddress("Sheet1", 0, 0),
            CellAddress("Sheet1", 0, 1),
            CellAddress("Sheet1", 0, 2),
        }
        assert CellAddress("Sheet1", 0, 3) not in report.circular_cells


class TestTopologicalSortAndRecalcPlan:
    def test_topological_sort_diamond_dependency(self):
        dag = DependencyGraph()
        # A1 is input
        # B1 = A1 * 2
        # C1 = A1 * 3
        # D1 = B1 + C1
        dag.set_cell_formula("Sheet1", 0, 1, "=A1 * 2")
        dag.set_cell_formula("Sheet1", 0, 2, "=A1 * 3")
        dag.set_cell_formula("Sheet1", 0, 3, "=B1 + C1")

        plan = dag.get_recalc_plan([Change(sheet="Sheet1", r=0, c=0)])
        assert plan.cycle_report.has_cycle is False

        order = plan.eval_order
        b1 = CellAddress("Sheet1", 0, 1)
        c1 = CellAddress("Sheet1", 0, 2)
        d1 = CellAddress("Sheet1", 0, 3)

        assert b1 in order
        assert c1 in order
        assert d1 in order

        # B1 and C1 must appear before D1
        assert order.index(b1) < order.index(d1)
        assert order.index(c1) < order.index(d1)

    def test_cycle_handling_non_iterative(self):
        dag = DependencyGraph(iterative_enabled=False)
        dag.set_cell_formula("Sheet1", 0, 0, "=B1")
        dag.set_cell_formula("Sheet1", 0, 1, "=A1")

        plan = dag.get_recalc_plan([Change(sheet="Sheet1", r=0, c=0)])
        assert plan.cycle_report.has_cycle is True
        assert plan.is_iterative is False
        # All dirty cells are present in eval_order
        assert len(plan.eval_order) == 2

    def test_cycle_handling_iterative(self):
        dag = DependencyGraph(iterative_enabled=True, max_iterations=100, tolerance=0.001)
        dag.set_cell_formula("Sheet1", 0, 0, "=B1 / 2")
        dag.set_cell_formula("Sheet1", 0, 1, "=A1 + 10")

        plan = dag.get_recalc_plan([Change(sheet="Sheet1", r=0, c=0)])
        assert plan.cycle_report.has_cycle is True
        assert plan.is_iterative is True
        assert plan.max_iterations == 100
        assert plan.tolerance == 0.001

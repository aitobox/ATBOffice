"""Tests for deep DAG cascading dependency recalculation and cycle detection."""

from __future__ import annotations

import pytest

from atboffice.modules.spreadsheet.calc.dag import (
    CellAddress,
    Change,
    DependencyGraph,
)


class TestDAGDeepChainsAndCycles:
    def test_deep_cascading_dependency_chain(self):
        """Verify that a chain of 50 cascading cells (A1 -> A2 -> ... -> A50)
        sorts and calculates correctly without stack overflow.
        """
        graph = DependencyGraph()
        sheet = "Sheet1"

        # Build chain: A(i+1) = A(i) + 1 (0-indexed: row 1 references row 0, etc.)
        for i in range(1, 51):
            formula = f"=A{i} + 1"
            graph.set_cell_formula(sheet, i, 0, formula)

        # Mark A1 changed (row 0, col 0)
        changes = [Change(sheet=sheet, r=0, c=0)]
        plan = graph.get_recalc_plan(changes)

        assert not plan.cycle_report.has_cycle
        assert len(plan.eval_order) == 50
        # Verify topological ordering: A2 before A3 before A4 ...
        for idx in range(len(plan.eval_order) - 1):
            curr_row = plan.eval_order[idx].r
            next_row = plan.eval_order[idx + 1].r
            assert curr_row < next_row

    def test_three_color_cycle_detection(self):
        """Verify that a 3-cell loop (A1 -> B1 -> C1 -> A1) is properly identified
        with three-color DFS cycle detection.
        """
        graph = DependencyGraph()
        sheet = "Sheet1"

        graph.set_cell_formula(sheet, 0, 0, "=B1 * 2")  # A1
        graph.set_cell_formula(sheet, 0, 1, "=C1 + 5")  # B1
        graph.set_cell_formula(sheet, 0, 2, "=A1 - 1")  # C1

        changes = [Change(sheet=sheet, r=0, c=0)]
        plan = graph.get_recalc_plan(changes)

        assert plan.cycle_report.has_cycle is True
        assert len(plan.cycle_report.cycles) > 0
        flattened_cycle = {str(a) for cycle in plan.cycle_report.cycles for a in cycle}
        assert "Sheet1!A1" in flattened_cycle
        assert "Sheet1!B1" in flattened_cycle
        assert "Sheet1!C1" in flattened_cycle

    def test_diamond_dependency_graph(self):
        """Verify standard diamond pattern:
            A1
           /  \\
          B1   C1
           \\  /
            D1
        D1 must recompute after both B1 and C1 have recomputed.
        """
        graph = DependencyGraph()
        sheet = "Sheet1"

        graph.set_cell_formula(sheet, 0, 1, "=A1 * 10")  # B1
        graph.set_cell_formula(sheet, 0, 2, "=A1 + 20")  # C1
        graph.set_cell_formula(sheet, 0, 3, "=B1 + C1")  # D1

        changes = [Change(sheet=sheet, r=0, c=0)]
        plan = graph.get_recalc_plan(changes)

        assert not plan.cycle_report.has_cycle
        # D1 must come after both B1 and C1 in the recompute order
        order_indices = {plan.eval_order[i].c: i for i in range(len(plan.eval_order))}
        assert order_indices[3] > order_indices[1]  # D1 after B1
        assert order_indices[3] > order_indices[2]  # D1 after C1

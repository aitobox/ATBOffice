"""DAG dependency tracking, three-color cycle detection, and topological sorting."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from atboffice.modules.spreadsheet.calc.parser import parse
from atboffice.modules.spreadsheet.calc.references import cell_name, walk
from atboffice.modules.spreadsheet.calc.tokens import (
    AreaRefNode,
    ASTNode,
    CellRefNode,
    FunctionCallNode,
    SheetReference,
)

VOLATILE_FUNCTIONS: frozenset[str] = frozenset(
    {
        "NOW",
        "TODAY",
        "RAND",
        "RANDBETWEEN",
        "RANDARRAY",
        "OFFSET",
        "INDIRECT",
        "CELL",
        "INFO",
    }
)


class Color(IntEnum):
    """Three-color marking states for DFS cycle detection."""

    WHITE = 0  # Unvisited
    GRAY = 1  # Currently in recursion stack
    BLACK = 2  # Fully explored


@dataclass(frozen=True, slots=True)
class CellAddress:
    """Immutable coordinate identifying a single cell in a workbook."""

    sheet: str
    r: int
    c: int

    @property
    def sheet_id(self) -> str:
        return self.sheet

    def __str__(self) -> str:
        return f"{self.sheet}!{cell_name(self.r, self.c)}"

    def __repr__(self) -> str:
        return f"CellAddress(sheet={self.sheet!r}, r={self.r}, c={self.c})"


@dataclass(frozen=True, slots=True)
class CellRange:
    """Rectangular range of cells on a specific sheet."""

    sheet: str
    r1: int
    c1: int
    r2: int
    c2: int

    def contains(self, sheet: str, r: int, c: int) -> bool:
        """Check if coordinates fall inside this range on the same sheet."""
        if self.sheet != sheet:
            return False
        return self.r1 <= r <= self.r2 and self.c1 <= c <= self.c2

    def intersects(self, other: "CellRange") -> bool:
        """Check if this range intersects with another range."""
        if self.sheet != other.sheet:
            return False
        return not (
            self.r2 < other.r1 or self.r1 > other.r2 or self.c2 < other.c1 or self.c1 > other.c2
        )


@dataclass(slots=True)
class RangeEntry:
    """Bucket entry recording a dependent cell for a rectangular range."""

    sheet: str
    r1: int
    c1: int
    r2: int
    c2: int
    dependent: CellAddress
    dead: bool = False


@dataclass(slots=True)
class Change:
    """Cell modification notification payload."""

    sheet: str
    r: int | None = None
    c: int | None = None
    range: CellRange | None = None


@dataclass(slots=True)
class PrecedentsResult:
    """Result of extracting static precedents and volatility from an AST."""

    refs: list[CellAddress | CellRange] = field(default_factory=list)
    volatile: bool = False


@dataclass(slots=True)
class CycleReport:
    """Report detailing detected circular references."""

    has_cycle: bool
    cycles: list[list[CellAddress]] = field(default_factory=list)
    circular_cells: set[CellAddress] = field(default_factory=set)


@dataclass(slots=True)
class RecalcPlan:
    """Structured calculation plan ready for execution engine."""

    dirty_nodes: list[CellAddress]
    eval_order: list[CellAddress]
    cycle_report: CycleReport
    is_iterative: bool = False
    max_iterations: int = 100
    tolerance: float = 0.001


def extract_precedents(ast: ASTNode, default_sheet: str = "Sheet1") -> PrecedentsResult:
    """Extract precedent cell/area references and volatility from an AST."""
    out = PrecedentsResult()

    def visitor(node: ASTNode) -> None:
        if isinstance(node, FunctionCallNode):
            if node.name.upper() in VOLATILE_FUNCTIONS:
                out.volatile = True
        elif isinstance(node, CellRefNode):
            target_sheet = node.sheet or default_sheet
            out.refs.append(CellAddress(target_sheet, node.r, node.c))
        elif isinstance(node, AreaRefNode):
            target_sheet = node.sheet or default_sheet
            r1 = min(node.r1, node.r2)
            r2 = max(node.r1, node.r2)
            c1 = min(node.c1, node.c2)
            c2 = max(node.c1, node.c2)
            out.refs.append(CellRange(target_sheet, r1, c1, r2, c2))
        elif isinstance(node, SheetReference):
            target_sheet = node.sheet_name or default_sheet
            if node.is_range:
                r1 = min(node.r1, node.r2)
                r2 = max(node.r1, node.r2)
                c1 = min(node.c1, node.c2)
                c2 = max(node.c1, node.c2)
                out.refs.append(CellRange(target_sheet, r1, c1, r2, c2))
            else:
                out.refs.append(CellAddress(target_sheet, node.r, node.c))

    walk(ast, visitor)
    return out


class DependencyGraph:
    """Directed Acyclic Graph (DAG) maintaining formula cell dependencies.

    Uses dual indexing (direct cell dependents + column bucketing for ranges)
    to achieve sub-millisecond incremental invalidation across millions of cells.
    """

    def __init__(
        self,
        iterative_enabled: bool = False,
        max_iterations: int = 100,
        tolerance: float = 0.001,
    ) -> None:
        self.iterative_enabled = iterative_enabled
        self.max_iterations = max_iterations
        self.tolerance = tolerance

        # Registered formula cells
        self._formula_cells: set[CellAddress] = set()

        # Direct cell -> set of dependent formula cells
        self._cell_dependents: dict[CellAddress, set[CellAddress]] = {}

        # Formula cell -> set of precedent refs (CellAddress or CellRange)
        self._precedents: dict[CellAddress, set[CellAddress | CellRange]] = {}

        # Formula cell -> direct cell precedents (for fast topological sort)
        self._direct_precedents: dict[CellAddress, set[CellAddress]] = {}

        # Column buckets per sheet: sheet -> col -> list[RangeEntry]
        self._col_buckets: dict[str, dict[int, list[RangeEntry]]] = {}

        # Wide range buckets per sheet (width > 24 cols): sheet -> list[RangeEntry]
        self._wide_buckets: dict[str, list[RangeEntry]] = {}

        # Volatile cells set
        self._volatile_cells: set[CellAddress] = set()

        # Range entries registered per formula cell for cleanup
        self._node_range_entries: dict[CellAddress, list[RangeEntry]] = {}

        self._garbage_count = 0

    def set_cell_formula(
        self,
        sheet: str,
        r: int,
        c: int,
        formula: str | ASTNode,
    ) -> None:
        """Register or update a formula for the specified cell."""
        addr = CellAddress(sheet, r, c)
        self.remove_cell(sheet, r, c)

        ast = parse(formula) if isinstance(formula, str) else formula
        if ast is None:
            return

        precs = extract_precedents(ast, default_sheet=sheet)

        self._formula_cells.add(addr)
        self._precedents[addr] = set(precs.refs)
        self._direct_precedents[addr] = set()
        self._node_range_entries[addr] = []

        if precs.volatile:
            self._volatile_cells.add(addr)

        for ref in precs.refs:
            if isinstance(ref, CellAddress):
                if ref not in self._cell_dependents:
                    self._cell_dependents[ref] = set()
                self._cell_dependents[ref].add(addr)
                self._direct_precedents[addr].add(ref)
            elif isinstance(ref, CellRange):
                entry = RangeEntry(
                    sheet=ref.sheet,
                    r1=ref.r1,
                    c1=ref.c1,
                    r2=ref.r2,
                    c2=ref.c2,
                    dependent=addr,
                )
                self._node_range_entries[addr].append(entry)
                width = ref.c2 - ref.c1
                if width > 24:
                    if ref.sheet not in self._wide_buckets:
                        self._wide_buckets[ref.sheet] = []
                    self._wide_buckets[ref.sheet].append(entry)
                else:
                    if ref.sheet not in self._col_buckets:
                        self._col_buckets[ref.sheet] = {}
                    for col in range(ref.c1, ref.c2 + 1):
                        if col not in self._col_buckets[ref.sheet]:
                            self._col_buckets[ref.sheet][col] = []
                        self._col_buckets[ref.sheet][col].append(entry)

    def remove_cell(self, sheet: str, r: int, c: int) -> None:
        """Remove a formula cell and unregister all its dependencies."""
        addr = CellAddress(sheet, r, c)
        if addr not in self._formula_cells:
            return

        self._formula_cells.remove(addr)
        self._volatile_cells.discard(addr)

        # Remove from precedents
        old_precs = self._precedents.pop(addr, set())
        for ref in old_precs:
            if isinstance(ref, CellAddress) and ref in self._cell_dependents:
                self._cell_dependents[ref].discard(addr)
                if not self._cell_dependents[ref]:
                    del self._cell_dependents[ref]

        self._direct_precedents.pop(addr, None)

        # Mark range entries as dead
        entries = self._node_range_entries.pop(addr, [])
        for entry in entries:
            entry.dead = True
        self._garbage_count += len(entries)
        if self._garbage_count > 50000:
            self._compact()

    def clear(self) -> None:
        """Clear the entire dependency graph."""
        self._formula_cells.clear()
        self._cell_dependents.clear()
        self._precedents.clear()
        self._direct_precedents.clear()
        self._col_buckets.clear()
        self._wide_buckets.clear()
        self._volatile_cells.clear()
        self._node_range_entries.clear()
        self._garbage_count = 0

    def _compact(self) -> None:
        """Prune dead range entries from column and wide buckets."""
        for sheet, col_map in self._col_buckets.items():
            for col, entries in list(col_map.items()):
                alive = [e for e in entries if not e.dead]
                if alive:
                    col_map[col] = alive
                else:
                    del col_map[col]
        for sheet, entries in list(self._wide_buckets.items()):
            self._wide_buckets[sheet] = [e for e in entries if not e.dead]
        self._garbage_count = 0

    def get_dependents(self, sheet: str, r: int, c: int) -> set[CellAddress]:
        """Query all formula cells that depend on the given coordinate."""
        addr = CellAddress(sheet, r, c)
        dependents: set[CellAddress] = set()

        # Direct cell dependents
        if addr in self._cell_dependents:
            dependents.update(self._cell_dependents[addr])

        # Column bucket range dependents
        if sheet in self._col_buckets:
            col_list = self._col_buckets[sheet].get(c)
            if col_list:
                for entry in col_list:
                    if not entry.dead and entry.r1 <= r <= entry.r2:
                        dependents.add(entry.dependent)

        # Wide bucket range dependents
        if sheet in self._wide_buckets:
            for entry in self._wide_buckets[sheet]:
                if not entry.dead and entry.r1 <= r <= entry.r2 and entry.c1 <= c <= entry.c2:
                    dependents.add(entry.dependent)

        return dependents

    def get_range_dependents(self, rng: CellRange) -> set[CellAddress]:
        """Query all formula cells that depend on any cell in a given range."""
        dependents: set[CellAddress] = set()
        for r in range(rng.r1, rng.r2 + 1):
            for c in range(rng.c1, rng.c2 + 1):
                dependents.update(self.get_dependents(rng.sheet, r, c))
        return dependents

    def get_precedents(self, sheet: str, r: int, c: int) -> set[CellAddress | CellRange]:
        """Query all precedents registered for the given cell."""
        addr = CellAddress(sheet, r, c)
        return self._precedents.get(addr, set())

    def get_direct_cell_precedents(self, sheet: str, r: int, c: int) -> set[CellAddress]:
        """Query direct cell precedents for topological ordering."""
        addr = CellAddress(sheet, r, c)
        return self._direct_precedents.get(addr, set())

    def invalidate(
        self,
        changes: list[Change | CellAddress | tuple[str, int, int]],
    ) -> list[CellAddress]:
        """Mark changed cells and downstream dependencies dirty via BFS."""
        dirty: set[CellAddress] = set()
        queue: deque[CellAddress] = deque()

        def push(n: CellAddress) -> None:
            if n not in dirty:
                dirty.add(n)
                queue.append(n)

        for item in changes:
            if isinstance(item, CellAddress):
                if item in self._formula_cells:
                    push(item)
                for dep in self.get_dependents(item.sheet, item.r, item.c):
                    push(dep)
            elif isinstance(item, tuple):
                sh, r, c = item
                addr = CellAddress(sh, r, c)
                if addr in self._formula_cells:
                    push(addr)
                for dep in self.get_dependents(sh, r, c):
                    push(dep)
            elif isinstance(item, Change):
                if item.range is not None:
                    rng = item.range
                    for dep in self.get_range_dependents(rng):
                        push(dep)
                elif item.r is not None and item.c is not None:
                    addr = CellAddress(item.sheet, item.r, item.c)
                    if addr in self._formula_cells:
                        push(addr)
                    for dep in self.get_dependents(item.sheet, item.r, item.c):
                        push(dep)

        # Include volatile cells and their downstream dependents
        for v in self._volatile_cells:
            push(v)

        # BFS propagate downstream
        while queue:
            node = queue.popleft()
            for dep in self.get_dependents(node.sheet, node.r, node.c):
                push(dep)

        return sorted(dirty, key=lambda a: (a.sheet, a.r, a.c))

    def detect_cycles(self, nodes: list[CellAddress] | None = None) -> CycleReport:
        """Perform three-color DFS cycle detection over given nodes or entire graph."""
        target_nodes = set(nodes) if nodes is not None else set(self._formula_cells)
        colors: dict[CellAddress, Color] = {node: Color.WHITE for node in target_nodes}
        cycles: list[list[CellAddress]] = []
        circular_cells: set[CellAddress] = set()
        stack: list[CellAddress] = []

        def dfs(u: CellAddress) -> None:
            colors[u] = Color.GRAY
            stack.append(u)

            # Check neighbors: cells that depend on u or cells u depends on?
            # In Excel dependency terms, A depends on B (B -> A).
            # If B depends on A, then A -> B and B -> A forms a cycle.
            # We traverse along downstream dependents within the target set.
            deps = self.get_dependents(u.sheet, u.r, u.c)
            for v in deps:
                if v not in target_nodes:
                    continue
                v_color = colors.get(v, Color.WHITE)
                if v_color == Color.GRAY:
                    # Back-edge detected!
                    if v in stack:
                        idx = stack.index(v)
                        cycle_path = stack[idx:] + [v]
                        cycles.append(cycle_path)
                        circular_cells.update(cycle_path)
                    else:
                        circular_cells.add(u)
                        circular_cells.add(v)
                elif v_color == Color.WHITE:
                    dfs(v)

            stack.pop()
            colors[u] = Color.BLACK

        for node in target_nodes:
            if colors[node] == Color.WHITE:
                dfs(node)

        return CycleReport(
            has_cycle=len(circular_cells) > 0,
            cycles=cycles,
            circular_cells=circular_cells,
        )

    def topological_sort(self, dirty_nodes: list[CellAddress]) -> list[CellAddress]:
        """Kahn's algorithm topological sort for dirty subgraph.

        Ensures precedents are evaluated before dependents.
        """
        if len(dirty_nodes) <= 1:
            return list(dirty_nodes)

        dirty_set = set(dirty_nodes)

        # Precedents map within dirty set: node -> set of dirty precedents
        in_degree: dict[CellAddress, int] = {node: 0 for node in dirty_nodes}
        dependents_map: dict[CellAddress, list[CellAddress]] = {node: [] for node in dirty_nodes}

        for node in dirty_nodes:
            deps = self.get_dependents(node.sheet, node.r, node.c)
            for dep in deps:
                if dep in dirty_set and dep != node:
                    dependents_map[node].append(dep)
                    in_degree[dep] += 1

        # Queue nodes with in_degree == 0
        queue: deque[CellAddress] = deque([node for node in dirty_nodes if in_degree[node] == 0])
        # Deterministic initial sort
        queue = deque(sorted(queue, key=lambda a: (a.sheet, a.r, a.c)))

        order: list[CellAddress] = []
        while queue:
            u = queue.popleft()
            order.append(u)
            for v in dependents_map[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)

        # If circular references exist, some nodes remain with in_degree > 0
        if len(order) < len(dirty_nodes):
            remaining = [node for node in dirty_nodes if node not in set(order)]
            remaining.sort(key=lambda a: (a.sheet, a.r, a.c))
            order.extend(remaining)

        return order

    def get_recalc_plan(
        self,
        changes: list[Change | CellAddress | tuple[str, int, int]],
    ) -> RecalcPlan:
        """Generate a complete calculation plan for given changes."""
        dirty = self.invalidate(changes)
        cycle_report = self.detect_cycles(dirty)
        order = self.topological_sort(dirty)

        is_iter = cycle_report.has_cycle and self.iterative_enabled

        return RecalcPlan(
            dirty_nodes=dirty,
            eval_order=order,
            cycle_report=cycle_report,
            is_iterative=is_iter,
            max_iterations=self.max_iterations,
            tolerance=self.tolerance,
        )

    def recalculate(
        self,
        workbook: Any,
        ctx: Any | None = None,
    ) -> CycleReport:
        """Scan all formula cells across all sheets in workbook, detect cycles, and recompute."""
        from atboffice.modules.spreadsheet.calc.context import EvalContext
        from atboffice.modules.spreadsheet.calc.errors import CYCLE, VALUE
        from atboffice.modules.spreadsheet.calc.evaluator import evaluate

        if ctx is None:
            ctx = EvalContext(workbook=workbook)
        elif ctx.workbook is None:
            ctx.workbook = workbook

        # 1. Clear existing formula registrations and rebuild from workbook
        self.clear()
        sheets = getattr(workbook, "sheets", [])
        for sh in sheets:
            sh_name = getattr(sh, "name", "Sheet1")
            cells_dict = getattr(sh, "cells", {})
            for (r, c), cell in cells_dict.items():
                formula = getattr(cell, "formula", None)
                if formula:
                    self.set_cell_formula(sh_name, r, c, formula)

        # 2. Cycle detection across all registered formula cells
        cycle_report = self.detect_cycles()

        # 3. For any circular cells, mark them with CYCLE error immediately
        for addr in cycle_report.circular_cells:
            sh = (
                workbook.get_sheet_by_name(addr.sheet)
                if hasattr(workbook, "get_sheet_by_name")
                else None
            )
            if sh is not None:
                cell = sh.get_cell(addr.r, addr.c) if hasattr(sh, "get_cell") else None
                if cell is not None:
                    cell.value = CYCLE

        # 4. Filter non-circular formula cells and topologically sort them
        non_circular_dirty = [
            addr for addr in self._formula_cells if addr not in cycle_report.circular_cells
        ]
        eval_order = self.topological_sort(non_circular_dirty)

        # 5. Evaluate in topological order
        for addr in eval_order:
            sh = (
                workbook.get_sheet_by_name(addr.sheet)
                if hasattr(workbook, "get_sheet_by_name")
                else None
            )
            if sh is not None:
                cell = sh.get_cell(addr.r, addr.c) if hasattr(sh, "get_cell") else None
                if cell is not None and getattr(cell, "formula", None):
                    ctx.current_sheet = addr.sheet
                    ctx.current_row = addr.r
                    ctx.current_col = addr.c
                    try:
                        cell.value = evaluate(cell.formula, ctx)
                    except Exception:
                        cell.value = VALUE

        return cycle_report

    def recalculate_cell(
        self,
        sheet: str,
        r: int,
        c: int,
        workbook: Any,
        ctx: Any | None = None,
    ) -> RecalcPlan:
        """Invalidate and recalculate downstream dependents when cell (sheet, r, c) changes."""
        from atboffice.modules.spreadsheet.calc.context import EvalContext
        from atboffice.modules.spreadsheet.calc.errors import CYCLE, VALUE
        from atboffice.modules.spreadsheet.calc.evaluator import evaluate

        if ctx is None:
            ctx = EvalContext(workbook=workbook)
        elif ctx.workbook is None:
            ctx.workbook = workbook

        plan = self.get_recalc_plan([CellAddress(sheet, r, c)])

        for addr in plan.cycle_report.circular_cells:
            sh = (
                workbook.get_sheet_by_name(addr.sheet)
                if hasattr(workbook, "get_sheet_by_name")
                else None
            )
            if sh is not None:
                cell = sh.get_cell(addr.r, addr.c) if hasattr(sh, "get_cell") else None
                if cell is not None:
                    cell.value = CYCLE

        for addr in plan.eval_order:
            if addr in plan.cycle_report.circular_cells:
                continue
            sh = (
                workbook.get_sheet_by_name(addr.sheet)
                if hasattr(workbook, "get_sheet_by_name")
                else None
            )
            if sh is not None:
                cell = sh.get_cell(addr.r, addr.c) if hasattr(sh, "get_cell") else None
                if cell is not None and getattr(cell, "formula", None):
                    ctx.current_sheet = addr.sheet
                    ctx.current_row = addr.r
                    ctx.current_col = addr.c
                    try:
                        cell.value = evaluate(cell.formula, ctx)
                    except Exception:
                        cell.value = VALUE

        return plan

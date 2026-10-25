# Implementation Plan: Issue #7 — [Ledger] DAG 依赖拓扑重算图、三色环路检测与迭代计算

## Task List

- [ ] **Task 1: Core Data Structures & Precedent Extraction in `dag.py`**
  - Define `Color`, `CellAddress`, `CellRange`, `Change`, `RangeEntry`, `PrecedentsResult`.
  - Implement `extract_precedents(ast: ASTNode, default_sheet: str = "Sheet1") -> PrecedentsResult`.
    - Handles `CellRefNode`, `AreaRefNode` with sheet references.
    - Flags `VOLATILE_FUNCTIONS` (NOW, TODAY, RAND, RANDBETWEEN, RANDARRAY, OFFSET, INDIRECT, CELL, INFO).
  - Write unit test stubs in `tests/unit/spreadsheet/test_dag.py` for address parsing and precedent extraction.

- [ ] **Task 2: Bi-directional Dependency Graph & Column Bucketing in `DependencyGraph`**
  - Implement `DependencyGraph`:
    - Storage: `_cell_dependents`, `_precedents`, `_col_buckets`, `_wide_buckets`, `_volatile_cells`.
    - `set_cell_formula(sheet, r, c, formula)`: parses formula if string, extracts precedents, updates direct and bucketed dependencies.
    - `remove_cell(sheet, r, c)`: removes formula node and unregisters dependents/buckets.
    - `get_dependents(sheet, r, c) -> set[CellAddress]`: queries direct and range bucket overlaps.
    - `get_precedents(sheet, r, c) -> set[CellAddress | CellRange]`.
  - Add unit tests in `test_dag.py` verifying direct and range dependencies (including wide ranges and column ranges).

- [ ] **Task 3: Recursive Dirty Invalidation (`invalidate`)**
  - Implement `invalidate(changes: list[Change | CellAddress | tuple]) -> list[CellAddress]`:
    - Collect direct dependents of changed cells/ranges.
    - If changed cell has a formula, mark it dirty.
    - Include volatile cells in the queue.
    - BFS propagation along downstream dependents.
    - Return deterministically ordered list of all dirty nodes.
  - Add unit tests verifying cascading multi-hop dirty propagation (`A1 -> B1 -> C1 -> D1`) and volatile cell invalidation.

- [ ] **Task 4: Three-Color DFS Cycle Detection (`detect_cycles`)**
  - Implement `detect_cycles(nodes: list[CellAddress] | None = None) -> CycleReport`:
    - Three-color marking: WHITE (0), GRAY (1), BLACK (2).
    - Detect self-cycles (`A1 = A1`), direct 2-cycles (`A1 = B1, B1 = A1`), and multi-node cycles (`A1 -> B1 -> C1 -> A1`).
    - Extract cycle paths and full `circular_cells` set.
  - Add unit tests verifying cycle detection on acyclic graphs, self-referencing cells, mutual loops, and indirect multi-hop loops.

- [ ] **Task 5: Kahn's Algorithm Topological Sort & Iterative Calculation Planning (`topological_sort`, `get_recalc_plan`)**
  - Implement Kahn's algorithm:
    - Build in-degree map within the dirty subgraph.
    - Queue zero-in-degree nodes, pop and decrement downstream in-degrees.
    - Output linear execution order where precedents precede dependents.
  - Handle cycles:
    - When remaining nodes have in-degree > 0:
      - If `iterative_enabled = True`: produce iterative plan with `max_iterations = 100`, `tolerance = 0.001`.
      - If `iterative_enabled = False`: append remaining cyclic nodes in physical order, marked with `CycleReport`.
  - Expose API in `src/atboffice/modules/spreadsheet/calc/__init__.py`.
  - Add unit tests for diamond dependencies (`A1 -> (B1, C1) -> D1`), complex DAGs, and cycle handling.

- [ ] **Task 6: Full Verification & Integration Suite**
  - Run `pytest tests/unit/spreadsheet/test_dag.py -v`.
  - Run full test suite `pytest` across the repository to ensure 100% pass and 0 regressions.

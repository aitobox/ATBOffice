# ATBOffice Phase 13B — Ledger Constrained Solver (`规划求解`) Design Specification

> **Status**: Implemented (Phase 13B)  
> **Scope**: `Ledger` spreadsheet multi-variable constrained optimization engine, Luna 2003 dialogs, menu/ribbon wiring, undo integration, i18n, and automated tests.

---

## 1. Overview & Goals

Phase 13B completes Ledger's What-If Analysis suite alongside `单变量求解` (`Goal Seek`), `方案管理器` (`Scenario Manager`), and `模拟运算表` (`Data Table`) by adding an Excel 2003-compatible constrained optimization **Solver (`规划求解`)**.

Design constraints:
- **Zero third-party solver dependencies**: Pure Python 3.12+ using only stdlib (`math`, `random`, `time`, `dataclasses`, `copy`) and existing Ledger calculation primitives (`EvalContext`, `DependencyGraph`, `parse_cell_reference`, `WorkbookModel`). `scipy` is not used.
- **Non-blocking UI**: Long optimization runs execute on a background `QThread` with cooperative cancellation (`cancel_check`) and progress callbacks (`progress_cb`), preserving responsive Luna 2003 chrome.
- **Workbook safety & Undo**: `solve_model()` always restores initial cell values before returning (even on failure, error, or cancellation). User acceptance (`保留规划求解的解`) commits changes through Ledger's `UndoService` (`Ctrl+Z` / `Ctrl+Y`) and persists model parameters in `sheet.extra["solver_model"]`.

---

## 2. Architecture

### 2.1 Calculation Engine (`src/atboffice/modules/spreadsheet/calc/solver.py`)

Public API contract:
- **Types**:
  - `SolverGoal = Literal["max", "min", "value_of"]`
  - `SolverMethod = Literal["simplex_lp", "grg_nonlinear", "evolutionary"]`
  - `ConstraintOp = Literal["<=", "=", ">=", "int", "bin", "dif"]`
- **Data Models**:
  - `SolverConstraint(lhs_ref, op, rhs="")`
  - `SolverOptions(max_iterations=200, max_time_sec=30.0, precision=1e-6, integer_optimality=0.01, population_size=40, random_seed=42)`
  - `SolverParams(objective_ref, goal="max", target_value=0.0, variable_refs="", constraints=..., make_unconstrained_non_negative=True, method="simplex_lp", default_sheet="Sheet1", options=...)`
  - `ConstraintReportItem(cell_ref, formula, cell_value, op, rhs_value, binding, slack)`
  - `SolverResult(success, status, message, iterations, objective_ref, initial_objective, final_objective, initial_values, solution_values, constraint_reports, elapsed_sec)`
- **Functions**:
  - `parse_cell_list(refs_str, default_sheet="Sheet1")` — comma-separated cells & ranges (`A1:B3`), `$` anchors, quoted/unquoted sheet qualifiers, deduplicated in order.
  - `format_cell_ref(sheet, r, c, default_sheet=None)`
  - `solve_model(workbook, params, cancel_check=None, progress_cb=None) -> SolverResult`
  - `apply_solver_solution(workbook, solution_values)`
  - `generate_answer_report(workbook, params, result) -> str` — creates unique `Answer Report N` worksheet summarizing Objective Cell, Variable Cells (Initial vs. Final), and Constraints (Value, Formula, Status, Slack).
  - `save_solver_model(sheet, params)` / `load_solver_model(sheet)` — serializes/deserializes model JSON under `sheet.extra["solver_model"]`.

### 2.2 Solver Algorithms

1. **`simplex_lp` (Linear & Mixed-Integer Programming)**:
   - Evaluates numerical finite differences and second-order curvature checks to reject nonlinear models (`success=False, status="non_linear"`).
   - Builds the exact linear tableau and solves via Two-Phase Simplex (handling `<=`, `>=`, `=`, `value_of` target equality, non-negativity / free-variable splitting, infeasibility, and unboundedness).
   - Supports `int` and `bin` constraints via Branch-and-Bound respecting `integer_optimality`.
2. **`grg_nonlinear` (Smooth Nonlinear Optimization)**:
   - Supports `max`, `min`, and `value_of` objectives with variable bounds (`x >= 0` when `make_unconstrained_non_negative=True`, `[0, 1]` for `bin`) and penalty / Augmented Lagrangian + derivative-free/projected search (Nelder-Mead / coordinate search) plus local rounding/branching for integer/binary constraints and distinctness penalties for `dif`.
3. **`evolutionary` (Non-smooth / Discontinuous & Combinatorial)**:
   - Deterministic seeded Differential Evolution (`random_seed`) with feasibility-first selection supporting discontinuous functions (`IF`, `MAX`, `ABS`), `int`, `bin`, and `dif` (`AllDifferent`) constraints.

---

## 3. UI Dialogs (`src/atboffice/modules/spreadsheet/dialogs/solver_dialog.py`)

Styled strictly with `theme_tokens()` and `ui_font()` (zero hardcoded colors/fonts) and localized via `safe_tr()` + `retranslate_ui()`:
- **`SolverParametersDialog`**:
  - Preloads saved model from `load_solver_model(current_sheet)` or initializes `objective_ref` from active cell `(initial_r, initial_c)`.
  - Controls: 目标单元格 (`objective_edit`), 目标 (`最大` / `最小` / `值为` + `target_value_edit`), 可变单元格 (`variables_edit`), 约束列表 (`添加` / `更改` / `删除` / `全部重置`), `使无约束变量为非负数`, 求解方法 (`单纯形 LP` / `GRG 非线性` / `演化`), `选项...`, `保存模型`, `求解`, `关闭`.
  - Runs `solve_model` in a background `QThread` with cooperative cancellation and clean teardown in `closeEvent`.
- **`AddConstraintDialog`**: Add or edit a constraint (`<=`, `=`, `>=`, `int`, `bin`, `dif`).
- **`SolverOptionsDialog`**: Configure `max_iterations`, `max_time_sec`, `precision`, `integer_optimality`, `population_size`, `random_seed`.
- **`SolverResultsDialog`**: Displays solver status/message, allows choosing `保留规划求解的解` vs. `恢复原值`, and optionally generating an `Answer Report` worksheet (`生成运算结果报告`).

---

## 4. Shell Wiring, Undo Integration & i18n

- **Action & Menu Wiring**:
  - `src/atboffice/ui/shell/mac_menu.py`: Registers `tools_solver` (alias `solver`) in Tools menu alongside `tools_goal_seek`, visible only in Ledger (`is_ledger`), with localized label `规划求解(&V)...`.
  - `src/atboffice/ui/shell/ledger_window.py`: Binds `solver` and `tools_solver` to `self.open_solver`.
  - `src/atboffice/ui/shell/ledger_ribbon.py`: Exposes `tools_solver` in Data -> 预测 (`What-If`) group with a valid theme icon mapping (`"goalSeek"`).
- **Undo & Refresh (`src/atboffice/ui/shell/ledger_auditing.py`)**:
  - `open_solver()` snapshots workbook cell state prior to launching `SolverParametersDialog`.
  - `apply_callback(params, result, keep_solution)`:
    - When `keep_solution=True`: applies `result.solution_values` via `apply_solver_solution`, saves model via `save_solver_model`, and records a reversible step in `LedgerWindow.undo_service()` restoring cell values, `solver_model` metadata, and recalculated formulas on `Ctrl+Z` / `Ctrl+Y`.
    - When `keep_solution=False`: restores the pre-solve cell snapshot without pushing an undo step.
  - Refreshes grid viewport, status bar calculation, and `SheetTabBar` (including when `dlg.created_report_sheet` creates a new Answer Report tab).
- **Localization (`src/atboffice/resources/locale/source/zh-CN_to_en.json`)**:
  - All new Chinese `safe_tr()` strings across engine, dialogs, and shell wiring are mapped to English equivalents preserving placeholder parity.

---

## 5. Verification Gates

All Phase 13B changes must pass:
- `ruff check .` & `ruff format --check .`
- `mypy src/atboffice/core`
- `scripts/source_diff.py --check` (`CLEAN`)
- `scripts/audit_toolbars_parity.py`
- `pytest` covering `test_solver_engine.py`, `test_phase13b_solver_ui.py`, `test_i18n.py`, `test_ribbon_spec_parity.py`, and `test_toolbars_icons.py`.

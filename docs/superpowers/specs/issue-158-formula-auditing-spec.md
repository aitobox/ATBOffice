# Specification: Formula Auditing (Trace Precedents/Dependents), Step-by-Step Evaluator, and Watch Window

## Overview & Context
- **Issue**: #158 `[Phase 4] 实现公式审核拓扑追踪箭头、单步求值与监视窗口`
- **Parent Epic**: #151 `Phase 4: 1:1 Visual Parity, Advanced Subsystems & Final Parity Acceptance`
- **Module**: `atboffice.modules.spreadsheet`

Currently, `ledger_window.py` has empty stubs for `trace_precedents()`, `trace_dependents()`, `remove_arrows()`, `watch_window()`, and `evaluate_formula()`. This feature restores full formula auditing capabilities replicating classic Excel 2003 / ATBOffice original design.

---

## Architecture & Components

### 1. `AuditTracer` & Arrow Data Model
File: `src/atboffice/modules/spreadsheet/calc/audit_tracer.py`

#### Data Structures:
- `AuditArrow`:
  - `from_sheet: str`
  - `from_r1: int`, `from_c1: int`, `from_r2: int`, `from_c2: int`
  - `to_sheet: str`
  - `to_r: int`, `to_c: int`
  - `is_error: bool = False`
  - `is_cross_sheet: bool = False`

#### Functions & Services:
- `trace_precedents(workbook: WorkbookModel, sheet_name: str, r: int, c: int, is_error: bool = False) -> list[AuditArrow]`:
  - Retrieves cell formula at `(r, c)`.
  - If no formula or empty formula, returns empty list (or raises descriptive error for UI prompt).
  - Parses AST using `parse_formula(formula)`.
  - Walks AST extracting `CellRefNode`, `AreaRefNode`, and `SheetReference`.
  - Resolves target sheet (defaulting to current sheet if not qualified).
  - Constructs `AuditArrow` instances.
- `trace_dependents(workbook: WorkbookModel, sheet_name: str, r: int, c: int) -> list[AuditArrow]`:
  - Uses `DependencyGraph` to inspect all formula cells depending on `(sheet_name, r, c)`.
  - Returns arrows from `(sheet_name, r, c)` to each dependent cell `(dep.sheet, dep.r, dep.c)`.
- `trace_error(workbook: WorkbookModel, sheet_name: str, r: int, c: int) -> list[AuditArrow]`:
  - Traces precedents specifically looking for error origin or marking arrows with `is_error=True`.

---

### 2. Viewport Arrow Rendering
File: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`

In `GridViewport.paintEvent`:
- Read `arrows = getattr(self.model, "audit_arrows", [])`.
- If arrows are present:
  - Antialiasing enabled for smooth arrow vector drawing.
  - For each arrow where `arrow.to_sheet == current_sheet.name` or `arrow.from_sheet == current_sheet.name`:
    - **Intra-sheet (same sheet)**:
      - Line color: Blue (`#0000FF`, pen width 1.5) or Red (`#FF0000` if `is_error`).
      - If range `from_r1 != from_r2 or from_c1 != from_c2`: draw bounding rectangle around `(from_r1, from_c1) .. (from_r2, from_c2)`.
      - Source anchor: small filled circle ($r=3$) at center of `(from_r1, from_c1)`.
      - Destination anchor: arrowhead polygon pointing to center of target cell `(to_r, to_c)`.
      - Straight line connecting source anchor to arrowhead base.
    - **Cross-sheet (different sheet)**:
      - When `from_sheet != current_sheet.name` and `to_sheet == current_sheet.name`:
        - Destination point: center of `(to_r, to_c)`: $(x_2, y_2)$.
        - Source origin: $(x_2 - 40, y_2 - 30)$.
        - Black dashed line (`Qt.PenStyle.DashLine`, black, width 1.2) ending with arrowhead at $(x_2, y_2)$.
        - Draw a small white rectangle ($14 \times 11$) with black border and a sheet glyph at $(x_2 - 52, y_2 - 40)$ representing the external sheet icon.

---

### 3. Step-by-Step Formula Evaluator Dialog
File: `src/atboffice/modules/spreadsheet/dialogs/evaluate_formula_dialog.py`

#### Class: `EvaluateFormulaDialog(QDialog)`
- Layout:
  - Reference indicator: `[Sheet]!$A$1`
  - Formula expression text area with HTML/styled formatting.
  - The current sub-expression to be evaluated is underlined: `<u>expr</u>`.
  - Bottom controls:
    - `Evaluate` button: evaluates the underlined sub-expression to its literal value, replaces the AST node, updates expression string.
    - `Restart` button (appears or re-labels when evaluation is complete to re-evaluate from beginning).
    - `Close` button.
- Sub-expression evaluation engine:
  - Identifies innermost evaluatable AST node (e.g. cell reference or function call whose arguments are already literals).
  - Evaluates via `calc.evaluator.evaluate_ast(node, ctx)`.
  - Replaces node with literal value (`num`, `str`, `bool`, `err`).
  - Converts updated AST back to formula text with the next node underlined.

---

### 4. Watch Window Dialog
File: `src/atboffice/modules/spreadsheet/dialogs/watch_window_dialog.py`

#### Class: `WatchWindowDialog(QDialog)`
- Modeless dialog (`setModal(False)`), floating tool window behavior.
- Top action bar:
  - `Add Watch... (&A)`: adds current selection from spreadsheet view.
  - `Delete Watch (&D)`: removes selected watch entry.
- Table view (`QTableWidget`) with columns:
  1. `Book` (工作簿名称)
  2. `Sheet` (工作表名称)
  3. `Name` (已定义名称，若有时显示)
  4. `Cell` (单元格坐标，如 `$A$1`)
  5. `Value` (当前计算值)
  6. `Formula` (公式文本，如 `=SUM(B1:B10)`)
- Live sync:
  - Connected to workbook `cell_changed` or recalculation signals.
  - Double-clicking a row jumps to the target worksheet and selects the cell in `GridViewport`.

---

### 5. `LedgerWindow` Integration
File: `src/atboffice/ui/shell/ledger_window.py`

- Implement `trace_precedents()`:
  - Gets active cell coordinates.
  - Runs `audit_tracer.trace_precedents(...)`.
  - If cell has no formula: show informational message box.
  - Attaches arrows to `sheet.audit_arrows` and calls `viewport().update()`.
- Implement `trace_dependents()`:
  - Gets active cell coordinates.
  - Runs `audit_tracer.trace_dependents(...)`.
  - If no dependents: show message box ("Ledger cannot find any dependent cells.").
  - Attaches arrows to `sheet.audit_arrows` and calls `viewport().update()`.
- Implement `remove_arrows()`:
  - Clears `sheet.audit_arrows = []`, updates viewport, updates status bar.
- Implement `evaluate_formula()`:
  - Checks if active cell has formula. If not, alerts user.
  - Opens `EvaluateFormulaDialog`.
- Implement `watch_window()`:
  - Opens or activates modeless `WatchWindowDialog`.

---

## Verification Plan
1. Unit tests: `tests/modules/spreadsheet/test_formula_auditing.py`:
   - `test_audit_tracer_precedents_single_and_range`: Test AST extraction of single cells and ranges.
   - `test_audit_tracer_cross_sheet`: Test precedents from another sheet.
   - `test_audit_tracer_dependents`: Test finding dependent cells via DAG.
   - `test_grid_viewport_arrow_rendering`: Test viewport painting helper with audit arrows.
   - `test_evaluate_formula_step_by_step`: Test stepwise AST evaluation from formula to final value.
   - `test_watch_window_add_delete_sync`: Test watch window table population, live update, and deletion.
   - `test_ledger_window_auditing_actions`: Test UI integration methods in LedgerWindow.
2. Full test suite verification:
   `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/test_formula_auditing.py -v`

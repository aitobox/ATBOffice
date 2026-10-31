# Implementation Plan: Formula Auditing, Step-by-Step Evaluator, and Watch Window

- **Issue**: #158 `[Phase 4] 实现公式审核拓扑追踪箭头、单步求值与监视窗口`
- **Spec**: `docs/superpowers/specs/issue-158-formula-auditing-spec.md`

---

## Tasks

### Task 1: Formula Audit Tracer Backend
- **Files**:
  - `src/atboffice/modules/spreadsheet/calc/audit_tracer.py`
- **Details**:
  - Implement `AuditArrow` dataclass.
  - Implement `AuditTracer` class with:
    - `extract_precedents_for_cell(sheet, r, c)`
    - `trace_precedents(workbook, sheet_name, r, c, is_error=False)`
    - `trace_dependents(workbook, sheet_name, r, c)`
  - Handle range precedents, single cell precedents, cross-sheet references, and missing formulas cleanly.

### Task 2: Grid Viewport Arrow Painting
- **Files**:
  - `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- **Details**:
  - In `paintEvent`, after drawing comment indicators and validation circles, add section 5.9: `Draw Audit Tracer Arrows`.
  - Draw intra-sheet blue (or red) lines, rectangles for ranges, center anchor dots, and arrow heads.
  - Draw cross-sheet dashed lines with sheet glyph icon.
  - Clean clipping with `cell_clip`.

### Task 3: Step-by-Step Evaluate Formula Dialog
- **Files**:
  - `src/atboffice/modules/spreadsheet/dialogs/evaluate_formula_dialog.py`
- **Details**:
  - Implement `EvaluateFormulaDialog` with:
    - Reference indicator (`Sheet1!$A$1`).
    - Formula expression preview with underline `<u>` on next node.
    - `next_evaluable_node(ast)` algorithm to find innermost sub-expression.
    - `evaluate_step()` to evaluate selected node, replace with literal, and advance.
    - "重新启动 (Restart)" capability when formula evaluation completes.
    - Full i18n via `safe_tr()`.

### Task 4: Watch Window Modeless Dialog
- **Files**:
  - `src/atboffice/modules/spreadsheet/dialogs/watch_window_dialog.py`
- **Details**:
  - Implement `WatchWindowDialog` (modeless tool dialog).
  - Columns: Book, Sheet, Name, Cell, Value, Formula.
  - `add_watch(sheet, r, c)` / `add_watches_from_selection(sheet, selection)`.
  - `delete_selected_watch()`.
  - Double-click jump to cell in sheet.
  - Refresh on model data changes.
  - Full i18n via `safe_tr()`.

### Task 5: LedgerWindow Actions Wiring
- **Files**:
  - `src/atboffice/ui/shell/ledger_window.py`
- **Details**:
  - Implement `trace_precedents()`: call `AuditTracer.trace_precedents`, attach to `sheet.audit_arrows`, refresh viewport.
  - Implement `trace_dependents()`: call `AuditTracer.trace_dependents`, attach to `sheet.audit_arrows`, refresh viewport.
  - Implement `remove_arrows()`: clear `sheet.audit_arrows = []`, refresh viewport.
  - Implement `evaluate_formula()`: launch `EvaluateFormulaDialog`.
  - Implement `watch_window()`: launch or toggle `WatchWindowDialog`.

### Task 6: Unit Tests & Verification
- **Files**:
  - `tests/modules/spreadsheet/test_formula_auditing.py`
- **Details**:
  - Test precedent extraction (single cell, range, cross-sheet).
  - Test dependent cell queries via DAG.
  - Test viewport arrow painting logic.
  - Test stepwise formula evaluation with arithmetic, functions, and errors.
  - Test watch window adding, deleting, refreshing, and jumping.
  - Test LedgerWindow actions and user alerts for empty formulas.

### Task 7: Full Regression Verification
- Run:
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/test_formula_auditing.py -v`

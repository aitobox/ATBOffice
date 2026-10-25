# Implementation Plan: Issue #13 [Ledger] 原位单元格编辑、公式栏双向绑定与自动计算状态栏

## Overview
Implement in-cell editor, two-way bound formula bar with NameBox and action buttons, formula pointing mode with colored reference border canvas overlays, and AutoCalculate status bar with selection aggregation.

---

## Task Breakdown & Execution Sequence

### Task 1: FormulaBar Implementation
- **File**: `src/atboffice/modules/spreadsheet/views/formula_bar.py`
- **Details**:
  - `FormulaBar(QWidget)` containing:
    - `name_box`: `QLineEdit` showing cell name (e.g. `A1`) or range dimension (e.g. `2R x 3C`); `returnPressed` parses target and emits `navigate_requested(row, col)`.
    - `btn_cancel`: Tool button with "✕" icon / text, emits `cancel_requested`.
    - `btn_commit`: Tool button with "✓" icon / text, emits `commit_requested`.
    - `btn_fx`: Tool button with "fx" styling, emits `fx_requested`.
    - `formula_input`: `QLineEdit` for editing formula/value, emits `text_changed(str)`, `editing_started`, `commit_requested`, `cancel_requested`.
  - Methods: `set_cell_text(text: str)`, `set_address(text: str)`, `set_editing_state(active: bool)`.
  - Full i18n support with `safe_tr()` and `retranslate_ui()`.

### Task 2: AutoCalculate StatusBar Implementation
- **File**: `src/atboffice/ui/components/status_bar.py`
- **Details**:
  - `StatusBar(QStatusBar)` containing:
    - Mode indicator label: "就绪" (Ready), "输入" (Enter), "编辑" (Edit), "点选" (Point).
    - Status message label.
    - AutoCalculate panel with clickable / right-clickable context menu:
      - None ("无"), Average ("平均值"), Count ("计数"), Count Nums ("数值计数"), Max ("最大值"), Min ("最小值"), Sum ("求和"). Default: Sum.
      - Calculates metrics across given `SelectionModel` and `SheetDataModel`.
      - Hides text when single cell or None selected.
    - Lock indicators (CAPS, NUM, SCRL).
  - Methods: `set_mode(mode: str)`, `update_calculation(model, selection)`, `retranslate_ui()`.
  - Full i18n support with `safe_tr()`.

### Task 3: EditorController & In-Cell Editor
- **File**: `src/atboffice/modules/spreadsheet/views/editor_controller.py`
- **Details**:
  - `EditorMode(Enum)`: `READY`, `ENTER`, `EDIT`, `POINT`.
  - `ReferenceHighlight`: Data structure containing range `(r1, c1, r2, c2)` and QColor.
  - `InCellEditor(QLineEdit)`:
    - Subclass of `QLineEdit` overlaying `GridViewport.viewport()`.
    - Auto-expands width based on text metrics (`QFontMetrics.horizontalAdvance`).
    - Styled to match target cell formatting.
  - `EditorController(QObject)`:
    - Manages state, active cell `(r, c)`, original cell value.
    - Bridges `InCellEditor` and `FormulaBar` with `_syncing` flag to prevent echo loops.
    - Detects operand position in formula (`operand_at()`) to switch into `POINT` mode.
    - Tokenizes formula via `atboffice.modules.spreadsheet.calc.parser.tokenize` to extract references and compute colored bounding boxes.
    - Handles point selection: clicking/dragging grid cells replaces or inserts reference.
    - Commits value back to `SheetDataModel` on Enter/Tab, restores on Esc.

### Task 4: GridViewport Enhancements
- **File**: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- **Details**:
  - Add `reference_highlights: list[ReferenceHighlight]` property and drawing in `paintEvent`:
    - Draws 2px colored rectangle with corners around each highlighted range.
  - Expose `cell_double_clicked` and keyboard typing hooks to activate `EditorController`.
  - In point mode, route mouse presses/moves to `EditorController.point_at()`.
  - Reposition in-cell editor on scroll or viewport resize.

### Task 5: Integration in SpreadsheetView and MainWindow
- **Files**:
  - `src/atboffice/modules/spreadsheet/view.py`
  - `src/atboffice/ui/shell/main_window.py`
- **Details**:
  - Add `FormulaBar` above `GridViewport` in `SpreadsheetView`.
  - Instantiate `EditorController` wiring up `FormulaBar`, `GridViewport`, `model`, and `selection`.
  - Attach `StatusBar` to `MainWindow` and connect selection updates to `StatusBar.update_calculation`.

### Task 6: Automated Test Suite (TDD Verification)
- **File**: `tests/gui/test_editor_and_status_bar.py`
- **Details**:
  - Test FormulaBar text sync, NameBox navigation, button clicks.
  - Test InCellEditor activation via double-click, F2, and character key press.
  - Test two-way synchronization between FormulaBar and InCellEditor without infinite loop.
  - Test Point Mode: formula starting with `=`, clicking cell inserts `A1`, dragging inserts `A1:B2`.
  - Test Reference Highlights: correct colors assigned and bounding boxes updated.
  - Test StatusBar AutoCalculate: Sum, Average, Count, Max, Min across multiple cells.
  - Test i18n retranslation.

### Task 7: Full Test Suite Verification
- Run `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`
- Ensure 100% pass with zero regressions.

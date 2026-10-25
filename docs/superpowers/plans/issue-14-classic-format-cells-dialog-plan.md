# Implementation Plan: Issue #14 [Ledger] 经典 6 标签“单元格格式”对话框

## Overview
Implement the classic 6-tab "Format Cells" dialog for ATBOffice Ledger, including Number, Alignment, Font, Border, Patterns (54 ECMA-376 pattern fills), and Protection tabs, integrated with the spreadsheet data model and GUI viewports.

## Phase Breakdown

### Task 1: Data Model Expansion & Format Delta
- **Files**:
  - `src/atboffice/modules/spreadsheet/models/sheet_model.py`
  - `tests/unit/spreadsheet/test_cell_format_model.py`
- **Actions**:
  - Extend `CellData` with border, alignment, font effects, patterns, and protection attributes.
  - Introduce `BorderStyle` and `FormatDelta` dataclasses.
  - Implement `apply_format_delta(range, delta)` on `SheetDataModel`.
  - Add unit tests for `CellData` formatting and delta applications.

### Task 2: 54 Pattern Presets & Rendering Utilities
- **Files**:
  - `src/atboffice/modules/spreadsheet/dialogs/pattern_defs.py`
  - `tests/unit/spreadsheet/test_pattern_defs.py`
- **Actions**:
  - Port all 54 ECMA-376 / Office 2003 8x8 bitmap pattern definitions from `.vibeoffice/public/common/geometry.js`.
  - Provide `create_pattern_pixmap(pattern_name, fg_color, bg_color, size)` and `create_pattern_brush()`.
  - Add unit tests for pattern generation.

### Task 3: Implementation of FormatCellsDialog & 6 Tabs
- **Files**:
  - `src/atboffice/modules/spreadsheet/dialogs/format_cells.py`
  - `src/atboffice/modules/spreadsheet/dialogs/__init__.py`
- **Actions**:
  - Implement `NumberFormatTab`: 12 categories, live sample preview with `format_value`.
  - Implement `AlignmentTab`: H/V align, indent, wrap text, shrink to fit, merge cells, orientation dial (-90° to 90° & 255 vertical), text direction.
  - Implement `FontTab`: Font family list, styles, size (1-409), underline styles, colors, effects (strikethrough, superscript, subscript), live preview.
  - Implement `BorderTab`: Presets, 14 line styles, color, and `BorderPreviewWidget` interactive canvas.
  - Implement `PatternsTab`: Shading colors, 54-pattern dropdown/grid, pattern color, composite sample.
  - Implement `ProtectionTab`: Locked, hidden, and hint text.
  - Implement `FormatCellsDialog` container dialog with `retranslate_ui()` and `apply_to_selection()`.

### Task 4: Viewport & Menu Integration
- **Files**:
  - `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
  - `src/atboffice/ui/shell/main_window.py`
- **Actions**:
  - Connect ⌘1 / Ctrl+1 shortcut in `grid_viewport.py` and `mac_menu.py`.
  - Add right-click context menu in `grid_viewport.py` with "设置单元格格式…".
  - Wire `MainWindow.format_cells()` to launch `FormatCellsDialog`.

### Task 5: Verification & Full GUI Test Suite
- **Files**:
  - `tests/gui/test_format_cells_dialog.py`
- **Actions**:
  - Test all 6 tabs and controls.
  - Test applying formats to single and multi-cell selections.
  - Verify complete test suite passes without regressions.

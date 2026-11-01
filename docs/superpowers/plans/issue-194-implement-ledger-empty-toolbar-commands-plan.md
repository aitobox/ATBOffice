# Implementation Plan: [Phase 5] 实现 Ledger 已注册的空工具栏命令

- **Branch**: `agent/issue-194-implement-ledger-empty-toolbar-commands`
- **Specification**: `docs/superpowers/specs/issue-194-implement-ledger-empty-toolbar-commands-spec.md`
- **Issue**: [#194](https://github.com/aitobox/ATBOffice/issues/194)

## Task Breakdown

### Task 1: Hyperlink Dialog & Toolbar Wiring
- **Files**:
  - `src/atboffice/modules/spreadsheet/dialogs/hyperlink_dialog.py` (new)
  - `src/atboffice/modules/spreadsheet/dialogs/__init__.py`
  - `src/atboffice/ui/shell/ledger_window.py`
  - `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
  - `tests/ui/test_ledger_toolbar_wiring.py`
- **Details**:
  - Create `HyperlinkDialog` with Web/File, Place in Document, and Email tabs, ScreenTip, and Remove Link button.
  - Implement `insert_hyperlink` in `LedgerWindow` and wire it with active cell and `model.links`.
  - Format cell text and style (blue text, underline) when link is added; revert style and remove link when Remove Link is chosen.
  - Support Cancel with zero side effects.
  - Record undo/redo operations in `GridViewport._undo_stack`.
  - Write comprehensive tests in `test_ledger_toolbar_wiring.py`.

### Task 2: Floating Object Context Enablement & Format Object Dialog
- **Files**:
  - `src/atboffice/modules/spreadsheet/dialogs/format_object_dialog.py` (new)
  - `src/atboffice/modules/spreadsheet/dialogs/__init__.py`
  - `src/atboffice/ui/shell/ledger_window.py`
  - `tests/ui/test_ledger_toolbar_wiring.py`
- **Details**:
  - Connect `spreadsheet_view.object_layer.object_selected` signal to dynamically enable/disable the `formatObject` toolbar action.
  - Create `FormatObjectDialog` with Colors & Lines (fill color/alpha, line color/width), Size (width, height, aspect ratio), and Properties (anchor type, alt text).
  - Implement `format_selected_object` in `LedgerWindow` to launch dialog when an object is selected.
  - Ensure Cancel preserves original object state; OK applies changes and requests layer update.
  - Write tests verifying disabled state without selection, enabled state upon selection, dialog execution, and cancel safety.

### Task 3: Total Row Toggle, Context Detection & Undo/Redo
- **Files**:
  - `src/atboffice/ui/shell/ledger_window.py`
  - `tests/ui/test_ledger_toolbar_wiring.py`
- **Details**:
  - Detect active table, auto-filter, or bounding data range for active cell.
  - When toggling ON: append summary row with "Total" in col 0 and SUM/SUBTOTAL formulas in numeric/last columns, with top thin and bottom double borders. Update `action_registry.set_checked("totalRow", True)`.
  - When toggling OFF: clear summary row cells, revert range, and update `action_registry.set_checked("totalRow", False)`.
  - Ensure `convert_table_to_range` cleanly resets `totalRow`.
  - Record changes in `GridViewport._undo_stack` for undo/redo.
  - Disable or reject `totalRow` if active sheet has no data.
  - Write tests for toggle on, toggle off, undo/redo, convert to range, and empty context.

### Task 4: Format Painter State Machine & Grid Application
- **Files**:
  - `src/atboffice/ui/shell/ledger_window.py`
  - `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
  - `tests/ui/test_ledger_toolbar_wiring.py`
- **Details**:
  - Implement `toggle_format_painter(self, double_click: bool = False)` in `LedgerWindow`.
  - Sample source cell formatting (font, fill, borders, align, number format).
  - Manage active, sticky, and cancelled states; change cursor in grid viewport to indicating brush state.
  - When target cells are selected/clicked in `GridViewport`, apply formatting while strictly preserving values and formulas.
  - Deactivate immediately after one application unless sticky (double-clicked).
  - Cancel on Esc or toolbar re-click without altering cells.
  - Push undo/redo command on application.
  - Delegate `LedgerWindow.undo()` and `LedgerWindow.redo()` to `grid.undo()` and `grid.redo()`.
  - Write tests for single-click, double-click sticky, cancel, and undo/redo.

### Task 5: i18n Localization, Docs & Full Test Suite Verification
- **Files**:
  - `src/atboffice/resources/locale/*.json` (all 7 locales)
  - `docs/clone/CLONE_DIFF.md`
  - Run `pytest` on all tests and ensure 100% pass rate.

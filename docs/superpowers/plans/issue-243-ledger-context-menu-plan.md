# Implementation Plan: Issue #243 [phase7] TASK-709: fix(ledger-menu): 补齐右键菜单的真实业务行为

## Phase 1: PasteSpecialDialog Implementation
- [ ] Task 1.1: Create `src/atboffice/modules/spreadsheet/dialogs/paste_special_dialog.py`
  - Design QDialog matching Excel 2003 / VibeOffice:
    - Paste options: All (`all`), Formulas (`formulas`), Values (`values`), Formats (`formats`), Comments (`comments`), Validation (`validation`), All except borders (`noBorders`), Column widths (`colWidths`), Formulas and number formats (`formulasNF`), Values and number formats (`valuesNF`).
    - Operations: None (`none`), Add (`add`), Subtract (`sub`), Multiply (`mul`), Divide (`div`).
    - Options: Skip blanks (`skipBlanks`), Transpose (`transpose`).
    - Action buttons: OK (`确定`), Cancel (`取消`), Paste Link (`粘贴链接(&L)`).
  - Implement full i18n with `safe_tr()` and `retranslate_ui()`.
  - Export dialog in `src/atboffice/modules/spreadsheet/dialogs/__init__.py`.

## Phase 2: Sparse Bounds & Paste Special Engine in GridViewport
- [ ] Task 2.1: Update `copy()` and `cut()` in `src/atboffice/modules/spreadsheet/views/grid_viewport.py` to use sparse bounds when full columns or full rows are selected (`max_r = min(max_r, max(rg.min_r, sheet.max_row))` and `max_c = min(max_c, max(rg.min_c, sheet.max_col))`).
- [ ] Task 2.2: Implement `paste_special(options=None)` in `grid_viewport.py` executing:
  - If options is None: show `PasteSpecialDialog` and collect settings.
  - Process values, formulas offset translation, formatting, column widths, transpose dimension swapping, skip blanks, and arithmetic operations.
  - Guard protection check (`guard_protect()`).
  - Dirty flag setting and undo stack transaction push.

## Phase 3: GridViewport Context Menus Refinement
- [ ] Task 3.1: Table / List conditional branch:
  - Add `table_at(r, c)` lookup on SheetDataModel / GridViewport.
  - If inside table, show `列表(&L)` submenu with `汇总行(&T)` and `转换为区域(&R)`.
  - If outside table, show `创建列表(&L)…`.
- [ ] Task 3.2: Verify comments & hyperlinks dynamic actions (`编辑批注` vs `插入批注`, `编辑超链接` vs `超链接`).
- [ ] Task 3.3: Verify Shift+F10 opens context menu at active cell center.
- [ ] Task 3.4: Verify in-cell editor commit failure stops right-click menu from moving active cell or opening.

## Phase 4: Sheet Tab Bar Context Menu Enhancements
- [ ] Task 4.1: In `src/atboffice/modules/spreadsheet/views/sheet_tab_bar.py`:
  - Enhance `_show_tab_context_menu`: add `选定全部工作表(&S)` and `取消成组工作表(&U)`.
  - Ensure move/copy sheet updates workbook dirty and emits sheet changes.
  - Add right-click context menu on navigation buttons to show sheet selector popup.

## Phase 5: ObjectLayer Context Menu Enhancements
- [ ] Task 5.1: In `src/atboffice/modules/spreadsheet/views/object_layer.py`:
  - Standardize context menu actions with `safe_tr()` and accelerators.
  - Add Chart Type, Chart Options, Format Area for charts.
  - Add Edit Text, Format Shape/TextBox for shapes.
  - Add Format Picture for images.

## Phase 6: LedgerWindow Integration & ActionRegistry
- [ ] Task 6.1: In `src/atboffice/ui/shell/ledger_window.py`:
  - Bind `pasteSpecial` in `_bind_action_handlers()`.
  - Add `paste_special()` window method routing to `self.spreadsheet_view.grid.paste_special()`.

## Phase 7: Comprehensive Acceptance Tests
- [ ] Task 7.1: Create `tests/gui/test_phase7_context_actions.py` covering all criteria:
  - Context menu selection targets (inside vs outside, Shift+F10, editor commit abort).
  - Paste special all modes (values, formulas, formats, transpose, skip blanks, arithmetic, col widths, cancel).
  - Table / List conditional menu items.
  - Sparse boundaries on 10^6 column selection (instant execution without hanging).
  - Sheet tab bar actions (move, copy, color, select all, nav popup).
  - Object layer menu actions (chart, shape, picture).
  - Status bar AutoCalculate radio functions.
  - Single undo reversion and save/reopen consistency.
- [ ] Task 7.2: Update `docs/clone/phase7_control_matrix.csv` and `docs/clone/phase7_features.csv`.
- [ ] Task 7.3: Run directional verification command:
  `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_context_actions.py tests/gui/test_ledger_context_menu.py -ra`

# Implementation Plan: Issue #216 - 补全 Ledger 视图 (分页符预览/全屏) 与完整右键菜单

## Overview
按照规范 `docs/superpowers/specs/issue-216-ledger-views-and-context-menus-spec.md`，依次实现 Ledger 模块的分页符预览模式、全屏模式、行标/列标右键菜单增强、工作表标签移动/复制对话框及右键菜单增强、状态栏自动计算区完善，并编写覆盖性单元测试。

---

## Tasks Breakdown

### Task 1: Enhance `GridViewport` with Page Break Preview and Header Actions
- **File**: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- **Details**:
  1. Add `view_mode` property (`"normal"` | `"page_break"`) and `view_mode_changed = Signal(str)`.
  2. In `paintEvent`:
     - If `view_mode == "page_break"`, calculate used area or default printable area.
     - Paint outside area with dim gray `#999999`.
     - Paint print boundaries with solid/dashed blue lines (`#184cc8`).
     - Paint "Page 1", "Page 2" watermark text centered on each printable page in bold gray.
  3. Add `show_page_break_welcome_dialog(parent)` method.
  4. Implement `autofit_selected_rows()` and `autofit_selected_cols()`.
  5. Implement `set_standard_col_width_dialog()`.
  6. Update `_build_row_header_menu` with "最适合的行高(&A)".
  7. Update `_build_col_header_menu` with "最适合的列宽(&A)" and "标准列宽(&S)…".
- **Verification**: Unit tests on `GridViewport` view mode and menu items.

---

### Task 2: Enhance `LedgerWindow` with Full Screen and View Mode Handlers
- **File**: `src/atboffice/ui/shell/ledger_window.py`
- **Details**:
  1. Implement `FullScreenToolBar` (a small floating tool window with "关闭全屏" / "Close Full Screen").
  2. Implement `toggle_full_screen(enable: bool | None = None)` in `LedgerWindow`:
     - Save visibilities of toolbars, menu bar, formula bar, status bar.
     - Toggle `showFullScreen()` vs `showNormal()`.
     - Show/hide `FullScreenToolBar`.
  3. Handle `keyPressEvent`: if `Esc` is pressed and in full screen, exit full screen.
  4. Wire `view_normal`, `view_page_break` (or `view_page_break_preview`), and `view_fullscreen` actions in `ActionRegistry` and sync with `GridViewport.set_view_mode`.
- **Verification**: Unit tests on full screen toggle, escape handling, view mode action invocation.

---

### Task 3: Create `MoveCopySheetDialog` and Enhance `SheetTabBar` Context Menu
- **Files**:
  - `src/atboffice/modules/spreadsheet/dialogs/move_copy_sheet_dialog.py`
  - `src/atboffice/modules/spreadsheet/views/sheet_tab_bar.py`
- **Details**:
  1. Create `MoveCopySheetDialog`:
     - Lists all sheets in the workbook + `(移至最后)`.
     - "建立副本(&C)" checkbox.
     - "确定" / "取消" buttons.
  2. In `SheetTabBar._show_tab_context_menu`:
     - Update "移动或复制(&M)..." to open `MoveCopySheetDialog`.
     - On accept, perform either copy (duplicate sheet at target position) or move (`workbook.move_sheet`).
     - Add "工作表标签颜色(&T)...", "隐藏(&H)", "取消隐藏(&U)...".
- **Verification**: Unit tests on `MoveCopySheetDialog` and tab bar menu actions.

---

### Task 4: Polish `StatusBar` Localization and AutoCalculate Context Menu
- **File**: `src/atboffice/ui/components/status_bar.py`
- **Details**:
  1. Ensure `safe_tr` uses string templates: `safe_tr("求和={0}").format(fmt_num(total_sum))`, etc.
  2. Ensure immediate calculation refresh on menu item change and selection change.
- **Verification**: Unit tests verifying `StatusBar` function changes and output format.

---

### Task 5: Expand `tests/gui/test_ledger_context_menu.py` & Full Verification
- **File**: `tests/gui/test_ledger_context_menu.py`
- **Details**:
  1. Add tests for Page Break Preview mode and watermark rendering.
  2. Add tests for row header autofit and col header autofit / standard width.
  3. Add tests for Ledger full screen mode and Esc key exit.
  4. Add tests for `MoveCopySheetDialog` and `SheetTabBar` context menu.
  5. Add tests for `StatusBar` calculation switching.
- **Verification**:
  - `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_ledger_context_menu.py -v`
  - Zero regressions across existing tests.

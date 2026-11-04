# Spec: Issue #243 [phase7] TASK-709: fix(ledger-menu): 补齐右键菜单的真实业务行为

## 1. Overview & Context

- **Issue**: #243 (TASK-709, Step 9 of 13 in Epic #234)
- **Goal**: 对照 VibeOffice `app.js:847`、`commands.js`、`clipboard.js`、`drawing.js` 及截图 049–053，全面补齐并核准 Ledger 单元格、行头、列头、工作表标签、浮动对象和状态栏计算区域的右键上下文菜单。
- **Key Modules Affected**:
  - `src/atboffice/modules/spreadsheet/views/grid_viewport.py` (Cell, Row Header, Col Header context menus, sparse bounds copy/paste, Shift+F10, commit validation)
  - `src/atboffice/modules/spreadsheet/dialogs/paste_special_dialog.py` (New: Complete Paste Special dialog & logic)
  - `src/atboffice/modules/spreadsheet/views/sheet_tab_bar.py` (Sheet tab context menu, Select All Sheets / Ungroup Sheets, navigation buttons context menu)
  - `src/atboffice/modules/spreadsheet/views/object_layer.py` (Object context menu for Shapes, Charts, Pictures with order and formatting options)
  - `src/atboffice/ui/shell/ledger_window.py` (Action bindings, window-level dispatch, state persistence)
  - `tests/gui/test_phase7_context_actions.py` (New: Comprehensive acceptance tests)

---

## 2. Detailed Technical Requirements

### 2.1 GridViewport Context Menus (Cell, Row, Col, Shift+F10)
1. **Target Selection Integrity**:
   - Right-click within active selection preserves multi-cell/multi-range selection.
   - Right-click outside active selection moves active cell and sets primary selection to target cell.
   - Right-click while editing in-cell:
     - Attempts `editor_controller.commit()`.
     - If commit succeeds, editor closes and target is selected.
     - If commit fails (validation or syntax error), editor remains active and context menu is aborted.
   - Shift+F10 (and Windows Menu key): triggers `open_context_menu()` at the visual center of the active cell.
2. **Sparse Bounds for Full Row/Col Copy & Clear**:
   - When copying whole column(s) (e.g. 1,048,576 rows) or whole row(s) (e.g. 16,384 columns):
     - Restrict bounded iteration to `min(max_r, max(rg.min_r, sheet.max_row))` and `min(max_c, max(rg.min_c, sheet.max_col))`.
     - Avoid allocating or scanning 10^6 empty cells.
3. **Table / List Conditional Branching**:
   - Check if active cell is inside a table (`table_at(r, c)`).
   - Inside Table: Display `List` (`列表(&L)`) submenu with `Total Row` (`汇总行(&T)`) and `Convert to Range` (`转换为区域(&R)`).
   - Outside Table: Display `Create List...` (`创建列表(&L)…`).
4. **Comments & Hyperlinks Dynamic Visibility**:
   - Cell with comment: `Edit Comment`, `Delete Comment`, `Show/Hide Comment`.
   - Cell without comment: `Insert Comment`.
   - Cell with link: `Edit Hyperlink...`, `Open Hyperlink`, `Remove Hyperlink`.
   - Cell without link: `Hyperlink...`.

### 2.2 Paste Special Dialog & Execution (`PasteSpecialDialog`)
1. **Dialog UI Layout**:
   - Options Group: All, Formulas, Values, Formats, Comments, Validation, All Except Borders, Column Widths, Formulas & Number Formats, Values & Number Formats.
   - Operation Group: None, Add, Subtract, Multiply, Divide.
   - Checkboxes: Skip Blanks, Transpose.
   - Buttons: OK, Cancel, Paste Link.
2. **Transformation Logic**:
   - Values: copies numeric or text values, evaluates formulas if dirty.
   - Formulas: translates relative cell coordinates `(r - src_r, c - src_c)` using AST / regex relative reference translator.
   - Formats: preserves target values/formulas and applies style/border/font/fill.
   - Col Widths: transfers width metadata to target columns.
   - Transpose: flips rows and columns `(h, w) -> (w, h)`.
   - Skip Blanks: cells in source that have no value/formula do not overwrite existing target cells.
   - Arithmetic operations (`add`, `sub`, `mul`, `div`): combines source value with existing target value.
   - Protection & Undo: validates `guard_protect()`, pushes single undo transaction to `undo_stack`.

### 2.3 Sheet Tab Bar Context Menu (`SheetTabBar`)
1. **Tab Menu Options**:
   - Insert Sheet (`插入(&I)…`)
   - Delete Sheet (`删除(&D)`) - disabled if only 1 sheet remains.
   - Rename Sheet (`重命名(&R)`)
   - Move or Copy Sheet (`移动或复制(&M)…`) - invokes `MoveCopySheetDialog` and handles deep copy with automatic name numbering `Name (2)`.
   - Tab Color (`工作表标签颜色(&T)…`) - opens `QColorDialog`.
   - Select All Sheets (`选定全部工作表(&S)`) - groups all visible sheets.
   - Ungroup Sheets (`取消成组工作表(&U)`) - visible when multiple sheets are selected/grouped.
   - View Code (`查看代码(&V)`) [disabled]
   - Protect Sheet (`保护工作表(&P)…`) [disabled]
   - Hide (`隐藏(&H)`) [disabled if 1 sheet] / Unhide (`取消隐藏(&U)…`)
2. **Nav Buttons Context Menu**:
   - Right-click on First/Prev/Next/Last nav buttons displays popup list of all sheets for quick navigation.

### 2.4 Floating Object Context Menu (`ObjectLayer`)
1. **Context Menu Hierarchy**:
   - Cut, Copy, Paste, Delete.
   - Order (`叠放次序(&R)`): Bring to Front (`置于顶层(&T)`), Send to Back (`置于底层(&K)`), Bring Forward (`上移一层(&F)`), Send Backward (`下移一层(&B)`).
   - Chart Objects: Chart Type (`图表类型(&T)…`), Chart Options (`图表选项(&O)…`), Format Chart Area (`设置图表区域格式(&F)…`).
   - Shape Objects: Edit Text (`编辑文字(&T)`), Format AutoShape/TextBox (`设置自选图形/文本框格式(&O)…`).
   - Image Objects: Format Picture (`设置图片格式(&O)…`).
2. **i18n & Accelerators**:
   - All actions wrapped with `safe_tr()` and standard keyboard accelerators.

### 2.5 Status Bar AutoCalculate Menu (`StatusBar`)
1. **AutoCalculate Menu**:
   - None (`无(&N)`), Average (`平均值(&A)`), Count (`计数(&C)` / COUNTA), Count Nums (`数值计数(&U)` / COUNT), Max (`最大值(&M)`), Min (`最小值(&I)`), Sum (`求和(&S)`).
   - Checkable radio options, clicking updates `auto_calc_fn` and immediately triggers `update_calculation()`.

---

## 3. Edge Cases & Safety Guardrails
- **Cell Protection**: Guard protect checks whether sheet protection is active and cell is locked; prompts warning dialog and cancels edit.
- **Sparse Boundaries**: Iterating row/col ranges must never allocate arrays of 1,000,000 items.
- **Undo / Redo & Dirty Flag**: Every menu command that mutates data triggers `self.dirty = True`, emits change signals, and supports one-shot Undo.
- **Modal Re-entrancy**: Context menus use `QMenu.exec()` safely without recursion or blocking Qt event processing.

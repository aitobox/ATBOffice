# Specification: Issue #157 — 实现 519 函数检索与参数即时计算的“插入函数 (fx) 向导”

## 1. Overview & Objectives

In ATBOffice Ledger (the spreadsheet module), 519 worksheet functions are cataloged in `src/atboffice/modules/spreadsheet/calc/fn_info.py` and supported by the calculation engine (`evaluator.py`, `context.py`).
This specification details the design and implementation of the two-step formula authoring wizard:
1. **Insert Function Dialog (`InsertFunctionDialog`)**: Allows users to filter functions by category, perform keyword and fuzzy searches, preview syntax and function descriptions, and maintain a 10-item Most Recently Used (MRU) list.
2. **Function Arguments Dialog (`FunctionArgumentsDialog`)**: Provides a dedicated parameter editing interface for the selected function, displays argument explanations, supports dynamic repeating arguments (`...`), previews per-argument and total formula calculation results in real-time, supports range picking from the grid, and safely commits the constructed formula into the active cell and formula bar.
3. **Integration**: Connects the `fx` button on the formula bar (`FormulaBar.btn_fx`), toolbar actions ("更多函数(&F)..."), and the application menu (`插入 -> 函数(&F)...`).

---

## 2. Architecture & Component Design

### 2.1 File Organization
- `src/atboffice/modules/spreadsheet/dialogs/function_wizard.py`:
  - `FunctionCatalogService`: Helper class wrapping `fn_info.py` and `ARGHELP` metadata with search, category filtering, and MRU caching.
  - `InsertFunctionDialog(QDialog)`: Step 1 dialog for searching and selecting a function.
  - `FunctionArgumentsDialog(QDialog)`: Step 2 dialog for editing parameters, live evaluation, and formula assembly.
  - `launch_function_wizard(parent, workbook, sheet, active_r, active_c, editor_controller=None, default_fn=None)`: Factory entry point.
- `src/atboffice/modules/spreadsheet/views/formula_bar.py`:
  - Ensure `btn_fx` signal is properly emitted and handled.
- `src/atboffice/modules/spreadsheet/views/editor_controller.py`:
  - Enhance `_on_fx_clicked` to invoke the function wizard or launch `FunctionArgumentsDialog` if a function is being edited.
- `src/atboffice/ui/shell/ledger_window.py`:
  - Connect `open_function_wizard` to `launch_function_wizard`.
- `src/atboffice/ui/shell/mac_menu.py`:
  - Add `insert_function` action under `menu_insert` with shortcut `Shift+F3` and connect to `open_function_wizard`.
- `tests/modules/spreadsheet/test_function_wizard.py`:
  - Comprehensive unit and integration tests covering catalog lookup, search, MRU persistence, parameter validation, live evaluation, and dialog interactions.

---

## 3. Detailed Component Specifications

### 3.1 Metadata & Argument Help Catalog
In addition to `fn_info.ALL_FUNCTIONS_CATALOG`, add the comprehensive `ARGHELP` dictionary translated and adapted from original `fninfo.js`:
- Standard categories:
  - `Most Recently Used` (常用)
  - `All` (全部)
  - `Financial` (财务)
  - `Date & Time` (日期与时间)
  - `Math & Trig` (数学与三角)
  - `Statistical` (统计)
  - `Lookup & Reference` (查找与引用)
  - `Database` (数据库)
  - `Text` (文本)
  - `Logical` (逻辑)
  - `Information` (信息)
  - `Engineering` (工程)
  - `Cube` (多维数据集)
  - `Web` (Web)
- `ARGHELP` mapping for parameter names (`number`, `number1`, `range`, `criteria`, `lookup_value`, `table_array`, `logical_test`, etc.).

### 3.2 Insert Function Dialog (`InsertFunctionDialog`)
- **Search Box**: `QLineEdit` with search text prompt and a `&Go` button. Typing keywords filters functions by name (highest score) and description keywords.
- **Category Dropdown**: `QComboBox` listing all categories. Changing the category filters the function list.
- **Function List**: `QListWidget` displaying sorted function names. Selecting an item updates the syntax and description labels below. Double-clicking an item immediately triggers `accept()` to open Step 2.
- **Syntax Preview**: Displays `{NAME}({arg1}, {arg2}, ...)`.
- **Description Preview**: Displays localized function summary.
- **MRU Management**: Reads MRU list from config/settings; upon confirmation, moves chosen function to top of MRU.

### 3.3 Function Arguments Dialog (`FunctionArgumentsDialog`)
- **Layout**:
  - Top header displaying the function name in bold.
  - Scrollable argument list with a row per parameter:
    - Parameter name label (bold for required, regular for optional `[arg]`).
    - Input `QLineEdit`.
    - Range pick button (icon/text to grab coordinates from sheet).
    - Per-parameter evaluated value preview `= value`.
  - Focused argument explanation box: Displays parameter name and localized help from `ARGHELP`.
  - Repeating arguments support: When `...` is present in function args and user focuses the last argument, automatically append the next argument row (`number3`, `number4`, etc.).
  - Live result preview:
    - Calls `evaluate(formula_text, ctx=EvalContext(workbook=..., current_sheet=..., current_row=..., current_col=...))`.
    - Catches any syntax or evaluation errors gracefully without crashing, displaying `= ` or error summary.
    - Bottom total label: `Formula result = {value}` (计算结果 = ...).
- **Commit Action**:
  - Constructs sanitized formula string: strips trailing empty optional parameters.
  - Injects constructed formula into active cell or active editor controller.

### 3.4 Wireup & Menu Integration
- `LedgerWindow.open_function_wizard`: Launches the wizard passing current workbook, active sheet, selection, and editor controller.
- `EditorController._on_fx_clicked`: Opens the wizard for active cell or edits existing formula function.
- `mac_menu.py`: In `menu_insert`, add `insert_function` ("插入函数(&F)...", `Shift+F3`) and wire to `open_function_wizard`.
- `ledger_toolbars.py`: Ensure "更多函数(&F)..." is wired to `open_function_wizard`.

---

## 4. Verification & Testing Strategy
- Test catalog queries, syntax formatting, and argument help resolution.
- Test category filtering and keyword search ranking.
- Test MRU persistence and ordering.
- Test Function Arguments dialog instantiation with required, optional, and repeating parameters.
- Test real-time calculation preview with various functions (SUM, AVERAGE, IF, etc.).
- Test formula construction with partial or omitted optional arguments.
- Test i18n completeness and `retranslate_ui()`.

# Implementation Plan: Issue #157 — 实现 519 函数检索与参数即时计算的“插入函数 (fx) 向导”

## Task Overview
Implement the two-step formula authoring wizard (`InsertFunctionDialog` and `FunctionArgumentsDialog`), wire it to the formula bar `fx` button, application menus, and toolbars, and verify with tests.

---

## Tasks

### Task 1: Create `function_wizard.py` Dialog Module
- **File**: `src/atboffice/modules/spreadsheet/dialogs/function_wizard.py`
- **Details**:
  - Implement `FunctionCatalogService`: categories, search filtering with scoring algorithm, MRU persistence with fallback.
  - Implement `ARGHELP` map derived from `fninfo.js` with localized explanations for common arguments.
  - Implement `InsertFunctionDialog`:
    - Search input + `&Go` button
    - Category combo box
    - Function list widget with selection and double-click handlers
    - Syntax and description display
    - `retranslate_ui()` for complete i18n
  - Implement `FunctionArgumentsDialog`:
    - Function title banner
    - Argument rows with input field, coordinate picker button, and individual evaluated value preview
    - Focused argument help panel
    - Repeating argument (`...`) auto-expansion on focus
    - Live formula evaluation using `evaluate()` and safe error handling
    - Total result preview label
    - Formula constructor stripping trailing optional empty parameters
    - `retranslate_ui()` for complete i18n
  - Implement `launch_function_wizard(...)` helper function
  - Expose in `src/atboffice/modules/spreadsheet/dialogs/__init__.py`

### Task 2: Wire Formula Bar `fx`, Menus, and Window Actions
- **Files**:
  - `src/atboffice/modules/spreadsheet/views/editor_controller.py`
  - `src/atboffice/ui/shell/ledger_window.py`
  - `src/atboffice/ui/shell/mac_menu.py`
- **Details**:
  - In `editor_controller.py`: Implement `_on_fx_clicked` to trigger the function wizard on the active cell/selection.
  - In `ledger_window.py`: Implement `open_function_wizard` to instantiate and show the wizard dialog.
  - In `mac_menu.py`: Add `insert_function` action under `menu_insert` with shortcut `Shift+F3` and connect to `open_function_wizard`.

### Task 3: Comprehensive Test Suite
- **File**: `tests/modules/spreadsheet/test_function_wizard.py`
- **Details**:
  - Test catalog queries, categories, and fuzzy search ranking.
  - Test MRU retrieval, updating, and saving.
  - Test `InsertFunctionDialog` UI initialization, category filtering, search execution, and selection.
  - Test `FunctionArgumentsDialog` UI initialization, default arguments, live calculation preview for `SUM`, `AVERAGE`, `IF`, etc.
  - Test dynamic repeating arguments expansion on focus.
  - Test coordinate picker integration.
  - Test formula assembly with omitted optional parameters.
  - Test integration with `LedgerWindow.open_function_wizard`.
  - Verify all tests pass with `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/test_function_wizard.py -v`.

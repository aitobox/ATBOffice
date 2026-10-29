# Implementation Plan: Issue #111 - 跨模块通用查找与替换系统 (Find & Replace)

## Task Breakdown

### Task 1: Core Search Architecture & Engine
- **Files to create/modify**:
  - `src/atboffice/core/search.py`: `SearchOptions`, `SearchMatch`, `SearchAdapter`, `SearchController`, `WriterSearchAdapter`, `SpreadsheetSearchAdapter`
  - `tests/core/test_search.py`: Comprehensive unit tests
- **Details**:
  - `SearchOptions`: options for case, whole word, regex, direction, scope, compilation logic.
  - `SearchMatch`: target identifier, start/end offset, matched string, metadata.
  - `SearchController`: coordinator with signals `match_found`, `no_match_found`, `replace_completed`, `status_message`.
  - `WriterSearchAdapter`: binds to `Document` and `CaretController` (or paragraph models).
  - `SpreadsheetSearchAdapter`: binds to `SheetDataModel` and `SelectionModel`.
- **Verification Command**:
  `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/core/test_search.py -v`

### Task 2: Office 2003 Luna Find & Replace Dialog
- **Files to create/modify**:
  - `src/atboffice/ui/dialogs/__init__.py`
  - `src/atboffice/ui/dialogs/find_replace_dialog.py`: `FindReplaceDialog(QDialog)`
  - `tests/ui/test_find_replace_dialog.py`: UI testing for dialog
- **Details**:
  - Tabs: "查找" (Find) & "替换" (Replace)
  - Inputs: Find what, Replace with
  - Options: Match case, Whole words only, Regular expressions, Direction Up/Down
  - Buttons: Find Next (default), Replace, Replace All, Close
  - 100% `safe_tr()` localization & `retranslate_ui()`
- **Verification Command**:
  `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/ui/test_find_replace_dialog.py -v`

### Task 3: Shell Menus & Window Integration
- **Files to create/modify**:
  - `src/atboffice/ui/shell/mac_menu.py`: add `edit_find` and `edit_replace`
  - `src/atboffice/ui/shell/quire_window.py`: wire `open_find_dialog`, `open_replace_dialog` with `WriterSearchAdapter`
  - `src/atboffice/ui/shell/ledger_window.py`: wire `open_find_dialog`, `open_replace_dialog` with `SpreadsheetSearchAdapter`
  - `src/atboffice/core/action_registry.py`: register default find/replace action specs
- **Verification Command**:
  `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/ui/ -k "menu or window" -v`

### Task 4: Full Regression Testing & Gate Check
- Run all tests across the repository.
- **Verification Command**:
  `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`

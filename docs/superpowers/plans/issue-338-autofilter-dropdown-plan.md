# Implementation Plan: Issue #338 - Implement AutoFilter Classic Interactive Column Dropdown with Checkbox Search Tree

## Proposed Changes

### 1. `src/atboffice/modules/spreadsheet/views/filter_dropdown.py`
- Rename/alias `FilterDropdownPopup` and keep `FilterDropdown = FilterDropdownPopup`.
- Add search filter `QLineEdit` with instant search:
  - Add search input right above the value list.
  - Connect `textChanged` to `_on_search_text_changed(text: str)`.
  - When filtering, hide items that do not contain `text.lower()`.
  - If text is non-empty, change select-all label to `(Select All Search Results)`.
  - When select-all is clicked during search, only toggle visible items.
- Enhance unique value extraction to sort numbers numerically and text alphabetically, exactly like Excel 2003 and `.vibeoffice/public/ledger/js/filter.js`.
- Add `retranslate_ui()` for 100% i18n support.

### 2. `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- Connect filter actions to Undo/Redo stack:
  - Push snapshot `{ "action": "filter", "af": af, "before_cols": copy.deepcopy(...), "after_cols": copy.deepcopy(...) }` onto `_undo_stack`.
  - In `undo()`, if `action == "filter"`, restore `before_cols`, reapply filter, update scrollbars and viewport.
  - In `redo()`, if `action == "filter"`, restore `after_cols`, reapply filter, update scrollbars and viewport.
- Update status bar:
  - When filter is applied or cleared, calculate visible records count `vis` and total records `total`.
  - Display `safe_tr("{0} of {1} records found").format(vis, total)`.
  - Store `self.last_status_message` for accessibility and programmatic testing.

### 3. Automated Test Suite
- Create `tests/gui/test_phase9_autofilter_interactive.py`:
  - Test 1: `test_filter_dropdown_search_instant_filtering`: verify search box filters list items in real time.
  - Test 2: `test_filter_dropdown_select_all_search_results`: verify toggling select all when searching only affects matching items.
  - Test 3: `test_filter_dropdown_numeric_vs_text_sorting`: verify numeric values sort numerically (`1, 2, 10, 25, 300, 1200`).
  - Test 4: `test_grid_viewport_filter_status_bar`: verify status bar updates with "M of N records found".
  - Test 5: `test_grid_viewport_filter_undo_redo`: verify applying filter, undoing, and redoing works without mutating cell contents.

## Verification Steps
```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_phase9_autofilter_interactive.py -v
QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_filter_and_sort.py tests/unit/spreadsheet/test_filter_and_sort_logic.py -v
```

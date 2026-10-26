# Implementation Plan: [Ledger] 自动筛选 (AutoFilter) 下拉菜单与多列排序 (Sort)

- **Issue**: #15
- **Branch**: `agent/issue-15-autofilter-and-multi-column-sort`
- **Spec**: `docs/superpowers/specs/issue-15-autofilter-and-multi-column-sort-spec.md`

## Proposed Tasks

### Task 1: AutoFilter & Multi-Column Sort Logic (Pure Logic / Model)
- **Files**:
  - `src/atboffice/modules/spreadsheet/models/filter_model.py` (new)
  - `src/atboffice/modules/spreadsheet/models/sheet_model.py` (integrate sort_range & filter methods)
  - `tests/unit/spreadsheet/test_filter_and_sort_logic.py` (new)
- **Details**:
  - Implement `excel_sort_cmp(a, b, desc=False, case_sensitive=False)`:
    - Blanks always at bottom in both asc and desc.
    - Type rank: Number (0) < String (1) < Bool (2) < Error (3) < Blank (4).
  - Implement `sort_sheet_range(model, r1, c1, r2, c2, keys, has_header=True, case_sensitive=False)`.
  - Implement `ColumnFilter` and `AutoFilter` evaluation:
    - `apply_filter(model, auto_filter)`: computes filtered rows and updates `geometry.hidden_rows`.
    - `clear_filter(model, col=None)`: clears column or entire filter.
- **Verification**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/spreadsheet/test_filter_and_sort_logic.py -v`

### Task 2: Multi-Column Sort Dialog
- **Files**:
  - `src/atboffice/modules/spreadsheet/dialogs/sort_dialog.py` (new)
  - `tests/gui/test_filter_and_sort.py` (new - Part 1: Sort dialog tests)
- **Details**:
  - PySide6 `QDialog` based on classic Excel 2003:
    - 3 Key sections: Sort by, Then by 1, Then by 2.
    - Ascending / Descending options.
    - "My data range has": Header row / No header row.
    - Options: Case sensitive checkbox.
    - Dynamic column labels (e.g. Header cell text vs "Column A").
    - Full i18n support (`retranslate_ui`, `safe_tr`).
- **Verification**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_filter_and_sort.py -k "test_sort_dialog" -v`

### Task 3: AutoFilter Dropdown & Condition Dialogs
- **Files**:
  - `src/atboffice/modules/spreadsheet/views/filter_dropdown.py` (new)
  - `tests/gui/test_filter_and_sort.py` (Part 2: Filter dropdown tests)
- **Details**:
  - `FilterDropdown`:
    - `(Sort Ascending)` & `(Sort Descending)`
    - `(All)`
    - `(Top 10...)` dialog (Top/Bottom, Items/Percent, Count spinbox)
    - `(Custom...)` dialog (2 condition rows, And/Or, equals, does not equal, greater than, less than, begins with, ends with, contains)
    - Unique values list with checkboxes and `(Select All)`, `(Blanks)`
    - Full i18n support.
- **Verification**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_filter_and_sort.py -k "test_filter_dropdown" -v`

### Task 4: Grid Viewport Integration (Drawing & Hit Testing)
- **Files**:
  - `src/atboffice/modules/spreadsheet/views/grid_viewport.py` (modify)
  - `tests/gui/test_filter_and_sort.py` (Part 3: Viewport integration tests)
- **Details**:
  - In `paintEvent` or `_paint_headers`:
    - When `model.auto_filter` is active, draw 16x16 button with beveled border and downward arrow at the bottom-right of cell `(r1, c)` for all `c` in `c1..c2`.
    - Paint arrow blue if column has active criteria, black otherwise.
  - In `hit_test` and `mousePressEvent`:
    - Detect click on the filter button of cell `(r1, c)`.
    - Popup `FilterDropdown` directly below the cell.
  - Add `toggle_auto_filter()` on `GridViewport` / `SpreadsheetView`.
- **Verification**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_filter_and_sort.py -v`

### Task 5: Full Test Suite Regression & Quality Assurance
- **Command**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/ -v`
- **Criteria**:
  - 100% test pass with zero failures or regressions.

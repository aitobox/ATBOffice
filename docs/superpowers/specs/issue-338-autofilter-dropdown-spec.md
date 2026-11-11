# Specification: Issue #338 - Implement AutoFilter Classic Interactive Column Dropdown with Checkbox Search Tree

## 1. Problem Statement & Background
In `.vibeoffice/public/ledger/js/filter.js`, clicking a column header's AutoFilter drop-down button opens an interactive Excel 2003-style popup menu containing:
1. Sort Ascending / Sort Descending actions.
2. `(All)`, `(Top 10...)`, `(Custom...)`.
3. A searchable checkbox tree/list aggregating unique values present in the column, allowing multi-select inclusion/exclusion and instant text search filtering.
4. Feedback on status bar displaying `"{0} of {1} records found"`.
5. Non-destructive Undo/Redo for filter applications without mutating cell contents.

Currently, `src/atboffice/modules/spreadsheet/views/filter_dropdown.py` is a simplified popup without live instant search filtering, alias `FilterDropdownPopup`, or proper undo/redo integration in `GridViewport`.

## 2. Requirements & Acceptance Criteria
- **FilterDropdownPopup Component**:
  - Provide both `FilterDropdownPopup` and `FilterDropdown` class names for full compatibility.
  - Add search input field (`QLineEdit`) with placeholder text `safe_tr("搜索...")` / `safe_tr("Search...")`.
  - Provide instant filtering of unique values as search text changes:
    - Case-insensitive substring matching.
    - If search is active, top item updates to `safe_tr("(Select All Search Results)")` and only affects visible matching items.
    - If search is empty, top item shows `safe_tr("(Select All)")`.
  - Separate numerical values from text values during aggregation:
    - Numbers sorted numerically (`2 < 10`).
    - Strings sorted alphabetically.
    - Blanks aggregated as `safe_tr("(Blanks)")`.
- **GridViewport & FilterModel Integration**:
  - Apply filter without display lag.
  - Update status bar with formatted text: `safe_tr("{0} of {1} records found").format(vis, total)`.
  - Support Undo and Redo in `GridViewport`:
    - Stores `{ "action": "filter", "before_cols": ..., "after_cols": ... }` in `_undo_stack`.
    - Restores previous filter state and updates hidden rows in geometry without altering any cell contents.
- **i18n & Architecture**:
  - 100% of UI strings wrapped in `safe_tr()`.
  - Provide `retranslate_ui()`.
- **Automated Verification**:
  - Dedicated GUI test suite in `tests/gui/test_phase9_autofilter_interactive.py`.
  - All existing filter tests pass cleanly.

## 3. Architecture & Interfaces

### 3.1 `FilterDropdownPopup` (in `filter_dropdown.py`)
```python
class FilterDropdownPopup(QWidget):
    filter_applied = Signal(object)  # ColumnFilter
    filter_cleared = Signal()
    sort_requested = Signal(bool)    # desc

    def __init__(self, model: SheetDataModel, af: AutoFilter, col: int, parent: QWidget | None = None): ...
    def _on_search_text_changed(self, text: str) -> None: ...
    def _extract_unique_values(self) -> tuple[list[str], bool]: ...
    def retranslate_ui(self) -> None: ...
```

### 3.2 `GridViewport` Undo/Redo Integration
```python
# In grid_viewport.py on_applied / on_cleared:
self._commit_filter_undo(af, before_cols, after_cols)

# In grid_viewport.py undo():
if action == "filter":
    # restore cols and apply_auto_filter
    ...
```

## 4. Verification Plan
```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_phase9_autofilter_interactive.py -v
```

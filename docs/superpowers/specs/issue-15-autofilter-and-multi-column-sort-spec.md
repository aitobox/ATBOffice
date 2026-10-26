# Specification: [Ledger] 自动筛选 (AutoFilter) 下拉菜单与多列排序 (Sort)

- **Issue**: #15
- **Branch**: `agent/issue-15-autofilter-and-multi-column-sort`
- **Module**: `src/atboffice/modules/spreadsheet/`
- **Reference**: `.vibeoffice/public/ledger/js/filter.js`, `.vibeoffice/public/ledger/js/dialogs2.js`, `.vibeoffice/public/ledger/js/ops.js`

---

## 1. Overview & Architecture

This specification covers the implementation of the Excel 2003 classic AutoFilter and Multi-Column Sort subsystems in Python 3.12+ / PySide6 for ATBOffice Ledger.

### 1.1 Core Components

1. **AutoFilter Engine & State (`src/atboffice/modules/spreadsheet/models/filter_model.py` / integrated with `SheetDataModel`)**:
   - Data structure `AutoFilter`:
     - `ref`: `tuple[int, int, int, int]` representing `(r1, c1, r2, c2)`.
     - `columns`: `dict[int, ColumnFilter]` storing criteria per column offset `col_idx = col - c1`.
     - `filtered_rows`: `set[int]` tracks rows that are hidden specifically by the filter (distinguishing them from manually hidden rows).
   - Evaluator:
     - Supports value list matching (`values: set[str]`), blank matching, non-blank matching, top 10 (items/percent, top/bottom), custom conditions (`op: equal, notEqual, greaterThan, lessThan, begins, ends, contains` with AND/OR logic).
   - Applying filter:
     - Updates `sheet.geometry.hidden_rows` and triggers viewport repaint.

2. **AutoFilter Dropdown UI (`src/atboffice/modules/spreadsheet/views/filter_dropdown.py`)**:
   - Classic Excel 2003 drop-down menu widget:
     - `(Sort Ascending)` & `(Sort Descending)`
     - `(All)`: Reset column filter
     - `(Top 10...)`: Filter top/bottom N items or %
     - `(Custom...)`: Custom filter dialog with 2 condition rows and And/Or logic
     - Unique values list with checkable items or single-click selection, including `(Blanks)` and `(NonBlanks)`.
   - Keyboard navigation (Esc to close, Arrow keys, Enter to commit).

3. **Multi-Column Sort Engine & Dialog (`src/atboffice/modules/spreadsheet/dialogs/sort_dialog.py`)**:
   - Multi-key sorting function:
     - Range: `(r1, c1, r2, c2)`
     - Keys: up to 3 keys `[(col_idx, desc: bool)]`
     - Options: `has_header: bool`, `case_sensitive: bool`, `by_cols: bool` (top-to-bottom default vs left-to-right).
     - Excel sorting semantics: Numbers < Text < Booleans < Errors < Blanks. Blanks are always placed at the bottom regardless of ascending/descending.
     - Preserves cell data, formulas, styles, and row heights across sorted rows.
   - Qt Dialog `SortDialog`:
     - Group 1: "Sort by" (Primary Key combo + Ascending/Descending radios)
     - Group 2: "Then by" (Secondary Key combo with `(none)` + Ascending/Descending radios)
     - Group 3: "Then by" (Third Key combo with `(none)` + Ascending/Descending radios)
     - "My data range has": Header row vs No header row radios (dynamically updates combo labels from cell text in row `r1` or "Column A", "Column B")
     - Full i18n support with `retranslate_ui()`.

4. **Grid Viewport Integration (`src/atboffice/modules/spreadsheet/views/grid_viewport.py`)**:
   - AutoFilter Button Rendering:
     - If `model.auto_filter` is active, for each column `c` in `c1..c2` on header row `r1`:
       - Paints a 16x16 classic beveled button at the bottom-right of cell `(r1, c)`.
       - Paints a downward triangle (arrow) inside the button: blue if column has active filter, black if inactive.
   - Hit Testing:
     - Detects clicks within the filter button rect.
     - Spawns `FilterDropdown` without triggering cell selection or editor activation.

---

## 2. Interface Contracts

### 2.1 `AutoFilter` & `ColumnFilter` Data Classes
```python
@dataclass
class ColumnFilter:
    values: set[str] | None = None
    blank: bool = False
    custom_list: list[tuple[str, str]] | None = None  # [(op, val), ...]
    custom_and: bool = True
    top10_top: bool | None = None
    top10_percent: bool = False
    top10_val: int = 10

@dataclass
class AutoFilter:
    r1: int
    c1: int
    r2: int
    c2: int
    cols: dict[int, ColumnFilter] = field(default_factory=dict)
    filtered_rows: set[int] = field(default_factory=set)
```

### 2.2 Sheet Model Integration
- `sheet_model.auto_filter: AutoFilter | None`
- `sheet_model.apply_filter()`: computes visible rows and updates `geometry.hidden_rows`.
- `sheet_model.clear_filter()`: restores filtered rows in `geometry.hidden_rows`.
- `sheet_model.sort_range(r1, c1, r2, c2, keys, has_header=True, case_sensitive=False)`: executes multi-column sort.

### 2.3 `FilterDropdown`
```python
class FilterDropdown(QMenu):
    filter_applied = Signal(int, object)  # col_idx, ColumnFilter or None
    sort_requested = Signal(int, bool)    # col, desc
```

### 2.4 `SortDialog`
```python
class SortDialog(QDialog):
    def get_sort_keys(self) -> list[tuple[int, bool]]: ...
    def has_header(self) -> bool: ...
```

---

## 3. Edge Cases & Robustness

1. **Empty Selection / No Contiguous Region**:
   - Detects bounded region around cursor using `current_region`. If empty, shows polite warning.
2. **Hidden Rows Interaction**:
   - Tracks `filtered_rows` separately so unfiltering does not unhide rows that were explicitly hidden by the user.
3. **Data Type Ordering in Sort**:
   - Strict Excel order: Numbers < Text < Booleans < Errors < Blanks. Blanks stay at bottom in both sort directions.
4. **i18n & Translations**:
   - Complete localized strings for all dialogs, buttons, tooltips, and sort options in English and Chinese.

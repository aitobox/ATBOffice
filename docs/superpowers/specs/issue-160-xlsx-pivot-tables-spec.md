# Design Specification: XLSX Pivot Table Cache Preservation & Static Summary Wizard (Issue #160)

## 1. Overview & Objective
This specification defines the architecture, data models, OPC part preservation engine, calculation engine, and Qt GUI wizard for Pivot Tables in ATBOffice Ledger, porting and extending `.vibeoffice/public/ledger/js/pivots.js` and `.vibeoffice/public/ledger/js/dialogs2.js`.

The implementation addresses two key requirements:
1. **Low-level OPC / XLSX Pivot Cache Preservation (`pivot_model.py`)**:
   - Parses existing `xl/pivotCaches/pivotCacheDefinition*.xml`, `xl/pivotTables/pivotTable*.xml`, and their records.
   - Preserves 100% byte-for-byte fidelity when parts are unmodified.
   - Tracks mutations (cell edits in source ranges, row/col line insertions/deletions, sheet deletions).
   - Dynamically updates XML attributes (e.g. `refreshOnLoad="1"`, shifted `ref`) or drops orphaned caches when source data is removed.
2. **High-Level Wizard & Static Cross-Tabulation Calculation Engine (`pivot_dialog.py` & `pivot_model.py`)**:
   - Implements `PivotTableWizardDialog` replicating Word/Excel 2003 classical dialog.
   - Automatically detects headers, data ranges, numeric columns, and suggested aggregation functions.
   - Configures Row field, Column field (optional), Data field, Aggregation type (`sum`, `count`, `average`, `max`, `min`, `countNums`), Page field (optional), and Target location (New Sheet or Active Sheet).
   - Renders a formatted cross-tabulation table with styled headers, subtotals, grand totals, and column auto-fitting.

---

## 2. Architecture & Components

```
┌─────────────────────────────────────────────────────────────┐
│                      LedgerWindow UI                        │
│  - mac_menu action: data_pivottable                         │
│  - Toolbar / ribbon action: pivotTable                      │
└──────────────────────────────┬──────────────────────────────┘
                               │ opens
                               ▼
┌─────────────────────────────────────────────────────────────┐
│         PivotTableWizardDialog (pivot_dialog.py)            │
│  - Source range validation & auto-detection                 │
│  - Field pickers (Row, Column, Data, Page/Filter)           │
│  - Function picker (Sum, Count, Average, Max, Min, etc.)    │
│  - Location selector (New worksheet / Existing cell)        │
└──────────────────────────────┬──────────────────────────────┘
                               │ executes
                               ▼
┌─────────────────────────────────────────────────────────────┐
│          Pivot Calculation Engine (pivot_model.py)          │
│  - build_pivot_table(workbook, source_range, config)        │
│  - Key grouping (rk \u0001 ck)                              │
│  - Statistical aggregations (SUM, COUNT, AVERAGE, etc.)     │
│  - Cell generation & styling in target SheetDataModel       │
└─────────────────────────────────────────────────────────────┘
                               ▲
                               │
┌──────────────────────────────┴──────────────────────────────┐
│           Pivot OOXML Model & OPC Preservation Engine       │
│  - PivotCacheDefinition & PivotTableDefinition dataclasses   │
│  - read_pivots(workbook, zip_file / source_pkg)             │
│  - write_pivots(workbook, pkg_writer)                       │
│  - Cell mutation watcher & line insertion/deletion tracking │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Data Models (`src/atboffice/modules/spreadsheet/models/pivot_model.py`)

### 3.1 Data Structures
- `PivotCacheSource`:
  - `kind`: `"worksheet"` | `"consolidation"` | `"external"` | `"unknown"`
  - `sheet_name`: Original worksheet name
  - `ref`: Cell range tuple `(r1, c1, r2, c2)`
  - `original_ref`: Raw string e.g. `"A1:D20"`
- `PivotCache`:
  - `cache_id`: `int`
  - `part_name`: e.g. `"xl/pivotCaches/pivotCacheDefinition1.xml"`
  - `sources`: `list[PivotCacheSource]`
  - `fields`: `list[str]`
  - `refresh`: `bool` (triggers `refreshOnLoad="1"`)
  - `drop`: `str | None`
  - `raw_bytes`: `bytes | None` (cached for byte-for-byte carry)
- `PivotTable`:
  - `part_name`: e.g. `"xl/pivotTables/pivotTable1.xml"`
  - `name`: e.g. `"PivotTable1"`
  - `sheet_name`: Worksheet containing table
  - `cache_id`: `int`
  - `location_ref`: `(r1, c1, r2, c2)`
  - `offsets`: `dict[str, int]` (`firstHeaderRow`, `firstDataRow`, `firstDataCol`)
  - `used_fields`: `list[int]`
  - `raw_bytes`: `bytes | None`
  - `drop`: `str | None`

### 3.2 Workbook Integration
- `WorkbookModel` stores pivot metadata on `wb.extra["pivots"] = PivotContainer(caches=[...], tables=[...])`.
- On cell value edit in `SheetDataModel.set_cell(...)`:
  - Checks if cell `(r, c)` falls within any `cache.source` range. If so, sets `cache.refresh = True`.
- On sheet removal or row/column line insertion/deletion:
  - Shifter adjusts table location refs and source ranges, or marks `drop` if completely deleted.

---

## 4. Calculation Engine (`build_pivot_table`)

```python
@dataclass
class PivotConfig:
    source_sheet: str
    source_range: tuple[int, int, int, int]  # (r1, c1, r2, c2)
    row_field_col: int
    col_field_col: int | None
    data_field_col: int
    agg_func: str  # "sum", "count", "average", "max", "min", "countNums"
    page_field_col: int | None = None
    page_filter_val: str | None = None
    target_sheet: str = "new"  # "new" or existing sheet name
    target_cell: tuple[int, int] = (0, 0)
```

### Aggregations:
- `sum`: $\sum x$ for all numeric values.
- `count`: count of non-empty cells.
- `countNums`: count of numeric cells.
- `average`: sum / countNums (or `#DIV/0!` if 0).
- `max`: max of numeric values.
- `min`: min of numeric values.

### Formatting & Layout:
- Row header & column header labels: bold, grey fill (`#C0C0C0`), borders.
- Subtotals & Grand totals: bold, lighter fill (`#E3E3E3`), top border.
- Result cells written directly to destination worksheet.

---

## 5. UI: `PivotTableWizardDialog` (`pivot_dialog.py`)

- Window Title: `safe_tr("数据透视表和数据透视图向导")` / `"PivotTable and PivotChart Wizard"`
- Geometry: Fixed 460x420, modal dialog with macOS Fusion style.
- Input Controls:
  - **Range**: `QLineEdit` with current selection or auto-detected continuous region (e.g. `'Sheet1'!$A$1:$D$20`).
  - **Layout Group**:
    - Row field (`QComboBox` populated with source column headers).
    - Column field (`QComboBox` with `(无)` / `(none)` as first item).
    - Data field (`QComboBox`) + Summarize by (`QComboBox`: 求和, 计数, 平均值, 最大值, 最小值, 数值计数).
    - Page field (`QComboBox` with `(none)`).
  - **Location Group**:
    - Radio button: `新工作表(&N)` (default).
    - Radio button: `现有工作表 (位于当前活动单元格)(&E)`.
  - **Buttons**:
    - `完成(&F)` (primary default button).
    - `取消(&C)`.
- 100% i18n support with `retranslate_ui()` and `safe_tr()`.

---

## 6. Verification Plan
- Unit tests in `tests/modules/spreadsheet/test_pivot_tables.py`:
  1. `test_pivot_cache_ooxml_preservation`: Verify reading an XLSX with pivotTable and pivotCache definitions preserves bytes untouched on unmodified write.
  2. `test_pivot_cache_refresh_on_edit`: Verify editing a source cell sets `refreshOnLoad="1"` on save.
  3. `test_pivot_calculation_sum_count_avg`: Test mathematical cross-tabulation accuracy for single row, row+col, and grand totals.
  4. `test_pivot_dialog_ui`: Test `PivotTableWizardDialog` instantiation, field population, selection change, and execution.
  5. `test_ledger_window_action`: Test invocation from `ledger_window` action registry.

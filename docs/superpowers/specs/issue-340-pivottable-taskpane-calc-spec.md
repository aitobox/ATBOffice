# Design Specification: Interactive PivotTable Field List Task Pane & Multi-Dimensional Calculation Engine (Issue #340)

## 1. Overview & Objective
This specification defines the architecture, data models, multi-dimensional calculation engine, interactive drag-and-drop task pane, and `GridViewport` dynamic rendering and context menu for PivotTables in ATBOffice Ledger (Issue #340 / Phase 9 Step 7 of 12).

Building on the existing OPC preservation layer (`src/atboffice/modules/spreadsheet/models/pivot_model.py`) and wizard dialog (`src/atboffice/modules/spreadsheet/dialogs/pivot_dialog.py`), this feature delivers:
1. **Multi-dimensional pivot calculation engine (`src/atboffice/modules/spreadsheet/calc/pivots.py`)**:
   - Multi-field `filters`, `columns`, `rows`, and `values` dimensions.
   - Supported aggregations: `sum`, `count`, `average`, `max`, `min`, `product`, `countNums`.
   - Automatic nested subtotals for multi-level rows, column totals, and grand totals.
   - Cell-level layout metadata (`PivotLayoutMeta`) tracking filter rows, header rows, banded data rows, subtotal rows, grand total rows/columns, and interactive filter dropdown coordinates.
   - Non-destructive refresh (`refresh_pivot_report`) clearing prior stale output cells before re-rendering.
2. **Interactive `PivotFieldsTaskPane` (`src/atboffice/modules/spreadsheet/panes/pivot_fields_pane.py`)**:
   - Top section: Available source fields list with checkboxes (smart routing numeric fields to Values and text/category fields to Rows when checked, removing from all zones when unchecked) and drag support.
   - Bottom section: 2x2 grid of 4 drop areas — **Filters (报表筛选)**, **Columns (列标签)**, **Rows (行标签)**, **Values (数值)** — supporting drag-and-drop between zones and from the field list, reordering, value aggregation picker (`SUM`, `COUNT`, `AVERAGE`, `MAX`, `MIN`, `PRODUCT`, `COUNTNUMS`), filter value selection, and Defer Layout Update toggle.
   - Full `safe_tr()` i18n support and `retranslate_ui()`.
3. **`GridViewport` Dynamic Rendering & Context Menu (`src/atboffice/modules/spreadsheet/views/grid_viewport.py`)**:
   - Dynamic visual rendering for pivot regions: header shading, alternating banded data rows, bold subtotal rows with subtle divider fills/borders, grand total footer/column styling with double bottom borders, and interactive filter dropdown arrow buttons on filter/header cells.
   - PivotTable-aware cell context menu with **"刷新数据(&R)" (Refresh Data)**, **"显示字段列表(&L)" (Show Field List)**, and **"数据透视表向导(&W)…"**.
4. **Shell & Wizard Integration**:
   - `SheetDataModel.pivot_reports` stores active `PivotReport` instances per worksheet.
   - `build_pivot_table()` in `pivot_model.py` registers a `PivotReport` on the target sheet while preserving 100% backward compatibility with existing single-axis/two-axis cell layout assertions.
   - `LedgerWindow` registers `PivotFieldsTaskPane` in `TaskPaneDock` (`"pivot_fields"`), syncs active pivot selection, and opens the field list upon wizard completion or context menu activation.

---

## 2. Autonomous Design Decisions (>= 90% Confidence)
- **Compatibility with `pivot_model.build_pivot_table`**: Keep `build_pivot_table()`'s existing cell placement for 1-row / 1-col / 1-value configs so existing tests (`tests/modules/spreadsheet/test_pivot_tables.py`) continue passing unchanged, while delegating aggregation/metadata and attaching a `PivotReport` to `dst_sheet.pivot_reports`.
- **Single-source-of-truth Layout Spec**: Store `PivotLayoutSpec` inside `PivotReport` on `SheetDataModel.pivot_reports` so `PivotFieldsTaskPane`, `GridViewport`, and `LedgerWindow` share live state without duplicating config dicts.
- **Drag-and-Drop MIME Format**: Use custom MIME type `"application/x-atb-pivot-field"` with JSON payload (`col_idx`, `name`, `source_zone`, `source_index`, `agg_func`) so drag-and-drop works seamlessly in both live GUI events (`QDrag`/`dropEvent`) and headless tests (`QMimeData` / `QDropEvent`).
- **Context Menu & Dropdown Hit Testing**: Add `pivot_table_at(r, c)` on `GridViewport` mirroring `table_at(r, c)`, and extend `_paint_pane` and `hit_test` / `mousePressEvent` to handle PivotTable dropdown buttons without interfering with standard AutoFilter buttons.

---

## 3. Architecture & Data Flow

```
Source SheetDataModel (cells in source_range)
        │
        ▼
PivotCalculationEngine (calc/pivots.py)
  ├─ PivotFieldSpec (filters, columns, rows)
  ├─ PivotValueSpec (values + agg_func: sum/count/average/max/min/product/countNums)
  ├─ PivotLayoutMeta (filter_rows, header_rows, data_rows, subtotal_rows, grand_total_rows/cols, dropdown_cells)
  └─ PivotReport (bound to target SheetDataModel.pivot_reports)
        ▲                                      │
        │ layout_changed / refresh             ▼
PivotFieldsTaskPane                    GridViewport
  ├─ Checkable Field List                ├─ Dynamic paint (headers, banded rows, subtotals, grand totals, dropdown arrows)
  ├─ 4 Drop Zones (Filters/Cols/Rows/Vals)├─ Hit test & filter dropdown popup
  └─ Aggregation Settings & Defer Update └─ Context Menu: Refresh Data, Show Field List, Wizard
```

---

## 4. Edge Cases & Error Handling
1. **Empty or header-only source range**: Produces empty table headers gracefully without raising `IndexError` or `ZeroDivisionError`.
2. **AVERAGE with non-numeric / empty cells**: When a group has matching records with zero numeric entries, emits `"#DIV/0!"`. When `(row_key, col_key)` intersection has zero records, cell remains `None`.
3. **PRODUCT aggregation**: Multiplies all numeric values (ignoring booleans and non-numeric strings); returns `0` when records exist with no numbers.
4. **Shrinking pivot output on filter/drag**: `render_pivot_report` explicitly clears `sheet.cells` inside the previous `report.bbox` (and prior filter rows) before writing the new cells so stale values/borders never persist.
5. **Missing source sheet / deleted source columns**: `refresh_pivot_report` safely returns `False` and reports status message instead of crashing.
6. **Stale selection outside pivot**: Clicking outside any `PivotReport` clears/idles the bound pane gracefully without disrupting active cell editing.
7. **Full i18n**: All UI controls, labels, buttons, context menu actions, and dialogs use `safe_tr()` with `retranslate_ui()`.

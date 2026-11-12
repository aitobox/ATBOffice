# Implementation Plan: Interactive PivotTable Field List & Dynamic Aggregation Engine (Issue #340)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task following strict TDD.

**Goal:** Implement a multi-dimensional PivotTable calculation engine (`calc/pivots.py`), an interactive drag-and-drop `PivotFieldsTaskPane` (`panes/pivot_fields_pane.py`), dynamic rendering and "Refresh Data" context menu in `GridViewport` (`views/grid_viewport.py`), and full shell integration in `LedgerWindow` with comprehensive GUI tests (`tests/gui/test_phase9_pivot_table_interactive.py`).

**Architecture:** `PivotLayoutSpec` and `PivotReport` models live in `calc/pivots.py` and attach to `SheetDataModel.pivot_reports`. `PivotCalculationEngine` computes multi-axis aggregations (SUM, COUNT, AVERAGE, MAX, MIN, PRODUCT, COUNTNUMS) with subtotals and grand totals and records cell roles in `PivotLayoutMeta`. `PivotFieldsTaskPane` provides a checkable/draggable field list and 4 drop zones (Filters, Columns, Rows, Values) emitting live updates. `GridViewport` renders dynamic headers, banded rows, subtotals, grand totals, and filter dropdown indicators, and adds PivotTable context menu actions.

---

### Task 1: Multi-Dimensional Pivot Calculation Engine & SheetModel Support

**Files:**
- Modify: `src/atboffice/modules/spreadsheet/models/sheet_model.py` (add `self.pivot_reports: list[Any] = []`)
- Modify: `src/atboffice/modules/spreadsheet/models/pivot_model.py` (add `"product"` to `_aggregate_values` & `AGG_FUNC_LABELS`, register `PivotReport` in `build_pivot_table`)
- Create: `src/atboffice/modules/spreadsheet/calc/pivots.py`
- Create: `tests/gui/test_phase9_pivot_table_interactive.py` (initial engine tests)

**Steps:**
1. Write failing tests in `tests/gui/test_phase9_pivot_table_interactive.py` covering `aggregate_values` (SUM, COUNT, AVERAGE, MAX, MIN, PRODUCT, COUNTNUMS, `#DIV/0!`), multi-level rows with subtotals, multi-level columns, multiple value fields, report filtering, and `refresh_pivot_report` clearing stale rows when source data changes.
2. Run `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_phase9_pivot_table_interactive.py -v` and confirm failures.
3. Implement `SheetDataModel.pivot_reports` and `src/atboffice/modules/spreadsheet/calc/pivots.py`.
4. Update `pivot_model.py` to support `"product"` and register `PivotReport` in `build_pivot_table` without breaking existing test coordinates.
5. Re-run tests and `tests/modules/spreadsheet/test_pivot_tables.py` to verify pass.

---

### Task 2: `PivotFieldsTaskPane` with 4 Drag-and-Drop Zones & Checkbox Toggling

**Files:**
- Create: `src/atboffice/modules/spreadsheet/panes/pivot_fields_pane.py`
- Modify: `src/atboffice/modules/spreadsheet/panes/__init__.py`
- Modify: `tests/gui/test_phase9_pivot_table_interactive.py`

**Steps:**
1. Add failing tests for `PivotFieldsTaskPane`:
   - Top field list displays source headers with checkboxes.
   - Checking a numeric field routes it to `Values` (with `sum`); checking a text field routes it to `Rows`; unchecking removes it from all zones.
   - Dragging/dropping MIME `"application/x-atb-pivot-field"` between `zone_filters`, `zone_columns`, `zone_rows`, and `zone_values` updates layout and triggers live recalculation.
   - Changing value aggregation (`SUM`, `COUNT`, `AVERAGE`, `MAX`, `MIN`, `PRODUCT`) updates bound pivot report immediately.
   - Defer layout update checkbox suppresses automatic recalculation until `Update` button is clicked.
   - `retranslate_ui()` executes cleanly.
2. Run pytest and confirm failure.
3. Implement `PivotFieldsTaskPane` (with `PivotFieldListWidget`, `PivotDropZoneWidget`, `ValueFieldSettingsDialog`, and `safe_tr()`).
4. Re-run pytest and verify pass.

---

### Task 3: `GridViewport` Dynamic Pivot Rendering, Filter Dropdowns & Context Menu

**Files:**
- Modify: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- Modify: `src/atboffice/modules/spreadsheet/view.py` (attach `self.grid.workbook = self._workbook`)
- Modify: `tests/gui/test_phase9_pivot_table_interactive.py`

**Steps:**
1. Add failing GUI tests for `GridViewport`:
   - `pivot_table_at(r, c)` detects cells inside a `PivotReport` and returns `None` outside.
   - `_build_cell_menu(r, c)` inside a pivot table includes `"刷新数据(&R)"` and `"显示字段列表(&L)"`; outside does not.
   - `refresh_pivot_table()` recalculates values after source cell modification and updates `last_status_message`.
   - Painting a `GridViewport` containing a `PivotReport` with headers, banded rows, subtotals, grand totals, and filter dropdowns renders cleanly with `grab()`.
   - Clicking a pivot filter dropdown cell triggers interactive filter selection and recalculates the pivot table.
2. Run pytest and confirm failure.
3. Implement `pivot_table_at`, `refresh_pivot_table`, `show_pivot_field_list`, dynamic pivot visual rendering in `_paint_pane`, dropdown hit testing & popup menu in `GridViewport`, and context menu entries in `_build_cell_menu`.
4. Re-run pytest and verify pass.

---

### Task 4: `LedgerWindow` & `PivotTableWizardDialog` Integration & Full Regression Verification

**Files:**
- Modify: `src/atboffice/ui/shell/ledger_window.py`
- Modify: `src/atboffice/modules/spreadsheet/dialogs/pivot_dialog.py`
- Modify: `tests/gui/test_phase9_pivot_table_interactive.py`

**Steps:**
1. Add failing integration tests for `LedgerWindow` (`pivot_fields` task pane registration, `open_pivot_fields_pane`, layout updates reflected on sheet, `retranslate_ui()`).
2. Wire `PivotFieldsTaskPane` into `LedgerWindow._setup_ledger_task_panes()`, selection sync, wizard completion, and `retranslate_ui()`.
3. Run:
   - `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_phase9_pivot_table_interactive.py -v`
   - `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/test_pivot_tables.py -v`
   - Full spreadsheet & regression tests.

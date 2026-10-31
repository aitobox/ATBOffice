# Implementation Plan: XLSX Pivot Table Cache Preservation & Static Summary Wizard (Issue #160)

## Proposed Changes

### 1. `src/atboffice/modules/spreadsheet/models/pivot_model.py`
- Create `PivotCacheSource`, `PivotCache`, `PivotTable`, `PivotContainer`, `PivotConfig`.
- Implement `parse_pivots_from_zip(zf, workbook) -> PivotContainer`.
- Implement `write_pivots_to_package(pkg_writer, workbook, container)`.
- Implement `build_pivot_table(workbook, config: PivotConfig) -> SheetDataModel`.
  - Implements grouping by row/column keys, aggregates (`sum`, `count`, `average`, `max`, `min`, `countNums`).
  - Writes formatted headers, row labels, cross-tabulated cells, row totals, column totals, grand total.

### 2. Integration in `xlsx_reader.py` & `xlsx_writer.py`
- In `read_xlsx`: call `parse_pivots_from_zip(z, wb)` and attach `wb.extra["pivots"] = container`.
- In `write_xlsx`: if `wb.extra.get("pivots")`, call `write_pivots_to_package(pkg_writer, workbook, wb.extra["pivots"])`.

### 3. `src/atboffice/modules/spreadsheet/dialogs/pivot_dialog.py`
- Create `PivotTableWizardDialog(QDialog)`:
  - Validates source range (minimum 2 rows with column headers).
  - ComboBoxes for Row field, Column field, Data field + Aggregation type, Page field.
  - Radio buttons for destination (New sheet / Existing sheet).
  - Fully translated UI strings via `safe_tr()`, `retranslate_ui()`.
  - On accept, calls `build_pivot_table` and activates target worksheet.

### 4. Integration in `src/atboffice/ui/shell/ledger_window.py`
- Register `open_pivot_wizard` on `action_registry`:
  - `self.action_registry.set_handler("data_pivottable", self.open_pivot_wizard)`
  - `self.action_registry.set_handler("pivotTable", self.open_pivot_wizard)`
- Implement `open_pivot_wizard(self) -> None`:
  - Determines default range from current selection or data bounds.
  - Launches `PivotTableWizardDialog`.

### 5. Test Suite `tests/modules/spreadsheet/test_pivot_tables.py`
- Tests:
  - `test_pivot_config_and_calculation`: unit testing calculation engine on sample dataset.
  - `test_pivot_ooxml_roundtrip_lossless`: tests zip read and write preservation.
  - `test_pivot_source_edit_triggers_refresh`: tests cell mutation marking `refreshOnLoad`.
  - `test_pivot_dialog_lifecycle`: tests GUI dialog initialization, combo selection, and submission.
  - `test_ledger_window_pivot_action`: tests action handler invocation.

---

## Verification Commands
```bash
PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/test_pivot_tables.py -v
PYTHONPATH=src conda run -n ATBOffice pytest tests/
```

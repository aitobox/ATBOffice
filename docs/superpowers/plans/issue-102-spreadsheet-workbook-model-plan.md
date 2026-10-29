# Implementation Plan - Issue #102: 电子表格 WorkbookModel 多工作表容器架构重构

## User Review Required

> [!NOTE]
> Autonomous decision rule applied (confidence >= 90%). Plan follows strict TDD (Test-Driven Development) and adheres to the specifications in `docs/superpowers/specs/issue-102-spreadsheet-workbook-model-spec.md`.

---

## Proposed Changes

### 1. `src/atboffice/modules/spreadsheet/models/sheet_model.py`
- Enhance `SheetDataModel.__init__` to accept `name: str = "Sheet1"`.
- Provide property/getter/setter for `name`.

### 2. `src/atboffice/modules/spreadsheet/models/workbook_model.py`
- Create `WorkbookModel(QObject)` with:
  - Signals: `sheet_added(int, str)`, `sheet_removed(int, str)`, `sheet_renamed(int, str, str)`, `sheet_moved(int, int)`, `active_sheet_changed(int)`.
  - Properties: `sheets -> list[SheetDataModel]`, `active_sheet_index -> int`, `active_sheet -> SheetDataModel`.
  - Methods: `add_sheet`, `remove_sheet`, `rename_sheet`, `move_sheet`, `get_sheet_by_name`, `sheet_index`, `set_active_sheet_index`, `set_active_sheet`.
  - Excel-compliant sheet name validation (`validate_sheet_name` and duplicate checks).
  - Update `src/atboffice/modules/spreadsheet/models/__init__.py` to export `WorkbookModel`.

### 3. `tests/modules/spreadsheet/test_workbook_model.py`
- Unit tests for:
  - Default workbook initialization.
  - Adding sheets (with auto naming and explicit naming).
  - Sheet name validation (illegal chars, length > 31, duplicates, case-insensitive).
  - Removing sheets (first, middle, last, preventing removing last remaining sheet, active index adjustment).
  - Renaming sheets (valid, duplicate, no-op).
  - Moving sheets (reordering, active index invariant).
  - Signal emissions for all mutation events.

### 4. `src/atboffice/modules/spreadsheet/view.py`
- Update `SpreadsheetView` to support `workbook: WorkbookModel | None`.
- Expose `view.workbook` and property `view.model` (pointing to `self.workbook.active_sheet`).
- Implement per-sheet selection isolation (`self._sheet_selections: dict[SheetDataModel, SelectionModel]`).
- Implement `set_active_sheet_index(index: int)` with automatic grid viewport and editor controller synchronization.

### 5. `tests/gui/test_spreadsheet_view_workbook.py`
- GUI tests verifying:
  - `SpreadsheetView` with default and custom `WorkbookModel`.
  - Switching active sheet updates `grid.model`.
  - Selection states in Sheet 1 are isolated from Sheet 2.
  - Backward compatibility with legacy `model` argument.

---

## Verification Plan

### Automated Tests
```bash
# 1. Unit tests for WorkbookModel:
PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/test_workbook_model.py -v

# 2. GUI integration tests for SpreadsheetView:
PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_spreadsheet_view_workbook.py -v

# 3. Full spreadsheet regression test suite:
PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/spreadsheet/ tests/gui/ -v
```

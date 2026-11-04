# Implementation Plan: TASK-707 (Issue #241) 修复真实工作簿载入后的显示与同步

## Task 1: XLSX Reader Comments, Freeze Panes, and Zoom Parsing
- **Files**: `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`
- **Actions**:
  1. Add `_parse_worksheet_comments(zip_file: zipfile.ZipFile, sheet_path: str, sheet: SheetDataModel) -> None`:
     - Inspect `sheet_path`'s `_rels` file for relationship type `http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments` or ending in `/comments`.
     - Read and parse XML: extract `<author>` elements and `<comment>` nodes with `ref`, `authorId`, and `<text>`.
     - If `vmlDrawing` relationship exists, read VML text and check for `<x:Visible>` to set `visible=True`.
     - Call `sheet.set_comment(r, c, text, author=author, visible=visible)`.
  2. In `_parse_worksheet`:
     - Scan `<sheetViews><sheetView>` for `<pane>`:
       - If `state in ("frozen", "frozenSplit")`, parse `xSplit` into `sheet.freeze_cols` and `ySplit` into `sheet.freeze_rows`.
       - If `zoomScale` attribute exists, parse into `sheet.extra["zoom"] = int(zoomScale)`.
     - Invoke `_parse_worksheet_comments(zip_file, sheet_path, sheet)`.
- **Verification**: Run unit check on `tests/docs/excel/xlsx/poi__SimpleWithComments.xlsx` ensuring 3 comments are parsed.

## Task 2: GridViewport Zoom and Undo Isolation
- **Files**: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- **Actions**:
  1. Add `clear_undo_stack()` to empty `_undo_stack`, `_redo_stack`, and reset `_internal_clipboard = None`.
  2. In `set_model_and_selection(model, selection)`:
     - Clear undo/redo stacks.
     - If `model.extra.get("zoom")` exists, apply `self.set_zoom(model.extra["zoom"] / 100.0)`.
  3. Add `zoom` property and `set_zoom(zoom: float) -> None`:
     - Bound zoom between `0.1` and `4.0`.
     - Repaint viewport and update scrollbars.
- **Verification**: Unit tests on zoom setter and undo stack clearing.

## Task 3: SpreadsheetView Unified Workbook Binding & Signal Isolation
- **Files**: `src/atboffice/modules/spreadsheet/view.py`
- **Actions**:
  1. In `workbook.setter`:
     - Disconnect old workbook signals safely with `try...except`.
     - Call `self.grid.clear_undo_stack()`.
     - Reset `_sheet_selections.clear()`.
     - Call `self.sheet_tab_bar.set_workbook(value)`.
     - Connect new workbook signals and trigger `self._on_active_sheet_changed(self._workbook.active_sheet_index)`.
  2. In `_on_active_sheet_changed`:
     - Ensure `grid.set_model_and_selection`, `editor_controller.set_model_and_selection`, and `object_layer.set_model` all reference `active_sheet`.
- **Verification**: Test binding workbook A then workbook B, checking object identity and signal detachment.

## Task 4: EditorController Formula Recalculation & Error Contract
- **Files**: `src/atboffice/modules/spreadsheet/views/editor_controller.py`
- **Actions**:
  1. In `commit()`:
     - If text starts with `=`, construct `EvalContext(workbook=wb, current_sheet=self.model.name, sheet=self.model)`.
     - Parse and evaluate AST. If evaluation returns `ExcelError`, assign string representation (e.g. `#NAME?`).
     - If parsing or evaluation raises an unhandled exception, assign `cell.value = "#VALUE!"`, never leave blank or old value.
- **Verification**: Test editing formula to unknown function and syntax error; assert `cell.value` is error string.

## Task 5: Comprehensive GUI Regression Test Suite
- **Files**: `tests/gui/test_phase7_xlsx_render.py` (New)
- **Actions**:
  1. Test 5 corpus samples loading (`cell-value`, `SimpleWithComments`, `GroupTest`, `conditional_fmt_origin`, `Pivot2_Row`).
  2. Test consecutive workbook replacement and undo/zoom isolation.
  3. Test formula recalculation and error contracts.
  4. Test offscreen GUI paint event and grab.
- **Verification**: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_xlsx_render.py -ra` exits 0.

## Task 6: Feature Tracking & Documentation
- **Files**: `docs/clone/phase7_features.csv`, `docs/tasks/07_phase7_fidelity_stability_compatibility_plan.md`
- **Actions**:
  1. Update `phase7_features.csv` for Virtualized Grid Viewport and Rendering to `verified` with test evidence.
  2. Update `07_phase7_fidelity_stability_compatibility_plan.md` marking TASK-707 as completed `[x]`.

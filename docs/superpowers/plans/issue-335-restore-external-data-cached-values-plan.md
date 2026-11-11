# Implementation Plan: Issue #335 - Restore External Data Cached Values Fallback Rendering

## Task 1: Extend CellData and SheetDataModel
- Target: `src/atboffice/modules/spreadsheet/models/sheet_model.py`
- Steps:
  1. Add `cached_value: Any = None` to `CellData`.
  2. Update `CellData.clone()` to copy `cached_value`.
  3. In `SheetDataModel.get_formatted_text(r, c)`: resolve effective value considering `cached_value` when `cell.value` is None, empty, or an error string (`#NAME?`, etc.).
  4. In `SheetDataModel.get_effective_alignment()`: ensure effective alignment resolves based on effective display value.

## Task 2: Preserve Cached Values in XLSX Reader
- Target: `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`
- Steps:
  1. In `_parse_worksheet()`: when a cell has a formula `f` and a value `v`, store `cached_value=parsed_value` on `CellData`.
  2. For external link formulas or cells with cached values, ensure `cell.value` is initialized with `parsed_value` and `cached_value=parsed_value`.

## Task 3: Fix DrawingML OneCellAnchor and AbsoluteAnchor Parsing
- Target: `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`
- Steps:
  1. In `_parse_worksheet_drawings()`:
     - Check `tag == "oneCellAnchor"`: set `anchor_type = AnchorType.ONE_CELL`.
     - Check `tag == "absoluteAnchor"`: set `anchor_type = AnchorType.ABSOLUTE`.
     - Read `<xdr:ext cx="..." cy="..."/>`: calculate `abs_w = max(4, int(cx) // 9525)` and `abs_h = max(4, int(cy) // 9525)`.
     - Set `abs_rect = (0, 0, abs_w, abs_h)` (or `(x, y, abs_w, abs_h)` for absoluteAnchor).
     - Pass `abs_rect` to all `FloatingObject(...)` constructors.

## Task 4: Support 3D Chart Variants in Chart Parsing
- Target: `src/atboffice/modules/presentation/chart/io.py`
- Steps:
  1. In `parse_chart_xml()`: check `tag_name in ("barChart", "bar3DChart")` to properly detect horizontal `bar` or vertical `col` charts based on `barDir`.
  2. Support `line3DChart`, `pie3DChart`, `area3DChart` equivalents.

## Task 5: Viewport Fallback Rendering
- Target: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- Steps:
  1. In `GridViewport.paintEvent` cell text rendering:
     - Check if `cell.value is None or cell.value == ""` or error string. If `cell.cached_value is not None`, render using `cell.cached_value`.
     - Do not skip painting when `cell.cached_value` is non-empty.

## Task 6: Formula Engine DAG Safe Fallback
- Target: `src/atboffice/modules/spreadsheet/calc/dag.py`
- Steps:
  1. When formula recalculation encounters unresolved external workbook references or evaluates to `#NAME?` / `#REF!`, check if `cell.cached_value is not None`.
  2. If `cached_value` is present, retain `cached_value` as the display value rather than clobbering with `#NAME?`.

## Task 7: Comprehensive Regression Testing
- Target: `tests/gui/test_phase9_external_data_cached_values.py`
- Steps:
  1. Write tests verifying:
     - `CellData` cached value storage and fallback formatting.
     - `openxml-sdk__NoExtDataB1.xlsx` loading, chart anchor placement, and cell cache retention.
     - Formula evaluation with external workbook links retaining cached values.
  2. Run full diff tool `scripts/run_office_diff.py --file tests/docs/excel/xlsx/openxml-sdk__NoExtDataB1.xlsx` to verify visual similarity >= 90%.

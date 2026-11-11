# Specification: Issue #335 - Restore External Data Cached Values Fallback Rendering for Complex XLSX Workbooks

## 1. Problem Statement & Background
In `docs/clone/OFFICE_DOCS_DIFF.md`, `openxml-sdk__NoExtDataB1.xlsx` was flagged as a `CRITICAL_MISMATCH` with only 68.8% visual canvas similarity.
Analysis reveals two coupled root causes:
1. **Formula Engine & Cache Retention**: When workbooks contain formulas referencing external workbooks, disconnected databases, or complex expressions with pre-calculated OpenXML `<v>` tags, ATBOffice's formula engine evaluated unknown external names as `#NAME?` or cleared them, ignoring the pre-computed cached values serialized within the `<v>` tags inside `<c>` elements in OpenXML SpreadsheetML.
   - In `.vibeoffice/public/ledger/js/xlsx-read.js`, cached `<v>` values are safely retained and displayed when formulas cannot be recalculated without external sources.
2. **OneCellAnchor & 3D Chart Parsing**: In `openxml-sdk__NoExtDataB1.xlsx`, `<xdr:oneCellAnchor>` anchors a `<c:bar3DChart>`. In `xlsx_reader.py`, `oneCellAnchor` was misidentified as `twoCellAnchor` because `editAs` was absent, setting `to_point` to (0,0) and placing the chart at (0,0) across cells A1:B6. Additionally, `bar3DChart` was not matched in `parse_chart_xml()`, falling back to `col` instead of `bar`.

## 2. Requirements & Acceptance Criteria
- [x] In `src/atboffice/modules/spreadsheet/models/sheet_model.py`, extend `CellData` with `cached_value: Any = None`. Update `clone()` and `get_formatted_text()` to prioritize `cached_value` when cell value is None or an error resulting from external dependencies.
- [x] In `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`, preserve pre-computed `<v>` values on `CellData.cached_value` and do not wipe them.
- [x] In `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`, correctly parse `<xdr:oneCellAnchor>` and `<xdr:absoluteAnchor>`, reading dimensions from `<xdr:ext>` (converting EMUs to pixels via EMU = 9525), setting `AnchorType.ONE_CELL` / `AnchorType.ABSOLUTE` and `abs_rect=(0, 0, w, h)`.
- [x] In `src/atboffice/modules/presentation/chart/io.py`, support `bar3DChart` (and related 3D chart tags) to recognize horizontal bar charts properly.
- [x] In `src/atboffice/modules/spreadsheet/views/grid_viewport.py`, prioritize displaying `cached_value` when formula engine reports external linkage errors or cell value is an error `#NAME?`.
- [x] In `src/atboffice/modules/spreadsheet/calc/dag.py`, ensure external workbook references or unresolvable formula names do not overwrite a cell with `#NAME?` if `cached_value` is present.
- [x] Elevate `openxml-sdk__NoExtDataB1.xlsx` similarity to >= 90.0%.
- [x] Add regression test in `tests/gui/test_phase9_external_data_cached_values.py`.

## 3. Architecture & Interface Contracts

### 3.1 CellData Model Extension
```python
@dataclass
class CellData:
    value: Any = None
    formula: str | None = None
    cached_value: Any = None  # Pre-computed cached value from OpenXML <v>
    ...
```

### 3.2 Display Fallback Priority
When rendering cell text via `SheetDataModel.get_formatted_text(r, c)` or `GridViewport`:
```python
val = cell.value
if (val is None or val == "" or (isinstance(val, str) and val.startswith("#"))) and cell.cached_value is not None:
    val = cell.cached_value
```

### 3.3 DrawingML OneCellAnchor Parsing
In `_parse_worksheet_drawings`:
```python
if tag == "oneCellAnchor":
    anchor_type = AnchorType.ONE_CELL
    ext_el = _find_child(anchor_el, "ext")
    abs_w = max(4, int(_attr(ext_el, "cx", "0")) // 9525) if ext_el is not None else 120
    abs_h = max(4, int(_attr(ext_el, "cy", "0")) // 9525) if ext_el is not None else 80
    abs_rect = (0, 0, abs_w, abs_h)
```

## 4. Verification & Testing Strategy
- Unit & GUI tests in `tests/gui/test_phase9_external_data_cached_values.py`:
  - Verify `CellData.cached_value` storage and fallback display.
  - Verify external formula reference evaluation retains cached values.
  - Verify `oneCellAnchor` chart placement and dimensions.
- Full visual diff execution via `scripts/run_office_diff.py --file tests/docs/excel/xlsx/openxml-sdk__NoExtDataB1.xlsx` confirming >= 90% visual similarity.
- Existing unit test suite passes with zero regressions.

# Implementation Plan: Issue #284 — feat(ledger): 对齐 .vibeoffice 实现冻结窗格多视口联动与基础图表绘制 (Step 3 of 4)

## Proposed Changes

### 1. `src/atboffice/modules/spreadsheet/views/object_layer.py`
- Add `chart_data: dict[str, Any] | None = None` field to `FloatingObject`.
- Update `to_dict()`, `from_dict()`, and `clone()` to preserve `chart_data`.
- In `SpreadsheetObjectLayer._draw_object(painter, obj, rect)`:
  - When `obj.kind == "chart"`:
    - Load `ChartData` from `obj.chart_data` (or fallback to `ChartData.create_sample()`).
    - Use `ChartPainter.paint_chart(painter, chart_data, QRectF(rect))` to draw the chart vectorially.
- In `object_to_rect(obj, geometry, scroll_x, scroll_y, ...)`:
  - Account for freeze panes if the geometry or model has `freeze_rows` / `freeze_cols`.

### 2. `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`
- In `_parse_worksheet_drawings`:
  - Inspect child `<xdr:graphicFrame>` elements in anchors.
  - Parse `<a:graphicData>` URI `http://schemas.openxmlformats.org/drawingml/2006/chart`.
  - Extract `<c:chart r:id="...">` and look up target in `drw_rels`.
  - Read XML from `zip_file`, parse into `ChartData` using `parse_chart_xml`.
  - Create `FloatingObject(kind="chart", chart_data=chart.to_dict(), ...)` and add to `sheet.drawings`.

### 3. `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- **Pane Coordinate Geometry**:
  - Implement `_pane_offset(r, c, scroll_x, scroll_y)`:
    - X offset: if `c < freeze_cols`, X is fixed (`0`); else `scroll_x`.
    - Y offset: if `r < freeze_rows`, Y is fixed (`0`); else `scroll_y`.
- **`cell_rect(r, c)`**:
  - Return exact viewport rect according to whether `r < freeze_rows` and `c < freeze_cols`.
- **`hit_test(x, y)`**:
  - Support multi-pane hit testing in headers (fixed columns/rows vs scrollable).
  - Support multi-pane hit testing in cells (corner, top, left, main).
- **`reveal(r, c)`**:
  - If `r < freeze_rows`, do not scroll vertically.
  - If `r >= freeze_rows`, maintain scrolling within `[fz_h, vh]`.
  - If `c < freeze_cols`, do not scroll horizontally.
  - If `c >= freeze_cols`, maintain scrolling within `[fz_w, vw]`.
- **Painting (`_render_paint_event` & `_paint_headers`)**:
  - Render frozen headers pinned and free headers scrolling.
  - Render gridlines and cells for frozen rows/cols and free rows/cols with proper clipping to avoid bleeding.
  - Render freeze divider lines at pane boundaries (`x = row_header_width + fz_w`, `y = col_header_height + fz_h`).

### 4. Tests: `tests/modules/spreadsheet/test_freeze_panes_and_charts.py`
- Test `FloatingObject` chart_data serialization and painting.
- Test `xlsx_reader` graphicFrame chart parsing.
- Test `GridViewport` freeze panes:
  - Cell rect calculation in frozen and scrolling panes.
  - Hit testing in frozen and scrolling panes.
  - Scroll reveal behavior.
  - Editor positioning in frozen panes.

---

## Verification Plan
1. `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/test_freeze_panes_and_charts.py -v`
2. `PYTHONPATH=src conda run -n ATBOffice pytest tests/ -k "ledger or spreadsheet" -v`

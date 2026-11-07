# Specification: Issue #284 — feat(ledger): 对齐 .vibeoffice 实现冻结窗格多视口联动与基础图表绘制 (Step 3 of 4)

## 1. Overview & Problem Statement

In ATBOffice spreadsheet module (Ledger), two key fidelity and rendering issues exist when loading and interacting with business spreadsheets:
1. **Frozen Panes Multi-Viewport Linking**: While `freeze_rows` and `freeze_cols` attributes exist on `SheetDataModel` and `GridViewport`, the viewport rendering pipeline in `grid_viewport.py` only rendered a static dividing line and scrolled all cells globally. As a result, frozen rows/columns scrolled off-screen when users navigated large sheets.
2. **DrawingML Chart Parsing & Vector Rendering**: In `SpreadsheetObjectLayer` (`src/atboffice/modules/spreadsheet/views/object_layer.py`), floating chart objects are rendered as simple text placeholders (`[Chart: <name>]`), and `xlsx_reader.py` did not parse `<xdr:graphicFrame>` elements pointing to `<c:chartSpace>` XML parts.

This specification designs:
1. Complete multi-pane geometry mapping (corner, top, left, main panes) matching `.vibeoffice` (`render.js` / `grid.js`), with pinned scrolling, independent clipping, coordinate translation, hit testing, selection overlays, cell editing cursor alignment, and high-visibility freeze dividers.
2. DrawingML chart relationship extraction in `xlsx_reader.py` (`<xdr:graphicFrame>`), data linking to `ChartData`, and vector rendering in `SpreadsheetObjectLayer` via `ChartPainter` (reusing the existing DrawingML chart subsystem from `presentation.chart`).

---

## 2. Architecture & Design

### 2.1 Multi-Viewport Pane Model for Freeze Panes

When `freeze_rows > 0` or `freeze_cols > 0`, the grid canvas is partitioned into up to 4 distinct viewports/panes, exactly aligned with `.vibeoffice`:

- **Corner Pane** (if `freeze_rows > 0` and `freeze_cols > 0`):
  - Row range: `[0, freeze_rows)`
  - Column range: `[0, freeze_cols)`
  - Bounds: `(x0, y0, fz_w, fz_h)`
  - Behavior: Static pinned, immune to both horizontal and vertical scrolling.
- **Top Pane** (if `freeze_rows > 0`):
  - Row range: `[0, freeze_rows)`
  - Column range: `[start_col, end_col]` (from `scroll_x`)
  - Bounds: `(x0 + fz_w, y0, vw - x0 - fz_w, fz_h)`
  - Behavior: Pinned vertically, scrolls horizontally with `scroll_x`.
- **Left Pane** (if `freeze_cols > 0`):
  - Row range: `[start_row, end_row]` (from `scroll_y`)
  - Column range: `[0, freeze_cols)`
  - Bounds: `(x0, y0 + fz_h, fz_w, vh - y0 - fz_h)`
  - Behavior: Pinned horizontally, scrolls vertically with `scroll_y`.
- **Main Scrollable Pane**:
  - Row range: `[start_row, end_row]` (from `scroll_y`)
  - Column range: `[start_col, end_col]` (from `scroll_x`)
  - Bounds: `(x0 + fz_w, y0 + fz_h, vw - x0 - fz_w, vh - y0 - fz_h)`
  - Behavior: Free data area, scrolls horizontally and vertically.

#### Coordinate Translation (`cell_rect(r, c)`)
For any cell `(r, c)`:
- If `c < freeze_cols`: `x = x0 + geometry_mapper.col_pos(c)`
- Else: `x = x0 + geometry_mapper.col_pos(c) - scroll_x`
- If `r < freeze_rows`: `y = y0 + geometry_mapper.row_pos(r)`
- Else: `y = y0 + geometry_mapper.row_pos(r) - scroll_y`

#### Hit Testing (`hit_test(x, y)`)
- If in header areas:
  - In column header:
    - If `freeze_cols > 0` and `x < x0 + fz_w`: `col = geometry_mapper.find_col_at(x - x0)`
    - Else: `col = geometry_mapper.find_col_at(scroll_x + (x - x0))`
  - In row header:
    - If `freeze_rows > 0` and `y < y0 + fz_h`: `row = geometry_mapper.find_row_at(y - y0)`
    - Else: `row = geometry_mapper.find_row_at(scroll_y + (y - y0))`
- In cell grid area:
  - Check pane by `(x, y)`:
    - If `freeze_cols > 0` and `x < x0 + fz_w`: `col = geometry_mapper.find_col_at(x - x0)`
    - Else: `col = geometry_mapper.find_col_at(scroll_x + (x - x0))`
    - If `freeze_rows > 0` and `y < y0 + fz_h`: `row = geometry_mapper.find_row_at(y - y0)`
    - Else: `row = geometry_mapper.find_row_at(scroll_y + (y - y0))`

#### Rendering Isolation & Clipping
During `_render_paint_event`:
1. Calculate panes and clip rects.
2. Render cells, gridlines, and selection overlays per-pane or with unified pane mapping so cells outside their valid pane region do not bleed across freeze boundaries.
3. Draw freeze divider lines:
   - If `freeze_rows > 0`: Draw a distinct divider line (`#969696`, 2px or 1px solid) at `y = y0 + fz_h`.
   - If `freeze_cols > 0`: Draw a distinct divider line (`#969696`, 2px or 1px solid) at `x = x0 + fz_w`.

#### Editor & Keyboard Navigation
- When navigating with keyboard (arrow keys, Tab, Enter, PageUp/PageDown) or clicking a cell, `reveal(r, c)` ensures the cell is visible:
  - If `r < freeze_rows`, Y is already pinned; no vertical scroll change needed.
  - If `r >= freeze_rows`, scrolling only adjusts if `cell_top < scroll_y + fz_h` or `cell_bottom > scroll_y + vh`.
  - Same logic for columns with `freeze_cols` and `fz_w`.
- `cell_rect(r, c)` accurately returns the on-screen geometry so `editor_controller` places the editing line-edit or formula editor directly over the active cell.

---

### 2.2 DrawingML Chart Parsing & Vector Rendering

1. **Model Extension**:
   - In `FloatingObject`: Add `chart_data: dict[str, Any] | None = None` and support it in `to_dict()` / `from_dict()`.
2. **XLSX Reader Support (`xlsx_reader.py`)**:
   - In `_parse_worksheet_drawings`: Add handling for `<xdr:graphicFrame>` elements.
   - Extract `<c:chart r:id="...">` from `<a:graphicData>`.
   - Resolve `r:id` via `drw_rels` to the target chart XML part (e.g., `xl/charts/chart1.xml`).
   - Parse XML using `parse_chart_xml` from `atboffice.modules.presentation.chart.io`.
   - Create a `FloatingObject(kind="chart", name=..., chart_data=chart.to_dict(), ...)` and append to `sheet.drawings`.
3. **Chart Vector Painting (`SpreadsheetObjectLayer._draw_object`)**:
   - In `SpreadsheetObjectLayer._draw_object(painter, obj, rect)`:
     When `obj.kind == "chart"`:
     - If `obj.chart_data` is present:
       Instantiate `ChartData.from_dict(obj.chart_data)`.
     - Else:
       Fallback to `ChartData.create_sample()`.
     - Invoke `ChartPainter.paint_chart(painter, chart_data, QRectF(rect))`.
     - Render selection bounding box and handles cleanly when selected.

---

## 3. Files Affected
- `src/atboffice/modules/spreadsheet/views/grid_viewport.py` (Multi-pane freeze support, hit testing, coordinate calculation, headers, reveal)
- `src/atboffice/modules/spreadsheet/views/object_layer.py` (`FloatingObject.chart_data` and vector `ChartPainter` rendering)
- `src/atboffice/modules/spreadsheet/io/xlsx_reader.py` (`graphicFrame` chart parsing in drawings)
- `tests/modules/spreadsheet/test_freeze_panes_and_charts.py` (New comprehensive unit tests)

---

## 4. Acceptance Criteria
- [x] Frozen rows remain pinned at the top while scrollable data rows scroll smoothly vertically.
- [x] Frozen columns remain pinned at the left while scrollable data columns scroll smoothly horizontally.
- [x] Clear freeze divider lines are rendered at pane boundaries.
- [x] Hit testing and cell selection correctly identify cells in frozen and free panes.
- [x] Cell editor is positioned accurately over active cells in frozen and free panes.
- [x] OOXML `<xdr:graphicFrame>` chart definitions are parsed into `FloatingObject` with `chart_data`.
- [x] Basic charts (column, bar, line) are drawn via `ChartPainter` as vector graphics rather than placeholders.
- [x] All automated unit tests pass without regressions.

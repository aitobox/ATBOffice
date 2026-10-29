# Implementation Plan: Spreadsheet Grid Floating Object Layer & DrawingML Sync (Issue #110)

## Proposed Architecture and Steps

### Step 1: Write Tests (TDD First)
- Create `tests/modules/spreadsheet/test_object_layer.py`.
- Define comprehensive tests:
  - `test_floating_object_model_and_anchors`: Unit test `CellAnchorPoint`, `FloatingObject`, copy/clone, dictionary serialization, and bounding box computation with `SheetGeometry`.
  - `test_spreadsheet_object_layer_hit_test_and_handles`: Test `SpreadsheetObjectLayer` handle hit testing (NW, N, NE, E, SE, S, SW, W, BODY) and cursor updating.
  - `test_spreadsheet_object_layer_z_order_and_clipboard`: Test `bring_to_front`, `send_to_back`, `bring_forward`, `send_backward`, copy, paste, delete.
  - `test_object_layer_coordinate_sync_with_scrolling`: Test that `object_to_rect` dynamically adjusts when scroll offsets and column/row dimensions change.
  - `test_drawingml_xlsx_writer_and_reader_roundtrip`: Test creating a workbook with a floating rectangle, textbox, and image, writing to XLSX bytes via `write_xlsx`, and reading back via `read_xlsx` to verify that `sheet.drawings` are fully preserved with identical anchors and properties.

### Step 2: Implement FloatingObject and Data Models
- In `src/atboffice/modules/spreadsheet/views/object_layer.py`:
  - Implement `CellAnchorPoint`, `AnchorType`, `HandleType`, and `FloatingObject`.
  - Implement `object_to_rect(obj, geometry, scroll_x, scroll_y, row_hdr_w, col_hdr_h)` and `rect_to_anchor(...)`.
- In `src/atboffice/modules/spreadsheet/models/sheet_model.py`:
  - Add `self.drawings: list[FloatingObject] = []` to `SheetDataModel.__init__`.

### Step 3: Implement SpreadsheetObjectLayer Component
- In `src/atboffice/modules/spreadsheet/views/object_layer.py`:
  - Implement `SpreadsheetObjectLayer(QWidget)`:
    - Double-buffered QPainter rendering for shapes (`rect`, `roundRect`, `oval`, `arrow`, `line`, `textbox`, `image`, `chart`).
    - Selection outline with 8 control handles.
    - Hit-testing (`hit_test(x, y)`).
    - Mouse drag interactions: resizing from any of the 8 handles, body translation.
    - Keyboard delete (`Delete` / `Backspace`).
    - Context menu with `safe_tr()` / `retranslate_ui()`.
    - Passthrough of unhandled mouse events (`mousePressEvent`, `mouseReleaseEvent`, `mouseDoubleClickEvent`) to underlying `GridViewport` when no object is hit.

### Step 4: Integrate Object Layer with SpreadsheetView & GridViewport
- In `src/atboffice/modules/spreadsheet/view.py`:
  - Instantiate `SpreadsheetObjectLayer` over `self.grid.viewport()`.
  - Hook scrollbar signals (`horizontalScrollBar().valueChanged`, `verticalScrollBar().valueChanged`) and grid resize to update the object layer.
  - Hook active sheet changed to switch object layer model and refresh.

### Step 5: Implement DrawingML Read/Write Sync in `xlsx_reader.py` & `xlsx_writer.py`
- In `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`:
  - Add `_read_sheet_drawings(z, sheet_file, sheet_model)`.
  - Parse `xl/drawings/drawing{N}.xml` using namespaces `xdr` and `a`.
  - Extract `<xdr:twoCellAnchor>` and `<xdr:oneCellAnchor>`.
  - Parse shapes, textboxes, images (loading image bytes from `xl/media/...` via relationships).
  - Populate `sheet_model.drawings`.
- In `src/atboffice/modules/spreadsheet/io/xlsx_writer.py`:
  - In `write_xlsx`, check if any sheet has `drawings`.
  - If so, generate `xl/drawings/drawing{i}.xml`.
  - Serialize `<xdr:twoCellAnchor editAs="twoCell">` for each drawing.
  - If image drawings exist, write image payloads to `xl/media/` and generate `xl/drawings/_rels/drawing{i}.xml.rels`.
  - Add drawing relationship to `xl/worksheets/_rels/sheet{i}.xml.rels`.
  - Add `<drawing r:id="..."/>` to worksheet XML.
  - Add drawing and image overrides in `[Content_Types].xml`.

### Step 6: Verification & Quality Assurance
- Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/test_object_layer.py -v`.
- Run all spreadsheet tests `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/ -v`.
- Run full test suite `PYTHONPATH=src conda run -n ATBOffice pytest tests/`.
- Ensure 100% test pass.

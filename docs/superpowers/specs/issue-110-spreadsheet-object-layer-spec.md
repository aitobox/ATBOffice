# Design Specification: Spreadsheet Grid Floating Object Layer (SpreadsheetObjectLayer) & DrawingML Sync (Issue #110)

## 1. Overview
In Office spreadsheets (Excel / LibreOffice Calc / ATBOffice Ledger), worksheets can contain floating graphic objects placed above the cell grid: auto-shapes (rectangles, ovals, arrows, lines), text boxes, embedded images, and charts. These objects are anchored to cells (`twoCellAnchor`, `oneCellAnchor`, or `absoluteAnchor`), maintaining their relative positions as columns and rows are resized or as the grid scrolls.

This specification implements:
1. **`FloatingObject` Model & `SheetDataModel.drawings` Integration**:
   - Represents floating graphics (`rect`, `roundRect`, `oval`, `arrow`, `line`, `textbox`, `image`, `chart`).
   - Supports two-cell anchoring (`from_col`, `from_row`, `from_col_off`, `to_col`, `to_row`, `to_col_off`) and absolute bounding box fallback.
   - Supports styling: fill color/alpha, line color/width, text content, image data.
   - Integrated into `SheetDataModel.drawings`.
2. **`SpreadsheetObjectLayer` Overlay Component**:
   - PySide6 `QWidget` overlay sitting directly above `GridViewport.viewport()`.
   - Synchronizes geometry with grid scrolling (`scroll_x`, `scroll_y`) and custom column/row sizing.
   - Hit-testing, multi-directional 8-point resize handles (`NW, N, NE, E, SE, S, SW, W`) and body drag translation.
   - Z-ordering (`bring_to_front`, `send_to_back`, `bring_forward`, `send_backward`).
   - Clipboard operations (`copy`, `paste`, `delete`).
   - Transparent pass-through for unhandled mouse events so grid cell selection and editing remain responsive.
   - Complete i18n support with `safe_tr()` and `retranslate_ui()`.
3. **DrawingML (`xl/drawings/drawingN.xml`) Read/Write Sync**:
   - `xlsx_reader.py`: Reads worksheet drawing relationships, parses `<xdr:wsDr>` anchors (`<xdr:twoCellAnchor>`, `<xdr:oneCellAnchor>`), extracts shapes (`<xdr:sp>`), text (`<xdr:txBody>`), and pictures (`<xdr:pic>`) with embedded media.
   - `xlsx_writer.py`: Serializes sheet floating objects into valid DrawingML `<xdr:wsDr>`, registers worksheet drawing relationship and content type override, and stores embedded media.

---

## 2. Technical Architecture & Data Models

### 2.1 FloatingObject & CellAnchorPoint (`src/atboffice/modules/spreadsheet/views/object_layer.py`)
```python
@dataclass
class CellAnchorPoint:
    col: int = 0
    col_off: int = 0   # pixel offset from cell left
    row: int = 0
    row_off: int = 0   # pixel offset from cell top

class AnchorType(Enum):
    TWO_CELL = "twoCell"
    ONE_CELL = "oneCell"
    ABSOLUTE = "absolute"

@dataclass
class FloatingObject:
    id: int = 1
    name: str = "Shape 1"
    kind: str = "rect"  # "rect", "roundRect", "oval", "arrow", "line", "textbox", "image", "chart"
    anchor_type: AnchorType = AnchorType.TWO_CELL
    from_point: CellAnchorPoint = field(default_factory=CellAnchorPoint)
    to_point: CellAnchorPoint = field(default_factory=CellAnchorPoint)
    abs_rect: tuple[int, int, int, int] = (0, 0, 100, 60) # (x, y, w, h) in pixels
    fill_color: str = "#4F81BD"
    fill_alpha: float = 1.0
    line_color: str = "#385D8A"
    line_width: float = 1.0
    text: str = ""
    text_color: str = "#000000"
    font_size: int = 11
    font_family: str = "Calibri"
    image_data: bytes | None = None
    image_mime: str = "image/png"
    z_index: int = 0
```

### 2.2 Coordinate Mapping & Viewport Synchronization
- Pixel coordinate of cell `(r, c)` relative to sheet origin `(0, 0)`:
  - `x = geometry_mapper.col_pos(c) + col_off`
  - `y = geometry_mapper.row_pos(r) + row_off`
- Widget viewport coordinate:
  - `vx = row_header_width + x - scroll_x`
  - `vy = col_header_height + y - scroll_y`
- When moving or resizing:
  - Calculate new `(vx, vy, vw, vh)` -> convert to sheet coordinates `(x, y)` -> find `from_col = find_col_at(x)`, `from_row = find_row_at(y)`, `col_off = x - col_pos(from_col)`, `row_off = y - row_pos(from_row)`.
  - Same calculation for `to_point`.

### 2.3 SpreadsheetObjectLayer UI Operations
- **Handles**: 8 bounding resize handles (NW, N, NE, E, SE, S, SW, W) drawn when object is selected.
- **Hit Test Priority**:
  1. Selected object resize handles.
  2. Floating object bodies in descending Z-index order.
  3. None (transparent area) -> Mouse events are forwarded or ignored so the underlying `GridViewport` can process cell clicks/drags.
- **Context Menu**:
  - Cut, Copy, Paste, Delete, Bring to Front, Send to Back, Bring Forward, Send Backward. All localized via `safe_tr()`.

### 2.4 DrawingML Serialization & Parsing (`xlsx_reader.py` / `xlsx_writer.py`)
- **Reading**:
  - Detect `xl/worksheets/_rels/sheet{N}.xml.rels` relationship of type `http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing`.
  - Resolve path to `xl/drawings/drawing{N}.xml`.
  - Parse `<xdr:twoCellAnchor>` / `<xdr:oneCellAnchor>`.
  - Parse `from` & `to` coordinates (`col`, `colOff`, `row`, `rowOff`). Note: in OOXML, `colOff` and `rowOff` are in EMUs (1 px = 9525 EMUs at standard 96 DPI).
  - Parse `<xdr:sp>` (shapes and textboxes) and `<xdr:pic>` (images).
  - Store results in `sheet.drawings`.
- **Writing**:
  - For each sheet with `sheet.drawings`, generate `xl/drawings/drawing{N}.xml` using namespaces `xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"` and `xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"`.
  - Write two-cell anchors, `cNvPr`, `spPr`, `prstGeom`, `solidFill`, `ln`, `txBody`.
  - For pictures, write image binary to `xl/media/image{M}.png`, generate `xl/drawings/_rels/drawing{N}.xml.rels`, and link `r:embed`.
  - Reference `<drawing r:id="..."/>` in `sheet{N}.xml`.
  - Add content type override in `[Content_Types].xml`.

---

## 3. Acceptance Criteria & Test Plan
- [x] `FloatingObject` model with two-cell anchoring, styling, geometry, and image storage.
- [x] `SpreadsheetObjectLayer` widget overlay supporting hit-testing, selection, 8-way resize handles, dragging, and Z-order manipulation.
- [x] Passthrough of unhandled mouse events to `GridViewport` for seamless grid operations.
- [x] DrawingML reader & writer supporting round-trip save/load of shapes, textboxes, and pictures.
- [x] Unit test suite in `tests/modules/spreadsheet/test_object_layer.py`.

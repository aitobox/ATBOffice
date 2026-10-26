# Specification: Issue #28 [Quire] 复杂表格排版与单元格跨行跨列合并 (gridSpan & vMerge)

## 1. Overview & Context

### 1.1 Background
In ATBOffice Quire (Word 2003 port), tables represent a foundational document layout primitive alongside paragraphs. Table structures in OOXML / Word 2003 support dynamic column grids, cell spanning (`gridSpan`), vertical cell merging (`vMerge` restart/continue), independent multi-paragraph rich text per cell, border and shading styling, vertical cell alignment, row height constraints, and multi-page pagination with repeated header rows.

This specification defines the complete implementation of:
1. `src/atboffice/modules/writer/models/table.py`: Table data model operations, grid mapping, row/column insertion & deletion, cell merging and splitting with OOXML `gridSpan` and `vMerge` conformance, and integrity cleanup.
2. `src/atboffice/modules/writer/layout/table_layout.py`: High-fidelity table layout engine calculating column widths, cell content layout, row height resolution with `vMerge` spanning, vertical alignment, and cross-page table splitting with repeated header rows (`tblHeader`).
3. Integration with `src/atboffice/modules/writer/layout/pagination.py`: Multi-page flowing of `Table` blocks across column frames and physical pages.
4. Rendering and mouse interactive resizing in `src/atboffice/modules/writer/views/canvas_view.py`: Table background shading, border rendering, hover hit-testing for column/row dividers with split cursors, and mouse drag resizing with visual guide lines.

Reference implementation: `.vibeoffice/public/quire/js/tables.js`, `.vibeoffice/public/quire/js/render.js` (`R.tblMap`), and `.vibeoffice/public/quire/js/layout.js` (`placeTable`).

---

## 2. Requirements & Acceptance Criteria

### 2.1 Model & Grid Mapping (`models/table.py`)
- **Grid Mapping (`table_map`)**:
  - Build a 2D mapping representing each physical cell on the table grid.
  - Calculate `span` (`grid_span`), starting column index `c0`, `rowspan` for vertical merges, and flag `is_hidden` for `v_merge == 'continue'`.
  - Handle rogue `vMerge` states gracefully (unmatched `continue` promoted to `restart` or cleared; trailing `restart` without `continue` cleaned).
- **Row & Column Manipulation**:
  - `insert_rows(table, row_idx, count, above)`: Inserts new rows; maintains `vMerge` continuation when inserting within an active vertical merge.
  - `delete_rows(table, r0, r1)`: Deletes rows; promotes continuing vertical merges in subsequent rows to restart.
  - `insert_cols(table, col_idx, count, left)`: Inserts grid columns; expands `gridSpan` for cells crossing the insertion index.
  - `delete_cols(table, c0, c1)`: Adjusts grid widths; decreases spans or removes cells contained within deleted columns.
- **Merge & Split Operations**:
  - `merge_cells(table, r0, r1, c0, c1)`: Grows rectangle to enclose any partially overlapping merged cells. Concatenates paragraph contents into top-left cell. Sets `grid_span = c1 - c0 + 1`, top cell `v_merge = 'restart'`, below cells `v_merge = 'continue'`. Removes intermediate cells in rows.
  - `split_cells(table, cell, num_rows, num_cols)`: Splits cell into `num_rows` rows and `num_cols` columns. Re-grids table columns if necessary and divides paragraphs among new cells.
- **Factory**:
  - `create_simple_table(rows, cols, width, col_widths)`: Generates a ready-to-use table with default paragraphs in each cell.

### 2.2 Table Layout & Multi-Page Splitting (`layout/table_layout.py`)
- **Geometry & Width Resolution**:
  - Resolve table grid widths against container width (handling `pct`, `dxa`, and `auto`).
  - Compute each cell's inner content width: `cell_width - cell_mar.left - cell_mar.right`.
  - Lay out independent paragraphs inside each cell using `layout_paragraph`.
- **Row Height & Vertical Alignment**:
  - Calculate row height based on cell contents, respecting `RowProperties.h` with rules:
    - `auto`: Height is at least the maximum cell content height in the row.
    - `atLeast`: Height is `max(h, max_content_height)`.
    - `exact`: Fixed height `h` regardless of content height.
  - Handle multi-row spans (`rowspan > 1`): distribute height across spanned rows if content height exceeds the sum of row heights.
  - Apply vertical cell alignment (`v_align`): `top` (offset 0), `center` (vertically centered), `bottom` (aligned to cell bottom).
- **Multi-Page Pagination with Repeated Headers**:
  - When a table exceeds the available vertical space of a column frame or page:
    - Break table across rows.
    - If `RowProperties.tbl_header` is True on row 0 (or leading rows), automatically replicate the header row(s) at the top of subsequent pages.
    - Respect `RowProperties.cant_split`: if a row does not fit on the current page, push the entire row to the next page.
    - Never split across the middle of a vertical merge group unless forced.

### 2.3 Canvas Rendering & Mouse Resizing (`views/canvas_view.py`)
- **Rendering**:
  - Render cell background shading (`ShadingProperties.fill`).
  - Render table borders: top, bottom, left, right, and cell dividers.
  - Render text and portions inside cells at correct physical coordinates.
- **Interactive Divider Resizing**:
  - Mouse hover within +/- 3 pt of a vertical column boundary changes cursor to `Qt.CursorShape.SplitHCursor`.
  - Mouse hover within +/- 3 pt of a horizontal row boundary changes cursor to `Qt.CursorShape.SplitVCursor`.
  - Mouse drag resizes column width or row height with minimum threshold (12 pt), rendering a dashed reference guideline during drag.
  - On mouse release, updates table grid/heights and triggers document repagination and viewport update.

---

## 3. Data Architecture & Contracts

### 3.1 Data Structures in `models/table.py`

```python
@dataclass
class CellMapEntry:
    cell: Cell
    row_idx: int
    col_idx: int
    span: int = 1
    rowspan: int = 1
    is_hidden: bool = False


def table_map(table: Table) -> list[list[CellMapEntry]]: ...
```

### 3.2 Layout Structures in `layout/table_layout.py`

```python
@dataclass
class CellLayout:
    cell: Cell
    col_idx: int
    row_idx: int
    x: float
    y: float
    width: float
    height: float
    paragraphs_layout: list[Any]
    borders: dict[str, BorderProperties]
    shd: ShadingProperties
    v_align: str = "top"
    content_offset_y: float = 0.0


@dataclass
class RowLayout:
    row: Row
    row_idx: int
    y: float
    height: float
    cells: list[CellLayout]
    is_header: bool = False
    is_repeated_header: bool = False


@dataclass
class TableLayout:
    table: Table
    x: float
    y: float
    width: float
    height: float
    rows: list[RowLayout]
    grid: list[float]
    total_grid_width: float
```

---

## 4. Verification Plan

- Unit test suite: `tests/unit/writer/test_tables.py`
  - Test 1: `table_map` gridSpan and vMerge mapping.
  - Test 2: Row insertion, deletion, and merge repair.
  - Test 3: Column insertion and deletion with span adjustments.
  - Test 4: Merge cells (horizontal, vertical, rectangular) and content preservation.
  - Test 5: Split cells (cols, rows) and paragraph distribution.
  - Test 6: Table layout calculation (column widths, row heights, v_align).
  - Test 7: Multi-page pagination with table breaking and repeating header rows.
- GUI test suite: `tests/gui/test_writer_canvas.py`
  - Table rendering on canvas.
  - Divider hit-testing and cursor change.
  - Divider drag-resizing column widths.

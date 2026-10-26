# Implementation Plan: Issue #28 [Quire] 复杂表格排版与单元格跨行跨列合并 (gridSpan & vMerge)

## Overview
Implement the full table sub-system for Quire (Word 2003 port):
1. Table data models and manipulation operations in `models/table.py` (`table_map`, row/col insert/delete, cell merge/split with `gridSpan` and `vMerge` conformance).
2. Table layout engine in `layout/table_layout.py` (grid calculation, cell paragraph layout, row height resolution with vertical merges, vertical alignment, and cross-page pagination with repeated header rows).
3. Pagination integration in `layout/pagination.py` to flow table blocks onto physical pages.
4. Canvas rendering and interactive mouse divider dragging in `views/canvas_view.py`.
5. Complete unit tests in `tests/unit/writer/test_tables.py` and GUI tests in `tests/gui/test_writer_canvas.py`.

---

## Tasks

### Task 1: Table Model Operations & Grid Mapping (`models/table.py`)
- **Files**:
  - `src/atboffice/modules/writer/models/table.py`
  - `tests/unit/writer/test_tables.py`
- **Details**:
  - Define `CellMapEntry(cell, row_idx, col_idx, span, rowspan, is_hidden)`.
  - Implement `table_map(table: Table) -> list[list[CellMapEntry]]`:
    - Computes `c0`, `span` (`grid_span`), `rowspan` (resolving `v_merge == 'restart'` followed by `v_merge == 'continue'`), and marks continuation cells as `is_hidden = True`.
    - Sanitizes orphaned `v_merge` values (`continue` without `restart`, or `restart` without `continue`).
  - Implement `create_simple_table(rows: int, cols: int, width: float = 468.0, col_widths: list[float] | None = None) -> Table`.
  - Implement `insert_rows(table: Table, row_idx: int, count: int = 1, above: bool = False) -> None`.
  - Implement `delete_rows(table: Table, r0: int, r1: int) -> None`.
  - Implement `insert_cols(table: Table, col_idx: int, count: int = 1, left: bool = False, default_width: float = 72.0) -> None`.
  - Implement `delete_cols(table: Table, c0: int, c1: int) -> None`.
  - Implement `merge_cells(table: Table, r0: int, r1: int, c0: int, c1: int) -> Cell`:
    - Expands bounding box if any cell crosses border.
    - Concatenates paragraphs from all cells in the bounding box into top-left cell.
    - Sets top-left `tc_pr.grid_span` and `tc_pr.v_merge = 'restart'` (if r1 > r0).
    - Replaces other rows' cells with continuation cells (`v_merge = 'continue'`).
    - Removes intermediate cells within the same rows.
  - Implement `split_cells(table: Table, cell: Cell, num_rows: int, num_cols: int) -> list[Cell]`.
  - Write comprehensive unit tests in `tests/unit/writer/test_tables.py`.

### Task 2: Table Layout Engine (`layout/table_layout.py`)
- **Files**:
  - `src/atboffice/modules/writer/layout/table_layout.py`
  - `tests/unit/writer/test_tables.py`
- **Details**:
  - Define `CellLayout`, `RowLayout`, `TableLayout`.
  - Implement `layout_table(table: Table, container_width: float, doc: Document) -> TableLayout`:
    - Resolves table width and column grid widths from `table.grid` and `table.tbl_pr.w`.
    - Lays out all paragraphs within each cell using `layout_paragraph`.
    - Resolves row heights:
      - Accounts for single-row cells and multi-row spanned cells (`rowspan > 1`).
      - Applies `RowProperties.h` and `h_rule` (`auto`, `atLeast`, `exact`).
    - Computes `CellLayout` geometry `(x, y, width, height)` and vertical alignment offset `content_offset_y` (`top`, `center`, `bottom`).
  - Implement `split_table_for_page(table_layout: TableLayout, start_row: int, avail_height: float, is_first_page: bool) -> tuple[TableLayout | None, int | None]`:
    - Supports repeating header rows (`tr_pr.tbl_header == True`).
    - Packs rows that fit within `avail_height`.
    - Handles `cant_split` and multi-row spans.

### Task 3: Pagination Flow Integration (`layout/pagination.py`)
- **Files**:
  - `src/atboffice/modules/writer/layout/pagination.py`
  - `tests/unit/writer/test_tables.py`
- **Details**:
  - Extend `PageFragment` (or add `table_layout: TableLayout | None = None`, `is_table: bool = False`) so column frames can hold table fragments.
  - In `paginate_document`, handle `isinstance(block, Table)`:
    - Invoke `layout_table`.
    - Use `split_table_for_page` to flow table across column frames and new physical pages.
    - Place repeated header rows at the top of subsequent pages.
    - Handle page breaks before/after tables properly.

### Task 4: Canvas Rendering & Interactive Resizing (`views/canvas_view.py`)
- **Files**:
  - `src/atboffice/modules/writer/views/canvas_view.py`
  - `tests/gui/test_writer_canvas.py`
- **Details**:
  - Render table background fills / cell shading (`ShadingProperties.fill`).
  - Render cell borders and outer table borders with configurable line styles/widths.
  - Render text and portions inside table cells using their computed `CellLayout` coordinates.
  - Hit-test mouse coordinates near column / row borders (+/- 3 pt):
    - Switch cursor to `Qt.CursorShape.SplitHCursor` / `Qt.CursorShape.SplitVCursor`.
  - Implement mouse dragging:
    - Display dashed reference guide line during drag.
    - On mouse release, apply new column width or row height (clamped >= 12 pt).
    - Repaginate document and refresh canvas viewport.

### Task 5: Verification & Full Test Suite Run
- **Files**:
  - `tests/unit/writer/test_tables.py`
  - `tests/gui/test_writer_canvas.py`
- **Details**:
  - Run `pytest tests/unit/writer/test_tables.py -v`.
  - Run full test suite: `PYTHONPATH=src pytest tests/`.
  - Verify zero regressions and 100% test pass.

# Design Specification: Issue #282 - Quire Word Layout Drift & Table Margins/Borders

## Context & Parent Epic
- **Issue**: aitobox/ATBOffice#282
- **Title**: `[office-diff] fix(quire): 修复 Word 排版断行漂移与表格单元格内边距边框渲染 (Step 1 of 4)`
- **Parent Epic**: aitobox/ATBOffice#281
- **Blocks**: Step 4 (#285)
- **Status**: in-progress

---

## 1. Problem Analysis & Root Causes

In `atb-office-diff` document comparison audits against `.vibeoffice`:
1. **Layout & Line Breaking Drift**:
   - `portions.py` previously used crude 4-bucket hardcoded character width heuristics (`0.28`, `0.50`, `0.58`, `0.85`), differing up to 9% from actual font metrics.
   - Long paragraphs accumulated rounding errors in character advance metrics, resulting in cascading premature or delayed line breaks.
2. **Table Margins (`w:tblCellMar` & `w:tcMar`)**:
   - `table_layout.py` only read `table.tbl_pr.cell_mar`, ignoring per-cell overrides in `entry.cell.tc_pr.tc_mar`.
   - `canvas_view.py` hardcoded horizontal padding to `+ 5.4` pt and ignored cell top margin in vertical positioning.
3. **Table Borders & Alignment**:
   - Cell borders were not inherited from table borders (`insideH`, `insideV`, `top`, `bottom`, `left`, `right`).
   - `canvas_view.py` painted a hardcoded gray rectangle (`120, 120, 120`) around all cells, ignoring individual border styles, colors, and line widths.
   - Cells with multiple paragraphs did not accumulate paragraph vertical offsets in canvas rendering, causing overlapping lines.
   - Caret navigation in tables suffered from identical margin and multi-paragraph coordinate discrepancies.
4. **OOXML Round-Trip Serialization**:
   - `docx_writer.py` lacked serialization of `w:tblCellMar`, `w:tblBorders`, `w:tcMar`, and `w:tcBorders`.

---

## 2. Architecture & Technical Design

### A. High-Precision Glyph Advance & Text Measurement (`portions.py`)
- Leverage Qt's `QFontMetricsF` when a GUI application instance is active (`QApplication.instance()` or `QGuiApplication.instance()`).
- Cache `QFontMetricsF` instances by `(family, size, bold, italic)` tuple.
- Fall back to an expanded, high-accuracy proportional typographic advance table for headless environments without a Qt windowing server.
- Support font weight (`bold`) and posture (`italic`) in width calculations.

### B. Table Cell Margins Resolution (`table_layout.py`)
- Define per-cell resolved margins in `CellLayout`: `mar_t`, `mar_b`, `mar_l`, `mar_r`.
- Resolve each cell's margin by cascading:
  `tc_mar[side]` (if explicitly defined on cell) -> `tbl_pr.cell_mar[side]` -> default (`t=0, b=0, l=5.4, r=5.4`).
- Calculate cell inner available width: `max(10.0, cell_w - mar_l - mar_r)`.
- Base content height calculation on `mar_t + sum(paragraphs) + mar_b`.

### C. Table Border Resolution & Rendering (`table_layout.py` & `canvas_view.py`)
- Implement `resolve_cell_borders(tbl_borders, cell_borders, row_idx, col_idx, rowspan, span, num_rows, num_cols)` adhering to `.vibeoffice` standard:
  - Outer edges inherit from `tbl_pr.borders['top'|'bottom'|'left'|'right']`.
  - Inner dividers inherit from `tbl_pr.borders['insideH'|'insideV']`.
  - Cell-level `tc_pr.borders` take priority over table-level borders.
- In `canvas_view.py`, draw top, bottom, left, and right border segments independently using resolved `sz`, `color`, and `val` (solid, dashed, dotted, double). Skip borders with `val == 'none'`.

### D. Multi-Paragraph Positioning & Vertical Alignment
- In `canvas_view.py`:
  - Position text starting at `frag_y + cl.y + cl.content_offset_y + cl.mar_t` and `frag_x + cl.x + cl.mar_l`.
  - For each paragraph in `cl.paragraphs_layout`, accumulate `effective_space_before`, line positions, and `effective_space_after`.
- Synchronize `caret_controller.py` with identical margin and paragraph offset tracking.

### E. Docx Writer Preservation (`docx_writer.py`)
- Serialize `w:tblCellMar` and `w:tblBorders` under `<w:tblPr>`.
- Serialize `w:tcMar` and `w:tcBorders` under `<w:tcPr>`.

---

## 3. Implementation Task Checklist

- [ ] Task 1: Comprehensive TDD unit tests for table margins (`tblCellMar`/`tcMar`), border resolution, and font measurement.
- [ ] Task 2: Enhance `portions.py` with `QFontMetricsF` caching and high-precision character advance measurement.
- [ ] Task 3: Enhance `table_layout.py` with per-cell margin inheritance (`tc_mar`), border resolution, and vertical layout.
- [ ] Task 4: Update `canvas_view.py` with per-cell margins, individual border segment rendering, and multi-paragraph layout.
- [ ] Task 5: Synchronize `caret_controller.py` table hit testing and positioning with resolved cell margins and offsets.
- [ ] Task 6: Add `tblCellMar`, `tblBorders`, `tcMar`, and `tcBorders` serialization in `docx_writer.py`.
- [ ] Task 7: Full test suite verification and `grill-me` stress-test audit.

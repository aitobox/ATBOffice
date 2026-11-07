# Implementation Plan: Issue #282 - Quire Word Layout Drift & Table Margins/Borders

## Objective
Implement high-precision font measurement, full resolution of `w:tblCellMar` and `w:tcMar` margins, cascading table border resolution and rendering, multi-paragraph vertical alignment, and round-trip OOXML serialization.

---

## Proposed Milestones & Chunks

### Chunk 1: Unit Tests & TDD Fixtures (Task 1)
- Create `tests/unit/writer/test_table_margins_and_borders.py`.
- Test cases:
  - Table-level `tblCellMar` default vs explicit margins.
  - Cell-level `tcMar` overriding table-level margins per side (`t`, `b`, `l`, `r`).
  - Border inheritance: table outer borders (`top`, `bottom`, `left`, `right`) vs inner dividers (`insideH`, `insideV`), and cell-level border overrides.
  - Multi-paragraph content height, cell vertical alignment (`center`, `bottom`, `top`).
  - High-precision font advance with `QFontMetricsF`.
  - Docx read/write roundtrip for `tblCellMar`, `tblBorders`, `tcMar`, `tcBorders`.
- Run pytest to verify initial failures.

### Chunk 2: Font Measurement & Layout Advance Metrics (Task 2)
- Edit `src/atboffice/modules/writer/layout/portions.py`:
  - Add `_fm_cache: dict[tuple[str, float, bool, bool], QFontMetricsF]`.
  - Add helper `get_font_metrics_advance(text, font_size, font_family, bold=False, italic=False) -> float`.
  - Update `measure_text_width` and `measure_char_width` to use `QFontMetricsF` when available.
  - Enhance fallback font metric tables for common standard fonts (Times New Roman, Arial, Calibri, Courier New, SimSun).

### Chunk 3: Table Layout Geometry & Margins/Borders (Task 3)
- Edit `src/atboffice/modules/writer/layout/table_layout.py`:
  - Enhance `CellLayout` dataclass with `mar_t: float`, `mar_b: float`, `mar_l: float`, `mar_r: float`.
  - Implement `resolve_cell_borders(tbl_borders, cell_borders, row_idx, col_idx, rowspan, span, num_rows, num_cols) -> dict[str, BorderProperties]`.
  - Implement per-cell margin resolution: `mar = {t, b, l, r}` cascading from `cell.tc_pr.tc_mar` -> `table.tbl_pr.cell_mar` -> defaults.
  - Update `inner_w = max(10.0, cell_w - mar_l - mar_r)`.
  - Calculate `total_h = cur_p_y + mar_b`.
  - Assign resolved borders to `cl.borders`.

### Chunk 4: Canvas Rendering & Multi-Paragraph Layout (Task 4)
- Edit `src/atboffice/modules/writer/views/canvas_view.py`:
  - Replace hardcoded `+ 5.4` with `cl.mar_l`.
  - Draw cell background shading.
  - Draw individual border lines (`top`, `bottom`, `left`, `right`) with line width `pt_to_px(b.sz)`, color `b.color`, and pen style based on `b.val`. Skip `val == "none"`.
  - Fix multi-paragraph vertical rendering:
    - Start `cur_y = frag_y + cl.y + cl.content_offset_y + cl.mar_t`.
    - For each `playout in cl.paragraphs_layout`:
      - `p_top = cur_y + playout.effective_space_before`
      - For `line in playout.lines`: draw at `p_top + line.top`
      - `cur_y = p_top + playout.height + playout.effective_space_after`

### Chunk 5: Caret Controller Table Positioning (Task 5)
- Edit `src/atboffice/modules/writer/views/caret_controller.py`:
  - In `pos_to_canvas`:
    - Use `cl.mar_l`, `cl.mar_t`, `cl.content_offset_y`.
    - Accumulate multi-paragraph vertical offsets across paragraphs.

### Chunk 6: Docx Writer Serialization (Task 6)
- Edit `src/atboffice/modules/writer/io/docx_writer.py`:
  - Serialize `w:tblCellMar` and `w:tblBorders` under `<w:tblPr>`.
  - Serialize `w:tcMar` and `w:tcBorders` under `<w:tcPr>`.

### Chunk 7: Verification & Grill-Me Audit (Task 7)
- Run pytest suite: `PYTHONPATH=src conda run -n ATBOffice pytest tests/ -k "writer or table" -v`.
- Test offscreen document capture with `capture_doc_atboffice.py`.
- Execute `grill-me` audit and advance state to `reviewing`.

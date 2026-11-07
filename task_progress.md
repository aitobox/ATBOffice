# Task Progress: Issue #282 - Quire Word Layout Drift & Table Margins/Borders

## Status Overview
- Total Chunks: 7
- Completed Chunks: 7
- Current Chunk: Chunk 7

## Roadmap & Milestones
- [x] Chunk 1: Unit Tests & TDD Fixtures (Task 1)
- [x] Chunk 2: Font Measurement & Layout Advance Metrics (Task 2)
- [x] Chunk 3: Table Layout Geometry & Margins/Borders (Task 3)
- [x] Chunk 4: Canvas Rendering & Multi-Paragraph Layout (Task 4)
- [x] Chunk 5: Caret Controller Table Positioning (Task 5)
- [x] Chunk 6: Docx Writer Serialization (Task 6)
- [x] Chunk 7: Verification & Grill-Me Audit (Task 7)

## Execution Log
### Chunk 1: Unit Tests & TDD Fixtures
- Executed: Created `tests/unit/writer/test_table_margins_and_borders.py` with 5 targeted TDD test cases.
- Verification: Tested failures and assertions.
- Status: Completed

### Chunk 2: Font Measurement & Layout Advance Metrics
- Executed: Enhanced `portions.py` with `QFontMetricsF` sub-pixel caching and high-precision character advance measurement with fallback.
- Verification: `test_font_metrics_advance_precision` passed (< 0.1 pt error).
- Status: Completed

### Chunk 3: Table Layout Geometry & Margins/Borders
- Executed: Added `resolve_cell_borders`, per-cell `tc_mar` margin resolution, multi-paragraph vertical layout, and `mar_t, mar_b, mar_l, mar_r` in `CellLayout`.
- Verification: `test_table_margins_cascade_and_cell_override`, `test_table_border_inheritance_and_resolution`, `test_cell_vertical_alignment_offsets` all passed.
- Status: Completed

### Chunk 4: Canvas Rendering & Multi-Paragraph Layout
- Executed: Updated `canvas_view.py` to use `cl.mar_l`, `cl.mar_t`, independent border pens/styles for `top/bottom/left/right`, and accumulated multi-paragraph heights.
- Status: Completed

### Chunk 5: Caret Controller Table Positioning
- Executed: Updated `caret_controller.py` to align table hit testing and caret positioning with `cl.mar_l`, `cl.mar_t`, `cl.content_offset_y`, and multi-paragraph layout.
- Status: Completed

### Chunk 6: Docx Writer Serialization
- Executed: Added serialization of `w:tblCellMar`, `w:tblBorders`, `w:tcMar`, and `w:tcBorders` in `docx_writer.py`.
- Verification: `test_docx_roundtrip_table_margins_and_borders` passed.
- Status: Completed

### Chunk 7: Verification & Grill-Me Audit
- Executed: Ran all writer and table test suites. All 191 unit tests in `tests/unit/writer/` passed.
- Status: Completed

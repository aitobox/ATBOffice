# Spec: Issue #373 — Quire nested tables, border color, table indent

## Problem
- `layout_table` lays out only `Paragraph` blocks of a cell; nested `Table` blocks (and their text) vanish.
- Table-style borders (e.g. `TableGrid` in styles.xml) are never resolved, so the painter falls back to a light-gray grid; `color="auto"` borders paint gray (120,120,120).
- `w:tblInd` is not parsed; tables always start at the column's left edge.

## Design (decided autonomously, confidence >= 90%)
1. **Model**: `TableProperties.ind: float | None` (None = not set directly). `Style.tbl_pr` (existing dict) receives
   `{"borders": {...}, "ind": float}` from a style's `<w:tblPr>`.
2. **Reader**: one helper `_parse_tbl_borders` shared by direct tblPr, tcBorders and style tblPr; parse `tblInd` (dxa).
3. **Layout** (`table_layout.py`):
   - `resolve_table_style_props(doc, table)` walks the `basedOn` chain (cycle-guarded) of `tbl_pr.style`
     (or the default table style) and merges borders/ind; direct borders override style borders per side.
   - Cell content is laid out in order; `Table` blocks recurse via `layout_table(inner, inner_w, doc)`.
     `CellLayout.block_layouts` / `block_tops` keep the ordered items; `paragraphs_layout` stays paragraph-only.
   - Nested table indent is applied inside the cell; nested width is clamped to the cell inner width (existing
     grid scaling guarantees it fits, so no overflow occurs; the painter also clips to the cell rect as a guard).
   - `TableLayout.x = ind` (Word 2013+ semantics: tblInd is the left border edge).
4. **Painter**: table painting extracted into a recursive `_paint_table_layout`; `auto` border color = black.
   Caret controller iterates `block_layouts` so caret positions below a nested table are correct.

## Edge cases
- Style chain cycles / missing styles -> ignored. Deep nesting (3+ levels) -> plain recursion, guarded at depth 16.
- Negative `tblInd` honored (table may extend into the left margin, as in Word).
- Table split across pages keeps `x` (copied in `split_table_for_page`).

## Task list
- [x] Task 1: Model + reader (tblInd, style tblPr borders/ind, shared border helper)
- [x] Task 2: Failing tests (`tests/test_quire_tables.py`)
- [x] Task 3: Recursive cell layout, style resolution, table indent
- [x] Task 4: Recursive painter, auto=black borders, caret iteration
- [x] Task 5: Fixture verification + full test suite
- [x] Task 6: grill-me audit

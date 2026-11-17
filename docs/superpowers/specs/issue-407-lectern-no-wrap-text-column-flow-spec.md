# Spec: Issue #407 — Preserve no-wrap slide text and column flow

## Problem
`ShapeTextEditorItem.render_static_text` (Lectern static canvas renderer):
1. Clips every text body to its inset text rectangle. Bodies with `wrap="none"`
   are expected to overflow the (often narrow) box, so tdf104722's subtitle is
   cut to "Su".
2. Fills multi-column bodies greedily: column 1 is filled to the full text-rect
   height before text flows to column 2. The reference (`.vibeoffice`
   `render.js`) uses CSS `column-count`, whose default `column-fill: balance`
   balances content across columns. Hence tdf140852's column 2 should start
   with "comes to", and the rtlCol fixture's third column ("Insert Text box |
   ...") is never reached.

## Design
- **No-wrap overflow**: when `text_body.wrap is False`, do not install the
  text-rect clip (the reference never clips text overflow).
- **Balanced columns**: for `cols > 1`, binary-search the smallest column
  height `H` in `[content_height / cols, avail_h]` for which the
  `QTextDocument` paginated at `(col_w, H)` needs at most `cols` pages. If the
  text does not fit even at `avail_h`, keep `avail_h` (previous behavior).
  Columns are drawn with height `H`.
- **Column order**: `rtl_col` continues to place column 0 at the right edge;
  covered by a new regression test. The reference ignores `rtlCol`, but all
  audited fixtures use `rtlCol="0"`, so behavior there is unchanged.

## Edge cases
- Empty paragraphs (rtlCol fixture has five) take a line each and are part of
  the balanced height.
- Text larger than total column capacity: fall back to `avail_h`; extra pages
  beyond `cols` remain undrawn (unchanged).
- Single-column, wrapping bodies keep the clip (unchanged).
- Binary search is bounded (~20 iterations of relayout on small documents).

## Out of scope
Editing-mode (`QGraphicsTextItem`) column layout; font-metric differences;
explicit `<a:noAutofit/>` not overriding an inherited `normAutofit` (tdf140852).

## Implementation notes
- Empty paragraphs (no runs) now size their line from the same fallback font
  size their empty run renders at (18 pt for non-placeholder level 0) instead
  of the 32 pt body default; this was why the rtlCol fixture never reached its
  third column.

## Task list
- [x] Task 1: Regression tests (no-wrap overflow, balanced column breaks, RTL column order)
- [x] Task 2: Skip text-rect clip for no-wrap bodies
- [x] Task 3: Balance multi-column height
- [x] Task 4: Run affected and full presentation test suites
- [x] Task 5: Audit (grilling) & stress-test

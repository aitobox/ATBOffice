# Spec: Issue #375 — Ledger comment callout color and duplicated author name

## Root causes
1. **Dark callout**: in `GridViewport._render_paint_event` the leader arrow head sets a
   `(60,60,60)` brush that stays active when the note border is drawn with `drawRect`, so the
   whole note box is flooded dark gray.
2. **Second dark box**: hovering a commented cell also showed a `QToolTip` with
   `"Author:\ntext"` in the platform (dark) palette, duplicating the painted callout.
3. **Author twice**: Excel stores a bold `"Author:"` run plus a line break at the start of the
   note text; the painter draws its own bold `"Author:"` header on top of that.

## Design
- `xlsx_reader._strip_author_prefix(text, author)`: drop a leading `"{author}:"` plus spaces/tabs
  and one line break. Text without the prefix, or with an empty author, is unchanged. The xlsx
  writer doesn't write comments, so nothing is lost on save.
- Painter: fixed `#FFFFE1` note background (`_COMMENT_NOTE_BG`), reset the brush before the
  border, black text (unchanged).
- `GridViewport._comment_callout_rect(r, c, cm, cell=None)`: callout geometry. Place it right of
  the cell; flip left if it overflows the right edge (or clamp to it if neither side fits); shift
  up to stay above the bottom edge.
- No system tooltip for comment cells; the painted callout is the hover UI.
- The red triangle indicator already exists; it is now covered by a test.

## Task list
- [x] Task 1: Regression tests (`tests/test_ledger_comments.py`)
- [x] Task 2: Strip stored author prefix in reader
- [x] Task 3: Fixed pale-yellow background, reset brush before border
- [x] Task 4: Callout geometry helper with right/bottom edge flipping
- [x] Task 5: Remove duplicate dark system tooltip on hover
- [x] Task 6: Full test suite + grill audit

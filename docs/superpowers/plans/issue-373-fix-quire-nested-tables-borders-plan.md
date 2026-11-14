# Plan: Issue #373 — Quire nested tables, border color, table indent

Spec: docs/superpowers/specs/issue-373-fix-quire-nested-tables-borders-spec.md

## Chunk 1 — Tests first
- Create `tests/test_quire_tables.py`:
  - nested table in a cell -> `block_layouts` holds ParagraphLayout + TableLayout, heights add up.
  - three-level nesting.
  - fixture `libreoffice__tdf131260.docx`: three tables in layout, text `Table` present.
  - fixture `libreoffice__tdf132802.docx`: `TableLayout.x == 36pt`, resolved borders single/auto.
  - `_get_border_pen` with color auto -> black.
- Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_quire_tables.py -q` -> FAIL.

## Chunk 2 — Model/reader
- `properties.py`: `TableProperties.ind`.
- `docx_reader.py`: `_parse_tbl_borders`, `tblInd`, style `tbl_pr`.

## Chunk 3 — Layout
- `table_layout.py`: `resolve_table_style_props`, recursive blocks, `x = ind`; `split_table_for_page` already copies x.

## Chunk 4 — Painter/caret
- `canvas_view.py`: `_paint_table_layout` recursive; auto color black; print path recursion + x.
- `caret_controller.py`: iterate block_layouts.

## Chunk 5 — Verify
- Targeted tests then full suite `python -m pytest tests/ -q`.

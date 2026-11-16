# Plan: Issue #365 — Quire DrawingML shapes and text boxes

Spec: `docs/superpowers/specs/issue-365-quire-drawingml-shapes-text-boxes-spec.md`
Test file: `tests/test_quire_shapes.py`. Run:
`PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_quire_shapes.py -q`

## Chunk 1 — shared parsing + model
1. Tests: `parse_shape_geometry`, `resolve_shape_fill` (spPr fill, fillRef, noFill),
   `resolve_shape_line` (ln, lnRef, noFill) on inline XML snippets.
2. Implement `src/atboffice/drawing/shape_style.py`.
3. Add `ShapeItem` to `models/drawing.py`, export from `models/__init__.py`.

## Chunk 2 — reader
1. Tests: tdf113183 → presets `star5`, `triangle`, fill = theme accent1; nested-runs → text
   "Test text box", no fill/line; poi__60316 → group with text child "Allison, Timothy B.",
   pos_h percent 5.9; textframe-borders → VML ShapeItem with fill `#D99594`, text `aaa`.
2. Implement `_load_theme`, `_parse_wsp`, `_parse_group`, `_parse_txbx`, anchor
   AlternateContent; VML branch in `_parse_vml_pict`.

## Chunk 3 — layout + painter
1. Tests: textframe frame x >= 0 within page; render page 1 of tdf113183 to a QImage and
   sample the star center = accent1; no placeholder drawn (patched `_paint_picture` fallback
   never reached for ShapeItem); invisible shape paints no pixels.
2. Fix `pagination.py` column origin; add `views/shape_painter.py`; hook into
   `_paint_picture`, `_paint_float_box`, `_paint_float_box_vector`.

## Chunk 4 — verification
Full test suite, office diff capture for tdf113183, grill-me audit.

# Spec: Issue #365 — Quire renders DrawingML shapes and text boxes

## Problem
`DocxReader._parse_drawing` stores `wps:wsp` / `wpg:wgp` content as a bare `PictureItem`
(name + raw XML). With no image to show, `QuireCanvas._paint_picture` draws a dashed gray
placeholder labelled with the shape name. VML `v:rect` text frames get the same treatment.

## Design (autonomous decisions, >= 90% confidence)
1. **Shared, Qt-free style parsing** — `atboffice/drawing/shape_style.py` resolves preset /
   custom geometry, fill (explicit `spPr` fill, then `wps:style/a:fillRef`) and outline
   (`a:ln`, then `a:lnRef`) into plain data (`DmlLine`, `DmlFill`). Built on `drawing/dml.py`;
   painted with the shared `geometry_helper.create_shape_path` (same as Ledger and Lectern).
2. **Model** — `ShapeItem(PictureItem)` (`t="shape"`). Subclassing `PictureItem` keeps every
   existing layout, wrap, selection and writer round-trip path (`raw_xml`) working unchanged.
   Fields: geometry, adjustments, custom path, fill, line, flips, text `Story`, insets,
   vertical anchor, and `children` (group members with their offsets in the group box).
   `is_invisible` is true for no fill + no line + no text + no children.
3. **Reader** — `wps:wsp` → `ShapeItem`; `wpg:wgp` / `wpc` → group `ShapeItem` whose children
   are mapped from child space (`chOff`/`chExt`) into the group box; `wps:txbx/w:txbxContent`
   → blocks via the existing `_collect_blocks`. Theme colors come from `word/theme/theme1.xml`.
   VML `v:rect|roundrect|oval` with `fillcolor`/`strokecolor`/`v:textbox` → `ShapeItem`.
   `mc:AlternateContent` keeps preferring `mc:Choice` (already implemented); inside `wp:anchor`
   the position choice (`wp14:pctPosHOffset`) is now read, falling back to `mc:Fallback`.
4. **Layout** — column-relative floats were positioned relative to the body origin instead of
   the page (missing left margin), so negative offsets pushed shapes off the page. Pass the
   absolute column left to `resolve_float_box`. `wrapThrough` maps to TIGHT (unchanged).
5. **Painter** — `views/shape_painter.py`: draws path, fill, line, then text box content laid
   out with `layout_paragraph` (tables via `layout_table`) inside the insets, honoring the
   vertical anchor. Invisible shapes paint nothing; no placeholder for shapes ever.
6. **Writer** — unchanged: `ShapeItem` is a `PictureItem` with `raw_xml`, round-trips verbatim.

## Out of scope
Shadows/effects, text warp/WordArt, vertical text, linked text box chains, charts/SmartArt
(#379), font substitution (#372).

## Task list
- [x] Task 1: Shared Qt-free shape style parser (`drawing/shape_style.py`) + tests
- [x] Task 2: `ShapeItem` model in `models/drawing.py`
- [x] Task 3: Reader — theme, `wps:wsp`, groups, text box blocks, anchor `mc:AlternateContent`
- [x] Task 4: Reader — VML rect/roundrect/oval shapes with text boxes
- [x] Task 5: Layout — absolute column origin for column-relative floats
- [x] Task 6: Painter — shape geometry, fill, line, text; no placeholder (screen + vector)
- [ ] Task 7: Fixture tests for the four acceptance documents + full suite
- [ ] Task 8: grill-me audit

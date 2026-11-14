# Spec: Issue #374 — Ledger drawing objects

## Problem
`_parse_worksheet_drawings` reads only `pic`/`sp`/`graphicFrame`, only `srgbClr` fills (else default blue),
and maps `twoCellAnchor editAs="oneCell|absolute"` to an anchor type whose rect comes from a default
`abs_rect=(0,0,120,80)` — so pictures land at A1 with a wrong size. Arrows paint as a line.

## Design
- New `atboffice/drawing/dml.py` (shared, Qt-free): resolve DrawingML colors (`srgbClr`, `schemeClr`,
  `sysClr`, `prstClr`, `scrgbClr` + mods incl. `alpha`) and fills (`noFill`, `solidFill`, `gradFill`,
  `pattFill`, `grpFill`) into a small `DmlFill` value; parse `custGeom` with literal points into the
  `custom_path` dict that `create_shape_path` already understands.
- Reader:
  - `grpSp` → `FloatingObject(kind="group", children=[...])`; each child gets `group_frac`
    (fractional sub-rect of the group frame via `chOff/chExt`), recursive for nested groups.
  - `sp`, `cxnSp`: preset name + `avLst` adjustments kept in `geometry`/`geometry_adj`; `flipH/V`;
    fill/line from `spPr`, falling back to `xdr:style` `fillRef`/`lnRef`/`fontRef`.
  - `twoCellAnchor` keeps `editAs` as `anchor_type` (writer round-trip, edit semantics) but the rect is
    taken from from/to: `oneCell` uses `xfrm/ext` size; otherwise `anchor_resolved=False` so the layer
    computes the rect from cells once and caches it in `abs_rect`.
  - pictures: `picLocks noChangeAspect` → `lock_aspect`; `noFill` respected.
- Layer: paint via `create_shape_path` for any object with `geometry`; QLinearGradient for gradients
  (OOXML `lin ang`), Qt pattern brush for `pattFill`; no brush on open paths; tail/head arrowheads;
  groups paint children into their sub-rects; aspect-locked images fit inside the frame; undecodable
  images (e.g. WMF) paint a neutral placeholder instead of a blue box.

## Out of scope
Text-body styling, `fontRef` theme fonts, effects/3D, guide formulas in `custGeom`.

## Task list
- [x] Task 1: Shared DrawingML color/fill/custGeom helpers (`drawing/dml.py`)
- [x] Task 2: FloatingObject fields (geometry, fill spec, group children, lock aspect, anchor resolve)
- [x] Task 3: Reader — groups, connectors, fills, style refs, anchor fixes
- [x] Task 4: Object layer — preset paths, gradients, groups, aspect-locked images
- [x] Task 5: Tests `tests/test_ledger_drawings.py` against the 5 fixtures
- [ ] Task 6: Full test suite + grilling audit

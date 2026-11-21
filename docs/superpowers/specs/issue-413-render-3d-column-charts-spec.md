# Spec: Render imported 3D column charts in slides (#413)

## Problem
`bar3DChart` is imported as a flat `col`/`bar` chart. The 3D view (`c:view3D`)
and the depth grouping (`c:grouping val="standard"`) are discarded, so slides
render flat columns where Office shows boxes with side faces and a depth grid.

## Reference (.vibeoffice)
- `lectern/js/pptx-read.js`: a 3D group keeps `d3`; `standard` grouping becomes
  `clustered` with `deep = true`; `view3D` defaults rotX 15, rotY 20, depthPercent 100.
- `lectern/js/chart-draw.js`: the plot box shrinks by a depth offset
  `(dx, dy)` derived from the view angles; back wall, side wall and floor are
  drawn with value gridlines on the back and side walls; each bar is a box
  (front face, lighter top, darker side). Deep charts put one series per depth
  row, drawn from the back, each row 0.75/n deep.

## Design
- `ChartData.view3d: dict | None` — `{"rotX", "rotY", "depth", "deep"}`;
  `None` for 2D charts. Round-trips via `to_dict`/`from_dict` (`view3D`).
- Import: `bar3DChart` sets `view3d`. Kind mapping is unchanged, so values,
  categories and series order are untouched.
- Export: a chart with `view3d` writes `c:view3D` and `c:bar3DChart`; deep
  charts write `grouping="standard"` and a `c:serAx`.
- New module `renderers/three_d.py`: `depth_offset`, `shrink_for_depth`,
  `draw_walls`, `draw_box`, `is_3d_bar`.
- `ChartPainter`: when `is_3d_bar`, the cartesian axes routine shrinks the plot
  for depth and draws walls/depth gridlines instead of flat gridlines; the depth
  offset is passed to `draw_columns` / `draw_bars`.
- 2D charts take exactly the old code path (offset `(0, 0)`).

## Edge cases
- `rotX = rotY = 0`: treated as 2D (as the reference).
- Missing `view3D` element on a 3D chart: reference defaults.
- Zero-height bars: box still drawn without errors; empty series/cats return early.
- Negative values: box spans zero line; side/top faces use the same geometry.
- Pie/line/area 3D remain out of scope (no 3D line/area in this issue).

## Task list
- [x] Task 1: Model field `view3d` + dict round-trip
- [x] Task 2: Import `bar3DChart` view/depth settings; export `bar3DChart`
- [x] Task 3: `three_d.py` geometry and drawing helpers
- [x] Task 4: Painter + column/bar renderers draw walls, depth grid and boxes
- [x] Task 5: Tests: fixture import, 3D visual regression, 2D control case
- [x] Task 6: Full test suite pass and fixture recapture

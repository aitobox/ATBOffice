# Spec: Issue #371 — Lectern custom geometry scale, connector flipV, handles on unselected shapes

## Root-cause findings

| Symptom | Fixture | Actual root cause |
|---|---|---|
| Outline drawn at ~50% height | `libreoffice__tdf164622.pptx` | The outline is a **picture** with `<a:srcRect b="41860"/>`, not a `custGeom`. The reader ignored `srcRect`, so the whole image was squeezed into the frame. |
| Custom geometry squashed (general) | synthetic | Path coordinates were converted EMU→pt with `emu_to_pt` (rounded to 0.01 pt). Small path spaces such as `w="100"` collapsed to 0. `arcTo` also used the current point as the ellipse centre instead of a point on the ellipse. |
| Connector descends instead of ascending | `libreoffice__connector-shape-animations.pptx` | `flipH`/`flipV` were never parsed into the model or applied when painting. |
| Blue handles with empty selection | `libreoffice__connector-shape-animations.pptx` | Product bug confirmed in a live window: on open, `AnimationPane._refresh_list()` called `setCurrentRow(0)` outside its `_updating_ui` guard, emitting `shapeSelectionRequested`, which **selected** the first animated shape (the connector). Handles were correctly bound to selection. |

## Design

- **Model**: `Shape.flip_h` / `Shape.flip_v` (serialized as `flipH` / `flipV`); the PPTX writer reads the new names.
- **Reader**: `_parse_flip()` for `sp`, `cxnSp`, `pic`, `grpSp`; `_parse_src_rect()` → `Shape.crop` fractions `{l,t,r,b}` (the format already used by the Format Shape dialog). Flipped groups bake the mirror into children (`_mirror_in_group`: reflect box, toggle leaf flips, negate rotation for a single reflection). `cxnSp` children of groups are now parsed. Custom path units are converted without rounding.
- **Renderer**: `flip_transform()` mirrors geometry/shadow (text stays upright) and pictures, applied in local coordinates before item rotation (DrawingML order). Pictures are drawn so the srcRect visible area fills the frame (negative crops pad). `arcTo` derives the centre from the current point (ported from `.vibeoffice/public/common/geometry.js`).
- **Connectors**: `connector_local_endpoints()` gives flipped start/end for handle positions and for re-routing fallbacks; recomputing a route clears flips (the route encodes direction).
- **Writer**: `<a:srcRect>` emitted for cropped pictures so a loaded crop survives save.
- **Animation pane**: the refresh restores the current row without pushing a canvas selection; user clicks still select the shape.

## Out of scope (noted)
- `geometry_to_xml` writes `prstGeom prst="custom"` for custom shapes (custGeom is not serialized).
- `LecternWindow.toggle_picture_crop` assigns a bool to `Shape.crop`; the renderer/writer ignore non-dict crops.
- `flipV` text rotation by 180° and kid rotation inside group painting.

## Task list
- [x] Task 1: Parse flipH/flipV and srcRect; bake flipped-group mirroring; parse cxnSp in groups
- [x] Task 2: Exact custom-path unit conversion and correct arcTo centre
- [x] Task 3: Render flips (shapes, shadows, group kids, pictures) and picture crop
- [x] Task 4: Flip-aware connector endpoints; reset flips on re-route
- [x] Task 5: Stop the animation pane selecting a shape on load
- [x] Task 6: Serialize flips and srcRect
- [x] Task 7: Tests (`tests/test_lectern_geometry.py`) + full suite + fixture visual check

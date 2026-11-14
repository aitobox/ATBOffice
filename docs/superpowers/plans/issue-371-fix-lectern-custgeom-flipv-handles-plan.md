# Plan: Issue #371

Spec: `docs/superpowers/specs/issue-371-fix-lectern-custgeom-flipv-handles-spec.md`

1. Write `tests/test_lectern_geometry.py` (AC1–AC4 plus arc, group flip, srcRect round-trip, no-selection-on-open) → verify failure.
2. `models/shape.py`: add `flip_h`, `flip_v` + dict round-trip; `io/xml_utils.py`: read new names.
3. `io/pptx_reader.py`: `_parse_flip`, `_parse_src_rect`, `_mirror_in_group`, `cxnSp` in groups, exact custom-path units.
4. `views/geometry_helper.py`: `flip_transform`, `connector_local_endpoints`, arcTo centre fix.
5. `views/shape_item.py`: apply flips to shape/shadow/group kids/pictures, picture crop target rect, flip-aware handle fallback, clear flips on re-route.
6. `views/slide_canvas.py`: flip-aware connector endpoint fallback.
7. `views/animation_pane.py`: restore current row inside `_updating_ui`.
8. `io/writer_shapes.py`: `<a:srcRect>`.
9. Verify: `pytest tests/test_lectern_geometry.py`, full `pytest tests/`, render both fixtures.

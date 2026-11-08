# Implementation Plan: Magnetic Shape Connector Lines and Base SmartArt Layout

- **Issue**: #315
- **Branch**: `agent/issue-315-magnetic-shape-connectors-smartart`
- **Spec**: `docs/superpowers/specs/issue-315-magnetic-shape-connectors-smartart-spec.md`

## Proposed Changes

### Task 1: Shape Model & PPTX I/O
- Add `cxn_start` and `cxn_end` fields to `Shape` in `src/atboffice/modules/presentation/models/shape.py`.
- Update `to_dict`, `from_dict`, and `clone`.
- In `src/atboffice/modules/presentation/io/pptx_reader.py`:
  - Support `<p:cxnSp>` in `_parse_shape`.
  - Parse `<a:stCxn>` and `<a:endCxn>` from `<p:nvCxnSpPr>/<p:cNvCxnSpPr>` into `cxn_start` and `cxn_end`.

### Task 2: Shape Connection Sites & Geometry Helpers
- In `src/atboffice/modules/presentation/views/geometry_helper.py`:
  - Implement `get_shape_connection_sites(geom, w, h, adj=None) -> list[tuple[float, float]]` (4 cardinal points: top, right, bottom, left).
  - Add geometry paths for `straightConnector1`, `bentConnector2`, `bentConnector3`, `curvedConnector3`.
  - Implement `calculate_elbow_route(p1, p2, site1_idx=None, site2_idx=None)` for orthogonal stepped routes.

### Task 3: Magnetic Snapping & ShapeGraphicsItem Connector Support
- In `src/atboffice/modules/presentation/views/shape_item.py`:
  - Identify connector shapes (`is_connector`: type == 'line' or geom in connector presets).
  - Handle endpoints dragging for connectors (`HandleType.START`, `HandleType.END`).
  - Search scene for nearby connection sites within magnetic threshold (15px) and snap to site.
  - Draw magnetic snap highlight markers on target shape connection sites during drag.
  - On mouse release, save `cxn_start` / `cxn_end`.

### Task 4: Dynamic Connector Updates in SlideCanvas
- In `src/atboffice/modules/presentation/views/slide_canvas.py`:
  - Implement `update_connected_connectors(shape_id)` on `SlideScene`.
  - Automatically recalculate connector start/end positions and route when connected shapes move or resize.
  - Hook into `ShapeGraphicsItem.itemChange` on `ItemPositionChange`.

### Task 5: SmartArt Hierarchical & Linear Layouts
- In `src/atboffice/modules/presentation/smartart/layouts/`:
  - Verify hierarchical tree layouts (`make_org_chart`, `make_hierarchy`, `make_h_hierarchy`) place nodes and vector connector paths correctly.
  - Verify linear process layouts (`make_process`, `make_chevron`) with step arrows and clean bounds.

### Task 6: Unit Test Suite & Verification
- Create `tests/unit/presentation/test_connectors_and_smartart.py`:
  - Test connection sites for shapes.
  - Test `cxn_start` / `cxn_end` serialization and PPTX reader.
  - Test magnetic snap detection and connection tracking.
  - Test dynamic connector endpoint updates when shapes move.
  - Test elbow and straight connector routing.
  - Test SmartArt org chart and chevron layout placement.
- Run `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/presentation/test_connectors_and_smartart.py -v`.
- Run full unit tests to ensure zero regressions.

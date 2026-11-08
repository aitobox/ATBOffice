# Specification: Magnetic Shape Connector Lines and Base SmartArt Layout

- **Issue**: #315
- **Branch**: `agent/issue-315-magnetic-shape-connectors-smartart`
- **Component**: Lectern (`src/atboffice/modules/presentation`)
- **Status**: Approved (Autonomous >= 90% confidence)

## 1. Overview & Problem Statement
In PowerPoint presentations, connectors (`straightConnector1`, `bentConnector2`, `bentConnector3`, `curvedConnector3`) link shapes via connection sites (`a:stCxn`, `a:endCxn`). Previously in Lectern, connectors lacked magnetic snap attachment to shape bounds during editing, and moving a connected shape left the connector detached. Furthermore, SmartArt diagrams (such as hierarchical org charts and process chevrons) require robust auto-layout placement and connector routing.

## 2. Architecture & Data Model

### 2.1 Shape Model Extensions (`src/atboffice/modules/presentation/models/shape.py`)
Add `cxn_start` and `cxn_end` attributes to `Shape`:
```python
cxn_start: dict[str, Any] | None = None  # e.g. {"id": "target_shape_id", "idx": 0}
cxn_end: dict[str, Any] | None = None    # e.g. {"id": "target_shape_id", "idx": 2}
```
- Fully serialized and deserialized in `Shape.to_dict()` and `Shape.from_dict()`.
- Deep-copied in `Shape.clone()`.

### 2.2 Connection Site Calculation (`geometry_helper.py`)
Define `get_connection_sites(shape: Shape) -> list[tuple[float, float]]`:
- Standard shapes provide 4 cardinal connection sites:
  - Index 0: Top-center `(w / 2, 0)`
  - Index 1: Right-center `(w, h / 2)`
  - Index 2: Bottom-center `(w / 2, h)`
  - Index 3: Left-center `(0, h / 2)`
- Special geometries (triangles, diamonds) provide specialized perimeter sites.
- Helper `get_shape_connection_site_scene(shape_item: ShapeGraphicsItem, idx: int) -> QPointF` translates local connection site coordinates to scene coordinates accounting for rotation and position.

### 2.3 Connector Routing & Geometry Helper
- `straightConnector1`: Straight line `(x1, y1) -> (x2, y2)`.
- `bentConnector3` (Elbow connector): Orthogonal stepped routing between start and end. Calculates intermediate bend coordinates based on connection site normals.
- `curvedConnector3`: Smooth cubic Bezier interpolation.

### 2.4 Magnetic Snapping & Interactive Dragging (`shape_item.py`)
- Identify connector shapes (`is_connector` or geom in `straightConnector1`, `bentConnector2`, `bentConnector3`, `curvedConnector3`, `line`).
- Connector handles: Start endpoint handle and End endpoint handle.
- During handle drag:
  - Query scene for nearby target shapes.
  - Test distance to connection sites (threshold: 15.0 px).
  - Snap handle to the nearest site and highlight visual snap indicator.
  - On drag release: commit `cxn_start` / `cxn_end`.

### 2.5 Dynamic Connector Updates (`slide_canvas.py`)
- In `SlideScene`:
  - `update_connected_connectors(shape_id: str)`: Find all connectors connected to `shape_id` via `cxn_start` or `cxn_end`, recompute their endpoints and route, and update their graphics items.
  - Triggered in `ShapeGraphicsItem.itemChange` upon `ItemPositionChange` or resize.

### 2.6 SmartArt Hierarchical & Linear Vector Layouts
- Ensure hierarchical layouts (`make_org_chart`, `make_hierarchy`, `make_h_hierarchy`) and linear layouts (`make_process`, `make_chevron`) generate consistent node bounds and vector connector routing.

## 3. Verification & Acceptance Criteria
1. Magnetic snap handles snap to shape bounds within threshold.
2. `cxn_start` and `cxn_end` maintain shape ID and connection site index across serialization.
3. Moving or resizing a shape automatically recalculates and updates connected connector endpoints and routes.
4. Base SmartArt hierarchical and linear layouts place nodes and connectors cleanly.
5. 100% pass on `tests/unit/presentation/test_connectors_and_smartart.py`.

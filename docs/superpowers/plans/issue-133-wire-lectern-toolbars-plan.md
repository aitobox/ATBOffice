# Implementation Plan: Wire Lectern Toolbars to Vector Canvas, Layers, and View Modes

## Phase 1: Interactive Drawing Tool Support in SlideScene and SlideCanvasView
- **Goal**: Implement `set_drawing_tool(tool_info)` on `SlideScene` and `SlideCanvasView`, supporting cursor updates, mouse drag shape generation, default sizing, Escape key cancellation, and shape model emission.
- **Files Affected**:
  - `src/atboffice/modules/presentation/views/slide_canvas.py`
  - `tests/gui/test_slide_canvas.py` (or new test in `tests/ui/test_lectern_toolbars.py`)
- **Tasks**:
  1. Add `set_drawing_tool` to `SlideScene` and `SlideCanvasView`.
  2. In `mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent`, implement shape creation logic when a drawing tool is active.
  3. Ensure pressing Escape or switching tool clears the tool and resets cursor.
- **Verification**:
  - Write test verifying selecting a drawing tool changes cursor and simulates mouse press/release to add a shape.

## Phase 2: Drawing Toolbar Actions & Dropdown Menu Wiring
- **Goal**: Register and wire drawing shape actions (`drawLine`, `drawArrow`, `drawRect`, `drawOval`, `textBox`, `selectObjects`) and layer/arrangement dropdown items in `lectern_toolbars.py` and `lectern_window.py`.
- **Files Affected**:
  - `src/atboffice/ui/shell/lectern_toolbars.py`
  - `src/atboffice/ui/shell/lectern_window.py`
- **Tasks**:
  1. In `lectern_toolbars.py`, ensure Drawing menu items (`置于顶层`, `置于底层`, `上移一层`, `下移一层`, `组合`, `取消组合`, `对齐或分布`) are linked to corresponding ActionRegistry actions (`bringFront`, `sendBack`, `bringForward`, `sendBackward`, `group`, `ungroup`, `align_left`, etc.).
  2. In `lectern_window.py`, register action handlers for all drawing actions, layer ordering, grouping, and alignment.
- **Verification**:
  - Verify triggering `bringFront`, `sendBack`, `group`, `ungroup` through `action_registry` alters `slide.shapes`.

## Phase 3: View Mode Switching & Slideshow Actions
- **Goal**: Register and wire `viewNormal`, `viewSorter`, `viewMaster`, `closeMaster`, and slideshow actions (`start_slideshow`, `start_slideshow_current`).
- **Files Affected**:
  - `src/atboffice/ui/shell/lectern_window.py`
  - `src/atboffice/ui/shell/lectern_toolbars.py`
- **Tasks**:
  1. Add action bindings for `viewNormal`, `viewSorter`, `viewMaster`, `start_slideshow_current` (Shift+F5).
  2. Verify view mode changes switch workspace stack and update toolbar visibilities.
- **Verification**:
  - Verify `action_registry.trigger_action("viewSorter")` switches view mode to sorter.

## Phase 4: IntelliArt (SmartArt) Diagram Toolbar Actions
- **Goal**: Wire Diagram toolbar actions (`diagramAddShape`, `diagramPromote`, `diagramDemote`, `diagramMoveUp`, `diagramMoveDown`, `diagramReset`, `diagramToShapes`) to the active SmartArt shape using `smartart/engine.py`.
- **Files Affected**:
  - `src/atboffice/ui/shell/lectern_window.py`
- **Tasks**:
  1. Implement helper method `_get_active_diagram_shape() -> Shape | None`.
  2. Implement `_on_diagram_add_shape(position="after")`, `_on_diagram_promote()`, `_on_diagram_demote()`, `_on_diagram_move(direction="up")`, `_on_diagram_reset()`, `_on_diagram_to_shapes()`.
  3. Bind these handlers to `diagramAddShape`, `diagramPromote`, etc. in `action_registry`.
- **Verification**:
  - Test adding a node to a SmartArt diagram via toolbar action and checking that node count increased and shapes were recomputed.

## Phase 5: Comprehensive Unit & Integration Tests
- **Goal**: Add end-to-end tests covering all 5 acceptance criteria in `tests/ui/test_lectern_toolbars.py`.
- **Verification Command**:
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_lectern_toolbars.py -v`

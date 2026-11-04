# Technical Specification: TASK-710 / Issue #244
## 恢复填充柄完整事件链与保护事务 (Ledger Fill Handle Event Chain & Protection Transaction)

### 1. Overview & Context
This specification addresses GitHub Issue #244 (Parent Epic #234, Phase 7, TASK-710):
- Ported from `.vibeoffice/public/ledger/js/grid.js:435–770`, `ops.js`, and `app.js:899-911`.
- Restores the complete event lifecycle for the autofill handle (hit-testing, overlay forwarding, cursor feedback, mouse capture, auto-scroll, double-click fill down).
- Enforces worksheet protection gates (abort on protected targets with zero dirty records/undo entries).
- Replaces whole-table cloning with sparse delta transactions in the undo/redo subsystem to prevent memory spikes.
- Connects dirty state, recalculation, and status reporting on autofill commit and undo/redo.

### 2. Edge Case Analysis & Architectural Decisions

#### Edge Case 1: Sheet Protection & Target Lock Status
- **Issue**: Previously, `mouseReleaseEvent` executed `AutoFillEngine.auto_fill` without calling `guard_protect()`, bypassing sheet protection and dirtying protected cells.
- **Solution**: Before applying changes, inspect `self.guard_protect(cell_edit=True)`. If the worksheet is protected (or target cells in `dest` are locked under protection), abort autofill immediately, display the standard protection dialog, reset drag state, and do NOT record any undo record or mark dirty.

#### Edge Case 2: Memory Spike from Whole-Sheet Cloning
- **Issue**: Prior implementation cloned `self.model.cells` for all entries in the workbook on drag release, causing severe memory spikes for large sheets.
- **Solution**: Capture only the sparse delta:
  - `affected_coords`: set of coordinates in `dest` (and cleared cells if shrinking).
  - `before_delta_cells`: mapping of `(r, c) -> CellData.clone()` or `None` if previously empty.
  - `after_delta_cells`: mapping of `(r, c) -> CellData.clone()` or `None`.
  - In `undo()` and `redo()`, apply delta updates selectively.

#### Edge Case 3: Overlay Cursor & Event Forwarding (`SpreadsheetObjectLayer`)
- **Issue**: `SpreadsheetObjectLayer` overlays `grid.viewport()`. Hovering over empty space previously called `self.setCursor(Qt.CursorShape.ArrowCursor)`, which masked the grid's `CrossCursor` over the fill handle.
- **Solution**: In `SpreadsheetObjectLayer.mouseMoveEvent`, call `self.unsetCursor()` when the mouse is not over a floating object. In Qt, this causes the widget to inherit the cursor from its parent (`GridViewport.viewport()`), ensuring the fill handle's cross cursor, header split cursors, and selection border cursors are visible.

#### Edge Case 4: Active Editor Commit
- **Issue**: If the cell editor is active when clicking the fill handle, typing was not committed.
- **Solution**: In `GridViewport.mousePressEvent` under `HitZone.FILL_HANDLE`, commit the active editor before starting the drag, exactly as in `.vibeoffice/public/ledger/js/grid.js:438, 466`.

#### Edge Case 5: Modifier Keys on macOS vs Windows
- **Issue**: Only `ControlModifier` was checked, but on macOS, Cmd is `MetaModifier`.
- **Solution**: Check `ControlModifier | MetaModifier` for incrementing single numeric values vs copy.

#### Edge Case 6: Drag Cancellation Lifecycle
- **Issue**: Cancelling via Esc, blur, tab switch, secondary button press, or lost release must clean up preview range, timers, and tooltips without leaving orphan state or modified cells.
- **Solution**: Strengthen `cancel_drag()` to cleanly restore selection, clear preview rects, stop auto-scroll timers, and hide tooltips.

#### Edge Case 7: Double-Click Fill Down (`fill_down_to_data`)
- **Issue**: Double-clicking the fill handle had no handler in `mouseDoubleClickEvent`.
- **Solution**: Implement `fill_down_to_data()` matching `.vibeoffice` `A.fillDownToData()`, finding boundary based on adjacent column data.

### 3. Implementation Plan
- **Phase 1**: Update `grid_viewport.py` to check `guard_protect()`, commit active editor on press, check `ControlModifier | MetaModifier`, and implement sparse delta undo.
- **Phase 2**: Update `object_layer.py` to use `unsetCursor()` on empty space.
- **Phase 3**: Implement double-click fill down (`fill_down_to_data`).
- **Phase 4**: Create integration test suite `tests/gui/test_phase7_fill_integration.py`.
- **Phase 5**: Update `docs/clone/phase7_features.csv` with evidence.

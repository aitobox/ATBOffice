# Implementation Plan: TASK-710 / Issue #244
## 恢复填充柄完整事件链与保护事务 (Ledger Fill Handle Event Chain & Protection Transaction)

### Tasks

#### Task 1: Create Comprehensive Integration Tests (TDD)
- **Target File**: `tests/gui/test_phase7_fill_integration.py`
- **Tests**:
  1. `test_fill_handle_linear_drag_real_data`: A1=1, A2=2 dragged to A10 yields 1..10; single value with Cmd/Ctrl increments, without Cmd/Ctrl copies.
  2. `test_fill_handle_protection_blocks_and_no_dirty`: When sheet is protected, dragging fill handle into protected cells does not alter data, does not create undo entry, and does not flag dirty.
  3. `test_fill_handle_sparse_undo_redo`: Verify undo reverts autofill changes and restores selection; redo reapplies changes; no whole-table copying occurred.
  4. `test_fill_handle_cancellation_lifecycle`: Esc mid-drag, focus loss (blur), and secondary mouse click cancel drag cleanly without modifying cells.
  5. `test_fill_handle_commits_active_editor`: Clicking fill handle while editing a cell commits the value before drag starts.
  6. `test_object_layer_cursor_forwarding`: Hovering over fill handle through `SpreadsheetObjectLayer` displays `CrossCursor`.
  7. `test_fill_handle_double_click_fill_down`: Double-clicking fill handle fills down adjacent data column extent.

#### Task 2: Implement Fixes in `grid_viewport.py`
- **Target File**: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- **Modifications**:
  1. In `mousePressEvent` for `HitZone.FILL_HANDLE`: commit `editor_controller` if active.
  2. In `mouseReleaseEvent` for `HitZone.FILL_HANDLE`:
     - Check `self.guard_protect(cell_edit=True)`. If blocked, reset drag state and exit without mutating data or dirtying state.
     - Check `ControlModifier | MetaModifier` for macOS Cmd key support.
     - Compute sparse delta (`before_delta_cells` and `after_delta_cells`) for only affected cells in `dest` (and shrink-cleared cells).
     - Commit undo entry with sparse delta, call `self.mark_dirty()`, call recalculation, update viewport.
  3. In `undo()` and `redo()`:
     - Add support for `delta_cells` in `cmd`, restoring/applying only changed cells.
  4. In `mouseDoubleClickEvent`:
     - Handle `HitZone.FILL_HANDLE` by calling `fill_down_to_data()`.
  5. Implement `fill_down_to_data()` matching `.vibeoffice` `A.fillDownToData()`.

#### Task 3: Fix Cursor Masking in `object_layer.py`
- **Target File**: `src/atboffice/modules/spreadsheet/views/object_layer.py`
- **Modifications**:
  1. In `mouseMoveEvent`, replace `self.setCursor(Qt.CursorShape.ArrowCursor)` with `self.unsetCursor()` when hovering over empty space.

#### Task 4: Verification & Acceptance
- Run:
  `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_fill_integration.py tests/gui/test_autofill.py tests/gui/test_gestures_drag.py -ra`
- Run full test suite:
  `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`
- Verify 0 regressions.

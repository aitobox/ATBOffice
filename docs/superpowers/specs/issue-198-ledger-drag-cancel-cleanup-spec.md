# Design Specification: Issue #198 - 建立 Ledger 拖动取消与资源清理机制

## 1. Problem Statement & Background
In ATBOffice Ledger (`GridViewport`), mouse interactions currently do not adhere to the robust drag lifecycle established by original ATBOffice (`.vibeoffice/public/ledger/js/grid.js:514-553` and `.vibeoffice/public/common/ui.js:834-925`).

Specific gaps identified:
1. **No 3px Movement Threshold**: Drags immediately initiate selection changes on 1px or 2px micro-movements, instead of waiting for a 3px Euclidean distance threshold (`Math.hypot(dx, dy) >= 3`).
2. **Missing Drag Cancellation**:
   - Pressing `Escape` during an active drag does not cancel the drag or restore previous selection / geometry / preview.
   - Loss of focus (`focusOutEvent` / blur) leaves drag state active and uncommitted.
   - Second mouse button press (e.g. right-click while left-dragging) does not cancel the drag or swallow the secondary button context menu.
   - Lost capture or release outside the window (`buttons & LeftButton == 0` during move) leaves the viewport in an orphaned dragging state.
3. **No Selection & Geometry Rollback**:
   - Cancelling a drag must restore the selection snapshot taken before mouse press, or restore original column/row size if resizing, or clear autofill preview without committing changes.
4. **Missing Auto-Scroll Timer & Cleanup**:
   - Auto-scroll during drags should run on a controlled timer (`60ms`), and must be rigorously stopped and cleared on drag end, cancellation, sheet switch, or widget close.
5. **Right-Click Parity**:
   - In original `.vibeoffice/public/ledger/js/grid.js:435-447`, right-click adjusts selection if clicked outside current selection, commits any active formula editor, and immediately returns. It never initiates a drag or creates an unverified drag-context-menu.

---

## 2. Evidence from Original Implementation (.vibeoffice)
From `.vibeoffice/public/ledger/js/grid.js:513-565`:
- `beginDrag(e, d)`:
  - Sets `d.moved = false`, `x0`, `y0`.
  - Configures `threshold = 3`.
  - Implements `move`, `up`, and `cancel` handlers.
- `snapSel(sh)` and `restoreSel(snap)`:
  - Takes a complete snapshot of selection `{ sh, s: { r, c, active, ranges, anchor, extent } }`.
  - `restoreSel(snap)` restores exactly the snapshot if the active sheet matches.
- `stopDrag()`:
  - Clears `autoTimer` (`clearInterval(autoTimer)`).
  - Hides guide line and tooltip.
  - Clears `drag = null`.
- `onDragCancel()`:
  - Calls `stopDrag()`.
  - Resets preview states (`fillTo = null`, `dragTo = null`, `editor.pointCancel()`).
  - Calls `restoreSel(d.before)`.
  - Repaints grid and restores focus.
- `common/ui.js:834-925`:
  - `why` reasons: `'esc'`, `'button'`, `'lost'`, `'blur'`, `'undo'`, `'api'`.
  - Swallow button: When a second button cancels a drag, its subsequent release, auxclick, and contextmenu events are swallowed so no erroneous popup menu appears.

---

## 3. Architecture & Data Structures

### 3.1 Drag Lifecycle State in `GridViewport`
Introduce structured tracking for active drag sessions:
```python
@dataclass
class DragSnapshot:
    zone: HitZone
    sheet_index: int
    active_cell: tuple[int, int]
    ranges: list[SelectionRange]
    anchor: tuple[int, int] | None
    extent: tuple[int, int] | None
    resize_index: int = -1
    resize_orig_size: int = 0
    fill_start_src: SelectionRange | None = None
```

Viewport instance variables:
- `self._drag_mode: HitZone = HitZone.NONE`
- `self._drag_start_pos: QPoint | None = None`
- `self._drag_moved: bool = False`
- `self._drag_threshold: int = 3`
- `self._drag_snapshot: DragSnapshot | None = None`
- `self._auto_scroll_timer: QTimer | None = None`
- `self._auto_scroll_delta: tuple[int, int] = (0, 0)`
- `self._swallow_secondary_button: bool = False`

### 3.2 Cancel Logic: `cancel_drag(why: str)`
```python
def cancel_drag(self, why: str = "api") -> None:
    if self._drag_mode == HitZone.NONE and not self._drag_snapshot:
        return
    
    self._stop_auto_scroll()
    
    snap = self._drag_snapshot
    if snap is not None:
        if snap.zone in (HitZone.CELL, HitZone.COL_HEADER, HitZone.ROW_HEADER):
            # Restore selection if on same sheet
            if self.model.active_sheet_index == snap.sheet_index:
                self.selection.restore_snapshot(snap.active_cell, snap.ranges, snap.anchor, snap.extent)
        elif snap.zone == HitZone.COL_RESIZE:
            self.geometry_mapper.set_col_width(snap.resize_index, snap.resize_orig_size)
            self._update_scrollbars()
        elif snap.zone == HitZone.ROW_RESIZE:
            self.geometry_mapper.set_row_height(snap.resize_index, snap.resize_orig_size)
            self._update_scrollbars()
        elif snap.zone == HitZone.FILL_HANDLE:
            self._fill_start_src = None
            self._fill_preview_range = None
            
        if self.editor_controller and self.editor_controller.is_active:
            if hasattr(self.editor_controller, "point_cancel"):
                self.editor_controller.point_cancel()

    if why == "button":
        self._swallow_secondary_button = True

    self._drag_mode = HitZone.NONE
    self._drag_moved = False
    self._drag_start_pos = None
    self._drag_snapshot = None
    self._resize_index = -1
    self._point_anchor = None
    self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
    self.viewport().update()
```

### 3.3 Event Handling Hooks
1. **`keyPressEvent`**:
   - If `event.key() == Qt.Key.Key_Escape` and `self._drag_mode != HitZone.NONE`:
     Call `self.cancel_drag(why="esc")`, `event.accept()`, return.
2. **`mousePressEvent`**:
   - If `self._drag_mode != HitZone.NONE` and `event.button() != Qt.MouseButton.LeftButton`:
     Call `self.cancel_drag(why="button")`, `event.accept()`, return.
3. **`mouseMoveEvent`**:
   - Check threshold: if `not self._drag_moved`:
     `dist = math.hypot(x - self._drag_start_pos.x(), y - self._drag_start_pos.y())`
     If `dist < self._drag_threshold`: return without extending selection/preview.
     `self._drag_moved = True`
   - Check lost capture:
     If `not (event.buttons() & Qt.MouseButton.LeftButton)`:
       Call `self.cancel_drag(why="lost")`, return.
   - Check edge bounds for auto-scroll.
4. **`focusOutEvent`**:
   - When focus is lost, if `self._drag_mode != HitZone.NONE`:
     Call `self.cancel_drag(why="blur")`.
5. **`contextMenuEvent`**:
   - If `self._swallow_secondary_button`:
     `self._swallow_secondary_button = False`
     `event.accept()`
     return
6. **`closeEvent` & Sheet Switch**:
   - Always cancel drag and stop auto-scroll timer.

---

## 4. Test Strategy
Comprehensive test suite in `tests/gui/test_grid_viewport.py`:
1. `test_drag_threshold_3px`: Mouse movement under 3px does not extend selection; movement >= 3px extends selection.
2. `test_drag_cancel_escape`: Esc key restores original selection snapshot and cancels active drag.
3. `test_drag_cancel_focus_out`: `focusOutEvent` cancels drag and restores selection.
4. `test_drag_cancel_second_button`: Right-click while dragging cancels drag and swallows context menu.
5. `test_drag_cancel_lost_capture`: Mouse move without left button held down cancels drag.
6. `test_drag_cancel_resize`: Esc or blur during column/row resize restores original width/height.
7. `test_drag_cancel_autofill`: Esc during fill handle drag clears fill preview without modifying cell values.
8. `test_drag_autoscroll_timer_cleanup`: Auto-scroll timer starts on boundary drag and is cleanly stopped on cancel, release, or close.
9. `test_right_click_no_drag`: Right-click does not initiate any drag state.

---

## 5. 90% Confidence Decision Summary
All behavior matches `.vibeoffice/public/ledger/js/grid.js:514-553` and `.vibeoffice/public/common/ui.js:834-925`.
No user confirmation is required. Proceed autonomously to Phase 3 (writing-plans).

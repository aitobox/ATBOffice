# Implementation Plan: Issue #198 - 建立 Ledger 拖动取消与资源清理机制

## 1. Overview
Implement robust drag lifecycle management in `GridViewport` for Ledger spreadsheet module, matching `.vibeoffice/public/ledger/js/grid.js:514-553` and `.vibeoffice/public/common/ui.js:834-925`.
Includes:
- 3px distance threshold before drag move takes effect.
- Complete snapshot and rollback of selection, resize, and autofill preview.
- Drag cancellation triggers: `Esc` key, window/widget `blur` (`focusOutEvent`), secondary button press (`mousePressEvent`), lost pointer capture / unheld release (`mouseMoveEvent`), sheet switch, and window close.
- Auto-scroll timer lifecycle management (`60ms` interval) and clean shutdown.
- Right-click behavior parity: right button does not initiate drag.

---

## 2. Tasks

### Task 1: Add Snapshot & Restore to SelectionModel
- File: `src/atboffice/modules/spreadsheet/models/selection_model.py`
- Add `snapshot()` and `restore_snapshot(snap: dict)` methods to `SelectionModel`.
- Emits signals on restoration so views update consistently.

### Task 2: Implement Drag Lifecycle & Cancellation in GridViewport
- File: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- Add `DragSnapshot` data class.
- Initialize drag tracking attributes in `__init__`:
  - `self._drag_start_pos: QPoint | None = None`
  - `self._drag_moved: bool = False`
  - `self._drag_threshold: int = 3`
  - `self._drag_snapshot: DragSnapshot | None = None`
  - `self._auto_scroll_timer: QTimer | None = None`
  - `self._auto_scroll_delta: tuple[int, int] = (0, 0)`
  - `self._swallow_secondary_button: bool = False`
- Implement helper methods:
  - `cancel_drag(why: str = "api") -> None`
  - `_start_auto_scroll(dr: int, dc: int) -> None`
  - `_stop_auto_scroll() -> None`
  - `_on_auto_scroll_tick() -> None`
- Update `mousePressEvent`:
  - On left press: capture snapshot before changing selection/resize/fill, record `self._drag_start_pos`, set `self._drag_moved = False`.
  - On non-left press during active drag: call `self.cancel_drag(why="button")`, accept event and return.
  - On right press: verify it returns without starting drag.
- Update `mouseMoveEvent`:
  - Check lost capture: if `self._drag_mode != HitZone.NONE and not (event.buttons() & Qt.MouseButton.LeftButton)`:
    Call `self.cancel_drag(why="lost")` and return.
  - Check 3px threshold: if `not self._drag_moved`:
    If `math.hypot(x - self._drag_start_pos.x(), y - self._drag_start_pos.y()) < self._drag_threshold`:
      Return early.
    `self._drag_moved = True`
  - Boundary check for auto-scroll.
- Update `mouseReleaseEvent`:
  - Stop auto-scroll timer.
  - Reset drag state.
- Update `keyPressEvent`:
  - If `event.key() == Qt.Key.Key_Escape` and `self._drag_mode != HitZone.NONE`:
    Call `self.cancel_drag(why="esc")`, accept event and return.
- Add `focusOutEvent`:
  - If `self._drag_mode != HitZone.NONE`:
    Call `self.cancel_drag(why="blur")`.
- Update `contextMenuEvent`:
  - If `self._swallow_secondary_button`:
    Clear flag, accept event and return without opening context menu.
- Add `closeEvent`:
  - Call `self.cancel_drag(why="close")` and stop timers.
- Update sheet switch (`set_sheet` or equivalent):
  - Call `self.cancel_drag(why="api")`.

### Task 3: Write Test Cases in `tests/gui/test_grid_viewport.py`
- Test 3px threshold behavior.
- Test Esc key cancellation (selection restored, preview cleared).
- Test blur / focus out cancellation.
- Test second button cancellation & context menu swallowing.
- Test lost capture cancellation.
- Test column/row resize cancellation (restores geometry).
- Test autofill cancellation (restores without cell value changes).
- Test auto-scroll timer start and cleanup.
- Test right-click does not initiate drag.

### Task 4: Verify Full Regression Suite
- Run `PYTHONPATH=src QT_QPA_PLATFORM=offscreen conda run -n ATBOffice python -m pytest tests/`
- Ensure all tests pass.

### Task 5: Transition to Code Review
- Update `.github-agent-state.yml` to `reviewing`.
- Hand off to `atb-github-code-reviewer`.

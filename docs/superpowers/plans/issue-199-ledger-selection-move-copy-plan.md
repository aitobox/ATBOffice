# Implementation Plan: [Phase 5] 还原 Ledger 选区边框移动与复制 (Issue #199)

## Overview
Implement selection border drag-and-drop for moving and copying cell ranges in ATBOffice Ledger (`grid_viewport.py`), matching the behavior of `.vibeoffice/public/ledger/js/grid.js` and `clipboard.js`.

---

## Tasks & Steps

### Task 1: Add HitZone.BORDER, Hit Testing, and Cursor Updates
- **Files**:
  - Modify `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
  - Test `tests/gui/test_grid_viewport.py`
- **Details**:
  - Add `BORDER` to `HitZone` enum.
  - Implement border edge detection in `hit_test(x, y)`:
    - Within 2px of left/right/top/bottom boundaries of single selection range.
    - Exclude corner resize, headers, and fill handle (which has precedence).
    - Ignore if whole rows/cols or if editor is active.
  - Update hover cursor to `Qt.CursorShape.SizeAllCursor` when `hit.zone == HitZone.BORDER`.
  - Implement double click jump on border in `mouseDoubleClickEvent` (jump to data boundary).
- **Verification**:
  - Write test `test_border_hit_test_and_cursor` in `tests/gui/test_grid_viewport.py`.
  - Run `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_grid_viewport.py -k test_border_hit_test`

### Task 2: Implement Drag State, Move Preview, and Auto-Scroll for Selection Border
- **Files**:
  - Modify `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
  - Test `tests/gui/test_grid_viewport.py`
- **Details**:
  - Add `_move_src_range`, `_move_grab_cell`, `_move_preview_range`, `_move_ctrl_pressed`.
  - In `mousePressEvent`: start border drag on left click in `HitZone.BORDER`.
  - In `mouseMoveEvent` / `_process_drag_at`:
    - Enforce 3px threshold (`_drag_moved`).
    - Calculate delta `(dr, dc)` relative to grab cell.
    - Clamp destination range within grid bounds `(0 <= r < max_rows, 0 <= c < max_cols)`.
    - Set status tip / tooltip with destination range name.
    - Track Ctrl/Meta modifier to toggle move vs copy mode.
  - In `paintEvent`: draw dashed preview rectangle for `_move_preview_range`.
  - In `cancel_drag`: clear preview range and drag state, restoring original selection.
- **Verification**:
  - Write test `test_border_drag_preview_and_cancel` in `tests/gui/test_grid_viewport.py`.
  - Run `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_grid_viewport.py -k test_border_drag`

### Task 3: Implement Data Transfer (Move & Copy), Overwrite Confirmation, and Protection
- **Files**:
  - Modify `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
  - Test `tests/gui/test_grid_viewport.py`
- **Details**:
  - Implement `_holds_data(to_range, except_range=None) -> bool`:
    - Check if cells in destination have values or formulas outside source.
  - In `mouseReleaseEvent`:
    - Check protection (`guard_protect(cell_edit=True)`).
    - If destination holds data, prompt confirmation: `safe_tr("是否替换目标单元格内容？")`.
    - If cancelled, abort move/copy.
  - Implement `move_range(src, to, copy=False)`:
    - Buffer source cells, formulas, formatting, comments, and merges.
    - For copy: copy cells to destination, shift relative formulas via `translate(f, dr, dc)`, replicate merges.
    - For move: clear source cells outside overlap, write to destination, update internal & external formula references via `adjust_move`, move comments and merges.
    - Update selection to destination range.
- **Verification**:
  - Write tests `test_border_move_empty`, `test_border_move_overlapping`, `test_border_copy_ctrl`, `test_border_overwrite_confirmation`, `test_border_protection`.
  - Run `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_grid_viewport.py -k test_border`

### Task 4: Implement Undo / Redo for Selection Move and Copy
- **Files**:
  - Modify `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
  - Test `tests/gui/test_grid_viewport.py`
- **Details**:
  - Implement `undo_stack` / `undo()` and `redo()` on `GridViewport`.
  - Record snapshots before and after `move_range`.
  - Calling `viewport.undo()` restores cells, merges, and selection to pre-drag state.
  - Calling `viewport.redo()` re-applies the move/copy state.
- **Verification**:
  - Write test `test_border_move_undo_redo`.
  - Run `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_grid_viewport.py -k test_border_move_undo_redo`

### Task 5: Full Regression Testing & Parity Verification
- **Files**:
  - Run all tests across the repository.
- **Verification**:
  - `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_grid_viewport.py`
  - `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/modules/spreadsheet/`
  - `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`

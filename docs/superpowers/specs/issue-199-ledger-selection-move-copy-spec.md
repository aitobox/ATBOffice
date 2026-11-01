# Specification: [Phase 5] 还原 Ledger 选区边框移动与复制 (Issue #199)

## 1. Overview & Context
- **Issue**: #199 - [Phase 5] 还原 Ledger 选区边框移动与复制
- **Epic**: #188 - [Epic] 第五期：原版交互与工具栏对齐、稳定性治理
- **Dependency**: #198 (Resolved & Merged)
- **Blocks**: #201
- **Original Source Reference**: `.vibeoffice/public/ledger/js/grid.js` (lines 398-407, 495, 556, 623-631, 737-752, 785-793), `.vibeoffice/public/ledger/js/clipboard.js` (lines 397-480)

## 2. Requirements & Behavioral Specification

### 2.1 Zone Hit Testing & Cursor
- Add `HitZone.BORDER` to `HitZone` enumeration.
- In `GridViewport.hit_test(x, y)`:
  - Active when exactly 1 range is selected (`len(self.selection.ranges) == 1`), editor is not active, and the selection is neither whole columns nor whole rows.
  - Compute viewport pixel bounds for the primary range:
    - `x1 = self.row_header_width + self.geometry_mapper.col_pos(pr.min_c) - scroll_x`
    - `x2 = self.row_header_width + self.geometry_mapper.col_pos(pr.max_c + 1) - scroll_x`
    - `y1 = self.col_header_height + self.geometry_mapper.row_pos(pr.min_r) - scroll_y`
    - `y2 = self.col_header_height + self.geometry_mapper.row_pos(pr.max_r + 1) - scroll_y`
  - Fill handle check (+/- 5px from `(x2, y2)`) takes precedence.
  - Border zone check:
    - Vertical edges: within 2px of `x1` or `x2` and `y1 - 2 <= y <= y2 + 2`.
    - Horizontal edges: within 2px of `y1` or `y2` and `x1 - 2 <= x <= x2 + 2`.
  - When in border zone: return `HitResult(HitZone.BORDER, row=hit_r, col=hit_c)`.
  - Hover cursor: Set cursor to `Qt.CursorShape.SizeAllCursor` (4-way move cursor).
- Double Click on Border:
  - Excel / VibeOffice parity: Jump selection to edge of data in clicked direction.

### 2.2 Drag Interaction
- **Press (`mousePressEvent`)**:
  - When `hit.zone == HitZone.BORDER`:
    - Commit active editor if any.
    - Set `_drag_mode = HitZone.BORDER`.
    - Record `_move_src_range = self.selection.primary_range`.
    - Record `_move_grab_cell = (hit.row, hit.col)`.
    - Record `_move_preview_range = _move_src_range`.
    - Record `_move_ctrl_pressed = bool(modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))`.
    - Take snapshot in `DragSnapshot` for cancellation/restoration.
- **Move (`mouseMoveEvent` / `_process_drag_at`)**:
  - 3px threshold before activating move.
  - Target calculation:
    - `dr = curr_r - grab_r`
    - `dc = curr_c - grab_c`
    - Target rectangle: `r1 = max(0, src.min_r + dr)`, `c1 = max(0, src.min_c + dc)`.
    - Target width/height matches source. Clamped within sheet maximum dimensions.
    - Update `_move_preview_range`.
    - Update `_move_ctrl_pressed`.
    - Show tooltip with target range name (e.g. `B2:C3`).
    - Trigger auto-scroll if dragging past viewport boundaries.
    - Redraw viewport.
- **Painting (`paintEvent`)**:
  - If `_drag_mode == HitZone.BORDER` and `_drag_moved` and `_move_preview_range`:
    - Draw distinct dashed border for preview range: `QPen(self.COLOR_ACTIVE_BORDER, 2, Qt.PenStyle.DashLine)`.
- **Cancel (`cancel_drag`)**:
  - When user presses Esc, clicks secondary mouse button, or loses capture:
    - Discard `_move_src_range`, `_move_preview_range`, `_move_grab_cell`.
    - Restore original selection.
    - Repaint viewport without modifying sheet data.
- **Drop / Release (`mouseReleaseEvent`)**:
  - If `not _drag_moved` or target range matches source range:
    - Reset drag state, repaint, no data changes.
  - Sheet protection check:
    - If `self.guard_protect(cell_edit=True)` returns True, abort.
  - Overwrite Check:
    - Check if destination range has data (value or formula) outside `src` (or anywhere in destination if copying).
    - If data exists, display confirmation message box:
      - Title: `safe_tr("ATBOffice Ledger")`
      - Text: `safe_tr("是否替换目标单元格内容？")` ("Do you want to replace the contents of the destination cells?")
      - Buttons: OK and Cancel.
      - If user cancels: abort drop, leave source data unchanged, selection remains on source.
  - Move vs Copy:
    - If Ctrl/Meta key was pressed: Copy range.
    - Otherwise: Move range.

### 2.3 Data Semantics & Parity Details
- **Snapshot First**: Always snapshot source cells, merges, and comments prior to clearing or writing. This ensures overlapping moves (e.g. A1:A2 to A2:A3) preserve all data.
- **Copy Semantics**:
  - Source cells are untouched.
  - Destination cells are written with cloned cells.
  - Formulas in copied cells are shifted using `translate(formula, dr, dc)`.
  - Merged cells inside source are cloned and shifted by `(dr, dc)` to destination.
  - Comments inside source are duplicated at destination.
- **Move Semantics**:
  - External formulas pointing to overwritten destination cells become `#REF!`.
  - External formulas pointing to source cells update to follow the move (`adjust_move`).
  - Formulas inside moved cells: references to cells within the moved block follow `(dr, dc)`; references to cells outside retain original target.
  - Merged cells inside source are relocated to destination. Overwritten destination merges are cleared.
  - Comments inside source are relocated to destination.
  - Source cells outside destination overlap are cleared (`CellData()`).
- **Undo / Redo Support**:
  - Complete command recorded into `undo_stack` (holding before and after sheet snapshots and selections).
  - Calling `viewport.undo()` restores the previous data and selection.
  - Calling `viewport.redo()` re-applies the move/copy and selection.
- **i18n & Translation**:
  - All user-facing strings wrapped in `safe_tr()`.
  - Default text in Chinese with accurate translation keys.

## 3. Architecture & Class Design
- `HitZone`: Add `BORDER = auto()`.
- `GridViewport`:
  - `_move_src_range: SelectionRange | None`
  - `_move_grab_cell: tuple[int, int] | None`
  - `_move_preview_range: SelectionRange | None`
  - `_move_ctrl_pressed: bool`
  - `_holds_data(to_range, except_range) -> bool`
  - `move_range(src, to, copy=False) -> None`
  - `undo() -> None`, `redo() -> None`
  - Command object / undo recording for reversible sheet state.

## 4. Verification Plan
- Unit and GUI tests in `tests/gui/test_grid_viewport.py`:
  1. `test_border_hit_test`: Cursor and hit zone along all 4 edges, excluding fill handle.
  2. `test_border_drag_preview`: Move drag shows preview range and cancel restores state.
  3. `test_border_move_empty_destination`: Move A1:B2 to D4:E5, assert data moved, source cleared, undo restores.
  4. `test_border_move_overlapping`: Move A1:A2 to A2:A3, verify correct data and no overwrite loss.
  5. `test_border_copy_ctrl`: Ctrl-drag copies data, source remains intact, formulas shifted.
  6. `test_border_overwrite_confirmation`: Target with data prompts confirmation; verify cancel aborts, confirm proceeds.
  7. `test_border_move_formulas`: Formula references inside and outside moved block adjust accurately.
  8. `test_border_move_merges`: Merged cells moved/copied correctly.
  9. `test_border_protection`: Protected sheet blocks move/copy.
  10. `test_undo_redo`: Full undo and redo cycle for move and copy operations.

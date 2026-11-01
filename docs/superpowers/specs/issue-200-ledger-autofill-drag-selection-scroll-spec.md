# Specification: [Phase 5] 完善 Ledger 填充、行列拖选与边缘滚动

## 1. Overview & Context

- **Issue**: [#200](https://github.com/aitobox/ATBOffice/issues/200) - `[Phase 5] 完善 Ledger 填充、行列拖选与边缘滚动`
- **Parent Epic**: #188 (Phase 5 parity, interaction and stability)
- **Reference**: `.vibeoffice/public/ledger/js/grid.js` (lines 50–150, 368–450, 514–635, 685–750)
- **Target Files**:
  - `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
  - `src/atboffice/modules/spreadsheet/views/autofill.py`
  - `src/atboffice/modules/spreadsheet/models/sheet_model.py`
  - `tests/gui/test_grid_viewport.py`
  - `docs/clone/CLONE_DIFF.md`

## 2. Requirements & Parity Analysis

| Feature | Original (`grid.js`) Behavior | Current Python Port Status | Target Implementation |
|---|---|---|---|
| **AutoFill (Bidirectional & Shrink)** | Lines 606–621, 722–736: Down/Up/Right/Left series extrapolation; shrinking clears contracted cells; single cell Ctrl=linear/inc, multi-cell Ctrl=copy. | `AutoFillEngine.auto_fill` handles series, but `grid_viewport.py` does not record undo/redo for autofill or shrink, and status tooltip is missing. | Implement preview vs atomic commit, tooltip preview, batch undo/redo tracking in `_undo_stack`. |
| **Col/Row Drag Selection** | Lines 475–492, 598–600: Header click selects whole col/row; Shift extends from anchor; Ctrl adds new range; drag extends across cols/rows; Esc restores snapshot. | Single-header click selects, but header drag across columns/rows, Shift/Ctrl modifier combinations, and cancel restoration need hardening. | Complete header drag-selection with Shift/Ctrl, continuous drag extension, and snapshot restoration on cancel. |
| **Col/Row Resize** | Lines 375–389, 636–658, 705–720: Dragging boundary shows guide line and tooltip; resizing a selected col/row resizes all selected cols/rows; cancel restores; commit on release. | Mutates single column live without batch resizing of selection, lacks guide line preview and undo/redo. | Distinguish preview (guide line + tooltip) from commit on release; support `colsForResize` / `rowsForResize` batch resizing; record undo/redo. |
| **Edge Auto-Scroll** | Lines 566–579, 132–139: Periodic timer scrolls viewport when pointer is near/past edge; upward/leftward scroll respects frozen panes; skips hidden rows/cols. | Basic pixel scroll delta, does not respect freeze pane boundaries, does not skip hidden rows/cols. | Implement freeze-pane-aware edge detection and hidden row/col skipping on scroll ticks. |
| **Freeze Panes** | Lines 210–239 in `render.js`: Fixed rows/cols at top/left; split line; main scroll pane begins below/right. | Not yet modeled on `GridViewport` / `SheetDataModel`. | Add `freeze_rows` and `freeze_cols` to `SheetDataModel` and `GridViewport`, render split lines and fixed offsets. |
| **Undo / Redo** | Every grid modification is an atomic command on the undo stack. | Border move has undo, but autofill, shrink, and resize lack undo/redo commands. | Unify undo/redo for autofill, shrink, column width resize, and row height resize. |
| **i18n & Localization** | All tooltip and UI texts localized via `safe_tr()`. | Partial hardcoded English strings in some tooltips. | Wrap 100% of user-visible strings in `safe_tr()` / `tr()` and implement dynamic `retranslate_ui()`. |

## 3. Detailed Technical Architecture

### 3.1. AutoFill Engine & Drag Lifecycle
1. **Preview State**:
   - On `mousePressEvent` in `FILL_HANDLE`:
     - Record snapshot: `_fill_start_src = selection.primary_range`, `_fill_preview_range = _fill_start_src`.
     - Record pre-action snapshot in `_drag_snapshot`.
   - On `mouseMoveEvent`:
     - `AutoFillEngine.determine_destination(src, hover_r, hover_c)` returns `(dest, is_shrink)`.
     - Update `_fill_preview_range = dest`.
     - Display status tooltip with target range name or extrapolated value.
     - Paint dashed preview box over destination cells. Model is NOT modified during drag.
   - On `cancel_drag()` (Esc key, lost capture, right-click):
     - Clear `_fill_preview_range` and tooltip, repaint without altering model cells.
   - On `mouseReleaseEvent`:
     - If `_drag_moved` and valid `dest`:
       - Record `before_cells`, `before_merges`, `before_comments`, `before_sel`.
       - Execute `AutoFillEngine.auto_fill(model, src, dest, mode, ctrl_pressed)`.
       - Record `after_cells`, `after_merges`, `after_comments`, `after_sel`.
       - Push atomic command to `_undo_stack`, clear `_redo_stack`.
       - Update selection to `dest`.

### 3.2. Column & Row Drag-Selection
1. **Header Press**:
   - `COL_HEADER`:
     - If `Shift`: extend from anchor column: `min_c = min(anchor_c, hit.col)`, `max_c = max(anchor_c, hit.col)`.
     - If `Ctrl`/`Cmd`: add new column range `SelectionRange(0, hit.col, max_rows - 1, hit.col)` to `selection.ranges`.
     - Else: select single whole column `SelectionRange(0, hit.col, max_rows - 1, hit.col)`.
   - `ROW_HEADER`:
     - If `Shift`: extend from anchor row: `min_r = min(anchor_r, hit.row)`, `max_r = max(anchor_r, hit.row)`.
     - If `Ctrl`/`Cmd`: add new row range `SelectionRange(hit.row, 0, hit.row, max_cols - 1)` to `selection.ranges`.
     - Else: select single whole row `SelectionRange(hit.row, 0, hit.row, max_cols - 1)`.
2. **Header Drag Move**:
   - As pointer moves across columns/rows, update the active selection range to span from anchor to current column/row.
   - When pointer moves past viewport edge, trigger horizontal/vertical auto-scrolling.
3. **Cancel**:
   - Restores pre-drag selection snapshot cleanly.

### 3.3. Column & Row Resizing with Batch Selection
1. **Batch Target Detection**:
   - Define helper methods:
     - `cols_for_resize(col: int) -> list[int]`: If `col` is inside a whole-column selection, return all columns in that selection; otherwise `[col]`.
     - `rows_for_resize(row: int) -> list[int]`: If `row` is inside a whole-row selection, return all rows in that selection; otherwise `[row]`.
2. **Preview vs Commit**:
   - While dragging `COL_RESIZE` / `ROW_RESIZE`:
     - Do not mutate geometry mapper live for the permanent model state; maintain `_resize_preview_pos = (x if col else y)`.
     - Calculate preview delta and size: `w = max(0, orig_size + delta)`.
     - Draw vertical/horizontal guide line across the viewport.
     - Show tooltip: `safe_tr("宽度: {0} ({1} 像素)").format(...)`.
   - On release:
     - Record before/after geometry sizes in undo command:
       `{"type": "col_resize", "cols": cols, "before_sizes": {c: mapper.col_size(c)}, "after_size": w}`.
     - Apply new size to all affected columns/rows.
     - Update scrollbars and repaint.
   - On cancel:
     - Reset preview, clear guide line and tooltip, geometry mapper remains unchanged.

### 3.4. Edge Auto-Scrolling with Freeze Panes & Hidden Rows/Cols
1. **Freeze Panes Properties**:
   - `freeze_rows: int = 0`, `freeze_cols: int = 0` on `SheetDataModel` and accessible via `GridViewport`.
   - Visual split line rendered at bottom of frozen rows and right of frozen columns.
2. **Edge Scroll Logic**:
   - Virtual scroll pane boundary:
     - Top boundary: `col_header_height + frozen_rows_height`.
     - Left boundary: `row_header_width + frozen_cols_width`.
     - Bottom boundary: `viewport.height() - 2`.
     - Right boundary: `viewport.width() - 2`.
   - Scroll speed: 60ms timer step.
   - Skipping hidden rows/columns:
     - Advance scroll position to next visible row/column where `row_size(r) > 0` and `col_size(c) > 0`.
   - Bounds safety: clamp to `[0, max_scroll]`.
   - On each scroll tick, re-execute hit-test and update drag destination.

## 4. Verification & Testing Plan

1. **AutoFill Tests**:
   - Downward and upward fill sequences (numbers, dates, cyclical lists).
   - Horizontal right and left fill sequences.
   - Shrinking range and verifying cell clearing.
   - Undo/redo verification: verifying model restores after undo and re-applies on redo.
   - Drag cancel via Esc key and second button: confirming no modifications occur.
2. **Header Drag-Selection Tests**:
   - Column drag across multiple columns with Shift, Ctrl, and normal drag.
   - Row drag across multiple rows with Shift, Ctrl, and normal drag.
   - Drag-selection across hidden rows/columns.
   - Cancel drag restores previous selection.
3. **Resize Tests**:
   - Resizing single column and row.
   - Batch resizing multiple selected columns and rows.
   - Cancel resize leaves sizes unchanged.
   - Undo and redo resize operations.
4. **Edge Auto-Scroll Tests**:
   - Auto-scroll triggers at edges and stops when within bounds.
   - Upward/leftward auto-scroll respects frozen pane boundaries.
   - Skipping hidden rows and columns during scroll.

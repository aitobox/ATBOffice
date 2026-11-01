# Implementation Plan: [Phase 5] 完善 Ledger 填充、行列拖选与边缘滚动

- **Branch**: `agent/issue-200-ledger-autofill-drag-selection-scroll`
- **Specification**: `docs/superpowers/specs/issue-200-ledger-autofill-drag-selection-scroll-spec.md`
- **Issue**: [#200](https://github.com/aitobox/ATBOffice/issues/200)

## Task Breakdown

### Task 1: Freeze Panes & Geometry Integration
- **Files**:
  - `src/atboffice/modules/spreadsheet/models/sheet_model.py`
  - `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
  - `tests/gui/test_grid_viewport.py`
- **Details**:
  - Add `freeze_rows: int = 0` and `freeze_cols: int = 0` to `SheetDataModel`.
  - Add `freeze_rows` and `freeze_cols` properties and `set_freeze_panes(rows, cols)` to `GridViewport`.
  - Update `paintEvent` to render freeze split line indicator when `freeze_rows > 0` or `freeze_cols > 0`.
  - Add unit test verifying freeze pane initialization and properties.

### Task 2: AutoFill Preview, Tooltip, Shrink, and Undo/Redo Integration
- **Files**:
  - `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
  - `tests/gui/test_grid_viewport.py`
- **Details**:
  - While dragging `FILL_HANDLE`:
    - Show destination tooltip (`fillTip` with target range / extrapolated value).
    - Paint dashed preview border without touching model cells.
    - Cancel drag on Esc / secondary click: restores pre-drag state without committing changes.
  - On mouse release:
    - Support bidirectional fill (Down, Up, Right, Left) and shrink.
    - If shrink: clears contracted cells and selects remaining range.
    - If expand: extrapolates series using `AutoFillEngine.auto_fill`.
    - Push atomic command to `_undo_stack` so that `viewport.undo()` restores cells/selection and `viewport.redo()` re-applies changes.
  - Add GUI tests for fill down, fill up/left, shrink, drag cancel, and undo/redo.

### Task 3: Column & Row Header Drag-Selection
- **Files**:
  - `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
  - `tests/gui/test_grid_viewport.py`
- **Details**:
  - On header press:
    - Support Shift+Click to extend from anchor column/row to clicked column/row.
    - Support Ctrl/Cmd+Click to add a new full column/row range to selection ranges.
  - On header drag move:
    - Continuously extend selection range from anchor to current hovered column/row.
  - On cancel (Esc / lost capture):
    - Revert selection to pre-drag snapshot cleanly.
  - Add GUI tests for Shift-header, Ctrl-header, multi-column/row drag-selection, and cancel.

### Task 4: Column & Row Resizing with Batch Selection & Undo/Redo
- **Files**:
  - `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
  - `tests/gui/test_grid_viewport.py`
- **Details**:
  - Add `cols_for_resize(col: int) -> list[int]` and `rows_for_resize(row: int) -> list[int]`:
    - If `col`/`row` belongs to a whole column/row selection, return all columns/rows in the selection; otherwise `[col]` or `[row]`.
  - In `COL_RESIZE` and `ROW_RESIZE`:
    - Preview guide line and status tooltip (`safe_tr("宽度: {0} 像素")` / `safe_tr("高度: {0} 像素")`).
    - Cancel restores original sizes.
    - On release: apply new sizes to all target columns/rows, and record undo/redo command.
  - Add GUI tests for single resize, batch resize across selected columns/rows, cancel, and undo/redo.

### Task 5: Edge Auto-Scrolling with Freeze Pane Boundaries & Hidden Rows/Cols
- **Files**:
  - `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
  - `tests/gui/test_grid_viewport.py`
- **Details**:
  - Calculate scrolling area boundaries:
    - Top boundary: `col_header_height + frozen_rows_height`.
    - Left boundary: `row_header_width + frozen_cols_width`.
    - Bottom boundary: `viewport.height() - 2`.
    - Right boundary: `viewport.width() - 2`.
  - Auto-scroll ticks advance scrollbar while skipping hidden rows (`row_size == 0`) and hidden columns (`col_size == 0`).
  - Upward/leftward auto-scroll only triggers if drag started inside the scrolling area and scroll position is beyond freeze pane.
  - Add GUI tests for edge scroll trigger, freeze pane boundary clamp, and skipping hidden rows/cols.

### Task 6: Comprehensive Verification & Clone Diff Evidence
- **Files**:
  - `docs/clone/CLONE_DIFF.md`
  - `tests/gui/test_grid_viewport.py`
- **Details**:
  - Run full test suite with `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`.
  - Update `docs/clone/CLONE_DIFF.md` with verified behavior and test evidence.
  - Verify clean code and type safety.

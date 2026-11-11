# Implementation Plan: Issue #343 — Quire Interactive Canvas Ruler & Dynamic Fields Convergence

## Task 1: Implement Undo/Redo Transaction Engine in `WriterCanvasView` & `QuireView`
- **File**: `src/atboffice/modules/writer/views/canvas_view.py`
  - Add `_undo_stack: list[dict[str, Any]]` and `_redo_stack: list[dict[str, Any]]`.
  - Implement `push_undo_command(cmd: dict[str, Any]) -> None`.
  - Implement `undo() -> bool` handling `"paragraph_indent"`, `"paragraph_tabs"`, `"section_margins"`.
  - Implement `redo() -> bool` handling `"paragraph_indent"`, `"paragraph_tabs"`, `"section_margins"`.
  - Implement `can_undo() -> bool` and `can_redo() -> bool`.
- **File**: `src/atboffice/modules/writer/view.py`
  - Expose `undo()`, `redo()`, `can_undo()`, `can_redo()` on `QuireView` forwarding to `canvas_view`.

## Task 2: Connect Ruler Handle Release to Transactional Commands in Rulers
- **File**: `src/atboffice/modules/writer/views/rulers/horizontal_ruler.py`
  - In `mousePressEvent`: Capture initial `_orig_indents`, `_orig_tabs`, `_orig_margins`.
  - In `mouseReleaseEvent`: Compare final values with initial values; if modified, construct undo command and call `canvas.push_undo_command(...)`.
- **File**: `src/atboffice/modules/writer/views/rulers/vertical_ruler.py`
  - In `mousePressEvent`: Capture initial `_orig_margins`.
  - In `mouseReleaseEvent`: If margins modified, construct `"section_margins"` command and call `canvas.push_undo_command(...)`.

## Task 3: Wire Ruler Double-Click to TabsDialog & PageSetupDialog
- **File**: `src/atboffice/modules/writer/view.py`
  - Connect `self.h_ruler.tabs_dialog_requested` to `_on_tabs_dialog_requested()`.
  - Connect `self.h_ruler.page_setup_requested` to `_on_page_setup_requested()`.
  - Connect `self.v_ruler.page_setup_requested` to `_on_page_setup_requested()`.
  - In `_on_tabs_dialog_requested`: launch `TabsDialog`, apply changes via `canvas_view.push_undo_command`, repaginate and refresh.
  - In `_on_page_setup_requested`: launch `PageSetupDialog`, apply changes via `canvas_view.push_undo_command`, repaginate and refresh.
- **File**: `src/atboffice/modules/writer/views/rulers/horizontal_ruler.py` and `vertical_ruler.py`
  - Add helper methods `open_tabs_dialog()` and `open_page_setup_dialog()`.

## Task 4: Implement Multi-Pass Dynamic Field Convergence in Pagination
- **File**: `src/atboffice/modules/writer/layout/pagination.py`
  - Enhance `paginate_document(doc: Document, max_passes: int = 4) -> PaginationResult`.
  - Loop up to `max_passes`, executing `_execute_single_pagination_pass` and `update_fields(doc, res)`.
  - Track pagination state signature `(res.total_pages, tuple(res.section_pages))` in `seen_states` to detect and break circular oscillation loops.
  - Stop early when layout and field values converge.

## Task 5: Implement Comprehensive GUI & Acceptance Test Suite
- **File**: `tests/gui/test_phase9_ruler_and_field_convergence.py`
  - Test indent dragging (first, hanging, left, right) with guide lines and undo/redo.
  - Test tab stop dragging (add, move, drag off >18px to delete) with undo/redo.
  - Test horizontal & vertical margin dragging with undo/redo.
  - Test ruler double-clicking opening `TabsDialog` and `PageSetupDialog`.
  - Test multi-pass dynamic field convergence across `PAGE`, `NUMPAGES`, `DATE`, `TIME`, and `TOC`/`PAGEREF`.

## Task 6: Verification & Quality Gate
- Run `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_phase9_ruler_and_field_convergence.py -v`.
- Run full test suite: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_ruler.py -v`.

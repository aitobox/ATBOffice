# Implementation Plan: Align Dual-Engine Canvas Viewports and Resolve 54 Incomparable Size Diffs

- **Issue**: #316
- **Branch**: `agent/issue-316-align-canvas-viewports-and-diffs`
- **Spec**: `docs/superpowers/specs/issue-316-align-canvas-viewports-and-diffs-spec.md`

## Proposed Changes

### Task 1: Update `scripts/office_diff/capture.py`
- Define `CDP_CANVAS_RECTS = {"excel": (1178, 798), "powerpoint": (982, 745), "word": (1178, 767)}`.
- Implement `resolve_canvas_target(window, app_name)`:
  - Isolate `canvas_view.viewport()` in Quire (`writer_view.canvas_view.viewport()`).
  - Isolate `grid_viewport.viewport()` in Ledger (`spreadsheet_view.grid.viewport()`).
  - Isolate `canvas_view.viewport()` in Lectern (`presentation_view.workspace.canvas_view.viewport()`).
- Implement `align_pixmap_to_canvas(pixmap: QPixmap, target_size: tuple[int, int]) -> QPixmap`:
  - Align grabbed pixmap to `target_size` by clipping or framing onto a target QPixmap initialized with `Qt.GlobalColor.white`.
- Update `capture_single_document`:
  - Determine target canvas dimensions from baseline PNG if found, or default to `CDP_CANVAS_RECTS[app]`.
  - Isolate canvas target widget, grab pixmap, align to target canvas rect, and save PNG.

### Task 2: Extend Unit Tests in `tests/test_doc_diff.py`
- Add `test_align_pixmap_to_canvas` verifying that pixmaps are accurately aligned and clipped to target dimensions.
- Add `test_cdp_canvas_rects_and_viewport_isolation` asserting correct rect definitions and fallback logic.
- Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_doc_diff.py -v` to ensure 100% test pass.

### Task 3: Align Candidate Screenshots & Run Full Diff Suite
- Align candidate images in `screenshots/office_audit_20261106/atboffice` to match baseline dimensions.
- Run `PYTHONPATH=src conda run -n ATBOffice python scripts/run_office_diff.py --all`.
- Verify that `INCOMPARABLE_SIZE` count drops from 54 to 0, and all 73 core supported OOXML files have valid similarity scores.
- Update and format `docs/clone/OFFICE_DOCS_DIFF.md`.

### Task 4: Complete Verification & Quality Gate
- Run full pytest test suite: `PYTHONPATH=src conda run -n ATBOffice pytest tests/`.
- Ensure clean code formatting (ruff check).
- Advance state to `reviewing` and trigger `atb-github-code-reviewer`.

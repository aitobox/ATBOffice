# Task Progress: Issue #292 - [office-diff] 调查 PowerPoint 打开后画布过小及适合窗口缩放

## Status Overview
- Total Chunks: 5
- Completed Chunks: 5
- Current Chunk: All Completed

## Roadmap & Milestones
- [x] Chunk 1: SlideCanvasView Auto-Fit & Defensive Zoom Lifecycle
- [x] Chunk 2: LecternWorkspace Integration & Slide Switching Zoom Retention
- [x] Chunk 3: LecternWindow Zoom Combo & Toolbar Synchronization
- [x] Chunk 4: Capture Script Offscreen Settling & Canvas Viewport Alignment
- [x] Chunk 5: Comprehensive Unit & Regression Tests

## Execution Log
### Chunk 1: SlideCanvasView Auto-Fit & Defensive Zoom Lifecycle
- Executed: Added `zoom_changed` signal, `is_auto_fit` state, defensive `zoom_fit` bounds check (`vw > margin and vh > margin and sw > 0 and sh > 0`), and `resizeEvent`/`showEvent` hooks.
- Verification: Tested with tiny and valid viewports; bounds clamping avoids negative/0.1 zoom.
- Files touched: `src/atboffice/modules/presentation/views/slide_canvas.py`
- Status: Completed

### Chunk 2: LecternWorkspace Integration & Slide Switching Zoom Retention
- Executed: Implemented `is_auto_fit`, `set_zoom`, `fit_to_window`, `zoom_in`, `zoom_out`, and `resizeEvent`. Preserved manual zoom during slide navigation.
- Verification: Verified slide navigation maintains manual zoom when not in auto-fit.
- Files touched: `src/atboffice/modules/presentation/views/workspace.py`
- Status: Completed

### Chunk 3: LecternWindow Zoom Combo & Toolbar Synchronization
- Executed: Connected zoom signals between canvas view and standard toolbar zoom combo. Added `fit_to_window()`, `set_zoom()`, `resizeEvent`, and `showEvent` in `LecternWindow`.
- Verification: Changing combo to "适合比例" fits window; selecting "150%" sets zoom to 1.5.
- Files touched: `src/atboffice/ui/shell/lectern_window.py`
- Status: Completed

### Chunk 4: Capture Script Offscreen Settling & Canvas Viewport Alignment
- Executed: Added `--canvas-only` argument to `capture_doc_atboffice.py`, ensuring offscreen captures settle layouts and support grabbing pure canvas viewports.
- Verification: Captured `libreoffice__TextFittingComparisonWithMSO_3.pptx` in offscreen mode with 1012x658 resolution and proper zoom.
- Files touched: `.agents/skills/atb-office-diff/scripts/capture_doc_atboffice.py`
- Status: Completed

### Chunk 5: Comprehensive Unit & Regression Tests
- Executed: Added 6 comprehensive tests in `tests/test_lectern_canvas_zoom.py` covering defensive zoom fit, auto-fit state transitions, workspace delegation, slide switching preservation, aspect ratio scaling, and zoom combo integration.
- Verification: 6/6 tests passed in `test_lectern_canvas_zoom.py`; all 39 presentation tests passed.
- Files touched: `tests/test_lectern_canvas_zoom.py`
- Status: Completed

# Implementation Plan: Issue #292 - 调查 PowerPoint 打开后画布过小及适合窗口缩放

## Chunk 1: SlideCanvasView Auto-Fit & Defensive Zoom Lifecycle
- **Files**: `src/atboffice/modules/presentation/views/slide_canvas.py`
- **Changes**:
  - Add `zoom_changed = Signal(float)` signal.
  - Add `self._auto_fit: bool = True` in `SlideCanvasView.__init__`.
  - Expose `is_auto_fit` property.
  - Refactor `set_zoom(self, zoom: float, auto_fit: bool = False)`:
    - If `not auto_fit`, set `self._auto_fit = False`.
    - Emit `zoom_changed.emit(self.zoom)`.
  - Refactor `zoom_fit(self) -> None`:
    - Set `self._auto_fit = True`.
    - Check `vw > margin and vh > margin and self._scene.slide_width > 0 and self._scene.slide_height > 0`.
    - Calculate `scale_x = (vw - margin) / self._scene.slide_width`, `scale_y = (vh - margin) / self._scene.slide_height`.
    - Call `self.set_zoom(min(scale_x, scale_y), auto_fit=True)`.
  - Implement `resizeEvent(self, event: QResizeEvent)`:
    - Call `super().resizeEvent(event)`.
    - If `self._auto_fit`, call `self.zoom_fit()`.
  - Implement `showEvent(self, event: QShowEvent)`:
    - Call `super().showEvent(event)`.
    - If `self._auto_fit`, call `self.zoom_fit()`.

## Chunk 2: LecternWorkspace Integration & Slide Switching Zoom Retention
- **Files**: `src/atboffice/modules/presentation/views/workspace.py`
- **Changes**:
  - Implement `set_zoom(self, zoom: float)` -> forwards to `canvas_view.set_zoom(zoom, auto_fit=False)`.
  - Implement `fit_to_window(self)` -> calls `canvas_view.zoom_fit()`.
  - Implement `zoom_in(self)` / `zoom_out(self)` -> forwards to `canvas_view`.
  - Expose `is_auto_fit` property -> returns `canvas_view.is_auto_fit`.
  - In `_refresh_active_slide(self)`:
    - If `self.canvas_view.is_auto_fit`: call `self.canvas_view.zoom_fit()`.
    - Else: re-apply existing zoom to newly loaded scene without resetting manual zoom.
  - Implement `resizeEvent(self, event: QResizeEvent)`:
    - Call `super().resizeEvent(event)`.
    - If `self.canvas_view.is_auto_fit`: call `self.canvas_view.zoom_fit()`.

## Chunk 3: LecternWindow Zoom Combo & Toolbar Synchronization
- **Files**: `src/atboffice/ui/shell/lectern_window.py`
- **Changes**:
  - Connect `canvas_view.zoom_changed` signal to `_sync_zoom_ui`.
  - In `_sync_zoom_ui(self, zoom: float)`:
    - If `workspace.is_auto_fit`:
      - Set `zoom_combo.setCurrentText(safe_tr("适合比例"))`.
    - Else:
      - Set `zoom_combo.setCurrentText(f"{int(round(zoom * 100))}%")`.
  - In `_on_zoom_combo_changed`:
    - Handles "适合比例", "Fit", or custom percentages cleanly.
  - Implement `resizeEvent(self, event: QResizeEvent)` on `LecternWindow` to ensure event propagation.

## Chunk 4: Capture Script Offscreen Settling & Canvas Viewport Alignment
- **Files**: `.agents/skills/atb-office-diff/scripts/capture_doc_atboffice.py`
- **Changes**:
  - Add `--canvas-only` CLI flag.
  - When `--canvas-only` is passed, grab `canvas_view.viewport()` (for PowerPoint) or corresponding inner viewport.
  - Ensure `window.show()` and event draining trigger `zoom_fit` so PowerPoint offscreen captures have correct non-clamped slide scale.

## Chunk 5: Comprehensive Unit & Regression Tests
- **Files**: `tests/test_lectern_canvas_zoom.py`
- **Verification**:
  - Initial load zoom calculation on 16:9 (`libreoffice__TextFittingComparisonWithMSO_3.pptx`) and 4:3 presentations.
  - Window resize updates zoom when auto-fit is active.
  - Manual zoom overrides auto-fit and remains constant during resize.
  - Switching slides preserves manual zoom vs auto-fit.
  - "适合比例" combo selection resets to fit-to-window.
  - Full test suite passes.

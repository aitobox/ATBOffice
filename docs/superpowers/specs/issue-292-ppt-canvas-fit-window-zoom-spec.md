# Specification: Issue #292 - 调查 PowerPoint 打开后画布过小及适合窗口缩放

## 1. Problem Diagnosis & Root Cause Analysis

### 1.1 The Bug
When opening presentations (such as `TextFittingComparisonWithMSO_3.pptx`) in Lectern (`LecternWindow`), the slide in the slide canvas appears extremely small (`zoom = 0.1`, which is the 10% minimum clamp limit) instead of fitting the viewport (~75% zoom for 1440x900).

### 1.2 Root Cause
1. **Pre-Layout Negative/Zero Viewport Calculation**:
   During `LecternWindow.__init__` and `open_file()`, `load_presentation()` is invoked before Qt has displayed or performed layout calculations on the window. At this moment, the `SlideCanvasView.viewport()` has initial dimensions of `98 x 28`.
   In `SlideCanvasView.zoom_fit()`:
   ```python
   margin = 32.0
   scale_y = (vh - margin) / self._scene.slide_height  # (28 - 32) / 540 = -0.0074
   ```
   `min(scale_x, scale_y)` evaluates to a negative number, which is clamped by `set_zoom` to `clamped = max(0.1, min(zoom, 4.0)) = 0.1` (10%).

2. **Missing Resize & Show Event Handling**:
   `SlideCanvasView` and `LecternWorkspace` lacked `resizeEvent` and `showEvent` implementations. When the window is subsequently shown or resized to its full dimensions (e.g. 1440x900), no zoom adjustment occurred, leaving the slide permanently stuck at `zoom = 0.1`.

3. **Missing Integration Methods on `LecternWorkspace`**:
   `LecternWindow` attempts to invoke `ws.set_zoom(scale_val)` and `ws.fit_to_window()`, but neither method existed on `LecternWorkspace`, preventing user zoom combo adjustments from functioning.

4. **Offscreen Capture Viewport Discrepancy**:
   `capture_doc_atboffice.py` grabbed `window.centralWidget()` (which includes thumbnails, notes pane, and right task pane) without draining the event loop after resize to settle the canvas zoom.

---

## 2. Proposed Architectural Design

### 2.1 SlideCanvasView (`slide_canvas.py`)
- **Stateful `auto_fit` flag**: Tracks whether "Fit to Window" mode is active (`self._auto_fit: bool = True`).
- **Defensive `zoom_fit`**: Guards against negative/too-small viewport calculations: only updates zoom if `vw > margin and vh > margin and slide_width > 0 and slide_height > 0`.
- **Event-driven auto-fit**:
  - `resizeEvent`: If `self._auto_fit`, recalculates `zoom_fit()`.
  - `showEvent`: If `self._auto_fit`, recalculates `zoom_fit()`.
- **Manual zoom deactivates auto-fit**: Explicit `set_zoom` or `zoom_in`/`zoom_out` sets `_auto_fit = False`.
- **Signal**: Exposes `zoom_changed = Signal(float)` to update UI toolbars.

### 2.2 LecternWorkspace (`workspace.py`)
- Implement `set_zoom(zoom: float)`, `fit_to_window()`, `zoom_in()`, `zoom_out()`.
- Expose `is_auto_fit` property.
- In `_refresh_active_slide()`, only auto-fit if `canvas_view.is_auto_fit` is True, preserving manual zoom across slide navigation.
- Implement `resizeEvent` to coordinate with canvas view.

### 2.3 LecternWindow (`lectern_window.py`)
- Wire up zoom combo box with two-way synchronization:
  - User selecting "适合比例" triggers `fit_to_window()`.
  - User selecting or typing a percentage triggers `set_zoom(pct / 100.0)`.
  - Canvas zoom changes update the zoom combo text and status bar indicator.
- Implement `resizeEvent` to ensure window resize events propagate cleanly.

### 2.4 Offscreen Capture Tool (`capture_doc_atboffice.py`)
- Add `--canvas-only` option to isolate the pure document canvas (matching `.vibeoffice` `.work` / `.center`).
- Ensure `window.show()` and event loop draining occur before capturing pixmaps.

---

## 3. Implementation Task Checklist

- [ ] Task 1: Enhance `SlideCanvasView` with defensive `zoom_fit`, `auto_fit` lifecycle, `showEvent`, `resizeEvent`, and `zoom_changed` signal.
- [ ] Task 2: Implement `set_zoom`, `fit_to_window`, and resize propagation on `LecternWorkspace`.
- [ ] Task 3: Complete zoom combo integration, toolbar synchronization, and window resize handling in `LecternWindow`.
- [ ] Task 4: Enhance `capture_doc_atboffice.py` to ensure stable layout settling and support `--canvas-only` viewport alignment.
- [ ] Task 5: Write comprehensive automated tests in `tests/test_lectern_canvas_zoom.py` covering initial fit, resizing, manual zoom, aspect ratios, and multi-slide switching.
- [ ] Task 6: Run full test suite and execute `grill-me` stress-test verification.

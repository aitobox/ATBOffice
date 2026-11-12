# Specification: Issue #342 - SlideShow Fullscreen Real-Time Ink Drawing Annotations & Laser Pointer Overlay

## 1. Overview & Objectives
This specification designs the interactive ink annotation overlay, pointer tools (Arrow, Ballpoint Pen, Highlighter, Laser Pointer, Eraser), presentation hotkeys (`B`, `W`, `E`, `Ctrl+A`, `Ctrl+P`, `Ctrl+L`, `Ctrl+E`), and presentation exit ink retention dialog for Lectern in ATBOffice, matching the behavior in `.vibeoffice/public/lectern/js/slideshow.js`.

## 2. Architecture & Components

### 2.1 `SlideAnnotationOverlay` in `src/atboffice/modules/presentation/slideshow/annotation_layer.py`
A dedicated, reusable annotation layer widget or overlay renderer for presentation slide canvases:
- **Data Models**:
  - `AnnotationPoint`: Represents `(x, y)` in normalized or slide canvas coordinates.
  - `AnnotationStroke`: Freehand vector stroke with `points`, `color`, `width`, `alpha`, `is_highlighter`.
- **Overlay Responsibilities**:
  - Manages active tool mode: `"arrow"`, `"pen"`, `"highlighter"`, `"laser"`, `"eraser"`.
  - Manages per-slide dictionary of strokes: `dict[int, list[AnnotationStroke]]`.
  - Real-time stroke tracking on mouse events (`mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent`).
  - Laser pointer position tracking and halo rendering (radial gradient glow + bright central core).
  - Eraser stroke hit-testing (point-to-point / point-to-segment distance check).
  - Clear / erase all ink on slide.
  - Ink retention converter: convert strokes into `Shape` instances (`geom="freeform"`, `poly=pts`, `line=Line(...)`) to persist into `slide.shapes`.
- **Signals**:
  - `strokeAdded(slide_idx, stroke)`
  - `strokeErased(slide_idx, stroke_idx)`
  - `laserMoved(pos)`
  - `modeChanged(tool, color)`

### 2.2 `SlideShowHud` Enhancements in `src/atboffice/modules/presentation/slideshow/slide_hud.py`
- Add **Laser Pointer (`Ctrl+L`)** option to `_build_pen_menu`:
  - `act_laser = menu.addAction(safe_tr("激光笔 (&L)"))`
  - Connected to `_select_pen_tool("laser")`
- Support tool selection across: Arrow, Pen, Highlighter, Laser, Eraser, Clear.
- Tooltips and accelerator keys for pointer options.
- 100% `safe_tr()` localization and `retranslate_ui()`.

### 2.3 `SlideShowView` Integration in `src/atboffice/modules/presentation/slideshow/slideshow_view.py`
- Integrate `SlideAnnotationOverlay`:
  - Delegate or synchronize ink strokes and laser pointer rendering via `SlideAnnotationOverlay`.
  - Coordinate system mapping: map viewport coordinates $(vw, vh)$ with letterbox offset $(ox, oy)$ and scale $k$ to slide units $(pw, ph)$.
- Keyboard Shortcuts in `keyPressEvent`:
  - `B` / `.`: Toggle Black Screen (`toggle_blank("#000000")`).
  - `W` / `,`: Toggle White Screen (`toggle_blank("#FFFFFF")`).
  - `E` (without Ctrl): Erase all ink on the current slide.
  - `Ctrl+A`: Set pointer tool to Arrow.
  - `Ctrl+P`: Set pointer tool to Ballpoint Pen.
  - `Ctrl+L`: Set pointer tool to Laser Pointer.
  - `Ctrl+E`: Set pointer tool to Eraser.
  - `Ctrl+H`: Hide pointer cursor.
- Exit Prompt on `end_show(prompt_ink=True, keep_ink=False)`:
  - If `prompt_ink` is True and `has_ink` is True across any slide:
    - Display standard PowerPoint exit prompt: `"Do you want to keep your ink annotations?"` / `"是否保留墨迹批注？"` with Keep / Discard buttons.
    - If Keep is chosen, convert strokes into freeform `Shape`s and append to `slide.shapes`.

### 2.4 GUI Acceptance Tests in `tests/gui/test_phase9_slideshow_annotations.py`
- Test `SlideAnnotationOverlay` tool switching, pen drawing, highlighter drawing, eraser removal, laser pointer tracking, and clear.
- Test `SlideShowHud` pointer menu item generation and signals.
- Test `SlideShowView` hotkeys (`B`, `W`, `E`, `Ctrl+L`, `Ctrl+P`, etc.).
- Test `end_show` ink retention conversion into slide shapes.

## 3. Edge Cases & Safeguards
- **Coordinate Transformations**: Handle resizing, different aspect ratios (4:3, 16:9, widescreen), zero dimensions gracefully.
- **Eraser Hit Radius**: Threshold around 20-30 slide coordinates so small strokes can be easily targeted.
- **Modifier Distinctions**: Do not mistake `Ctrl+E` (switch to eraser) with `E` (erase all ink on current slide).
- **Non-Interactive / Headless Mode**: When running tests with `prompt_ink=False` or simulated clicks, avoid modal blocking.

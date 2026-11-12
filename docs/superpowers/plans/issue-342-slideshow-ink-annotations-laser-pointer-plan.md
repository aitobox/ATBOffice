# Implementation Plan: Issue #342 - SlideShow Fullscreen Real-Time Ink Drawing Annotations & Laser Pointer Overlay

## Overview
Implement real-time vector ink annotations, pointer tool selection (Pen, Highlighter, Laser Pointer, Eraser), keyboard shortcuts (`B`, `W`, `E`, `Ctrl+A`, `Ctrl+P`, `Ctrl+L`, `Ctrl+E`), and presentation exit retention dialog for Lectern fullscreen SlideShowView.

## Proposed Changes

### 1. `tests/gui/test_phase9_slideshow_annotations.py`
- Test suite with TDD coverage:
  - `test_annotation_overlay_modes_and_strokes`: Tests `SlideAnnotationOverlay` with pen, highlighter, eraser, and clear.
  - `test_annotation_overlay_laser_pointer`: Tests laser movement signal and position tracking.
  - `test_annotation_overlay_convert_to_shapes`: Tests exporting strokes to `Shape` instances for persistence.
  - `test_slideshow_hud_laser_pointer_menu`: Tests HUD pen menu includes Laser Pointer and emits `("laser", ...)`.
  - `test_slideshow_view_hotkeys_and_blanking`: Tests `B`, `W`, `E`, `Ctrl+L`, `Ctrl+P`, `Ctrl+A`, `Ctrl+E`.
  - `test_slideshow_view_end_show_ink_retention`: Tests `end_show(prompt_ink=False, keep_ink=True)` preserving annotations on `slide.shapes`.

### 2. `src/atboffice/modules/presentation/slideshow/annotation_layer.py`
- Define `AnnotationStroke` dataclass.
- Define `SlideAnnotationOverlay` (inheriting from `QWidget`):
  - Manages strokes per slide index.
  - Supports tools: `"arrow"`, `"pen"`, `"highlighter"`, `"laser"`, `"eraser"`.
  - Maps widget coordinates to slide coordinates.
  - Handles mouse events to capture freehand ink paths.
  - Renders laser pointer dot and halo gradient.
  - Hit tests strokes for eraser.
  - Exports ink strokes into `Shape` instances (`geom="freeform"`).
  - Provides full `safe_tr` localization support.

### 3. `src/atboffice/modules/presentation/slideshow/slide_hud.py`
- In `_build_pen_menu`:
  - Add Laser Pointer action: `act_laser = menu.addAction(safe_tr("激光笔 (&L)"))`
  - Ensure menu correctly reflects current tool selection.
- Update `retranslate_ui()` for any new items.

### 4. `src/atboffice/modules/presentation/slideshow/slideshow_view.py`
- Embed or connect `SlideAnnotationOverlay`.
- Handle `keyPressEvent`:
  - `Qt.Key.Key_B`, `Qt.Key.Key_Period` -> toggle black screen.
  - `Qt.Key.Key_W`, `Qt.Key.Key_Comma` -> toggle white screen.
  - `Qt.Key.Key_E` without modifier -> erase all ink on current slide.
  - `Ctrl+A` -> switch tool to arrow.
  - `Ctrl+P` -> switch tool to pen.
  - `Ctrl+L` -> switch tool to laser.
  - `Ctrl+E` -> switch tool to eraser.
- Laser pointer drawing in `paintEvent` or via overlay.
- `end_show(prompt_ink: bool = True, keep_ink: bool = False)`:
  - If has ink and `prompt_ink`: show QMessageBox asking to keep annotations.
  - If keep_ink: convert strokes into `Shape` and append to `slide.shapes`.

## Verification Commands
```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_phase9_slideshow_annotations.py -v
QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_slideshow.py tests/gui/test_presenter_view.py -v
```

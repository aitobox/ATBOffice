# Implementation Plan: Lectern 双屏演讲者控制台 (Speaker View)

## Task Breakdown

### Task 1: Data Structures & Ink Engine
- Define `InkPoint` and `InkStroke` data structures.
- Implement ink stroke serialization, rendering with alpha/width/color, and radius-based hit testing for eraser.

### Task 2: Interactive Slide Canvas (`InteractiveSlideCanvas`)
- Implement custom `QWidget` that renders:
  - The current slide image scaled with aspect ratio preservation.
  - Active ink strokes for the current slide.
  - Laser pointer red dot with translucent halo/radial gradient.
- Handle mouse events:
  - Drawing pen/highlighter strokes.
  - Moving laser pointer.
  - Erasing strokes on mouse press/move when in eraser mode.
  - Emitting signals: `slideAdvanced`, `strokeAdded`, `strokeErased`, `laserMoved`.

### Task 3: Presenter Console UI Architecture (`PresenterConsole` / `PresenterView`)
- Build main window / widget with Fusion dark-mode-compatible presentation styling.
- Top control header:
  - Elapsed timer (hours:minutes:seconds) with Pause/Resume (`❚❚` / `▶`) and Reset (`↺`).
  - Real-time current wall clock (HH:MM:SS) updated every second.
  - Screen indicator and "Swap Displays" button.
  - End show button ("结束放映").
- Main split view:
  - Left side: `InteractiveSlideCanvas` (current slide) + navigation toolbar (Prev, Next, Tool selector, Black/White screen).
  - Right side:
    - Upper: Next slide preview thumbnail & title.
    - Lower: Speaker notes text area with Zoom In (`A+`) and Zoom Out (`A-`) buttons.
- Bottom Slide Drawer / Thumbnails strip:
  - Toggle button to expand/collapse thumbnail drawer.
  - Clickable slide thumbnails for smooth direct jumping without screen flash.

### Task 4: Dual-Screen Synchronization & Lifecycle Management
- Detect system displays using `QGuiApplication.screens()`.
- Create or link with an audience `SlideShowView`.
- Synchronize slide navigation, blank screen toggling, and ink annotations between presenter console and audience display.
- Handle show end: prompt user whether to keep ink annotations if any strokes were created during the session.

### Task 5: Internationalization (i18n) & Polish
- Ensure 100% of UI strings are wrapped in `safe_tr()`.
- Implement `retranslate_ui()` for dynamic language updates.

### Task 6: Unit & GUI Test Matrix
- Write comprehensive tests in `tests/gui/test_presenter_view.py`.
- Test all components: timer, navigation, notes zoom, ink & laser, dual-screen sync, drawer jump, end show.
- Run tests with `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_presenter_view.py -v`.

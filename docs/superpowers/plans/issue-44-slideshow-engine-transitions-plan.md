# Implementation Plan: Lectern Fullscreen Slide Show Engine & 58 Transitions

## Summary
Implements the full slide show presentation engine (`src/atboffice/modules/presentation/slideshow/`) including the complete 58-transition catalogue with QPainter visual rendering algorithms, the fullscreen double-buffered `SlideShowView` viewport with keyboard/mouse navigation, context menu, blanking, popbar, and timing control, and connects it to `LecternWorkspace` via F5 / Shift+F5 shortcuts.

---

## Tasks

### Task 1: Transitions Catalogue & Metadata Lookups
- **File**: `src/atboffice/modules/presentation/slideshow/transitions.py`
- **Details**:
  - `TransitionEffect`: Metadata container (key, name, type, category, dir, thruBlk, spokes, orient, dur, spd).
  - `TRANSITION_CATALOGUE`: 58 distinct transitions (plus 'none' and 'random') mapped directly from PowerPoint 2003 / `.vibeoffice/slideshow.js`.
  - Lookup functions: `get_transition_duration(trans)`, `get_transition_name(trans)`, `list_transitions()`.
- **Test**: `tests/unit/presentation/test_transitions.py::test_transition_catalogue`

### Task 2: Slide Rendering & 58 Transition Frame Rendering Algorithms
- **File**: `src/atboffice/modules/presentation/slideshow/transitions.py`
- **Details**:
  - `render_slide_to_image(slide: Slide, presentation: Presentation, width: int, height: int) -> QImage`:
    High-fidelity rendering of slide background (from design/theme) and all shapes (geometries, solid/gradient fills, borders, text approximations) to an ARGB32 `QImage`.
  - `render_transition_frame(painter: QPainter, img_from: QImage, img_to: QImage, trans: Transition, progress: float, width: int, height: int)`:
    High-performance QPainter 2D transition composition:
    - `cut` (normal, thruBlk)
    - `fade` (smooth alpha blend, thruBlk)
    - `push` (4 directions: d, l, r, u)
    - `cover` (8 directions: d, l, r, u, ld, lu, rd, ru)
    - `pull` / uncover (8 directions: d, l, r, u, ld, lu, rd, ru)
    - `wipe` (4 directions: d, l, r, u)
    - `split` (4 variants: horzIn, horzOut, vertIn, vertOut)
    - `blinds` (horz, vert with 6 rotating slats)
    - `comb` (horz, vert with interleaved moving strips)
    - `checker` (horz, vert alternating grid reveal)
    - `circle`, `diamond`, `plus` (expanding shape masks)
    - `zoom` / box (in, out)
    - `wedge` (conic dual-sweep)
    - `wheel` (1, 2, 3, 4, 8 spokes clockwise scan)
    - `randomBar` (horz, vert pseudo-random strips)
    - `strips` (4 diagonal staircase wipes: ld, lu, rd, ru)
    - `dissolve` (pixelated grid dissolve)
    - `newsflash` (720-degree spin + scale-up)
    - `random` (randomly selects one of above)
- **Test**: `tests/unit/presentation/test_transitions.py::test_render_transitions`

### Task 3: SlideShowView Fullscreen Presentation Viewport
- **File**: `src/atboffice/modules/presentation/slideshow/slideshow_view.py`
- **Details**:
  - `SlideShowView(QWidget)`:
    - Frameless / fullscreen presentation window with pure black stage and double-buffered QPainter blitting.
    - 60 FPS animation loop driven by precision monotonic timer and 16ms QTimer.
    - Slide navigation state: `order`, `pos`, `in_transition`, `blank` (black/white), `ended`, `goto_buf`.
    - Auto-advance timing (`slide.transition.after`) and loop playback (`presentation.show.loop`).
    - Mid-transition interruption: clicking or pressing a key finishes current transition instantly.
    - Keyboard input handling:
      - Next: Space, Enter, PageDown, Right, Down, 'N'
      - Prev: PageUp, Left, Up, Backspace, 'P'
      - First/Last: Home, End
      - Blank screen: 'B' / '.' (black), 'W' / ',' (white)
      - End show: Esc
      - Direct slide jump: Digits 0-9 followed by Enter
    - Mouse input handling:
      - Left-click to advance
      - Wheel up/down to page
      - Idle cursor auto-hiding after 3 seconds of inactivity
    - Right-click Context Menu (`QMenu`):
      - 下一页 (Next), 上一页 (Previous), 定位到幻灯片 (Go to Slide -> submenu of slides)
      - 屏幕 (Screen -> 黑屏 Black Screen, 白屏 White Screen, 暂停/继续 Pause/Resume)
      - 结束放映 (End Show)
    - Popbar: On-screen floating navigation pill at bottom-left (Previous, Menu, Next)
    - End-of-show screen ("放映结束，单击鼠标退出。")
    - Full i18n support with `safe_tr()` and `retranslate_ui()`.
- **Test**: `tests/gui/test_slideshow.py::test_slideshow_navigation`

### Task 4: Workspace & PresentationView Integration
- **Files**:
  - `src/atboffice/modules/presentation/views/workspace.py`
  - `src/atboffice/modules/presentation/view.py`
- **Details**:
  - Add `start_slideshow(from_current: bool = False) -> SlideShowView` to `LecternWorkspace`.
  - Connect keyboard shortcuts: F5 (from slide 0), Shift+F5 (from active slide).
  - Expose `start_slideshow` on `PresentationView`.
- **Test**: `tests/gui/test_slideshow.py::test_workspace_slideshow_launch`

### Task 5: Full Test Suite Verification & Quality Gate
- **Files**:
  - `tests/unit/presentation/test_transitions.py`
  - `tests/gui/test_slideshow.py`
- **Details**:
  - Verify 100% test pass on transitions and slideshow GUI.
  - Verify zero regressions in full project test suite.

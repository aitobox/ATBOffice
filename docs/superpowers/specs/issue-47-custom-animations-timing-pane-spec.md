# Technical Specification: 50+ Custom Animations & Timing Task Pane

## 1. Overview & Objectives

Port the complete PowerPoint 2003 custom animation engine and timing task pane from `.vibeoffice` (`.vibeoffice/public/lectern/js/slideshow.js` and `.vibeoffice/public/lectern/js/panes.js`) to PySide6/Python.

Key capabilities:
1. **50+ Effect Catalogue**: Complete set of Entrance (22), Emphasis (5), Exit (17), and Motion Paths (8) with directions, speeds, and easing curves.
2. **Animation Model & Serialization**: Enriched `Animation` data class supporting classes (`entr`, `emph`, `exit`, `path`), effect types, directions, triggers (`click`, `with`, `after`), duration, delay, and paragraph builds (`by='para'`).
3. **Step Compilation & 60 FPS Interpolation**: `compile_steps()` groups animations into build steps according to trigger rules, with smooth QTimer-driven 60 FPS transformation and opacity interpolation.
4. **Interactive Custom Animation Task Pane (`AnimationPane`)**: Right-side dockable widget with Add Effect cascading menu, trigger/direction/speed selectors, reordering (Up/Down), deletion, and preview playback.
5. **SlideShow Integration**: `SlideShowView` seamlessly steps through object animations on Click/Space before advancing to the next slide, with `finish_now()` on rapid click.
6. **Enterprise-grade i18n & Error Handling**: Comprehensive bilingual localization (English / Simplified Chinese), defensive validation against deleted/missing shapes, and clean resource cleanup.

---

## 2. Architecture & Module Design

```
src/atboffice/modules/presentation/
├── models/
│   └── slide.py                  <- Extended Animation dataclass
├── slideshow/
│   ├── animations.py             <- Effect catalogue, easing, frame math, step compiler & controller
│   └── slideshow_view.py         <- Enhanced with animation step progression
└── views/
    └── animation_pane.py         <- PySide6 AnimationPane widget with full i18n
```

### 2.1 Effect Catalogue (`animations.py`)
- **Entrance (`entr`)**: appear, blinds, box, checkerboard, circle, diamond, dissolve, fade, flyIn, peekIn, plus, randomBars, split, strips, wedge, wheel, wipe, zoom, ascend, descend, expand, spinner (22 effects).
- **Emphasis (`emph`)**: growShrink, spin, transparency, teeter, blink (5 effects).
- **Exit (`exit`)**: disappear, blinds, box, checkerboard, circle, diamond, dissolve, fade, flyOut, peekIn, plus, randomBars, split, strips, wedge, wheel, wipe, zoom, descend (17 effects).
- **Motion Paths (`path`)**: right, left, up, down, diagDR, diagUR, circle, bounce (8 effects).
- **Directions**: DIR8 (8 directions), DIR4 (4 directions), HV (Horizontal/Vertical), INOUT (In/Out), SPLIT (4 split modes), DIAG (4 diagonal modes), SPOKES (1/2/3/4/8 spokes).
- **Speed Presets**: Very Slow (5000ms), Slow (3000ms), Medium (2000ms), Fast (1000ms), Very Fast (500ms).

### 2.2 Animation Frame Computation & Transformation
For a target shape at normalized progress $t \in [0, 1]$:
- Ease curves: `ease_out(t) = 1 - (1 - t)^3`, `ease_in_out(t) = 2*t^2 if t < 0.5 else 1 - (-2*t + 2)^2 / 2`.
- Frame state produces:
  - `opacity`: float in [0.0, 1.0]
  - `translate`: (dx, dy) in pixels
  - `scale`: (sx, sy) scaling factor
  - `rotation`: degrees around center
  - `visible`: boolean visibility flag
  - `clip_rect` or wipe ratio for reveals

### 2.3 Compilation of Steps (`compile_steps`)
- Multi-paragraph shapes with `by='para'` are expanded into individual paragraph build items.
- Items starting with `click` begin a new `AnimationStep`.
- Items starting with `with` or `after` are attached to the current `AnimationStep` with computed relative offsets.
- Each item computes `start_time` and `end_time` relative to the step start.

### 2.4 AnimationPane UI
- **Add Effect**: Dropdown button with QMenu: Entrance, Emphasis, Exit, Motion Paths.
- **Remove**: Button to remove selected effect.
- **Modify Options**: Start (On Click, With Previous, After Previous), Direction, Speed (Very Slow to Very Fast).
- **List View**: QListWidget displaying step index, trigger icon, star color, and effect title + shape name.
- **Re-Order**: Up / Down buttons.
- **Preview & Slide Show**: Play slide animation in canvas or trigger fullscreen slideshow.

---

## 3. Verification Plan
- Unit test suite: `tests/gui/test_animations.py`
  - Catalogue query and metadata verification.
  - Easing functions and frame math tests.
  - Step compilation with triggers (`click`, `with`, `after`, `para`).
  - AnimationPane creation, adding effects, modifying properties, reordering, deleting.
  - SlideShowView stepping through animations and clicking to advance.
- Full regression: `pytest tests/` passing 100%.

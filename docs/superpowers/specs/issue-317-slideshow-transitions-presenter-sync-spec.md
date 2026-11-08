# Specification: SlideShow Smooth Transition Animations and Presenter View Sync

**Issue**: [#317](https://github.com/aitobox/ATBOffice/issues/317)  
**Parent Epic**: #308 (Phase 8 Step 9 of 12)  
**Module**: Lectern Presentation  
**Status**: In Progress  

---

## 1. Overview & Problem Statement

In Lectern's slide presentation engine:
1. `slideshow_view.py` and `presenter_view.py` existed with basic transitions, but transitions (wipe, push, fade) abruptly cut off when controlled from Presenter View due to premature calls to `finish_transition_now()`.
2. Presenter View bypassed sequential animation steps and jumped directly across slides when Spacebar / PageDown / Arrow keys were pressed.
3. Presenter View lacked two-way live synchronization of presentation elapsed time, speaker notes, and next-slide preview with the audience viewport (including respecting hidden slides and loop modes).
4. `SlideShowView`'s ink rendering contained a latent `AttributeError: '_curr_idx'` bug.

## 2. Requirements & Acceptance Criteria

- **AC-1 (Smooth 60fps Transition Player)**: Implement a dedicated `SlideTransitionPlayer` using `QTimeLine` (with 16ms update interval) for slide transitions (fade, push, wipe, etc.), supporting smooth normalized progress interpolation (`0.0` to `1.0`), pausing, cancelling, and instant finish.
- **AC-2 (Sequential Key Navigation Progression)**: Support Spacebar, PageDown, Right Arrow, Down Arrow, Return, N for forward sequential progression (completing active animations -> advancing animation steps -> triggering slide transitions) and Left Arrow, Up Arrow, PageUp, Backspace, P for backward progression in both `SlideShowView` and `PresenterConsole`.
- **AC-3 (Presenter View Synchronization)**:
  - **Speaker Notes**: Dynamically render notes with zoom controls (`A+`, `A-`) and empty state notice (`无演讲者备注`).
  - **Live Elapsed Timer**: Synchronize presentation elapsed time, pause/resume, and reset states between `SlideShowView` and `PresenterConsole`.
  - **Next-Slide Preview**: Accurately render thumbnail and slide title of the next upcoming slide (respecting `hidden` slide filtering and loop settings).
- **AC-4 (Verification & Zero Regressions)**: Add comprehensive unit and integration test suite in `tests/unit/presentation/test_slideshow_playback.py`, verifying transition player frames, key navigation sequences, timer synchronization, and presenter console synchronization.

---

## 3. Architecture & Design

### 3.1 `SlideTransitionPlayer` Class
Location: `src/atboffice/modules/presentation/slideshow/transitions.py`
- Inherits: `QObject`
- Wraps: `QTimeLine` (duration configurable, update interval 16ms = ~60 FPS)
- Signals:
  - `frameChanged(float progress)`: Emits progress in range `[0.0, 1.0]`.
  - `finished()`: Emits when timeline finishes or is explicitly finished.
- Methods:
  - `play(trans: Transition, duration_ms: int | None = None)`
  - `finish_now()`: Stops timeline and emits `frameChanged(1.0)` followed by `finished()`.
  - `stop()`: Aborts playback without emitting completion.
  - `is_playing -> bool`: Returns whether animation is currently active.
  - `progress -> float`: Returns current progress.

### 3.2 `SlideShowView` Enhancements
Location: `src/atboffice/modules/presentation/slideshow/slideshow_view.py`
- Integrates `SlideTransitionPlayer` instead of basic raw `QTimer`.
- Presentation Clock & Elapsed Timer:
  - `self.elapsed_seconds: int = 0`
  - `self.is_timer_running: bool = True`
  - `self._presentation_timer = QTimer(self)` (1000ms tick, emits `timerTicked(int)`)
  - `pause_timer()`, `resume_timer()`, `reset_timer()`
- Navigation & Next Slide Query:
  - `get_next_slide_index() -> int | None`: Scans `self.order` starting from `slide_pos + 1` for the next non-hidden slide, or wraps around if `loop` is active, returning `None` if presentation ends.
- Ink bug fix:
  - Line 819: Replace `self._curr_idx` with `self.current_slide_index`.
- Presenter Console integration:
  - `show_presenter_view()` method and context menu entry `safe_tr("显示演讲者视图 (&V)")`.

### 3.3 `PresenterConsole` Synchronization
Location: `src/atboffice/modules/presentation/slideshow/presenter_view.py`
- Navigation forwarding:
  - When `audience_view` is connected:
    - `next_slide()` forwards to `self.audience_view.next_slide()`.
    - `prev_slide()` forwards to `self.audience_view.prev_slide()`.
  - Do NOT call `finish_transition_now()` in `goto_slide` when triggered from legitimate progression, allowing smooth transition playback.
- Timer Synchronization:
  - Connect to `audience_view.timerTicked` (or bind `elapsed_seconds` and `is_timer_running`).
  - Forward `toggle_timer()` and `reset_timer()` actions to `audience_view`.
- Next-Slide Preview:
  - Call `audience_view.get_next_slide_index()` when `audience_view` is present to determine the actual next slide (avoiding hidden slides).

---

## 4. Edge Cases Analyzed

1. **Empty Presentation (0 slides)**: View initializes safely, displays empty stage, does not crash on timer or navigation.
2. **Single Slide (1 slide)**: Next slide advances to "End of Show" or stays at slide 1 without looping.
3. **All Remaining Slides Hidden**: Next-slide preview correctly indicates "放映结束" (End of show) instead of showing a hidden slide.
4. **Rapid Keypress / High-Frequency Triggers**: If a transition or custom animation is playing when Spacebar/PageDown is pressed, the active step finishes cleanly and the next step is triggered without dropped frames or timer leaks.
5. **Window Close & Cleanup**: On `closeEvent`, all timers (`_presentation_timer`, `_auto_timer`, `_idle_timer`, `SlideTransitionPlayer`, `AnimationStepPlayer`) are stopped cleanly to avoid re-entrancy and Qt memory leaks.

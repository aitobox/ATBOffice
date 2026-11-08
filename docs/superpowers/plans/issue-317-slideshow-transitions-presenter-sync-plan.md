# Implementation Plan: SlideShow Smooth Transition Animations and Presenter View Sync

**Issue**: [#317](https://github.com/aitobox/ATBOffice/issues/317)  
**Spec**: `docs/superpowers/specs/issue-317-slideshow-transitions-presenter-sync-spec.md`  
**Status**: Ready for Execution  

---

## Task Breakdown

### Task 1: Implement `SlideTransitionPlayer` in `transitions.py`
- **File**: `src/atboffice/modules/presentation/slideshow/transitions.py`
- **Details**:
  - Implement `SlideTransitionPlayer(QObject)` using `QTimeLine`.
  - Configurable duration (default based on `get_transition_duration(trans)`).
  - Interval: 16ms (~60 FPS).
  - Signals: `frameChanged = Signal(float)`, `finished = Signal()`.
  - Methods: `play(trans: Transition, duration_ms: int | None = None)`, `finish_now()`, `stop()`, properties `is_playing`, `progress`, `active_transition`.
  - Export `SlideTransitionPlayer` in `__all__`.

### Task 2: Enhance `SlideShowView` in `slideshow_view.py`
- **File**: `src/atboffice/modules/presentation/slideshow/slideshow_view.py`
- **Details**:
  - Replace manual `_anim_timer` with `SlideTransitionPlayer`.
  - Connect player's `frameChanged` to update and `finished` to complete transition.
  - Implement presentation elapsed timer:
    - `_presentation_timer: QTimer`, 1000ms tick.
    - `timerTicked = Signal(int)`.
    - `elapsed_seconds: int`, `is_timer_running: bool`.
    - `pause_timer()`, `resume_timer()`, `reset_timer()`.
  - Implement `get_next_slide_index() -> int | None`:
    - Checks next non-hidden slide in `order`, handles `loop` mode.
  - Fix latent bug: Replace `self._curr_idx` with `self.current_slide_index` at line 819.
  - Add `show_presenter_view()` and context menu action `safe_tr("显示演讲者视图 (&V)")`.

### Task 3: Upgrade `PresenterConsole` Synchronization in `presenter_view.py`
- **File**: `src/atboffice/modules/presentation/slideshow/presenter_view.py`
- **Details**:
  - Update `next_slide()` and `prev_slide()`:
    - If `self.audience_view` is connected, delegate to `self.audience_view.next_slide()` / `prev_slide()` to trigger sequential animations and smooth transitions.
  - In `goto_slide()`:
    - Do not forcibly abort `finish_transition_now()` during normal navigation.
  - Update `_bind_audience_view()`:
    - Connect `audience_view.timerTicked` to synchronize elapsed timer.
    - Connect `audience_view.slideChanged` to update current slide, speaker notes, and next slide preview.
  - Update `_load_next_slide_preview()`:
    - Use `audience_view.get_next_slide_index()` if available to filter out hidden slides and respect presentation loop settings.
  - Ensure `toggle_timer()` and `reset_timer()` synchronize back to `audience_view`.

### Task 4: Write Comprehensive Unit Tests
- **File**: `tests/unit/presentation/test_slideshow_playback.py`
- **Details**:
  - Test `SlideTransitionPlayer` (lifecycle, 60fps frames, `finish_now`, `stop`).
  - Test `SlideShowView` transition playback and key navigation (Spacebar, PageDown, Arrow keys).
  - Test sequential animation progression (anim steps before slide transition).
  - Test `PresenterConsole` synchronization:
    - Speaker notes rendering and zoom.
    - Live presentation timer sync and pause/resume/reset.
    - Next slide preview with hidden slide filtering.

### Task 5: Project-Wide Verification & Regressions Check
- Run `pytest tests/unit/presentation/test_slideshow_playback.py`
- Run `pytest tests/gui/test_slideshow.py tests/gui/test_presenter_view.py`
- Run full presentation test suite.

# Implementation Plan: 50+ Custom Animations & Timing Task Pane

## Task 1: Enhance `Animation` Model in `slide.py`
- Update `Animation` dataclass in `src/atboffice/modules/presentation/models/slide.py`.
- Add `cls`, `eff`, `dir`, `start`, `dur`, `delay`, `by`, `repeat`, `amount`, `pts`.
- Maintain property getters/defaults for `type`, `trigger`, and `duration` for backward compatibility.
- Update `to_dict()` and `from_dict()` for full serialization compatibility with both old and new formats.

## Task 2: Implement `animations.py` Engine
- Create `src/atboffice/modules/presentation/slideshow/animations.py`.
- Catalogue:
  - `ENTR_EFFECTS` (22)
  - `EMPH_EFFECTS` (5)
  - `EXIT_EFFECTS` (17)
  - `PATH_EFFECTS` (8)
  - Direction lists (`DIR8`, `DIR4`, `HV`, `INOUT`, `SPLIT`, `DIAG`, `SPOKES`)
  - Speed presets (`SPEEDS`)
- Easing: `ease_out`, `ease_in_out`.
- Frame calculation: `compute_frame(anim, t, bounds, slide_w, slide_h) -> FrameState`.
- Step compilation: `compile_steps(slide, slide_w, slide_h) -> list[AnimationStep]`.
- Controller: `AnimationPlayer` driving frame callbacks with QTimer.

## Task 3: Implement `AnimationPane` UI
- Create `src/atboffice/modules/presentation/views/animation_pane.py`.
- Build UI layout:
  - Add Effect popup menu (Entrance / Emphasis / Exit / Motion Paths).
  - Remove Effect button.
  - Effect properties group (Start, Direction, Speed).
  - Re-order buttons (Move Up, Move Down).
  - Preview buttons (Play, Slide Show).
- Implement signals: `animationAdded`, `animationRemoved`, `animationModified`, `animationReordered`, `previewRequested`.
- Add `retranslate_ui()` for 100% bilingual UI.

## Task 4: Integrate Animation Stepping into `SlideShowView`
- In `src/atboffice/modules/presentation/slideshow/slideshow_view.py`:
  - Initialize animation steps for current slide.
  - Apply initial state (hidden entrance elements).
  - Intercept key/click events to step through animations before slide switching.
  - Implement rapid click `finish_now()`.
  - Apply active frame transformations during slide rendering.

## Task 5: Comprehensive Unit & GUI Tests
- Create `tests/gui/test_animations.py`.
- Test catalogue entries, direction lookups, speed conversions.
- Test easing and frame state math.
- Test step compilation and paragraph expansion.
- Test `AnimationPane` interactions (add, remove, edit, reorder).
- Test `SlideShowView` animation step progression.

## Task 6: Full Verification & Code Review Hand-off
- Run `pytest tests/gui/test_animations.py -v`.
- Run `pytest tests/` (full test suite).
- Transition state to `reviewing` and chain-invoke `atb-github-code-reviewer`.

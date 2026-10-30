# Implementation Plan: Issue #137 - 实现 Lectern 幻灯片切换与自定义动画交互任务窗格

## Overview
Implement the Slide Transition Task Pane (`SlideTransitionPane`), enhance the Custom Animation Task Pane (`AnimationPane`), integrate them into `LecternTaskPane` and `LecternWorkspace`, bind transition/animation state to `SlideShowView`, and enhance PPTX XML serialization for roundtrip fidelity.

---

## Tasks Breakdown

### Task 1: TDD Test Suite Setup & SlideTransitionPane Unit Tests
- Create `tests/modules/presentation/test_animation_panes.py`.
- Add test fixtures and test cases for `SlideTransitionPane`:
  - `test_transition_pane_catalogue_population`: Verify all 58 transitions are loaded into the list widget.
  - `test_transition_pane_selection_and_modification`: Verify selecting a transition updates `slide.transition` and emits `transitionChanged`.
  - `test_transition_pane_speed_and_timing`: Verify speed dropdown (slow, med, fast) and advance timings (click, after seconds).
  - `test_transition_pane_apply_to_all`: Verify "Apply to All" copies transition to all slides in presentation.
  - `test_transition_pane_signals`: Verify `playRequested` / `previewRequested` and `slideshowRequested`.
  - `test_transition_pane_retranslate_ui`: Verify i18n text translation.
- **Verification**: Run `pytest tests/modules/presentation/test_animation_panes.py` and confirm failures before Task 2 implementation.

### Task 2: Implement SlideTransitionPane
- Create `src/atboffice/modules/presentation/views/transition_pane.py`:
  - `SlideTransitionPane` inheriting from `QWidget`.
  - Transitions catalogue list widget (58 effects with Chinese & English names from `TRANSITION_CATALOGUE`).
  - Speed selector combo box ("Fast", "Medium", "Slow").
  - Sound selector combo box.
  - Advance slide controls: On mouse click checkbox and Automatically after spin box.
  - Action buttons: "Apply to All Slides", "▶ Play", "Slide Show", and "AutoPreview" checkbox.
  - Full signals and `retranslate_ui()` method.
- Update `src/atboffice/modules/presentation/views/__init__.py` to export `SlideTransitionPane`.
- **Verification**: Re-run Task 1 tests and confirm 100% pass.

### Task 3: Enhance AnimationPane and Unit Tests
- Add test cases in `test_animation_panes.py`:
  - `test_animation_pane_add_effects`: Entrance, Emphasis, Exit, Motion Path addition.
  - `test_animation_pane_reorder`: Up / Down buttons and reordering.
  - `test_animation_pane_delay_adjustment`: Modify delay timing.
  - `test_animation_pane_shape_selection_sync`: Test bidirectional sync between shape and animation selection.
- Update `src/atboffice/modules/presentation/views/animation_pane.py`:
  - Add delay spin box to `grp_modify`.
  - Support drag & drop reorder on `list_anims`.
  - Add `shapeSelectionRequested` signal and enhance shape selection synchronization.
  - Ensure robust handling of empty slides and deleted shapes.
- **Verification**: Run `pytest tests/modules/presentation/test_animation_panes.py` and confirm pass.

### Task 4: Workspace & TaskPane Integration
- Update `src/atboffice/modules/presentation/views/workspace.py`:
  - In `LecternTaskPane`:
    - Maintain `self.pane_titles: dict[str, str]`.
    - Update `title_button` text using `self.pane_titles`.
  - In `LecternWorkspace`:
    - Register `transition` pane and `customAnim` pane in `task_pane`.
    - Connect `applyToAllRequested` on `transition_pane` to update all presentation slides and thumbnails.
    - Connect `previewRequested` and `slideshowRequested`.
    - In `_refresh_active_slide()`, synchronize `transition_pane` and `animation_pane` with the new active slide.
    - Connect canvas selection changes to `animation_pane.set_selected_shapes()`.
    - Connect `animation_pane.shapeSelectionRequested` to canvas selection.
- Add integration tests in `test_animation_panes.py`:
  - `test_workspace_task_pane_switching`: Verify switching to `"transition"` and `"customAnim"`.
  - `test_workspace_slide_navigation_sync`: Verify switching active slide updates both panes.
- **Verification**: Run tests to confirm pass.

### Task 5: Enhance PPTX Serialization for Transitions & Animations
- In `src/atboffice/modules/presentation/io/writer_slide.py`:
  - Enhance `transition_to_xml()`: Ensure directions, orientations, spokes, and speeds map accurately.
  - Enhance `timing_to_xml()`: Serialize `slide.animations` into `<p:childTnLst>` within `<p:seq>` node.
- Add test in `test_animation_panes.py`:
  - `test_pptx_transition_and_animation_xml_roundtrip`: Test XML serialization and verify `pptx_reader.py` parses them back.
- **Verification**: Run tests to confirm pass.

### Task 6: Project Verification & Zero Regression
- Run full test suite:
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/presentation/test_animation_panes.py -v`
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_animations.py tests/gui/test_slideshow.py tests/gui/test_slide_canvas.py -v`
- Confirm all tests pass.

# Implementation Plan: Issue #190 - 复现并修复交互崩溃与对象生命周期问题

## Overview
Eliminate Qt virtual method shadowing on `ShapeTextEditorItem`, `SlideShowView`, `WordArtThumbnailWidget`, and `GoalSeekStatusDialog`. Implement isolated subprocess 100-cycle interaction replay stress testing, write comprehensive regression tests, and update documentation.

---

## Tasks

### Task 1: Write Reproduction Tests for Shadowed Qt Methods
- **File**: `tests/gui/test_crash_replay_diagnostics.py`
- **Actions**:
  - Add test `test_qt_virtual_methods_unshadowed()` verifying that:
    - `ShapeTextEditorItem.shape` is callable and returns a `QPainterPath`.
    - `SlideShowView.pos` is callable and returns a `QPoint`.
    - `WordArtThumbnailWidget.style` is callable and returns a `QStyle`.
    - `GoalSeekStatusDialog.result` is callable and returns an `int` / `DialogCode`.
  - Add test `test_100_cycle_interaction_replay(replay_runner)` verifying 100 interaction replay cycles execute cleanly without crash.
- **Verification**: Run `PYTHONPATH=src /opt/anaconda3/envs/ATBOffice/bin/python -m pytest tests/gui/test_crash_replay_diagnostics.py -k test_qt_virtual_methods_unshadowed` to confirm failures on unpatched code.

### Task 2: Fix `ShapeTextEditorItem` Attribute Shadowing
- **File**: `src/atboffice/modules/presentation/views/text_editor.py`
- **Actions**:
  - In `ShapeTextEditorItem.__init__`: rename `self.shape = shape_item.model` to `self.model = shape_item.model`.
  - Update all internal references from `self.shape` to `self.model`.
  - Verify that `QGraphicsTextItem.shape(self)` remains unshadowed.

### Task 3: Fix `SlideShowView` Attribute Shadowing
- **File**: `src/atboffice/modules/presentation/slideshow/slideshow_view.py`
- **Actions**:
  - In `SlideShowView.__init__`: rename `self.pos` to `self.slide_pos`.
  - Update slide navigation methods (`goto_slide`, `advance`, `reverse`) to use `self.slide_pos`.
  - In `current_slide_index` property: return `self.order[self.slide_pos]`.
  - Verify that `QWidget.pos()` remains unshadowed and returns `QPoint`.

### Task 4: Fix `WordArtThumbnailWidget` Attribute Shadowing
- **File**: `src/atboffice/modules/common/wordart_gallery.py`
- **Actions**:
  - In `WordArtThumbnailWidget.__init__`: rename `self.style = style` to `self.wordart_style = style`.
  - Update paintEvent and click handlers to use `self.wordart_style`.
  - Verify that `QWidget.style()` remains unshadowed.

### Task 5: Fix `GoalSeekStatusDialog` Attribute Shadowing
- **File**: `src/atboffice/modules/spreadsheet/dialogs/goal_seek_dlg.py`
- **Actions**:
  - In `GoalSeekStatusDialog.__init__`: rename `self.result = result` to `self.goal_seek_result = result`.
  - Provide a backward-compatible `@property def goal_seek_result(self)`.
  - Update `_update_display`, `apply_solution`, `revert_solution` to use `self.goal_seek_result`.
  - Verify that `QDialog.result()` remains unshadowed.

### Task 6: Implement 100-Cycle Interaction Stress Replay
- **File**: `src/atboffice/__main__.py`
- **Actions**:
  - Add `--replay-iterations` argument in `parse_diagnostic_args`.
  - Implement `action_name == "stress_interaction"` in `main()`:
    - Runs 100 cycles of mouse events, shape hit testing with text editor item, slideshow stepping, and dialog creation.
    - Drains event loop cleanly after each cycle.

### Task 7: Verification, Evidence Documentation & Review Transition
- **Files**:
  - `docs/clone/CLONE_DIFF.md`
  - `.github-agent-state.yml`
- **Actions**:
  - Run all targeted tests in `tests/gui/test_crash_replay_diagnostics.py`.
  - Run regression tests for presentation, slideshow, wordart, and goal seek.
  - Update `docs/clone/CLONE_DIFF.md` with verification results.
  - Set state to `reviewing` and chain-invoke `atb-github-code-reviewer`.

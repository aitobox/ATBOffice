# Implementation Plan: Issue #50 - Slide Sorter View & Master View Switching

## Task 1: Write TDD Tests for Slide Sorter Card and View
- **File**: `tests/gui/test_sorter_view.py`
- **Actions**:
  - Test `SlideSorterCard`:
    - Initialization with slide and presentation.
    - Transition indicator visibility, tooltip, and timing display.
    - Hidden slide styling and badge.
    - Click selection and double-click signal emission.
  - Test `SlideSorterView`:
    - Responsive layout with multiple slides.
    - Empty presentation graceful empty state.
    - Single and multi-selection (Ctrl, Shift).
    - Slide reordering via drag-and-drop or `move_slides` method.
    - Context menu actions (Duplicate, Delete, Hide).
- **Verification**: Run `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_sorter_view.py -v` (expect failure before implementation).

## Task 2: Implement `SlideSorterCard` and `SlideSorterView`
- **File**: `src/atboffice/modules/presentation/views/sorter_view.py`
- **Actions**:
  - Implement `SlideSorterCard` with thumbnail, index footer, transition star icon, advance duration formatting, and hidden state styling.
  - Implement `SlideSorterView` as a scrollable container with dynamic responsive grid layout calculating columns by available width.
  - Implement drag-and-drop slide reordering with insertion indicator line and multi-slide movement.
  - Provide zoom scaling, keyboard navigation, and full i18n support (`safe_tr`, `retranslate_ui`).
- **Verification**: Run `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_sorter_view.py -v` (verify Task 1 tests pass).

## Task 3: Implement Master View Model & Synchronization Logic
- **Files**:
  - `src/atboffice/modules/presentation/views/workspace.py`
  - `tests/gui/test_sorter_view.py`
- **Actions**:
  - Implement `build_master_slide(presentation, design, master_kind='slide'|'title') -> Slide`:
    - Generates master slide with design decorations and title/body/footer placeholders.
  - Implement `sync_master_slide(presentation, master_slide)`:
    - Folds edits back into `DesignTemplate` (decorations, background, placeholder frames, text styles).
  - Add `MasterViewCloseBar` widget with "Close Master View" (关闭母版视图) button.
  - Add tests for `build_master_slide` and `sync_master_slide`.
- **Verification**: Run `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_sorter_view.py -v`.

## Task 4: Integrate View Mode Switching into `LecternWorkspace` & `PresentationView`
- **Files**:
  - `src/atboffice/modules/presentation/views/workspace.py`
  - `src/atboffice/modules/presentation/view.py`
  - `tests/gui/test_sorter_view.py`
- **Actions**:
  - In `LecternWorkspace`:
    - Add `view_mode` property (`"normal"`, `"sorter"`, `"master"`).
    - Add `set_view_mode(mode: str)` switching between normal workspace, slide sorter view, and master view.
    - In master view, populate left pane with Master thumbnails (Slide Master and Title Master if configured).
    - Connect double-click in sorter view to `set_view_mode("normal")` and `set_current_slide_index`.
  - In `PresentationView`:
    - Expose `set_view_mode(mode: str)` and helper methods.
  - Add integration tests for view mode switching.
- **Verification**: Run `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_sorter_view.py tests/gui/test_lectern_workspace.py -v`.

## Task 5: Project-Wide Verification & Quality Checks
- **Actions**:
  - Run full test suite: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`
  - Verify zero regressions across all 33+ test files.
- **Verification**: All tests pass.

# Implementation Plan: TASK-606 补全 Lectern 视图矩阵 (浏览/备注/母版) 与放映浮动控制条

## Phase 1: Target Components & Implementation Tasks

### Task 1: Notes Page View (`notes_view.py`)
- **File**: `src/atboffice/modules/presentation/views/notes_view.py`
- **Details**:
  - Implement `NotesPagePaper(QFrame)`: A white page widget with standard A4 aspect ratio and subtle drop shadow. Upper area renders `render_slide_thumbnail` of the active slide. Lower area contains a styled `QTextEdit` for speaker notes.
  - Implement `NotesPageView(QScrollArea)`: Scrollable viewport hosting `NotesPagePaper` with zoom control, slide navigation header (`◄ 上一张`, `幻灯片 X/Y`, `下一张 ►`), and notes change signal.
  - Bidirectional sync: Editing text in `NotesPageView` updates `slide.notes` and emits `notes_changed(int, str)`.
  - Full `safe_tr()` / `retranslate_ui()`.

### Task 2: Slide Master View (`master_view.py`)
- **File**: `src/atboffice/modules/presentation/views/master_view.py`
- **Details**:
  - Implement `SlideMasterView(QWidget)`:
    - Left side: thumbnail/hierarchy list with Slide Master (`幻灯片母版`) and Title Master (`标题母版`).
    - Top: `MasterViewCloseBar` toolbar with "Close Master View" (`关闭母版视图`), "Insert Title Master", and "Delete Title Master".
    - Center: Interactive canvas showing master slide with styled placeholders for title, 5-level bullet points body, and footer items (Date, Footer, Slide Number).
  - Synchronize edits back to presentation designs upon close.
  - Full `safe_tr()` / `retranslate_ui()`.

### Task 3: Slide Show HUD (`slide_hud.py`) and Slideshow Integration
- **File**: `src/atboffice/modules/presentation/slideshow/slide_hud.py`
  - Implement `SlideShowHud(QFrame)`:
    - Floating semi-transparent toolbar styled with dark translucent background (`rgba(30, 30, 30, 200)`).
    - Buttons: Previous (`◄`), Next (`►`), Pen Tool (`✎`), Menu (`☰`), End Show (`✕`).
    - Pen menu: Arrow pointer, Ballpoint Pen, Highlighter, Ink Color picker, Eraser, Clear all ink.
    - Jump menu: Go to slide list, Black screen, White screen.
    - Hover detection and auto-fade timer.
- **File**: `src/atboffice/modules/presentation/slideshow/slideshow_view.py`
  - Instantiate and overlay `SlideShowHud` in bottom-left corner of `SlideShowView`.
  - Wire mouse movements in bottom-left to show HUD.
  - Wire HUD button signals (`prev_clicked`, `next_clicked`, `pen_mode_changed`, `goto_slide_requested`, `end_clicked`).
  - Enable interactive freehand drawing with chosen pen tool / color on `SlideShowView`.

### Task 4: Workspace View Matrix Management
- **File**: `src/atboffice/modules/presentation/views/workspace.py`
  - Add `NotesPageView` and `SlideMasterView` to `LecternWorkspace.center_stack`.
  - Extend `set_view_mode(mode: str)` to support `"normal"`, `"sorter"`, `"notes"`, `"master"`.
  - Connect signals between workspace, notes view, master view, and sorter view.
  - Retranslate all views in `workspace.retranslate_ui()`.

### Task 5: Lectern Window Shell Integration
- **File**: `src/atboffice/ui/shell/lectern_window.py`
  - Register `viewNotesPage` action (`视图 -> 备注页`).
  - Add view switcher buttons on status bar (Normal, Sorter, Notes, Show).
  - Update context toolbars according to active view mode.
  - Retranslate UI strings in `retranslate_ui()`.

### Task 6: Test Suite Implementation
- **File**: `tests/gui/test_lectern_views_phase6.py`
  - Test all 4 view mode transitions (`normal`, `sorter`, `notes`, `master`).
  - Test `NotesPageView` rendering, text editing, slide navigation, and synchronization.
  - Test `SlideMasterView` hierarchy, placeholder rendering, and close action.
  - Test `SlideSorterView` multi-select, drag reordering, double-click to normal.
  - Test `SlideShowHud` creation, buttons, pen tools, and signal emissions.
  - Test status bar view switching and i18n retranslation.

### Task 7: Verification & Non-Regression
- Execute `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_lectern_views_phase6.py -v`.
- Run regression tests on all related presentation tests.

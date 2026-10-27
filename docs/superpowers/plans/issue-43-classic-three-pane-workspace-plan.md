# Implementation Plan: Lectern Classic Three-Pane Workspace Viewport

## Summary
Implements the PowerPoint 2003 classic three-pane workspace (`src/atboffice/modules/presentation/views/workspace.py`) and integrates it into `src/atboffice/modules/presentation/view.py`. Accompanied by full GUI tests in `tests/gui/test_lectern_workspace.py`.

---

## Tasks

### Task 1: Thumbnail Rendering & Slide Thumbnail List Widget
- **File**: `src/atboffice/modules/presentation/views/workspace.py`
- **Details**:
  - `render_slide_thumbnail(slide: Slide, presentation: Presentation, width: int = 160) -> QPixmap`:
    Renders background, shapes (geometries, fills, borders, text approximations) to a crisp `QPixmap`.
  - `SlideThumbnailList(QListWidget)`:
    Displays slide numbered cards with preview pixmaps, handles click selection, and supports drag-and-drop slide reordering (`presentation.move_slide`).

### Task 2: Outline Editor Widget
- **File**: `src/atboffice/modules/presentation/views/workspace.py`
- **Details**:
  - `OutlineEditorWidget(QWidget)`:
    Hierarchical text outline of presentation slides.
    Displays slide titles and body bullet paragraphs.
    Synchronizes text edits into slide title/body shapes.
    Clicking a slide entry changes active slide.

### Task 3: Speaker Notes Pane
- **File**: `src/atboffice/modules/presentation/views/workspace.py`
- **Details**:
  - `SpeakerNotesPane(QWidget)`:
    Editable text area with placeholder "单击此处添加备注" / "Click to add notes".
    Synchronizes bi-directionally with `current_slide.notes`.

### Task 4: Multi-Function Task Pane (Layout & Design)
- **File**: `src/atboffice/modules/presentation/views/workspace.py`
- **Details**:
  - `LecternTaskPane(QWidget)`:
    Navigation header with Back, Forward, Home, title dropdown selector, and Close button.
  - `SlideLayoutPane(QWidget)`:
    Displays 21 standard layouts grouped by category with visual thumbnail cards. Clicking applies layout to current slide.
  - `SlideDesignPane(QWidget)`:
    Displays "Used in This Presentation" and "Available For Use" design theme cards. Clicking applies design to current/all slides.

### Task 5: LecternWorkspace Container & Integration into PresentationView
- **Files**:
  - `src/atboffice/modules/presentation/views/workspace.py`
  - `src/atboffice/modules/presentation/view.py`
- **Details**:
  - `LecternWorkspace(QWidget)`:
    Horizontal `QSplitter` hosting Left Pane, Center Splitter (Canvas + Notes), and Right Task Pane.
    Exposes full programmatic API: `load_presentation`, `set_current_slide`, `current_slide`, `apply_layout`, `apply_design`.
    Full i18n support via `retranslate_ui()`.
  - `PresentationView`:
    Wraps `LecternWorkspace` as its primary central widget.

### Task 6: Comprehensive GUI Tests
- **File**: `tests/gui/test_lectern_workspace.py`
- **Details**:
  - Test workspace creation and splitter hierarchy.
  - Test slide switching and selection synchronization across thumbnails, canvas, and notes.
  - Test drag-and-drop slide reordering.
  - Test outline editing and shape synchronization.
  - Test speaker notes double-way binding.
  - Test task pane navigation and layout/design application.
  - Test `retranslate_ui()` for 100% i18n compliance.

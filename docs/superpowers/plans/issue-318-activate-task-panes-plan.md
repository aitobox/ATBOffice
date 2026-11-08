# Implementation Plan: Issue #318 - Activate Core Office 2003 Right Task Panes Across Modules

## Task Breakdown

### Task 1: Quire Style Application Backend in CanvasView
- Add `apply_style(style_id: str)` and `clear_formatting()` methods to `CanvasView` in `src/atboffice/modules/writer/views/canvas_view.py`.
- Ensure `apply_style` looks up or ensures heading styles via `ensure_heading_style`, sets `p.p_pr.style`, repaginates, and emits `document_modified`.
- Add `current_style_name()` and `current_paragraph_style()` helper methods to query the active cursor/selection style.

### Task 2: Quire Styles and Formatting Task Pane
- Create `src/atboffice/modules/writer/panes/__init__.py` and `src/atboffice/modules/writer/panes/styles_pane.py`.
- Implement `StylesAndFormattingPane` with:
  - Selected formatting preview label.
  - Action buttons: "Select All", "New Style...".
  - Scrollable list of styles (Normal, Heading 1-3, Title, Subtitle, Clear Formatting) with paragraph (`¶`) and character (`a`) badges.
  - One-click style application via signal `apply_style_requested(style_id)`.
  - Filter combo: "Available formatting", "Formatting in use", "Available styles", "All styles".
- Register `StylesAndFormattingPane` in `QuireWindow.task_pane_dock` under pane id `"styles"`, titled `safe_tr("样式与格式")`.

### Task 3: Lectern Slide Layout Task Pane
- Create `src/atboffice/modules/presentation/panes/slide_layout_pane.py` (extracting/enhancing `SlideLayoutPane` from `workspace.py`).
- Implement 21 standard layouts (with standard 12 core layouts: Title Slide, Title Only, Title and Text, Title and 2-Column Text, Blank, Content, Title and Content, Title and 2 Content, etc.).
- Render QPainter thumbnail preview for layout frames.
- Connect `apply_layout_requested` to `LecternWindow.apply_slide_layout` (or `LecternWorkspace.apply_layout`).
- Register `SlideLayoutPane` in `LecternWindow.task_pane_dock` under pane id `"slide_layout"`, titled `safe_tr("幻灯片版式")`.

### Task 4: Ledger Watch Window Task Pane
- Create `src/atboffice/modules/spreadsheet/panes/__init__.py` and `src/atboffice/modules/spreadsheet/panes/watch_window_pane.py`.
- Implement `WatchWindowPane` with:
  - Add Watch button and Delete Watch button.
  - QTableWidget with 6 columns: Book, Sheet, Name, Cell, Value, Formula.
  - Real-time watch list management: `add_watch`, `remove_watch`, `refresh_watches`.
  - Signal `navigate_requested(sheet_name, r, c)` when clicking/double-clicking a watched cell.
- Register `WatchWindowPane` in `LedgerWindow.task_pane_dock` under pane id `"watch_window"`, titled `safe_tr("监视窗口")`.

### Task 5: Task Pane Header Dropdown Verification
- Verify that `TaskPaneDock._build_menu_items()` and `TaskPaneHeader._show_title_menu()` cleanly list all registered module panes and allow seamless switching via dropdown menu.

### Task 6: Comprehensive GUI Tests
- Create `tests/gui/test_task_panes_coverage.py`.
- Test header dropdown switching across Quire, Ledger, and Lectern.
- Test Quire Styles and Formatting pane selection and style application.
- Test Lectern Slide Layout pane layout selection and application to slides.
- Test Ledger Watch Window pane adding watches, displaying values, and navigation.

### Task 7: Full Test Suite Verification
- Run test suite with `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_task_panes_coverage.py -v`.
- Verify zero regressions and 100% pass rate.

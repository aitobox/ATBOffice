# Specification: Issue #318 - Activate Core Office 2003 Right Task Panes Across Modules

## Overview
In the project Control Matrix (`docs/clone/phase7_control_matrix.csv`), interactive controls have gaps in right-side task pane integration. While `TaskPaneDock` is attached to shell windows, module-specific task panes for Quire (Styles and Formatting), Ledger (Watch Window), and Lectern (Slide Layout) are missing from registration or lack interactive model wiring.

This specification designs the integration of:
1. Universal task pane header dropdown switching across registered module panels.
2. Quire Styles and Formatting task pane (`StylesAndFormattingPane`) with one-click style application to active selection.
3. Lectern Slide Layout task pane (`SlideLayoutPane`) registered in `TaskPaneDock` with standard Office 2003 layout thumbnails and slide application.
4. Ledger Watch Window task pane (`WatchWindowPane`) registered in `TaskPaneDock` for real-time formula coordinate and cell value monitoring.
5. Comprehensive automated GUI testing in `tests/gui/test_task_panes_coverage.py`.

---

## Architecture & Component Design

### 1. TaskPaneDock & Header Dropdown Switching
- `TaskPaneDock` manages registered `PaneEntry` items.
- `TaskPaneHeader` provides a dropdown button (`btn_title`) that builds a `QMenu` showing all unhidden panes.
- Clicking any menu item emits `pane_selected(pane_id)` which invokes `show_pane(pane_id)`.
- The active pane displays a checkmark in the menu and updates `btn_title.setText(f"{title}  ▼")`.

### 2. Quire: Styles and Formatting (`StylesAndFormattingPane`)
- **Module location**: `src/atboffice/modules/writer/panes/styles_pane.py` (and registered in `QuireWindow`).
- **UI Elements**:
  - Selected formatting box: Displays current paragraph style name and inline run characteristics.
  - "Select All" button: Selects all paragraphs sharing the current style.
  - "New Style..." button: Invokes new style creation or dialog.
  - Formatting List: Scrollable list of styles (`Clear Formatting`, `Normal`, `Heading 1`, `Heading 2`, `Heading 3`, `Title`, `Subtitle`, etc.) with `¶` or `a` badges.
  - One-click application: Clicking any style applies it to the active selection / paragraph via `CanvasView.apply_style(style_id)`.
  - "Show" filter combo: Allows filtering by Available Formatting, Formatting in Use, Available Styles, All Styles.
- **Canvas Wiring**:
  - `CanvasView.apply_style(style_id: str)`: Sets `p.p_pr.style = style_id` for selected paragraphs (ensuring heading styles are present in `doc.styles`), repaginates, and emits `document_modified`.
  - `CanvasView.clear_formatting()`: Resets style to Normal and clears run overrides.

### 3. Lectern: Slide Layout (`SlideLayoutPane`)
- **Module location**: `src/atboffice/modules/presentation/panes/slide_layout_pane.py` (and registered in `LecternWindow.task_pane_dock`).
- **UI Elements**:
  - Layout Gallery: Organizes 21 standard Office 2003 layouts into groups:
    - Text Layouts (Title Slide, Title Only, Title and Text, Title and 2-Column Text)
    - Content Layouts (Blank, Content, Title and Content, Title and 2 Content, etc.)
    - Text and Content Layouts
    - Other Layouts (Title and Table, Title and Chart, etc.)
  - Thumbnail preview: Previews title/body frames with QPainter.
  - Selection / Click: One-click applies the layout to the active slide, rearranging placeholder shapes and notifying the workspace.

### 4. Ledger: Watch Window (`WatchWindowPane`)
- **Module location**: `src/atboffice/modules/spreadsheet/panes/watch_window_pane.py` (and registered in `LedgerWindow.task_pane_dock`).
- **UI Elements**:
  - Action buttons: "Add Watch..." (`btn_add`), "Delete Watch" (`btn_delete`).
  - Watched cells table: 6 columns: Book, Sheet, Name, Cell, Value, Formula.
  - Live model sync: When workbook cells change or recalculate, `refresh_watches()` reads values and formulas from the active `WorkbookModel`.
  - Navigation: Clicking a watched item emits `navigate_requested(sheet_name, r, c)` to navigate to that cell in the grid.

---

## Verification & Acceptance Criteria
- Full test in `tests/gui/test_task_panes_coverage.py`:
  1. `test_task_pane_header_dropdown_switching`: verifies header dropdown switching between panes across Quire, Ledger, and Lectern.
  2. `test_quire_styles_and_formatting_pane`: verifies Styles and Formatting pane listing, current style display, and one-click application to selected text.
  3. `test_lectern_slide_layout_pane`: verifies Slide Layout pane thumbnails and applying layouts to current slide.
  4. `test_ledger_watch_window_pane`: verifies Watch Window pane adding watches, displaying formula/value, deleting watches, and navigation.

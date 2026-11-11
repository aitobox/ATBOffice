# Implementation Plan: Issue #344 — Office 24-Item Clipboard Task Pane & Global Tell Me Command Search Palette

## Overview
Implement the 24-item Office Clipboard task pane (`ClipboardTaskPane`), the global "Tell Me" command search box (`CommandSearchBox`), and wire them into `BaseOfficeWindow` and `TaskPaneDock` across Quire, Ledger, and Lectern with full i18n support.

---

## Tasks

### Task 1: Implement `ClipboardTaskPane`
- **Files**:
  - `src/atboffice/ui/panes/__init__.py`
  - `src/atboffice/ui/panes/clipboard_pane.py`
- **Details**:
  - `ClipItem` dataclass: `id`, `text`, `html`, `item_type`, `mime_data`, `created_at`.
  - `ClipItemWidget`: Visual row/card displaying content-type icon (table, text, image, sheet), truncated text snippet (up to 160 chars), delete button, and hover styling.
  - `ClipboardTaskPane`:
    - Listens to `QClipboard.dataChanged` signal.
    - Capped at 24 items (drops oldest when capacity exceeded).
    - Ignores duplicate consecutive clippings and internal paste writes (`_inhibited`).
    - Top bar: "Paste All" button, "Clear All" button, counter label `"{0} of 24 - Clipboard. Click an item to paste."`.
    - Context menu or delete button on individual clips.
    - Signals: `item_clicked`, `paste_all_requested`, `cleared`.
    - 100% `safe_tr()` coverage and `retranslate_ui()`.

### Task 2: Implement `CommandSearchBox`
- **Files**:
  - `src/atboffice/ui/components/command_search_box.py`
- **Details**:
  - `CommandSearchResult` dataclass.
  - `CommandSearchBox(QWidget)`:
    - Search input field with search icon and placeholder ("请告诉我您想要做什么..." / "Tell me what you want to do...").
    - Shortcut: `Alt+Q` to focus and select text.
    - Real-time search algorithm matching `ActionRegistry` (id, label, tip, shortcut) + synonym table (print, copy, paste, sum, font, table, etc.).
    - Interactive dropdown popup (`QListWidget` / `QMenu` floating below search box).
    - Keyboard navigation (Up/Down arrow keys highlight, Enter executes `action_registry.trigger_action(action_id)`, Esc closes popup).
    - Mouse click on result row executes action.
    - 100% `safe_tr()` coverage and `retranslate_ui()`.

### Task 3: Integrate with `BaseOfficeWindow` & `TaskPaneDock`
- **Files**:
  - `src/atboffice/ui/shell/base_window.py`
  - `src/atboffice/ui/components/task_pane.py`
- **Details**:
  - In `BaseOfficeWindow`:
    - Add `init_command_search_box()` and mount to `menu_bar.setCornerWidget(search_box, Qt.Corner.TopRightCorner)`.
    - Register `"clipboard"` pane in `init_task_pane_dock()`:
      - Title: `safe_tr("剪贴板")`
      - Pane: `ClipboardTaskPane`
      - Connect signals to `paste()` / `paste_item()` / `paste_all()`.
    - Add action handler for `office_clipboard` / `taskPane_clipboard`.
    - Update `retranslate_ui()` to retranslate search box and clipboard pane.

### Task 4: Comprehensive Unit & GUI Tests
- **Files**:
  - `tests/gui/test_phase9_clipboard_and_command_search.py`
- **Test Scenarios**:
  - Clipboard collection, max 24 items limit, LIFO order.
  - Paste item and Paste All signal emission.
  - Clear All functionality.
  - CommandSearchBox fuzzy query and synonym scoring against ActionRegistry.
  - CommandSearchBox keyboard navigation (Alt+Q, Down, Enter, Esc).
  - Integration on BaseOfficeWindow (menu bar corner placement and TaskPaneDock registration).
  - i18n retranslation verification.

### Task 5: Verification & Regression Check
- Run targeted test suite:
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_phase9_clipboard_and_command_search.py -v`
- Run existing task pane tests:
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_task_pane.py tests/gui/test_task_panes_coverage.py -v`
- Run full regression suite:
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/ -k "test_phase9 or test_task_pane"`

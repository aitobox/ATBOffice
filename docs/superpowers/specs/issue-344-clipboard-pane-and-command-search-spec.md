# Specification: Issue #344 — Office 24-Item Clipboard Task Pane & Global "Tell Me" Command Search Palette

## 1. Overview & Context

This specification defines the architecture, UI controls, signals, and integration for two signature productivity features from `.vibeoffice/public/common/search.js`, `.vibeoffice/public/quire/js/panes.js`, and `.vibeoffice/public/ledger/js/panes.js`:
1. **Office 24-Item Clipboard Task Pane (`ClipboardTaskPane`)**:
   - Collects up to 24 cut/copied items from the system `QClipboard`.
   - Displays item counter, type icon (text, table, cells, image), and text preview.
   - Provides "Paste All" and "Clear All" batch actions, plus individual item click-to-paste and delete context actions.
   - Seamlessly integrates into `TaskPaneDock` across Quire, Ledger, and Lectern.
2. **Global Command Search ("Tell me what you want to do" / `CommandSearchBox`)**:
   - Positioned at the top right of the application menu bar (`QMenuBar.setCornerWidget(..., Qt.Corner.TopRightCorner)`).
   - Instant real-time fuzzy/synonym search across `ActionRegistry` actions.
   - Interactive dropdown list with keyboard navigation (Up/Down/Enter/Esc).
   - Direct execution of matched commands via `ActionRegistry.trigger_action(action_id)`.
   - Global shortcut `Alt+Q` to focus the search box.

---

## 2. Architecture & Data Structures

### 2.1 Clipboard Data Structures & `ClipboardTaskPane`

```
QClipboard (QGuiApplication.clipboard())
       │  (dataChanged signal)
       ▼
ClipboardManager / ClipboardTaskPane
       │
       ├── Item Collection: deque(maxlen=24) or list[ClipItem] (max 24)
       │     └── ClipItem(
       │           id: str,
       │           text: str,
       │           html: str,
       │           item_type: ClipType ("text" | "table" | "cells" | "image"),
       │           mime_data: QMimeData,
       │           timestamp: float
       │         )
       │
       ├── UI Layout:
       │     ├── Action Buttons (QHBoxLayout):
       │     │     ├── QPushButton("Paste All" / "全部粘贴")
       │     │     └── QPushButton("Clear All" / "全部清空")
       │     ├── Status Label: "{0} of 24 - Clipboard. Click an item to paste."
       │     └── QScrollArea -> QVBoxLayout containing ClipItemWidget rows
       │
       └── Signals:
             ├── item_pasted = Signal(object)
             ├── paste_all_requested = Signal()
             └── cleared = Signal()
```

#### Pre-Implementation Reflection & Edge Cases:
- **Duplicate Prevention**: If the latest clipboard change has identical text/mime content to the most recent clip, ignore it to prevent spam.
- **Internal Paste Inhibit**: When the user clicks a clip item to paste, the pane copies that item onto `QClipboard` before invoking `paste()`. A temporary `_inhibited` flag must suppress `dataChanged` handling during this write so the item is not re-added as a duplicate.
- **Empty States**: When 0 items exist, "Paste All" and "Clear All" are disabled, and a friendly placeholder label ("剪贴板为空。复制或剪切内容将在此处收集。") is shown.
- **MIME Support**: Inspects `QMimeData` for HTML containing `<table` (classified as `table`), spreadsheet tab-delimited text or spreadsheet MIME types (classified as `cells`), `hasImage()` (classified as `image`), and plain text.

### 2.2 Global Command Search (`CommandSearchBox`)

```
BaseOfficeWindow.menu_bar (MacMenuBar)
       │  (TopRightCorner Widget)
       ▼
CommandSearchBox (QWidget / QLineEdit)
       │
       ├── LineEdit:
       │     ├── Icon: Search magnifier
       │     ├── Placeholder: "请告诉我您想要做什么..." (Tell me what you want to do...)
       │     └── Shortcut: Alt+Q
       │
       ├── Search Engine:
       │     ├── ActionRegistry index: id, label, tip, shortcut
       │     ├── Synonym dictionary (SYN): maps everyday words to Office actions
       │     └── Ranking: Exact Match > Prefix Match > Synonym Match > Substring Match
       │
       └── Dropdown Popup (QMenu / QFrame):
             ├── Up to 10 matched actions
             ├── Keyboard navigation (Up/Down to highlight, Enter to execute, Esc to cancel)
             └── Click or Enter dispatches `action_registry.trigger_action(action_id)`
```

#### Pre-Implementation Reflection & Edge Cases:
- **Menu Bar Geometry & Corner Widget**: In Qt, `menu_bar.setCornerWidget(box, Qt.Corner.TopRightCorner)` neatly pins the search box to the right side of the menu bar without clipping the menus.
- **Disabled Actions**: If an action is registered but disabled in `ActionRegistry`, it should appear styled as disabled in the search results and prevent accidental execution.
- **Fuzzy Synonyms**: Include common Chinese and English synonyms:
  - 复制/copy, 粘贴/paste, 打印/print, 字体/font, 保存/save, 查找/find, 替换/replace, 求和/sum/autosum, 表格/table, 插入/insert, 撤销/undo, 重做/redo.
- **Focus Management**: Pressing `Alt+Q` focuses the search box and selects all text. Pressing `Escape` clears text, unfocuses the box, and returns focus to the active document canvas.

---

## 3. Detailed Component Contracts

### 3.1 `src/atboffice/ui/panes/clipboard_pane.py`
- Class `ClipItem`:
  - `id: str`
  - `text: str`
  - `html: str`
  - `item_type: str` ("text", "table", "cells", "image")
  - `mime_data: QMimeData`
  - `created_at: float`
- Class `ClipboardTaskPane(QWidget)`:
  - `item_clicked = Signal(object)`
  - `paste_all_requested = Signal()`
  - `cleared = Signal()`
  - `def __init__(self, parent: QWidget | None = None)`
  - `def start_monitoring(self) -> None`
  - `def stop_monitoring(self) -> None`
  - `def clear_all(self) -> None`
  - `def paste_all(self) -> None`
  - `def paste_item(self, item: ClipItem) -> None`
  - `def remove_item(self, item_id: str) -> None`
  - `def items(self) -> list[ClipItem]`
  - `def count(self) -> int`
  - `def retranslate_ui(self) -> None`

### 3.2 `src/atboffice/ui/components/command_search_box.py`
- Class `CommandSearchResult`:
  - `action_id: str`
  - `label: str`
  - `tip: str`
  - `shortcut: str`
  - `icon: QIcon | None`
  - `enabled: bool`
  - `score: float`
- Class `CommandSearchBox(QWidget)`:
  - `action_executed = Signal(str)`
  - `def __init__(self, action_registry: ActionRegistry | None = None, parent: QWidget | None = None)`
  - `def set_action_registry(self, registry: ActionRegistry) -> None`
  - `def search_commands(self, query: str) -> list[CommandSearchResult]`
  - `def execute_selected(self) -> None`
  - `def retranslate_ui(self) -> None`

### 3.3 Integration in `BaseOfficeWindow` & `TaskPaneDock`
- `BaseOfficeWindow.init_command_search_box()` creates and pins `CommandSearchBox` to `menu_bar.setCornerWidget(..., Qt.Corner.TopRightCorner)`.
- `BaseOfficeWindow.init_task_pane_dock()` creates and registers `ClipboardTaskPane` under ID `"clipboard"` with localized title `safe_tr("剪贴板")`.
- `BaseOfficeWindow` handles `"paste_all"` and `"paste_item"` by delegating to active document view / focused widget.

---

## 4. Verification & Testing Plan
- Test file: `tests/gui/test_phase9_clipboard_and_command_search.py`
  1. `test_clipboard_task_pane_collection_and_cap()`:
     - Push 30 clippings into clipboard.
     - Verify total items capped at 24.
     - Verify newest item at index 0.
     - Verify counter text shows "24 of 24".
  2. `test_clipboard_task_pane_paste_and_clear()`:
     - Verify single item click emits paste and updates clipboard.
     - Verify "Paste All" and "Clear All" work properly.
     - Verify duplicate consecutive clips are filtered.
  3. `test_command_search_box_fuzzy_matching()`:
     - Query registered actions by label, synonym ("print", "sum", "table", "打印").
     - Verify top ranked results.
     - Verify executing result calls `action_registry.trigger_action`.
  4. `test_command_search_box_keyboard_navigation()`:
     - Test Alt+Q shortcut, Up/Down navigation, Enter execution, Esc dismissal.
  5. `test_base_office_window_integration()`:
     - Verify `CommandSearchBox` mounted on menu bar.
     - Verify `ClipboardTaskPane` registered in `TaskPaneDock`.
     - Verify full i18n retranslation.

# Specification: Issue #10 macOS Native Desktop Shell, Global Menu Bar & Finder Dispatch

## 1. Overview & Objective
Implement the native desktop shell for macOS adhering to Apple Human Interface Guidelines (HIG), including:
- High-DPI / Retina floating point pixel scaling configuration.
- Custom `QApplication` (`ATBApplication`) subclass with `event()` override capturing `QFileOpenEvent` for Finder double-clicks, "Open With", and Dock icon drag-and-drops.
- Native macOS top menu bar (`QMenuBar.setNativeMenuBar(True)`) with standard application menus and HIG shortcuts (`⌘S`, `⇧⌘S`, `⌘Z`, `⇧⌘Z`, `⌘1`, `⌘C`, `⌘V`, `⌘W`, `⌘N`, `⌘O`, `⌘M`, etc.).
- Workbook lifecycle management in `MainWindow` with dirty tracking (`is_modified`), window modified dot indicators (`setWindowModified(True)`), and unsaved changes confirmation dialog on window close.
- Seamless CLI argument (`python -m atboffice <file.xlsx>`) and Finder open dispatch.
- 100% i18n localization compliance (`safe_tr()`, `retranslate_ui()`).

## 2. Architecture & Components

### 2.1 Core Application (`src/atboffice/core/app.py`)
- **Class `ATBApplication(QApplication)`**:
  - Sets High DPI scaling policy: `QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)`.
  - Maintains `file_open_requested = Signal(str)` (or `list[str]`) for open requests.
  - Maintains pending file queue `_pending_files: list[str]` if files arrive before the main window is registered or active.
  - Overrides `event(e: QEvent) -> bool`:
    - Intercepts `QEvent.Type.FileOpen` (macOS `QFileOpenEvent`).
    - Extracts `event.file()` or `event.url().toLocalFile()`.
    - Dispatches to registered active window or enqueues in `_pending_files`.
  - Method `register_main_window(window: MainWindow) -> None`:
    - Binds window to application; immediately flushes any queued `_pending_files` by calling `window.open_file(path)`.
  - Helper `create_application(argv: list[str] | None = None) -> ATBApplication`.

### 2.2 macOS Native Menu Bar (`src/atboffice/ui/shell/mac_menu.py`)
- **Class `MacMenuBar(QMenuBar)` / `setup_mac_menu(window: QMainWindow)`**:
  - `setNativeMenuBar(True)` (macOS system menu bar integration).
  - Menus structure:
    - **File (文件)**:
      - New (`新建工作簿`, `⌘N`)
      - Open… (`打开…`, `⌘O`)
      - Save (`保存`, `⌘S`)
      - Save As… (`另存为…`, `⇧⌘S`)
      - Close (`关闭`, `⌘W`)
    - **Edit (编辑)**:
      - Undo (`撤销`, `⌘Z`)
      - Redo (`重做`, `⇧⌘Z` / `⌘Y`)
      - Cut (`剪切`, `⌘X`)
      - Copy (`复制`, `⌘C`)
      - Paste (`粘贴`, `⌘V`)
      - Format Cells (`设置单元格格式…`, `⌘1`)
    - **View (视图)**:
      - Fullscreen (`全屏`, `Ctrl+Cmd+F` / `F11`)
      - Zoom In / Zoom Out (`放大` / `缩小`)
    - **Window (窗口)**:
      - Minimize (`最小化`, `⌘M`)
      - Zoom / Maximize (`缩放`)
      - Bring All to Front (`前置全部窗口`)
    - **Help (帮助)**:
      - ATBOffice Help (`ATBOffice 帮助`, `F1`)
      - About ATBOffice (`关于 ATBOffice`)
  - Full i18n support with `retranslate_ui()`.
  - Connects action triggers to target window slots or signals.

### 2.3 Shell Main Window (`src/atboffice/ui/shell/main_window.py`)
- **Class `MainWindow(QMainWindow)`**:
  - Central widget containing office module views (e.g. tabs for Writer, Spreadsheet, Presentation).
  - Document & Workbook Lifecycle:
    - `current_file_path: Path | None = None`
    - `is_modified: bool = False`
    - `set_modified(modified: bool) -> None`: updates macOS window modified dot (`self.setWindowModified(modified)`) and title formatting.
    - `new_file() -> bool`: prompts for save if dirty, creates blank workbook.
    - `open_file(file_path: str | Path) -> bool`: prompts for save if dirty, loads file into active module (e.g. SpreadsheetView), updates window title.
    - `save_file(file_path: str | Path | None = None) -> bool`: saves to current file path or triggers `save_file_as()`.
    - `save_file_as() -> bool`: prompts `QFileDialog.getSaveFileName` with filters (`*.xlsx`, `*.csv`, `*.*`).
    - `closeEvent(event: QCloseEvent) -> None`:
      - Checks `self.is_modified`.
      - If modified, presents a standard confirmation dialog:
        - "Do you want to save the changes you made to '<filename>'?"
        - Options: "Save" (保存), "Don't Save" (不保存), "Cancel" (取消).
        - Save -> calls `save_file()`, accepts if saved, ignores if cancelled.
        - Don't Save -> accepts close.
        - Cancel -> ignores close.
    - Installs `MacMenuBar` via `setup_mac_menu(self)`.
  - Aliased/exported in `src/atboffice/ui/main_window.py` for backward compatibility.

### 2.4 Command-line & Launcher Dispatch (`src/atboffice/__main__.py`)
- Uses `ATBApplication`.
- Parses CLI arguments for file paths to open on startup (`sys.argv[1:]`).
- Registers window with `ATBApplication` so startup files and runtime `QFileOpenEvent`s are routed to `MainWindow.open_file`.

## 3. Edge Cases & Robustness
1. **Empty / Nonexistent File**:
   - `open_file` validates file existence and catches IO/parse exceptions gracefully, showing a user-friendly error dialog rather than crashing the application.
2. **Multiple Files Opened Simultaneously**:
   - When multiple `QFileOpenEvent`s or CLI arguments are delivered, the application sequentially opens them or switches to the latest workbook without losing state.
3. **Closing with Unsaved Changes**:
   - macOS HIG requires standard sheet/dialog with Save / Discard / Cancel. The user can cancel without discarding their work.
4. **Window Modified Dot**:
   - Title set to `f"{title} [*]"` and `setWindowModified(is_modified)`. On macOS, Qt automatically shows the native grey dot in the red close button.
5. **Cross-Platform Compatibility**:
   - While prioritizing macOS (`setNativeMenuBar(True)`), the menu and window must function properly on Windows/Linux without error.
6. **i18n & Translation**:
   - All strings in `ATBApplication`, `MacMenuBar`, and `MainWindow` use `safe_tr()` / `tr()`.
   - `retranslate_ui()` is implemented on all UI classes.

## 4. Verification Plan
- Unit & GUI tests in `tests/gui/test_mac_shell.py`:
  - `test_atb_application_retina_and_open_event`: tests event filtering and queueing for `QFileOpenEvent`.
  - `test_mac_menu_structure_and_shortcuts`: tests native menu bar actions and standard key sequences (`⌘S`, `⌘W`, `⌘Z`, `⌘1`, etc.).
  - `test_main_window_dirty_lifecycle_and_close`: tests `set_modified`, dirty dot, and closeEvent interception.
  - `test_cli_file_open_dispatch`: tests file opening via CLI arguments.
- Regression testing: run full test suite with `PYTHONPATH=src conda run -n ATBOffice pytest tests/`.

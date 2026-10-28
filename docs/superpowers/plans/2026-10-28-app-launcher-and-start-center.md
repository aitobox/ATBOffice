# ATBOffice 启动中心与专属窗口入口实现计划 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 ATBOffice 的应用入口系统，包含启动中心 (Start Center) 欢迎界面、Quire/Ledger/Lectern 三大独立专属主窗口，以及具备窗口复活机制的生命周期窗口管理器 (WindowManager) 和 CLI 智能分发路由器。

**Architecture:** 
1. 抽离通用窗口基类 `BaseOfficeWindow`，处理脏状态跟踪、macOS 窗口红点、Luna 2003 主题与关闭拦截；
2. 基于基类派生 `QuireWindow`、`LedgerWindow`、`LecternWindow` 与 `StartCenterWindow`；
3. 全局单例 `WindowManager` 管理文档窗口集合与启动中心，实现“文档全关闭时自动唤回 Start Center”；
4. `RecentFilesManager` 持久化最近文档；`__main__.py` 负责 CLI 子命令与文件后缀自动分发。

**Tech Stack:** Python 3.12+, PySide6 (Qt6), pytest, pytest-qt, Fusion/Luna 2003 style.

**Spec:** [docs/superpowers/specs/2026-10-28-app-launcher-and-start-center-design.md](file:///Users/brainzhang/work/aitobox/ATBOffice/docs/superpowers/specs/2026-10-28-app-launcher-and-start-center-design.md)

## Global Constraints

- Python 3.12+ (全类型注解，遵循 PEP 484/526)
- 运行环境与测试：`conda run -n ATBOffice pytest`
- 国际化规范：所有 UI 文字 100% 使用 `safe_tr()` / `tr()` 包裹，支持 `retranslate_ui()`
- 窗口风格：macOS HIG 原生菜单栏支持 + Office 2003 Luna Blue/Silver/Olive 皮肤机制
- 鲁棒性防错：所有文件操作必须带异常捕获与友好弹窗提示，严禁抛出未捕获异常崩溃

## Review Focus

1. **缺失或受损文件**：从命令行、启动中心或最近历史打开一个已被删除或无读权限的文件，应弹窗友好提示而不崩溃。
2. **退出拦截原子性**：退出应用时若有多个脏窗口，任一窗口点击“取消”必须立即终止整个退出过程。
3. **窗口生命周期复活**：关闭最后一个文档窗口时，Start Center 必须可靠唤回、前置并激活 (`show()`, `raise_()`, `activateWindow()`)。
4. **拖拽非办公文件**：用户将非 Word/Excel/PPT 格式文件拖放进 Start Center 时，应提示格式不支持而非异常退出。
5. **并发快速点击**：在启动中心快速连续点击多次“新建 Quire”，应具备防重入保护，避免重复堆叠异常空白窗口。

---

### Task 1: `RecentFilesManager` 数据模型与持久化存储

**Files:**
- Create: `src/atboffice/core/recent_files.py`
- Test: `tests/test_recent_files.py`

**Interfaces:**
- Produces:
  - `class RecentItem(NamedTuple)`: `path: Path, app: str, title: str, size_bytes: int, last_opened: float`
  - `class RecentFilesManager`:
    - `__init__(storage_path: Path | None = None, max_items: int = 20)`
    - `add_file(path: str | Path, app: str) -> RecentItem`
    - `remove_file(path: str | Path) -> bool`
    - `clear_all() -> None`
    - `get_entries() -> list[RecentItem]`
    - `save() -> None`
    - `load() -> None`

- [ ] **Step 1: Write the failing test for RecentFilesManager**

```python
# tests/test_recent_files.py
from pathlib import Path
import pytest
from atboffice.core.recent_files import RecentFilesManager, RecentItem

def test_recent_files_add_and_get(tmp_path: Path):
    store_file = tmp_path / "recent.json"
    doc_file = tmp_path / "test.docx"
    doc_file.write_text("dummy")

    mgr = RecentFilesManager(storage_path=store_file, max_items=5)
    item = mgr.add_file(doc_file, app="quire")
    assert item.title == "test.docx"
    assert item.app == "quire"

    entries = mgr.get_entries()
    assert len(entries) == 1
    assert entries[0].path == doc_file.resolve()

def test_recent_files_max_limit_fifo(tmp_path: Path):
    store_file = tmp_path / "recent.json"
    mgr = RecentFilesManager(storage_path=store_file, max_items=2)
    f1 = tmp_path / "1.docx"
    f2 = tmp_path / "2.xlsx"
    f3 = tmp_path / "3.pptx"
    for f in (f1, f2, f3):
        f.touch()
        mgr.add_file(f, app="generic")
    
    entries = mgr.get_entries()
    assert len(entries) == 2
    assert entries[0].path == f3.resolve()
    assert entries[1].path == f2.resolve()

def test_recent_files_remove_and_clear(tmp_path: Path):
    store_file = tmp_path / "recent.json"
    mgr = RecentFilesManager(storage_path=store_file)
    f1 = tmp_path / "1.docx"
    f1.touch()
    mgr.add_file(f1, app="quire")
    assert len(mgr.get_entries()) == 1
    assert mgr.remove_file(f1) is True
    assert len(mgr.get_entries()) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_recent_files.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'atboffice.core.recent_files'"

- [ ] **Step 3: Implement `RecentFilesManager` in `src/atboffice/core/recent_files.py`**

Implement `RecentItem` dataclass/NamedTuple and `RecentFilesManager` with JSON loading/saving, default storage at `~/.atboffice/recent_files.json`, LRU ordering (newest first), and robust error handling against corrupted JSON files.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_recent_files.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/core/recent_files.py tests/test_recent_files.py
git commit -m "feat(core): implement RecentFilesManager for document history"
```

---

### Task 2: `BaseOfficeWindow` 通用窗口基类

**Files:**
- Create: `src/atboffice/ui/shell/base_window.py`
- Test: `tests/test_base_office_window.py`

**Interfaces:**
- Consumes: `atboffice.ui.styles.luna_2003.apply_luna_theme`
- Produces:
  - `class BaseOfficeWindow(QMainWindow)`:
    - `current_file_path: Path | None`
    - `is_modified: bool`
    - `set_modified(modified: bool) -> None`
    - `update_window_title() -> None`
    - `maybe_save_prompt() -> bool`
    - `save_file(file_path: str | Path | None = None) -> bool`
    - `save_file_as() -> bool`
    - `apply_theme(theme_name: str) -> None`
    - `closeEvent(event: QCloseEvent) -> None`
    - Signal: `window_closed = Signal(QMainWindow)`

- [ ] **Step 1: Write the failing test for BaseOfficeWindow**

```python
# tests/test_base_office_window.py
from pathlib import Path
from PySide6.QtWidgets import QMessageBox
from PySide6.QtGui import QCloseEvent
import pytest
from atboffice.ui.shell.base_window import BaseOfficeWindow

def test_base_office_window_title_and_dirty(qtbot):
    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    assert not win.is_modified
    assert "[*]" in win.windowTitle()

    win.set_modified(True)
    assert win.is_modified
    assert win.isWindowModified()

    win.current_file_path = Path("/tmp/sample.docx")
    win.update_window_title()
    assert "sample.docx" in win.windowTitle()

def test_base_office_window_close_signal(qtbot):
    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    closed_signals = []
    win.window_closed.connect(lambda w: closed_signals.append(w))

    ev = QCloseEvent()
    win.closeEvent(ev)
    assert ev.isAccepted()
    assert len(closed_signals) == 1
    assert closed_signals[0] is win
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_base_office_window.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'atboffice.ui.shell.base_window'"

- [ ] **Step 3: Implement `BaseOfficeWindow` in `src/atboffice/ui/shell/base_window.py`**

Inherit from `QMainWindow`, support safe translation (`safe_tr`), dirty flag tracking with macOS modified dot, Luna 2003 styling, standard `maybe_save_prompt()`, and emit `window_closed` on accepted close.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_base_office_window.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/ui/shell/base_window.py tests/test_base_office_window.py
git commit -m "feat(ui): implement BaseOfficeWindow with lifecycle and dirty management"
```

---

### Task 3: `WindowManager` 核心窗口生命周期调度器

**Files:**
- Create: `src/atboffice/core/window_manager.py`
- Test: `tests/test_window_manager.py`

**Interfaces:**
- Consumes:
  - `BaseOfficeWindow` (from Task 2)
  - `RecentFilesManager` (from Task 1)
- Produces:
  - `class WindowManager(QObject)`:
    - `get_instance() -> WindowManager`
    - `start_center: StartCenterWindow | None`
    - `active_windows: set[BaseOfficeWindow]`
    - `show_start_center() -> StartCenterWindow`
    - `register_window(win: BaseOfficeWindow) -> None`
    - `unregister_window(win: BaseOfficeWindow) -> None`
    - `open_quire(path: str | Path | None = None) -> BaseOfficeWindow`
    - `open_ledger(path: str | Path | None = None) -> BaseOfficeWindow`
    - `open_lectern(path: str | Path | None = None) -> BaseOfficeWindow`
    - `open_file_auto(path: str | Path) -> BaseOfficeWindow`
    - `detect_app_type(path: str | Path) -> str`
    - `quit_application() -> bool`

- [ ] **Step 1: Write the failing test for WindowManager**

```python
# tests/test_window_manager.py
from pathlib import Path
import pytest
from PySide6.QtWidgets import QMainWindow
from atboffice.core.window_manager import WindowManager
from atboffice.ui.shell.base_window import BaseOfficeWindow

def test_window_manager_detect_app_type():
    mgr = WindowManager()
    assert mgr.detect_app_type("doc.docx") == "quire"
    assert mgr.detect_app_type("sheet.xlsx") == "ledger"
    assert mgr.detect_app_type("sheet.csv") == "ledger"
    assert mgr.detect_app_type("slide.pptx") == "lectern"
    assert mgr.detect_app_type("unknown.xyz") == "generic"

def test_window_manager_register_and_resurrect(qtbot):
    mgr = WindowManager()
    # Mock start center
    sc = BaseOfficeWindow()
    qtbot.addWidget(sc)
    mgr._start_center = sc
    sc.hide()

    w1 = BaseOfficeWindow()
    qtbot.addWidget(w1)
    mgr.register_window(w1)
    assert len(mgr.active_windows) == 1

    # Closing the only window should resurrect start center
    mgr.unregister_window(w1)
    assert len(mgr.active_windows) == 0
    assert sc.isVisible()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_window_manager.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'atboffice.core.window_manager'"

- [ ] **Step 3: Implement `WindowManager` in `src/atboffice/core/window_manager.py`**

Implement registration, unregistration, auto-resurrection of Start Center when active windows reaches 0, extension detection, lazy creation of windows, and `quit_application()` atomic check across all dirty windows.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_window_manager.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/core/window_manager.py tests/test_window_manager.py
git commit -m "feat(core): implement WindowManager lifecycle and resurrect coordinator"
```

---

### Task 4: `QuireWindow`, `LedgerWindow`, `LecternWindow` 专属应用窗口

**Files:**
- Create:
  - `src/atboffice/ui/shell/quire_window.py`
  - `src/atboffice/ui/shell/ledger_window.py`
  - `src/atboffice/ui/shell/lectern_window.py`
- Test: `tests/test_dedicated_windows.py`

**Interfaces:**
- Consumes:
  - `BaseOfficeWindow` (from Task 2)
  - `WriterView`, `SpreadsheetView`, `PresentationView`
  - `OfficeToolBar`, `StatusBar`, `ColorPickerButton`
  - `MacMenuBar`
- Produces:
  - `class QuireWindow(BaseOfficeWindow)`
  - `class LedgerWindow(BaseOfficeWindow)`
  - `class LecternWindow(BaseOfficeWindow)`

- [ ] **Step 1: Write the failing test for Dedicated Windows**

```python
# tests/test_dedicated_windows.py
import pytest
from atboffice.ui.shell.quire_window import QuireWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.modules.writer.view import WriterView
from atboffice.modules.spreadsheet.view import SpreadsheetView
from atboffice.modules.presentation.view import PresentationView

def test_quire_window_init(qtbot):
    win = QuireWindow()
    qtbot.addWidget(win)
    assert isinstance(win.centralWidget(), WriterView)
    assert "Quire" in win.windowTitle()

def test_ledger_window_init(qtbot):
    win = LedgerWindow()
    qtbot.addWidget(win)
    assert isinstance(win.centralWidget(), SpreadsheetView)
    assert "Ledger" in win.windowTitle()

def test_lectern_window_init(qtbot):
    win = LecternWindow()
    qtbot.addWidget(win)
    assert isinstance(win.centralWidget(), PresentationView)
    assert "Lectern" in win.windowTitle()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_dedicated_windows.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'atboffice.ui.shell.quire_window'"

- [ ] **Step 3: Implement `QuireWindow`, `LedgerWindow`, `LecternWindow`**

1. Create `src/atboffice/ui/shell/quire_window.py`: embed `WriterView`, Word 2003 Luna menus and toolbars.
2. Create `src/atboffice/ui/shell/ledger_window.py`: embed `SpreadsheetView`, Excel 2003 Luna menus, formula bar, AutoCalculate status bar.
3. Create `src/atboffice/ui/shell/lectern_window.py`: embed `PresentationView`, PowerPoint 2003 Luna menus, presenter toolbar.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_dedicated_windows.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/ui/shell/quire_window.py src/atboffice/ui/shell/ledger_window.py src/atboffice/ui/shell/lectern_window.py tests/test_dedicated_windows.py
git commit -m "feat(ui): implement dedicated QuireWindow, LedgerWindow, and LecternWindow"
```

---

### Task 5: `StartCenterWindow` 启动中心界面与交互

**Files:**
- Create: `src/atboffice/ui/shell/start_center.py`
- Test: `tests/test_start_center_ui.py`

**Interfaces:**
- Consumes:
  - `BaseOfficeWindow` (from Task 2)
  - `WindowManager` (from Task 3)
  - `RecentFilesManager` (from Task 1)
- Produces:
  - `class StartCenterWindow(BaseOfficeWindow)`:
    - `btn_new_quire: QPushButton`
    - `btn_new_ledger: QPushButton`
    - `btn_new_lectern: QPushButton`
    - `btn_open_file: QPushButton`
    - `recent_list_widget: QListWidget`
    - `refresh_recent_files() -> None`
    - `dragEnterEvent(event: QDragEnterEvent) -> None`
    - `dropEvent(event: QDropEvent) -> None`

- [ ] **Step 1: Write the failing test for StartCenterWindow**

```python
# tests/test_start_center_ui.py
from pathlib import Path
from PySide6.QtCore import QMimeData, QUrl, QPoint
from PySide6.QtGui import QDragEnterEvent, QDropEvent
import pytest
from atboffice.ui.shell.start_center import StartCenterWindow

def test_start_center_window_ui_init(qtbot):
    win = StartCenterWindow()
    qtbot.addWidget(win)
    assert win.acceptDrops() is True
    assert "Start Center" in win.windowTitle() or "启动中心" in win.windowTitle()
    assert win.btn_new_quire is not None
    assert win.btn_new_ledger is not None
    assert win.btn_new_lectern is not None

def test_start_center_drag_drop_accepts_urls(qtbot, tmp_path):
    win = StartCenterWindow()
    qtbot.addWidget(win)

    sample_doc = tmp_path / "test.docx"
    sample_doc.touch()

    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(str(sample_doc))])

    event = QDragEnterEvent(QPoint(10, 10), None, mime_data, None, None)
    win.dragEnterEvent(event)
    assert event.isAccepted()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_start_center_ui.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'atboffice.ui.shell.start_center'"

- [ ] **Step 3: Implement `StartCenterWindow` in `src/atboffice/ui/shell/start_center.py`**

Build the Left navigation bar (brand logo, Quire/Ledger/Lectern big launch buttons, open file button, settings/about), Right content area (Recent files list with icon, title, path, time, and remove button; empty state banner; template gallery cards), full window file drop event handling with `WindowManager.open_file_auto`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_start_center_ui.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/ui/shell/start_center.py tests/test_start_center_ui.py
git commit -m "feat(ui): implement StartCenterWindow with recent files and drag-drop support"
```

---

### Task 6: CLI 命令行分发器与应用入口整合

**Files:**
- Modify: `src/atboffice/__main__.py`
- Modify: `pyproject.toml`
- Test: `tests/test_cli_router.py`

**Interfaces:**
- Consumes:
  - `WindowManager` (from Task 3)
  - `ATBApplication`
- Produces:
  - `main(argv: list[str] | None = None, exec_app: bool = True) -> int`
  - `main_quire(argv: list[str] | None = None) -> int`
  - `main_ledger(argv: list[str] | None = None) -> int`
  - `main_lectern(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write the failing test for CLI router**

```python
# tests/test_cli_router.py
import pytest
from atboffice.__main__ import parse_cli_args

def test_parse_cli_args_empty():
    action, path = parse_cli_args([])
    assert action == "start_center"
    assert path is None

def test_parse_cli_args_subcommands():
    action, path = parse_cli_args(["quire", "mydoc.docx"])
    assert action == "quire"
    assert path == "mydoc.docx"

    action, path = parse_cli_args(["ledger"])
    assert action == "ledger"
    assert path is None

def test_parse_cli_args_direct_file():
    action, path = parse_cli_args(["spreadsheet.xlsx"])
    assert action == "file"
    assert path == "spreadsheet.xlsx"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_cli_router.py -v`
Expected: FAIL with "ImportError: cannot import name 'parse_cli_args' from 'atboffice.__main__'"

- [ ] **Step 3: Update `src/atboffice/__main__.py` and `pyproject.toml`**

Implement `parse_cli_args`, update `main()` to integrate with `WindowManager`, add `main_quire`, `main_ledger`, `main_lectern` wrappers, and register script entry points in `pyproject.toml`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_cli_router.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/__main__.py pyproject.toml tests/test_cli_router.py
git commit -m "feat(cli): implement CLI subcommands and router for module launching"
```

---

### Task 7: 端到端集成验证与全量回归测试

**Files:**
- Create: `tests/test_launcher_e2e.py`
- Test: All test suites in `tests/`

- [ ] **Step 1: Write the E2E lifecycle test**

```python
# tests/test_launcher_e2e.py
from pathlib import Path
import pytest
from atboffice.core.app import create_application
from atboffice.core.window_manager import WindowManager
from atboffice.ui.shell.start_center import StartCenterWindow
from atboffice.ui.shell.quire_window import QuireWindow

def test_full_launch_open_close_resurrect_cycle(qtbot, tmp_path):
    app = create_application(["atboffice"])
    win_mgr = WindowManager.get_instance()
    
    # 1. Start Center shown
    sc = win_mgr.show_start_center()
    qtbot.addWidget(sc)
    assert sc.isVisible()

    # 2. Open Quire document -> Start Center hidden
    doc_path = tmp_path / "hello.docx"
    doc_path.touch()
    q_win = win_mgr.open_quire(doc_path)
    qtbot.addWidget(q_win)
    assert q_win.isVisible()
    assert not sc.isVisible()

    # 3. Close Quire document -> Start Center resurrected
    q_win.close()
    assert sc.isVisible()
```

- [ ] **Step 2: Run E2E test**

Run: `PYTHONPATH=src pytest tests/test_launcher_e2e.py -v`
Expected: PASS

- [ ] **Step 3: Run all existing tests to ensure no regression**

Run: `PYTHONPATH=src pytest tests/`
Expected: All existing tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_launcher_e2e.py
git commit -m "test: add E2E test for launcher lifecycle and resurrection"
```

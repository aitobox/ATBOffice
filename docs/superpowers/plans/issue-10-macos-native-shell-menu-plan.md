# Implementation Plan: Issue #10 macOS Native Desktop Shell & System Menu

## Objective
Implement macOS native desktop shell, global unified menu bar with standard shortcuts, and Finder double-click dispatch for ATBOffice Ledger.

---

### Task 1: Core Application & Retina Scaling (`src/atboffice/core/app.py`)
- **Files**:
  - `src/atboffice/core/__init__.py`
  - `src/atboffice/core/app.py`
  - `tests/gui/test_mac_shell.py`
- **Actions**:
  1. Write failing test for `ATBApplication` in `tests/gui/test_mac_shell.py` (testing instantiation, High DPI policy setup, `QFileOpenEvent` handling, and signal emission / queueing).
  2. Implement `ATBApplication` in `src/atboffice/core/app.py`:
     - Setup High DPI policy.
     - Override `event(event: QEvent)` for `QFileOpenEvent`.
     - Support registering a main window and routing file open events.
  3. Verify test passes: `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_mac_shell.py -k test_atb_application`.

---

### Task 2: macOS Native Global Menu Bar (`src/atboffice/ui/shell/mac_menu.py`)
- **Files**:
  - `src/atboffice/ui/shell/__init__.py`
  - `src/atboffice/ui/shell/mac_menu.py`
  - `tests/gui/test_mac_shell.py`
- **Actions**:
  1. Add tests in `tests/gui/test_mac_shell.py` for `MacMenuBar` and `setup_mac_menu`:
     - Verification of `nativeMenuBar == True` on macOS.
     - Presence of File, Edit, View, Window, Help menus.
     - Verification of shortcut bindings (`⌘S`, `⇧⌘S`, `⌘Z`, `⇧⌘Z`, `⌘1`, `⌘C`, `⌘V`, `⌘W`, etc.).
     - `retranslate_ui()` support and localized text.
  2. Implement `MacMenuBar` in `src/atboffice/ui/shell/mac_menu.py`:
     - Construct menus with standard HIG actions.
     - Connect action triggers to window callbacks or signals.
     - Full i18n localization with `safe_tr()`.
  3. Verify test passes: `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_mac_shell.py -k test_mac_menu`.

---

### Task 3: Shell Main Window & Workbook Lifecycle (`src/atboffice/ui/shell/main_window.py`)
- **Files**:
  - `src/atboffice/ui/shell/main_window.py`
  - `src/atboffice/ui/main_window.py` (backward compatibility)
  - `tests/gui/test_mac_shell.py`
- **Actions**:
  1. Add tests in `tests/gui/test_mac_shell.py` for `MainWindow`:
     - Document dirty tracking: `set_modified(True)`, `is_modified`.
     - Window title update with modified indicator `[*]`.
     - `open_file(path)` and `save_file(path)` lifecycle.
     - `closeEvent()` prompt handling when dirty (Save, Don't Save, Cancel).
     - Backward compatibility verification (has 3 office modules, matches `tests/test_main_window.py`).
  2. Implement `MainWindow` in `src/atboffice/ui/shell/main_window.py`.
  3. Update `src/atboffice/ui/main_window.py` to inherit or expose the new shell `MainWindow`.
  4. Verify test passes: `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_mac_shell.py -k test_main_window`.

---

### Task 4: Command-Line Dispatch & Application Entry Point (`src/atboffice/__main__.py`)
- **Files**:
  - `src/atboffice/__main__.py`
  - `tests/gui/test_mac_shell.py`
- **Actions**:
  1. Update `src/atboffice/__main__.py` to use `ATBApplication` and `MainWindow`, dispatching command line arguments `sys.argv[1:]` to `open_file()`.
  2. Add test in `tests/gui/test_mac_shell.py` verifying CLI argument handling.
  3. Verify test passes.

---

### Task 5: Full Regression Testing & Verification
- Run complete test suite:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice pytest tests/ -v
  ```
- Ensure all tests pass with 0 errors and 0 regressions.
- Transition state to `reviewing` and chain-invoke `atb-github-code-reviewer`.

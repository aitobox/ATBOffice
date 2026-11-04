# Technical Specification: TASK-703 Stability, Crash Replay Diagnostics & Object Lifecycle Governance

- **Issue**: [#237](https://github.com/aitobox/ATBOffice/issues/237)
- **Task ID**: TASK-703
- **Parent Epic**: [#234](https://github.com/aitobox/ATBOffice/issues/234)
- **Status**: Draft / Approved

---

## 1. Problem Statement & Motivation

Prior stability tests in Phase 6 proved basic smoke pass under short-range offscreen execution, but real-world office suites experience crashes primarily during **dynamic interaction sequences**:
1. Switching worksheets or opening another document while an in-cell editor is active or a cell drag/fill gesture is underway.
2. Closing a document window while background tasks, deferred events, or auto-scroll timers are pending.
3. Rapidly popping and dismissing modal dialogs or menus (modal re-entrancy).
4. Silent failures where unhandled exceptions inside Qt slots or normal launches do not produce actionable crash logs or command breadcrumbs, making user-reported bugs impossible to reproduce.

In `.vibeoffice` (`common/ui.js` lines 834-920 and `ledger/js/app.js`), any drag gesture or view switch strictly terminates previous gestures with explicit cancellation reasons (`'esc'`, `'button'`, `'blur'`, `'api'`), ensuring no dangling timers or half-committed states remain. Furthermore, document closing always goes through an atomic confirmation check.

In ATBOffice (Python / PySide6), we must match and exceed this robustness:
- Explicit QObject and widget ownership, disconnection of obsolete signals, and draining of pending deferred deletions.
- A thread-safe, bounded ring buffer for recent user action sequences and sanitized document SHA tracking.
- Automatic uncaught exception and Qt slot exception logging in both standard runs and test harnesses.
- Dedicated isolated subprocess replay tests covering opening during edit, window closure, view switching, menu/dialog lifecycle, and 100-cycle stress runs.

---

## 2. Architecture & Design

### 2.1 Action Sequence Recorder & Document SHA Telemetry (`core/diagnostics.py`)
- **`ActionRecorder`**:
  - Maintains a thread-safe circular buffer (default maxlen=50) of recent actions: `(timestamp, action_name, component, details)`.
  - Records events such as: `open_document`, `switch_sheet`, `start_drag`, `cancel_drag`, `commit_editor`, `open_dialog`, `close_dialog`, `close_window`.
  - In the event of an uncaught exception or crash, serializes the action sequence into the diagnostic report.
- **`DocumentTelemetry`**:
  - Computes and caches SHA-256 hashes of opened documents without exposing document text or confidential paths.
- **Default Crash Logger**:
  - `install_default_crash_handler()`: Installed on application startup. Ensures that even without `--diagnostics`, any fatal exception writes a crash report to `~/.atboffice/logs/crash.log` or platform log directory, containing environment telemetry, sanitized traceback, document SHA, and recent action sequence.
- **Qt Slot Exception Assertion**:
  - During test execution, unhandled exceptions inside Qt slots are trapped and registered as test failures.

### 2.2 Lifecycle & Cleanup in Window Manager (`core/window_manager.py`)
- **Document Switching & Opening During Edit**:
  - In `open_file_auto` / `open_*`: If a target window is already open and modified, safely invoke `maybe_save_prompt()`. If the user cancels, do not proceed or discard modifications.
- **Modal Reentrancy Guard**:
  - Protect against concurrent modal dialog loops using an explicit modal guard.
- **Safe Window Closing**:
  - Before closing a window, cancel any active drag or gestures on embedded viewports, disconnect signal listeners, stop any active view timers, and invoke `deleteLater()`.

### 2.3 Spreadsheet View Lifecycle & Gesture Cancellation (`modules/spreadsheet/view.py`)
- **Workbook & Sheet Rebinding**:
  - Before changing `workbook` or switching active sheet:
    - Cancel active drag: `self.grid.cancel_drag(why="api")`.
    - Commit or discard in-cell editor: `self.editor_controller.cancel_editing()`.
    - Disconnect listeners from previous workbook/sheets to prevent memory leaks and zombie slot invocations.
    - Synchronize `object_layer` cleanly without lingering scene items.

### 2.4 Subprocess Native Replay & Diagnostics Test Suite (`tests/gui/test_phase7_native_replay.py`)
- New comprehensive test file verifying:
  1. `test_open_during_edit_replay`: Opening another document while an editor is dirty.
  2. `test_window_close_during_drag_replay`: Cancelling drag and closing window without crash or resource leak.
  3. `test_view_mode_switching_replay`: Switching between normal and page-break preview while cells are selected.
  4. `test_modal_dialog_reentrancy_replay`: Popping and dismissing modal dialogs cleanly.
  5. `test_action_recorder_and_sha_telemetry`: Verifying action sequences and SHA are properly recorded upon error.
  6. `test_100_cycle_mixed_stress_replay`: 100 iterations of rapid sheet switching, cell editing, and modal dismissal.

---

## 3. Acceptance Criteria & Test Commands
- **Acceptance Criteria**:
  - [x] All 5 interaction patterns (open during edit, close window, switch view, menu/dialog, 100-cycle mixed) execute in isolated subprocesses with exit code 0.
  - [x] Simulated crash generates sanitized report with environment telemetry, document SHA, and recent action sequence.
  - [x] Zero unhandled Qt slot exceptions.
  - [x] `phase7_features.csv` updated with test and version evidence.
- **Target Command**:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_native_replay.py tests/gui/test_crash_replay_diagnostics.py -ra
  ```

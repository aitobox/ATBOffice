# Implementation Plan: TASK-703 Stability, Crash Replay Diagnostics & Object Lifecycle Governance

- **Issue**: [#237](https://github.com/aitobox/ATBOffice/issues/237)
- **Task ID**: TASK-703
- **Branch**: `agent/issue-237-stability-crash-lifecycle`
- **Spec**: `docs/superpowers/specs/issue-237-stability-crash-lifecycle-spec.md`

---

## Task 1: Action Sequence Tracking & Default Crash Logging in `core/diagnostics.py`
- **Files**:
  - `src/atboffice/core/diagnostics.py`
- **Implementation**:
  - Implement `ActionRecorder` singleton class with `record_action(action, component, details)`.
  - Implement `record_document_sha(filepath_or_bytes)` to calculate and cache SHA-256 for active documents without leaking content.
  - Implement `install_default_crash_handler(log_dir=None)`:
    - Installs excepthook even on standard desktop launches (logging to `~/.atboffice/logs/crash.log`).
    - Formats report including: Timestamp, Environment Telemetry, Recent Action Sequence, Document SHA, and Sanitized Traceback.
  - Implement `enable_qt_slot_exception_assertion()`:
    - Intercepts uncaught exceptions in Qt slots during test runs and asserts failure.
- **Verification**:
  - Unit tests verifying `ActionRecorder` maintains bounded FIFO order and `record_document_sha` produces valid sanitized SHA-256 string.

---

## Task 2: CLI Replay Capabilities & Automatic Handler in `__main__.py`
- **Files**:
  - `src/atboffice/__main__.py`
- **Implementation**:
  - Automatically call `install_default_crash_handler()` at application launch so standard runs capture unhandled exceptions without explicit flags.
  - Extend `--replay-action` to support new action sequences:
    - `open_during_edit`: Start editing a document, open another document, verify safe handling.
    - `switch_views`: Toggle sheet view modes (normal / page-break) while editing or selecting.
    - `modal_menu_dialog`: Open and close dialogs (e.g., About, Options, Goal Seek) and context menus.
    - `drag_cancel_lifecycle`: Start cell drag / fill, cancel via API/Esc/button, close window.
    - `stress_interaction`: Run repeated rapid operations across views.
- **Verification**:
  - Test invocation of each action with `--replay-action=<action>` in isolated subprocesses.

---

## Task 3: Lifecycle Hardening in `window_manager.py` and `spreadsheet/view.py`
- **Files**:
  - `src/atboffice/core/window_manager.py`
  - `src/atboffice/modules/spreadsheet/view.py`
- **Implementation**:
  - In `window_manager.py`:
    - Disarm live drags and cancel pending gestures before closing windows.
    - Implement modal re-entrancy prevention.
    - In `unregister_window`, ensure complete signal disconnection and event loop draining.
  - In `spreadsheet/view.py`:
    - In `_on_active_sheet_changed` and `workbook.setter`:
      - Explicitly invoke `self.grid.cancel_drag(why="api")`.
      - Cancel or commit cell editor before switching sheets.
      - Disconnect obsolete signals from previous sheet selections.
- **Verification**:
  - Replay test passes without unhandled exceptions or object reference errors.

---

## Task 4: New Native Replay Test Suite (`test_phase7_native_replay.py`)
- **Files**:
  - `tests/gui/test_phase7_native_replay.py`
- **Implementation**:
  - Implement pytest suite executing ATBOffice in isolated subprocesses:
    - `test_open_during_edit_replay`
    - `test_drag_cancel_and_window_close_replay`
    - `test_view_mode_switching_replay`
    - `test_modal_dialog_lifecycle_replay`
    - `test_action_recorder_and_sha_telemetry`
    - `test_100_cycle_mixed_stress_replay`
- **Verification**:
  - Run `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_native_replay.py tests/gui/test_crash_replay_diagnostics.py -ra`
  - Exit code 0, all tests pass.

---

## Task 5: Evidence & CSV Matrix Update
- **Files**:
  - `docs/clone/phase7_features.csv`
- **Implementation**:
  - Update entries for Application Lifecycle and Multi-Window Management:
    - Set `clone` to `yes`
    - Set `verification_status` to `verified`
    - Add evidence reference to `tests/gui/test_phase7_native_replay.py` and PR commit SHA.

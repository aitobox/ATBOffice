# Implementation Plan: Issue #319 — Mitigate Window Close Re-entrancy and Lifecycle Cleanup

## Tasks

### Task 1: Add Re-entrancy Protection to `drain_event_loop()`
- Target File: `src/atboffice/core/diagnostics.py`
- Description: Protect `drain_event_loop()` against recursive re-entrant execution by adding a global `_is_draining` state guard.
- Verification: Call `drain_event_loop` recursively within an event callback; verify no recursion error or hang.

### Task 2: Implement `RecoveryService` with Clean Lifecycle Management
- Target File: `src/atboffice/core/recovery_service.py`
- Description: Create `RecoveryService` managing document autosave and recovery drafts, providing `start()`, `stop()`, and `cleanup()`. Ensure its `QTimer` and any worker threads terminate immediately and cleanly when stopped.
- Export in `src/atboffice/core/__init__.py`.

### Task 3: Enhance `BaseOfficeWindow.closeEvent()` and Resource Cleanup
- Target File: `src/atboffice/ui/shell/base_window.py`
- Description:
  - Add `self.recovery_service = RecoveryService(self)` in `__init__`.
  - Implement `cleanup_resources()` to stop all descendant `QTimer`s, stop `recovery_service`, and disconnect signals.
  - Update `closeEvent()` with robust re-entrancy flags (`_is_closed`, `_in_close_event`) and invoke `cleanup_resources()` before draining event loop.

### Task 4: Create Unit Test Suite
- Target File: `tests/gui/test_window_close_reentrancy.py`
- Test Cases:
  - `test_drain_event_loop_reentrancy_guard`: Recursive invocation does not deadlock or crash.
  - `test_recovery_service_lifecycle_and_clean_stop`: Timer and background thread stop cleanly without lingering.
  - `test_base_office_window_close_stops_child_timers`: Child `QTimer`s are confirmed stopped upon window close.
  - `test_window_close_reentrancy_prevention`: Rapid duplicate close calls do not trigger multiple save prompts or recursive drains.
  - `test_rapid_multi_window_lifecycle`: Open and close Quire, Ledger, and Lectern windows rapidly in succession.

### Task 5: Verification & Regression Testing
- Command: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_window_close_reentrancy.py -v`
- Run regression tests to ensure zero regressions across existing test suites.

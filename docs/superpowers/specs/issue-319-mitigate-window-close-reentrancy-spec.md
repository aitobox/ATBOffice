# Technical Specification: Issue #319 — Mitigate Event Loop Re-entrancy During Window Close and Lifecycle Cleanup

## 1. Problem Statement & Motivation
During test suite diagnostics on macOS Cocoa (and headless offscreen CI environments), invoking `drain_event_loop()` inside `BaseOfficeWindow.closeEvent()` can trigger recursive event processing if window events, deferred deletions (`DeferredDelete`), or widget timers are pending.

When `app.processEvents()` is invoked inside an active `closeEvent()`:
1. Pending timers, layout requests, or duplicate close events for the window can be dispatched re-entrantly.
2. In rapid multi-window open/close sequences (such as batch test runs or tab cycling), recursive calls can lead to stack overflow, application event loop spinning, or segmentation faults during widget destruction.
3. Autosave timers or background threads from recovery services can continue firing after the parent window has begun destruction, referencing half-destroyed Qt widgets.

## 2. Proposed Architecture & Solutions

### A. Re-entrancy Guard & Safety in `drain_event_loop()`
In `src/atboffice/core/diagnostics.py`:
- Add a thread-safe / execution-scoped guard `_is_draining: bool = False` inside `drain_event_loop()`.
- If `_is_draining` is already True, immediately return to prevent recursive nested loop processing.
- Wrap event loop draining in `try...finally` ensuring `_is_draining` is reset even if an exception occurs.

### B. Safe Lifecycle Cleanup in `BaseOfficeWindow.closeEvent()`
In `src/atboffice/ui/shell/base_window.py`:
- Implement a dedicated cleanup method `cleanup_resources()` called upon close acceptance:
  1. **Stop all active `QTimer`s**: Iterate through `self.findChildren(QTimer)` and call `timer.stop()` to eliminate pending timer events.
  2. **Terminate Recovery Service**: Call `self.recovery_service.stop()` to stop any autosave timers and wait for background worker threads to terminate cleanly.
  3. **Cancel active edits & gestures**: Cancel active drag operations on grid viewports, cancel active inline cell/caret editors.
  4. **Safely Disconnect Signals**: Disconnect window signals and model change listeners that could trigger UI updates during deferred deletion.
- Guard `closeEvent()` against re-entrancy:
  - Check `_is_closing` and `_is_closed` flags. If `_is_closed` is True, accept event and return immediately.
  - Set `_is_closing = True` during prompt and cleanup, transitioning to `_is_closed = True` when close is accepted.
  - Wrap `drain_event_loop()` call in re-entrancy checks.

### C. `RecoveryService` Implementation (`src/atboffice/core/recovery_service.py`)
- Provides `RecoveryService(QObject)`:
  - Manages document autosave / draft intervals.
  - Supports `start()`, `stop()`, `schedule_autosave()`, and `cleanup()`.
  - Ensures all internal `QTimer` instances are stopped and worker threads joined on `stop()`.
  - Integrates cleanly with `BaseOfficeWindow` via `self.recovery_service = RecoveryService(self)`.

### D. Unit & Integration Test Suite
In `tests/gui/test_window_close_reentrancy.py`:
- Test rapid repeated `close()` and `closeEvent()` invocations.
- Test that all child `QTimer`s are stopped upon close.
- Test that `RecoveryService` timer and background tasks terminate cleanly without lingering threads.
- Test that `drain_event_loop()` handles recursive calls without hanging or crashing.
- Test multi-window open/close sequences across Quire, Ledger, and Lectern windows.

# Implementation Plan: Issue #189 - [Phase 5] 建立三模块崩溃诊断与子进程重放基线

## 1. Overview
This plan implements the crash diagnostics and subprocess GUI replay baseline for the Quire, Ledger, and Lectern modules in ATBOffice. It follows test-driven development (TDD) across all tasks.

## 2. Tasks & Detailed Steps

### Task 1: Diagnostics Core (`src/atboffice/core/diagnostics.py`)
- **Files**:
  - `src/atboffice/core/diagnostics.py`
  - `tests/unit/core/test_diagnostics.py`
- **Steps**:
  1. Write unit tests in `tests/unit/core/test_diagnostics.py`:
     - Test environment telemetry collection (Python, Qt, OS, Git commit SHA).
     - Test `CrashDiagnostics` enabling faulthandler and custom excepthook.
     - Test traceback privacy scrubbing (ensures file/function names are kept, but object data is sanitized).
     - Test detection of platform crash report locations.
  2. Implement `src/atboffice/core/diagnostics.py`.
  3. Run `pytest tests/unit/core/test_diagnostics.py` to confirm passes.

### Task 2: CLI Options & Event Loop Draining (`src/atboffice/__main__.py` & `app.py`)
- **Files**:
  - `src/atboffice/core/app.py`
  - `src/atboffice/__main__.py`
  - `tests/test_cli_router.py`
- **Steps**:
  1. Add event loop draining helper (`drain_event_loop()`) in `app.py`.
  2. Add CLI flags in `__main__.py`:
     - `--diagnostics`
     - `--crash-log <path>`
     - `--replay-action <action>` (e.g. `switch_windows`, `hover_canvas`, `open_dialog`, `close_drain`)
     - `--simulate-crash <segfault|exception>` (for test validation)
  3. Test CLI argument routing and event draining behavior in `tests/test_cli_router.py`.

### Task 3: Subprocess GUI Replay Test Suite (`tests/gui/test_crash_replay_diagnostics.py`)
- **Files**:
  - `tests/gui/test_crash_replay_diagnostics.py`
- **Steps**:
  1. Implement `SubprocessReplayRunner`:
     - Spawns subprocess with `python -m atboffice <module> ...`
     - Measures elapsed execution time.
     - Detects timeout (> 15s) and terminates process.
     - Detects crashes (exit code != 0, SIGSEGV, SIGABRT) and parses `faulthandler` stack.
     - Captures platform crash reports if present.
     - Asserts zero document content leakage in captured diagnostics.
  2. Implement tests for all three modules:
     - `test_quire_subprocess_replay()`
     - `test_ledger_subprocess_replay()`
     - `test_lectern_subprocess_replay()`
  3. Implement fault detection tests:
     - `test_subprocess_crash_detection()` (verifies crash status and stack trace capture)
     - `test_subprocess_timeout_detection()` (verifies timeout status)
  4. Implement event loop drain test:
     - `test_window_close_event_loop_drain()`

### Task 4: Project-wide Verification & Diff Doc Update
- **Files**:
  - `docs/clone/CLONE_DIFF.md`
- **Steps**:
  1. Run project-wide test suite:
     `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`
  2. Update `docs/clone/CLONE_DIFF.md` with the verified baseline evidence.
  3. Transition state to `reviewing` and trigger `atb-github-code-reviewer`.

# Specification: Issue #189 - [Phase 5] 建立三模块崩溃诊断与子进程重放基线

## 1. Background & Problem Statement

In Phase 4, ATBOffice completed the 1:1 migration and advanced features, but stability and interaction parity audit (Phase 5) identified the necessity of establishing a systematic diagnostic baseline. Users reported intermittent desktop crashes during interaction, while the reproduction trace and native stack logs were difficult to capture without sub-process isolation and automated fault telemetry.

Issue #189 establishes the foundational diagnostic and replay baseline (Step 1 of 13 for Epic #188). Subsequent Phase 5 issues (#190-#201) depend on this baseline to reproduce, isolate, and verify fixes for crashes, lifecycle issues, toolbar wiring, and mouse interactions across the Quire, Ledger, and Lectern modules.

## 2. Requirements & Acceptance Criteria

1. **Subprocess GUI Replay Harness**:
   - Capable of launching each module (`quire`, `ledger`, `lectern`) in an isolated subprocess.
   - Executes standard event sequences: launch, window switching, mouse hovering, dialog open/close lifecycle, and clean window closing.
   - Accurately classifies outcome into:
     - `normal_exit` (exit code 0, clean termination)
     - `crash` (non-zero exit code, SIGSEGV/SIGABRT, or unhandled exception)
     - `timeout` (process hung or unresponsive past deadline)

2. **Crash & Fault Diagnostics**:
   - Integrates Python `faulthandler` pointing to designated crash logs for SIGSEGV / SIGABRT native crash tracebacks.
   - Implements custom `sys.excepthook` capturing Python exception traces.
   - Collects environmental telemetry: Python version, PySide6/Qt version, OS platform & architecture, Git SHA of the clone (`ATBOffice`) and original (`.vibeoffice`).
   - Identifies platform-specific crash report directories (`~/Library/Logs/DiagnosticReports/` on macOS, `/var/crash` on Linux).
   - **Privacy Protection**: Diagnostics strictly log execution frames, module names, line numbers, and error classifications; user document text and payload data are never collected.

3. **Event Loop Draining & Clean Shutdown**:
   - Implements thorough event loop draining upon window close and application exit (`QCoreApplication.processEvents()` and `sendPostedEvents(None, QEvent.Type.DeferredDelete)`).
   - Prevents use-after-free or double-free segfaults during object destruction.

4. **i18n & Parity Integration**:
   - Any new diagnostic user-facing strings support `safe_tr()` / `tr()` with `retranslate_ui`.
   - Update `docs/clone/CLONE_DIFF.md` with the verified baseline results.

## 3. Architecture & Module Design

```
+-----------------------------------------------------------+
|               atboffice.core.diagnostics                  |
|  - enable_crash_diagnostics(log_path, capture_env)        |
|  - get_environment_telemetry() -> dict                    |
|  - find_recent_crash_reports() -> list[Path]              |
|  - sanitize_traceback(tb_str) -> str                      |
+-----------------------------------------------------------+
                             |
                             v
+-----------------------------------------------------------+
|               atboffice.__main__ / app                    |
|  - CLI options: --diagnostics, --crash-log, --replay-seq  |
|  - Clean shutdown & event loop drain in main()            |
+-----------------------------------------------------------+
                             |
                             v
+-----------------------------------------------------------+
|           tests/gui/test_crash_replay_diagnostics.py      |
|  - SubprocessReplayRunner:                                |
|      * run_replay(module, sequence, timeout)              |
|      * classify_result() -> ReplayResult                  |
|  - Replay Tests: Quire, Ledger, Lectern                   |
|  - Fault Detection Verification (Crash & Timeout tests)   |
|  - Event Loop Drain Validation                            |
+-----------------------------------------------------------+
```

## 4. Implementation Steps

1. **Create `src/atboffice/core/diagnostics.py`**:
   - Implement `EnvironmentTelemetry` collecting Python, Qt, OS, and Git commit hashes.
   - Implement `CrashDiagnostics` enabling `faulthandler`, custom `excepthook`, signal handlers, and platform report scanning.
   - Implement privacy-preserving trace formatting.

2. **Integrate into `src/atboffice/__main__.py` & `src/atboffice/core/app.py`**:
   - Support CLI arguments: `--diagnostics`, `--crash-log <path>`, `--replay-sequence <json>`, `--simulate-crash <type>`.
   - Ensure `ATBApplication` and `main()` invoke event loop draining during shutdown.

3. **Create Subprocess Replay Test Suite `tests/gui/test_crash_replay_diagnostics.py`**:
   - Implement `SubprocessReplayRunner`.
   - Write parameterized tests for Quire, Ledger, and Lectern executing full interaction sequences (launch -> switch -> hover -> dialog -> close).
   - Write tests validating crash discrimination (synthetic crash triggers `status == "crash"` with stack trace).
   - Write tests validating timeout discrimination (`status == "timeout"`).
   - Verify event loop drain and zero uncollected leaks.

4. **Update `docs/clone/CLONE_DIFF.md`**:
   - Document Phase 5.0 diagnostic baseline results.

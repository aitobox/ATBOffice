# Implementation Plan: Issue #201 - [Phase 5] 执行三模块端到端与稳定性最终验收

## Overview
Implement the comprehensive end-to-end acceptance test suite for Phase 5, execute mixed interaction stress tests across Quire, Ledger, and Lectern, run full verification, and synchronize audit documentation (`CLONE_DIFF.md`, `features.csv`, `05_phase5_parity_stability_plan.md`).

---

## Tasks

### Task 1: Implement `tests/gui/test_phase5_e2e_acceptance.py`
- **File**: `tests/gui/test_phase5_e2e_acceptance.py`
- **Tests**:
  1. `test_quire_e2e_workflow_and_roundtrip`:
     - Creates new Quire document in `QuireWindow`.
     - Types text, formats bold/italic, triggers undo/redo.
     - Saves to `.docx` via `win.save_file_as()`.
     - Reopens in a new window, verifies content matches.
     - Modifies, simulates close, cancels via message box mock, asserts window open and dirty state preserved.
  2. `test_ledger_e2e_workflow_and_roundtrip`:
     - Creates new workbook in `LedgerWindow`.
     - Inputs numbers, strings, and formula in cells.
     - Formats cell styling, verifies undo/redo.
     - Saves to `.xlsx` via `win.save_file_as()`.
     - Reopens in new window, verifies values and formula.
     - Modifies, simulates close, cancels close, asserts window open and dirty state preserved.
  3. `test_lectern_e2e_workflow_and_roundtrip`:
     - Creates new presentation in `LecternWindow`.
     - Adds shapes and text runs, formats fill and font.
     - Verifies undo/redo.
     - Saves to `.pptx` via `win.save_file_as()`.
     - Reopens in new window, verifies slides and shapes.
     - Modifies, simulates close, cancels close, asserts window open and dirty state preserved.
  4. `test_three_modules_in_process_100_mixed_interactions`:
     - Runs 100 mixed GUI interactions (caret/cursor navigation, edits, formatting toggles, mouse moves) on Quire, Ledger, and Lectern.
     - Asserts zero exceptions, zero memory corruption, and clean event processing.
  5. `test_three_modules_subprocess_100_stress_replay`:
     - Uses `SubprocessReplayRunner` to execute isolated OS processes for `quire`, `ledger`, and `lectern`.
     - Runs `--replay-action=stress_interaction` with `--replay-iterations=100`.
     - Asserts exit code 0, 0 crash logs, and clean exit.

### Task 2: Verify `test_phase5_e2e_acceptance.py`
- Run `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase5_e2e_acceptance.py -v`.
- Confirm all tests pass with exit code 0.

### Task 3: Audit & Parity Scripts Execution
- Run `python3 scripts/source_diff.py` (verify 0 orphans, 0 stubs).
- Run `python3 scripts/parity.py --markdown` (verify 100.0% must-have score).
- Run `python3 scripts/audit_toolbars_parity.py` (confirm baseline matrix consistency).

### Task 4: Documentation Synchronization & Evidence Backfill
- **`docs/clone/CLONE_DIFF.md`**:
  - Update TASK-503, TASK-505, TASK-506, TASK-507 checklist items to checked `[x]`.
  - Record the latest test pass counts, Python/PySide6 versions, and stress test metrics.
  - Update Shippability verdict to **SHIPPABLE / SUPERIOR** for Phase 5.
- **`docs/clone/features.csv`**:
  - Verify all audited items reflect the verified behavior.
- **`docs/tasks/05_phase5_parity_stability_plan.md`**:
  - Update implementation checklist items and mark Phase 5 complete.

### Task 5: Final Full-Suite Verification Gate
- Run full pytest suite: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`.
- Ensure zero failures, zero regressions across 1360+ tests.

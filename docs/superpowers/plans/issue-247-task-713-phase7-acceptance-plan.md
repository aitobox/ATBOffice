# Implementation Plan: Issue #247 - TASK-713 test(acceptance): 以真实用户路径完成第七期验收

## 1. Plan Overview
TASK-713 represents the comprehensive integration and acceptance test suite for ATBOffice Phase 7. This plan outlines the exact implementation tasks, files created/modified, and verification commands.

## 2. Tasks Breakdown

### Task 1: Create `tests/gui/test_phase7_acceptance.py`
- **File**: `tests/gui/test_phase7_acceptance.py`
- **Scope**:
  - `test_quire_user_journey_e2e_acceptance`: Quire New -> Edit Paragraphs -> Format -> Undo/Redo -> Save to Temp DOCX -> Reopen & Assert Parity.
  - `test_ledger_user_journey_e2e_acceptance`: Ledger New -> Set Cells/Formulas -> Right-Click Context Menu Actions -> Autofill Drag Handle Expansion -> Undo/Redo -> Save to Temp XLSX -> Reopen & Assert Parity.
  - `test_lectern_user_journey_e2e_acceptance`: Lectern New -> Add Slide -> Add Shape & Text -> Format Properties -> Undo/Redo -> Save to Temp PPTX -> Reopen & Assert Parity.
  - `test_phase7_transactional_safety_and_diagnostics`: Corrupt/invalid file open rejected cleanly without modifying window state, breadcrumbs logged.
  - `test_phase7_dynamic_locales_and_retranslate`: Dynamic switching through 9 supported locales (`zh-CN`, `zh-Hant`, `en`, `ja`, `ko`, `fr`, `de`, `es`, `ru`) ensuring `retranslate_ui` succeeds cleanly.
  - `test_phase7_mixed_operation_lifecycle_stress`: Mixed editing and window lifecycle in Qt event loop with clean event draining.
  - `test_phase7_features_matrix_evidence`: Validation that all `must` features in `docs/clone/phase7_features.csv` have status `verified` and non-empty `evidence`.

### Task 2: Audit and Complete `docs/clone/phase7_features.csv`
- **File**: `docs/clone/phase7_features.csv`
- **Scope**:
  - Map every feature to verified automated tests across unit and GUI test suites.
  - Ensure all 100% of `must` items are marked `verified` with concrete evidence.

### Task 3: Update `docs/clone/CLONE_DIFF.md`
- **File**: `docs/clone/CLONE_DIFF.md`
- **Scope**:
  - Update TASK-713 section with test output, parity metrics, and evidence log.
  - Update Phase 7 overall verdict.

### Task 4: Update `docs/tasks/07_phase7_fidelity_stability_compatibility_plan.md`
- **File**: `docs/tasks/07_phase7_fidelity_stability_compatibility_plan.md`
- **Scope**:
  - Check off `[x] TASK-713 全期真实验收`.
  - Record execution summary.

### Task 5: Full Test Suite Verification & Transition to Review
- **Commands**:
  - `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_acceptance.py -ra`
  - `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/ -ra -q`
- **State Transition**:
  - Update state to `reviewing`
  - Chain-invoke `atb-github-code-reviewer`

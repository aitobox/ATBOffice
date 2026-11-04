# Specification: Issue #247 - TASK-713 test(acceptance): 以真实用户路径完成第七期验收

## 1. Overview & Objectives
TASK-713 is the final integration and acceptance milestone (Step 13 of 13) of Phase 7 (#234). It synthesizes all prior Phase 7 deliverables—including transactional file open rollback (TASK-702), crash replay diagnostics and stability (TASK-703), 150-file corpus contracts (TASK-704), Strict DOCX rendering (TASK-705), XLSX/XLSM lossless preservation (TASK-706), Ledger viewport sync (TASK-707), Lectern PPTX roundtrip (TASK-708), Ledger context menus (TASK-709), drag-fill event chains (TASK-710), toolbar geometry calibration (TASK-711), and visible command localization (TASK-712).

This task delivers:
1. `tests/gui/test_phase7_acceptance.py`: An end-to-end acceptance test suite covering real user paths across Quire, Ledger, and Lectern, testing file opening, editing, context menus, drag autofill, undo/redo, saving/reopening, transactional rejection, multi-locale dynamic switching, and lifecycle integrity.
2. `docs/clone/phase7_features.csv`: A comprehensive verification matrix associating every feature with its verification status and concrete automated test / screenshot evidence.
3. `docs/clone/CLONE_DIFF.md`: Comprehensive documentation of Phase 7 acceptance results, parity scores, test counts, and shippability verdict.
4. `docs/tasks/07_phase7_fidelity_stability_compatibility_plan.md`: Updated execution status marking Phase 7 and TASK-713 as completed.

## 2. Requirements & Acceptance Gates

### Gate 1: Functional User Journeys (Real User Paths)
- **Quire User Journey**:
  - Open document, insert text paragraphs, apply formatting (bold/italic/headings).
  - Exercise undo/redo, check dirty flag transitions.
  - Save to temporary file, verify OPC structure and body content.
  - Reopen saved document in fresh window; assert exact text and layout parity.
- **Ledger User Journey**:
  - Open workbook, edit cells and formulas (e.g. SUM, cross-cell references).
  - Exercise right-click context menu (cut, copy, paste, clear, format).
  - Exercise drag autofill handle (sequential numbers/dates expansion, protection checks).
  - Exercise undo/redo.
  - Save to temporary XLSX, verify OPC package preservation.
  - Reopen saved workbook in fresh window; assert cell values, formulas, and sheet names.
- **Lectern User Journey**:
  - Open presentation, add slides, insert vector shapes and text bodies.
  - Modify shape geometry and properties, exercise undo/redo.
  - Save to temporary PPTX, verify PresentationML structure.
  - Reopen saved presentation; assert slide count, shapes, and text bodies.

### Gate 2: Safety & Transactional Rejection
- Attempt opening corrupt, encrypted-without-key, or invalid format files.
- Verify transactional rollback: `do_open` returns `False`, document path remains intact, clean/dirty state preserved, no uncaught Qt exceptions.

### Gate 3: Dynamic Multi-Locale & Command Integrity
- Dynamically toggle across all 9 supported locales (`zh-CN`, `zh-Hant`, `en`, `ja`, `ko`, `fr`, `de`, `es`, `ru`).
- Assert `retranslate_ui` reloads localized strings on menus, toolbars, and action registries without duplicate connections or memory leaks.

### Gate 4: Stability & Lifecycle
- Run multi-step mixed editing and window lifecycle operations with `drain_event_loop()`.
- Ensure proper teardown and window close events without dangling threads or segfaults.

### Gate 5: Verification Evidence & CSV Parity Matrix
- Audit `docs/clone/phase7_features.csv`.
- Map all `must` and completed features to concrete test files (`tests/gui/test_phase7_*.py`, `tests/unit/corpus/`, etc.).
- Update `CLONE_DIFF.md` and the Phase 7 task plan.

## 3. Architecture & Target Files

| Target File | Purpose |
|---|---|
| `tests/gui/test_phase7_acceptance.py` | New E2E acceptance test suite executing real user journeys and gates. |
| `docs/clone/phase7_features.csv` | Feature verification matrix with updated `verification_status` and `evidence`. |
| `docs/clone/CLONE_DIFF.md` | Phase 7 final acceptance report, feature parity, test statistics, and shippability. |
| `docs/tasks/07_phase7_fidelity_stability_compatibility_plan.md` | Final status update marking TASK-713 completed. |

## 4. Verification Command
```bash
PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_acceptance.py -ra
```
All tests must pass with exit code 0 and zero unhandled exceptions.

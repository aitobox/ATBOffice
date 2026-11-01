# Implementation Plan: Issue #168
## [Phase 4] 第四期最终全量对齐验收、Parity 98.5%+ 达标与 Epic 归档 (Phase 4 Final Validation & Release Prep)

- **Issue**: #168
- **Epic**: #151 (Parent Epic: ATBOffice 四期工程：原版界面 1:1 复刻、高级业务子系统、高级分析向导与深度兼容终态)
- **Author**: Antigravity Autonomous Agent
- **Target Release**: Phase 4 Final Closure
- **Status**: Planning

---

## 1. Overview of Tasks

This implementation plan executes the final verification, metrics recalculation, and documentation convergence for the Phase 4 milestone.

---

## 2. Step-by-Step Execution Plan

### Task 1: Implement `scripts/source_diff.py`
- Create `scripts/source_diff.py` with modular AST scanning logic:
  - Scans `src/atboffice/`
  - Validates 0 orphan widgets without signal connections or actions
  - Validates 0 stubbed methods in concrete classes
  - CLI flags: `--check`, `--json`, `--verbose`
  - Return exit code 0 on clean scan, 1 on errors found

### Task 2: Implement `scripts/parity.py`
- Create `scripts/parity.py` to compute parity metrics from `docs/clone/features.csv`:
  - Weighted parity formula: Must (weight 3.0), Should (weight 2.0), Could (weight 1.0)
  - Domain-by-domain breakdown generator
  - Markdown table output matching `CLONE_DIFF.md` format
  - CLI flag `--check <target_score>` to gate CI/validation at $\ge 98.5\%$

### Task 3: Unit Tests for Audit Scripts (`tests/test_audit_tools.py`)
- Test AST scanner on mock files (detects stubs and clean files correctly)
- Test parity script on sample CSVs (correct weighted calculation and gate checks)

### Task 4: Update `docs/clone/features.csv`
- Update all 13 Phase 4 feature entries from `no` to `yes` with module paths and PR references
- Run `python3 scripts/parity.py` to verify the resulting score achieves $\ge 98.5\%$

### Task 5: Update `docs/clone/CLONE_DIFF.md`
- Refresh Executive Parity Scorecard table with Phase 4 metrics
- Refresh Domain Area breakdown table
- Document resolution of all 15 Phase 4 remediation tasks (TASK-400A through TASK-445)
- Document 0 orphan controls and 0 stubbed slots in AST report
- Elevate Shippability Verdict to `SUPERIOR`

### Task 6: Comprehensive Verification & Linting
- Execute `python3 scripts/source_diff.py` -> 0 orphans, 0 stubs
- Execute `python3 scripts/parity.py --check 98.5` -> PASS
- Execute `ruff check .` -> PASS
- Execute full test suite `pytest tests/` -> 100% PASS

### Task 7: Final Epic #151 Handoff
- Stage and commit changes with `fix(#168): phase 4 final validation, parity 98.5%+ audit and epic archive`
- Advance state machine to `reviewing`

# Implementation Plan: Issue #285 — feat(qa): 接入 atb-office-diff 自动化视觉渲染双端比对基准与回归核验 (Step 4 of 4)

## Overview

Build and integrate the standardized, tracked office document visual diff automation pipeline in `scripts/office_diff/` and `scripts/run_office_diff.py`, provide robust process-isolated capture, dimension mismatch guardrails, report generation, and automated regression tests in `tests/test_doc_diff.py`.

---

## Tasks

### Task 1: Data Models & Corpus Partitioning
- **Files**:
  - `scripts/office_diff/__init__.py`
  - `scripts/office_diff/models.py`
  - `scripts/office_diff/corpus.py`
- **Actions**:
  - Define `DocumentTarget`, `CaptureResult`, `DiffResult`, `AuditSummary`.
  - Implement `load_expectations` and `partition_corpus` correctly categorizing 73 supported OOXML documents vs 77 legacy/corrupted files from `tests/docs/expectations.json`.

### Task 2: Subprocess-Isolated Offscreen Capture
- **Files**:
  - `scripts/office_diff/capture.py`
- **Actions**:
  - Implement single-document offscreen capture in PySide6 with modal dialog suppression (`QMessageBox`, `QDialog`).
  - Implement `run_isolated_capture` running worker subprocess with timeout and crash handling (e.g. exit codes, SIGSEGV).
  - Support `--json-single` for CLI worker communication.

### Task 3: Visual Difference & Scoring Engine with Size Guardrails
- **Files**:
  - `scripts/office_diff/comparator.py`
- **Actions**:
  - Implement `compare_canvases` measuring Pixel MAE, Central ROI similarity, and edge alignment.
  - Implement strict size mismatch detection (`INCOMPARABLE_SIZE`) returning no false similarity score.
  - Implement optional normalized canvas comparison mode.
  - Implement side-by-side / diff heatmap generation.

### Task 4: Report Synthesizer & Remediation Generator
- **Files**:
  - `scripts/office_diff/reporter.py`
- **Actions**:
  - Synthesize markdown report `docs/clone/OFFICE_DOCS_DIFF.md`.
  - Ensure unverified legacy documents are not marked as passed.
  - Generate structured task cards for downstream issue creation.

### Task 5: Standardized CLI Runner
- **Files**:
  - `scripts/run_office_diff.py`
- **Actions**:
  - CLI parser with `--all`, `--app`, `--file`, `--min-similarity`, `--min-single-similarity`, `--capture`, `--dry-run`, `--out`.
  - Connect corpus loader, capture runner, comparator, and reporter.
  - Enforce redline thresholds and exit with appropriate status code.

### Task 6: Comprehensive Automated Tests
- **Files**:
  - `tests/test_doc_diff.py`
- **Actions**:
  - Test corpus partitioning (73 supported, 77 unsupported).
  - Test model serialization and deserialization.
  - Test comparator with identical, different, and mismatched dimensions.
  - Test subprocess isolation crash handling.
  - Test report generation formatting and accuracy.
  - Test CLI entry point dry run.

### Task 7: Full Verification & Parity Deliverable Update
- **Commands**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_doc_*.py -v`
  - Run `scripts/run_office_diff.py --dry-run`
  - Update `docs/clone/OFFICE_DOCS_DIFF.md`
- **Actions**:
  - Verify all tests pass with zero regressions.

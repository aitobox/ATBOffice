# Specification: TASK-704 逐文件内容与显示合同及超时隔离语料测试

- **Issue**: #238 ([phase7] TASK-704: test(corpus): 建立逐文件内容与显示合同)
- **Parent Epic**: #234 (Phase 7: 可信基线与文档兼容完善)
- **Status**: Draft / In Review
- **Date**: 2026-11-04
- **Branch**: `agent/issue-238-task-704-corpus-contract`

---

## 1. Context and Problem Statement

ATBOffice is a pure Python 3.12+ / PySide6 port of a comprehensive desktop office suite (.vibeoffice). Phase 7 focuses on fidelity, stability, document compatibility, and evidence-based acceptance.

Currently, the corpus test suite in `tests/unit/corpus/` has several shortcomings identified in `docs/clone/CLONE_DIFF.md` and Issue #238:
1. **False Exclusions & Concealed Failures**: In `test_word_corpus.py`, `test_excel_corpus.py`, and `test_presentation_corpus.py`, any exception raised during loading is caught with `except Exception as e:` and silently labeled `status="excluded"`. This allows broken parsers or regressions to be ignored.
2. **Superficial Compatibility Checks**: For legacy binary files (`.doc`, `.xls`, `.ppt`), tests only checked for OLE2 (`\xd0\xcf\x11...`) or BIFF magic headers without verifying actual format handling contracts or explicitly acknowledging format support boundaries.
3. **Flawed Timeout Isolation**: In `scripts/run_corpus_audit.py`, `as_completed(future_to_path)` followed by `future.result(timeout=args.timeout)` fails to kill hanging worker processes, blocking the queue on infinite loops or deadlocks.
4. **Missing Single Source of Truth**: There is no authoritative, audited expectations manifest (`tests/docs/expectations.json`) that classifies every single one of the 150 curated in-tree corpus files into `valid`, `encrypted`, `corrupt`, and `unsupported_format` with SHA-256 and per-stage contracts (`parse`, `model`, `render`, `roundtrip`).

---

## 2. Requirements & Acceptance Criteria

### 2.1 File Categorization (150/150 Corpus Inventory)
- Every file in `tests/docs/` (25 docx, 25 doc, 25 xlsx/xlsm, 25 xls, 25 pptx, 25 ppt) must be inventoried in `tests/docs/expectations.json`.
- Metadata for each file:
  - `file`: filename
  - `path`: relative path
  - `format`: extension format (`docx`, `doc`, `xlsx`, `xlsm`, `xls`, `pptx`, `ppt`)
  - `app`: target application (`word`, `excel`, `powerpoint`)
  - `category`: one of `valid`, `encrypted`, `corrupt`, `unsupported_format`
  - `source`: upstream project (`libreoffice`, `poi`, `openxml-sdk`)
  - `license`: upstream license (`MPL-2.0`, `Apache-2.0`, `MIT`)
  - `sha256`: SHA-256 checksum
  - `size`: size in bytes
  - `expectations`:
    - `parse`: `ok` (for valid OOXML) or specific rejection code (`rejected_encrypted`, `rejected_corrupt`, `rejected_unsupported_format`)
    - `model`: `ok` or `skip`
    - `render`: `ok` or `skip`
    - `roundtrip`: `ok` or `skip`
    - `expected_status`: `ok`, `encrypted`, `corrupt`, `unsupported_format`

### 2.2 Independent Timeout, Crash, Fail, and Loss Isolation
- `scripts/run_corpus_audit.py` and `src/atboffice/deep/audit/core.py` must support true isolated execution per file:
  - Multi-process execution with hard per-file timeout (default 30 seconds).
  - Hanging tasks are forcefully terminated (`terminate()` / `kill()`) and logged with `timeout`.
  - Process crashes (segfault, abort, unexpected exit) are captured and classified as `crash`.
  - Unhandled exceptions on valid files are classified as `fail` (never silently converted to `excluded`).
  - Feature reductions during roundtrip are classified as `loss`.
  - Only manifest pre-declared rejections (`encrypted`, `corrupt`, `unsupported_format`) count as expected outcomes.

### 2.3 Semantic Model and Offscreen Rendering Contracts
- Valid supported OOXML files must be tested across four distinct pipeline stages:
  1. `parse`: Raw bytes decoded into internal document AST/structure.
  2. `model`: Document model validated for semantic content (paragraphs/runs for Word, worksheets/cells for Excel, slides/shapes for PPTX).
  3. `render`: Offscreen rendering / layout contract verified without headless display crashes or unhandled Qt exceptions.
  4. `roundtrip`: Document serialized back to OPC container and checked for feature preservation.

### 2.4 Verification Command Gate
- Running `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_phase7_corpus_runner.py tests/unit/corpus/ -ra` must pass with exit code 0.
- `docs/clone/phase7_features.csv` entry for corpus audit runner updated to `clone: yes` with verification evidence.

---

## 3. Architecture & Module Design

### 3.1 `tests/docs/expectations.json`
Authoritative manifest for the 150 files:
- 73 `valid` files: 24 DOCX, 24 XLSX/XLSM, 25 PPTX.
- 1 `encrypted` file: `poi__protected_agile.docx`.
- 1 `corrupt` file: `poi__clusterfuzz-testcase-minimized-XLSX2CSVFuzzer-5636439151607808.xlsx`.
- 75 `unsupported_format` files: 25 DOC, 25 XLS, 25 PPT (legacy binary 97-2003 OLE2/BIFF).

### 3.2 `src/atboffice/deep/audit/core.py`
Enhancements:
- `CorpusExpectations`: Loader and validator for `tests/docs/expectations.json`.
- `IsolatedFileRunner`: Runs an audit worker in an isolated `multiprocessing.Process`. Uses `join(timeout)` and sends `terminate()`/`kill()` if exceeded. Uses a `multiprocessing.Queue` to stream results.
- `audit_corpus_file()`: Evaluates a single file against its expected stage contracts (`parse`, `model`, `render`, `roundtrip`), producing standardized status: `ok`, `timeout`, `crash`, `fail`, `loss`, `encrypted`, `corrupt`, `unsupported_format`.
- `AuditSession`: Updated to track categorized results and compare outcomes against expectations.

### 3.3 `scripts/run_corpus_audit.py`
CLI tool refactored to use `IsolatedFileRunner` and `CorpusExpectations`, outputting structured JSONL and summary metrics matching the contract.

### 3.4 `tests/test_phase7_corpus_runner.py`
Unit and regression suite covering:
- Fault injection: verifies injected hang produces `timeout` and terminates process.
- Fault injection: verifies injected crash produces `crash`.
- Fault injection: verifies unhandled error produces `fail`.
- Fault injection: verifies feature loss produces `loss`.
- Manifest validation: asserts 150/150 files mapped, SHA-256 match, no orphaned or missing files.

### 3.5 `tests/unit/corpus/`
- `test_word_corpus.py`: Tests 25 DOCX + 25 DOC using expectations.
- `test_excel_corpus.py`: Tests 25 XLSX + 25 XLS using expectations.
- `test_presentation_corpus.py`: Tests 25 PPTX + 25 PPT using expectations.
- Replaces magic header checks with strict format contract validation.

---

## 4. TDD & Implementation Steps

1. **Step 1**: Generate `tests/docs/expectations.json` with all 150 files accurately classified with licenses, sources, and SHA-256 checksums.
2. **Step 2**: Write failing regression tests in `tests/test_phase7_corpus_runner.py` verifying fault injection (`timeout`, `crash`, `fail`, `loss`) and manifest constraints.
3. **Step 3**: Enhance `src/atboffice/deep/audit/core.py` with `IsolatedFileRunner` and expectation comparison logic.
4. **Step 4**: Update `scripts/run_corpus_audit.py` to use `IsolatedFileRunner`.
5. **Step 5**: Update `tests/unit/corpus/test_word_corpus.py`, `test_excel_corpus.py`, and `test_presentation_corpus.py` to use expectations.
6. **Step 6**: Execute directional test command and verify all pass.
7. **Step 7**: Update `docs/clone/phase7_features.csv` with evidence.

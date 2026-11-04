# Implementation Plan: TASK-704 建立逐文件内容与显示合同

- **Issue**: #238 ([phase7] TASK-704: test(corpus): 建立逐文件内容与显示合同)
- **Spec**: `docs/superpowers/specs/issue-238-task-704-corpus-contract-spec.md`
- **Target Command**: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_phase7_corpus_runner.py tests/unit/corpus/ -ra`

---

## Task 1: Generate `tests/docs/expectations.json` (150 Files Authoritative Manifest)

- **Target Files**: `tests/docs/expectations.json`
- **Objective**: Create the complete, deterministic expectations manifest for all 150 curated corpus files with SHA-256, upstream license, source, category (`valid`, `encrypted`, `corrupt`, `unsupported_format`), and per-stage contracts.
- **Verification**: Run python script asserting all 150 files are present and match on-disk file hashes.

---

## Task 2: Create `tests/test_phase7_corpus_runner.py` (TDD Failing Tests for Fault Injection & Runner)

- **Target Files**: `tests/test_phase7_corpus_runner.py`
- **Objective**: Write comprehensive tests for the corpus runner and isolated worker:
  1. Test timeout fault injection: worker that sleeps longer than timeout is forcefully terminated and returns `timeout`.
  2. Test crash fault injection: worker that raises `os._exit(1)` or crashes returns `crash`.
  3. Test exception fault injection: worker that raises unexpected error returns `fail` (not `excluded`).
  4. Test loss fault injection: worker with missing feature count returns `loss`.
  5. Test manifest integrity: all 150 files in `tests/docs/expectations.json` match on-disk files.
- **Verification**: Run `pytest tests/test_phase7_corpus_runner.py -v` (confirm initial failure before implementation).

---

## Task 3: Implement Isolated Process Execution and Audit Abstractions in `src/atboffice/deep/audit/core.py`

- **Target Files**: `src/atboffice/deep/audit/core.py`
- **Objective**:
  - Implement `IsolatedFileRunner` using `multiprocessing.Process` with hard timeout enforcement (`p.join(timeout)`, `terminate()`, `kill()`).
  - Implement `CorpusExpectations` loader and schema validator.
  - Implement multi-stage execution (`parse`, `model`, `render`, `roundtrip`) with granular status classification (`ok`, `timeout`, `crash`, `fail`, `loss`, `encrypted`, `corrupt`, `unsupported_format`).
  - Update `AuditSession` to record stage-level details and compare results with expected contracts.
- **Verification**: Re-run `pytest tests/test_phase7_corpus_runner.py -v` to confirm tests pass.

---

## Task 4: Refactor `scripts/run_corpus_audit.py` with Isolated Execution & Multi-stage Reporting

- **Target Files**: `scripts/run_corpus_audit.py`
- **Objective**:
  - Replace broken `as_completed` timeout pattern with robust `IsolatedFileRunner`.
  - Add CLI arguments for `--expectations`, `--stage` (`all`, `parse`, `model`, `render`, `roundtrip`), `--strict`.
  - Output detailed JSONL with stage outcomes and summary accounting (ok, timeout, crash, fail, loss, encrypted, corrupt, unsupported_format).
- **Verification**: Test CLI on sample documents and verify output.

---

## Task 5: Update `tests/unit/corpus/` Suites with Expectations Contract

- **Target Files**:
  - `tests/unit/corpus/test_word_corpus.py`
  - `tests/unit/corpus/test_excel_corpus.py`
  - `tests/unit/corpus/test_presentation_corpus.py`
- **Objective**:
  - Replace magic header checks and blanket `except Exception: status="excluded"` with strict expectations validation.
  - Assert 150/150 files account for their expected outcomes.
  - Validate that valid OOXML files pass semantic model inspection and roundtrip.
  - Validate that encrypted, corrupt, and unsupported binary files fail with expected errors and are not falsely reported as supported.
- **Verification**: Run `pytest tests/unit/corpus/ -v`.

---

## Task 6: Run Full Acceptance Suite & Update Evidence

- **Target Files**: `docs/clone/phase7_features.csv`
- **Objective**:
  - Execute directional command: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_phase7_corpus_runner.py tests/unit/corpus/ -ra`
  - Ensure 0 Qt errors and exit code 0.
  - Update `docs/clone/phase7_features.csv` to `clone: yes` with verification evidence.

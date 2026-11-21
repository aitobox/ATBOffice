# Plan: Issue #418 — Legacy XLS fixture expectations

Spec: `docs/superpowers/specs/issue-418-legacy-xls-fixture-expectations-spec.md`

1. Add `tests/test_issue418_xls_expectations.py` (fails first):
   - every `.xls` manifest entry has category `legacy_imported` or `corrupt`, consistent with `real_open.expected_outcome`; counts 23/2.
   - `audit_corpus_file(AutoFilter.xls)` -> status `imported`, parse/model/render ok, roundtrip skip, expected_match.
   - `audit_corpus_file(crash-5.xls)` -> status `corrupt`, parse `rejected_corrupt`, expected_match.
   - Opening `AutoFilter.xls` in `LedgerWindow` binds `current_file_path` to the file and loads >= 1 sheet with data (not empty fallback).
   Verify: `pytest tests/test_issue418_xls_expectations.py` fails.
2. Rewrite the 25 XLS entries in `tests/docs/expectations.json` with a one-off script (preserve key order / formatting, indent=2).
3. Update `_execute_file_audit_worker` and `AuditSession.summary` in `src/atboffice/deep/audit/core.py`.
4. Update `tests/test_phase7_corpus_runner.py` counts and the legacy sample test; run full suite.

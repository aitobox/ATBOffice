# Spec: Issue #418 — Legacy XLS fixture expectations reflect import results

## Problem
`tests/docs/expectations.json` labels all 25 `.xls` fixtures `category: unsupported_format`
with notes "native parser intentionally out of scope", and the stage audit worker
(`_execute_file_audit_worker`) hard-codes every `.xls` as `unsupported_format`.
In reality the application imports 23 of them (22 BIFF8 read-only via `xls_reader`,
1 SpreadsheetML 2003 XML disguised as `.xls` via `xmlss_io`) and rejects 2
(`libreoffice__CVE-2010-1246-1.xls`, `libreoffice__crash-5.xls`) with a corrupt dialog.
The per-file `real_open` blocks are already correct; the top-level classification is stale.

## Design (decided autonomously, >= 90% confidence)
- New manifest category `legacy_imported` (23 files) with
  `expectations = {parse: ok, model: ok, render: ok, roundtrip: skip, expected_status: imported}`.
  `expected_status` is deliberately not `ok`, so the OOXML visual-parity partition
  (`scripts/office_diff/corpus.partition_corpus`, 73 supported) and the real-open
  abnormal-corpus audit (`category != valid`, 77 files) stay unchanged.
  Roundtrip is `skip`: binary XLS is read-only (no XLS writer) — saving requires `.xlsx`.
- The 2 malformed files move to `category: corrupt`,
  `expectations = {parse: rejected_corrupt, ..., expected_status: corrupt}`.
- Notes per file describe the real dispatch path (BIFF8 read-only / SpreadsheetML XML / corrupt).
- The stage audit worker runs the real reader for `.xls`: imported -> status `imported`
  (parse/model ok, real offscreen render, roundtrip skip), parse error -> `corrupt`,
  `PermissionError` -> `encrypted`. `.doc`/`.ppt` behaviour unchanged.
- `AuditSession.summary()` reports an `imported` count.
- Resulting category counts: valid 73, legacy_imported 23, corrupt 3, encrypted 1, unsupported_format 50.

## Out of scope
Any XLS reader change, XLS writing, `.doc`/`.ppt` handling.

## Task list
- [ ] Task 1: Regression tests (manifest per-fixture expectations, successful XLS stage audit, corrupt XLS handling, loaded-path assertion)
- [ ] Task 2: Update the 25 XLS manifest entries
- [ ] Task 3: Audit worker + summary support for imported/corrupt XLS
- [ ] Task 4: Update dependent count assertions; full test suite pass
- [ ] Task 5: Grill audit

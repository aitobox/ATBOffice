# Plan: Issue #374 — Ledger drawing objects

Spec: docs/superpowers/specs/issue-374-fix-ledger-drawing-objects-spec.md

## Chunk 1 — Tests first
- `tests/test_ledger_drawings.py`: dml color/fill unit tests; fixture tests for acceptance criteria 1–4
  (group + child at C2:H12 painted; rightArrow gradient yellow pixel; no object over A1:B2 in 49156;
  logo aspect within 2%). Run -> FAIL.

## Chunk 2 — `drawing/dml.py` + model fields
## Chunk 3 — reader rewrite of shape parsing (helper functions, recursive groups)
## Chunk 4 — object layer painting
## Chunk 5 — `pytest tests/test_ledger_drawings.py` PASS, full suite, commit.

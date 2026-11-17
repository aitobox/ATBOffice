# Plan: Restore saved sheet view state (Issue #378)

Spec: `docs/superpowers/specs/issue-378-ledger-restore-sheet-view-state-spec.md`

## Chunk 1 — Tests first
- Create `tests/test_ledger_sheet_view.py` covering acceptance criteria:
  A9 (`libreoffice__Pivot2_Row.xlsx`, active sheet), G14
  (`libreoffice__conditional_fmt_origin.xlsx`), `C32:D32` (`poi__49156.xlsx`),
  no gridlines + zoom 0.75 + page-break view + stored row break 51, round trip,
  sqref multi-range parsing, malformed input, viewport behaviour.
- Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_ledger_sheet_view.py -q` -> FAIL.

## Chunk 2 — Model + reader (`sheet_model.py`, `xlsx_reader.py`)
## Chunk 3 — Writer (`xlsx_writer.py`)
## Chunk 4 — Selection seeding/sync (`view.py`)
## Chunk 5 — Viewport (`grid_viewport.py`): gridlines, first-display view/scroll, stored breaks
## Chunk 6 — Full suite: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/ -q`

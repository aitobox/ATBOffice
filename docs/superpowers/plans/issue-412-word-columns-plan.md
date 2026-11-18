# Word Section Columns Implementation Plan

> **For agentic workers:** Use `executing-plans` to implement this plan serially.

**Goal:** Restore explicit Word column widths and reference section balancing.

**Architecture:** Preserve column metadata in the existing model and DOCX IO.
Use it for frame geometry and constrain balancing to continuous transitions.

**Tech Stack:** Python 3.12+, PySide6, pytest.

**Spec:** `docs/superpowers/specs/issue-412-word-columns-spec.md`

## Global Constraints

No new dependencies or UI text. All code stays under `src/atboffice`.
Preserve the primary worktree's unrelated edit. Process only Issue #412.

## Review Focus

- A one-column section can still declare a narrow explicit width.
- Missing counts and zero spacing must survive import and export.
- Incomplete or invalid dimensions need positive usable frame widths.
- Moving content to a narrower column must not overflow or lose text.
- Next-page/final sections remain unbalanced; continuous sections still flow.

### Task 1: Preserve explicit column geometry

**Files:** `models/properties.py`, `io/docx_reader.py`, `io/docx_writer.py`,
`layout/pagination.py` under `src/atboffice/modules/writer/`;
`tests/unit/writer/test_section_columns.py`.

**Interfaces:** Extend `ColumnsProperties` with `spaces: list[float]`.
`start_region` consumes widths/spaces without changing the pagination API.

- [ ] Write regressions for fdo52208's 100 pt width/two lines; inferred count,
  explicit zero gaps, unequal widths, malformed dimensions, and roundtrip.
- [ ] Run the tests and confirm the missing metadata/geometry failures.
- [ ] Parse and write the existing column fields plus individual gaps; use
  explicit positive widths, otherwise an equal-width fallback.
- [ ] Run `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/writer/test_section_columns.py --tb=short`.

### Task 2: Section boundary and continuation behavior

**Files:** `layout/pagination.py`, `tests/unit/writer/test_section_columns.py`.

**Interfaces:** Keep `paginate_document(Document) -> PaginationResult` intact.

- [ ] Add regressions for next-page versus continuous breaks and the final
  section; cover a paragraph continuing into a narrower column.
- [ ] Confirm failures, then remove unconditional section-end balancing and
  ensure continuation uses the destination width without losing source offsets.
- [ ] Run the new tests plus `tests/unit/writer/test_layout_regression.py`,
  `tests/unit/writer/test_pagination.py`, and `tests/gui/test_phase9_docx_rendering.py`.

### Task 3: Verification and delivery

- [ ] Run the full pytest suite, record any baseline failures with evidence,
  and lint changed files.
- [ ] Recapture both fixtures, inspect matching document regions, and record
  results without modifying the primary worktree's audit report.
- [ ] Perform the grilling audit and independent branch review; resolve
  material findings with regression tests.
- [ ] Commit, push, create PR, verify GitHub checks, merge, and reset state.

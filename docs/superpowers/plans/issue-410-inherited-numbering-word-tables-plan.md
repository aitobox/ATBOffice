# Issue #410 Implementation Plan

Spec: `docs/superpowers/specs/issue-410-inherited-numbering-word-tables-spec.md`

## Chunk 1: Regression tests

File: `tests/unit/writer/test_layout_regression.py`

- Fixture renders markers 1-8 across the table and none on the `numId=0` paragraph.
- A hard page break keeps the number on the first segment only.
- Removing a numbered paragraph renumbers on the next pagination.
- Marker portions do not advance model character offsets.

Verify the new tests fail before the fix.

## Chunk 2: Pagination

File: `src/atboffice/modules/writer/layout/pagination.py`

- Pass `label` to the first segment in `_split_paragraph_by_hard_breaks`.
- Call `compute_lists(doc)` at the start of `paginate_document`.

## Chunk 3: Marker offsets

Files: `src/atboffice/modules/writer/layout/portions.py`,
`src/atboffice/modules/writer/views/caret_controller.py`

- Emit marker, suffix tab, and suffix space portions with `length=0` and no offset advance.
- Return the model offset from `_binary_search_char_offset` for zero-length portions.

## Chunk 4: Verification

```sh
QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/writer/test_layout_regression.py tests/gui/test_phase9_docx_rendering.py
```

Run the wider writer suites and recapture the fixture.

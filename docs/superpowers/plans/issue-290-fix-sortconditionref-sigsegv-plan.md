# Implementation Plan: Fix sortconditionref.xlsx Offscreen Event Loop SIGSEGV (Issue #290)

## Milestones & Chunks

### Chunk 1: Model & Parser Protection (Task 2A)
- **File**: `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`
- **Changes**:
  - Parse `<autoFilter>` elements using `parse_range(ref)`
  - Create proper `AutoFilter` instance with `(r1, c1, r2, c2)`
  - Maintain `sheet.extra["auto_filter_xml"]` for roundtrip
- **Verification**: Python unit test checking `wb.sheets[0].auto_filter` is an instance of `AutoFilter`.

### Chunk 2: Viewport & QPainter Lifecycle Safeguards (Task 2B)
- **File**: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- **Changes**:
  - Add defensive attribute checks to all `auto_filter` property accesses (`hasattr(af, "r1")`, etc.)
  - In `paintEvent`, wrap paint execution in `try...finally` ensuring `painter.isActive()` triggers `painter.end()`
- **Verification**: Viewport paint with mock invalid objects does not leak painter or cause backing store crash.

### Chunk 3: End-to-End Regression Tests (Task 3)
- **File**: `tests/test_issue_290_sortconditionref_crash.py`
- **Changes**:
  - Test subprocess/isolated loading of `libreoffice__sortconditionref.xlsx`
  - Test repeated `processEvents` iterations and viewport paint
  - Run `capture_doc_atboffice.py` on the document
- **Verification**: `pytest tests/test_issue_290_sortconditionref_crash.py` passes cleanly with exit code 0.

### Chunk 4: Full Test Suite, Audit & Review (Tasks 4 & 5)
- Run pytest suite
- Stress-test with `grill-me`
- Transition to `reviewing`

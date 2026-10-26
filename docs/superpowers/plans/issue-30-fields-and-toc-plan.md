# Implementation Plan: Dynamic Fields Evaluation & TOC System

## Task 1: Field Models, Tokenizer, and RunProperties Link Support
- **Files**:
  - `src/atboffice/modules/writer/models/properties.py` (add `link` to `RunProperties`)
  - `src/atboffice/modules/writer/models/field.py` (create module, implement tokenizer, AST, and helper models)
  - `tests/unit/writer/test_fields.py` (create test suite for tokenizer and AST parsing)
- **Commands**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/test_fields.py -k "test_token or test_parse"`

## Task 2: Field Evaluation, Format Switches, and Bookmarks
- **Files**:
  - `src/atboffice/modules/writer/models/field.py` (implement `format_field_date`, `apply_field_formatting`, `evaluate_field`, `find_bookmarks`, `ensure_para_bookmark`, `insert_field`, `update_fields`)
  - `tests/unit/writer/test_fields.py` (unit tests for DATE/TIME, switches, PAGE, NUMPAGES, PAGEREF, bookmarks)
- **Commands**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/test_fields.py -k "test_eval or test_bookmark"`

## Task 3: Automated Table of Contents (TOC) Engine
- **Files**:
  - `src/atboffice/modules/writer/layout/toc.py` (implement `build_toc`, `insert_or_update_toc`, heading scanner, leader dot tab stops)
  - `src/atboffice/modules/writer/models/styles.py` (ensure `TOC1`..`TOC9` styles exist in builtin styles)
  - `tests/unit/writer/test_fields.py` (unit tests for TOC extraction, styles, bookmark links, PAGEREF)
- **Commands**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/test_fields.py -k "test_toc"`

## Task 4: Two-Pass Dynamic Field Backfill & Repagination
- **Files**:
  - `src/atboffice/modules/writer/layout/pagination.py` (integrate `update_fields` and two-pass repagination)
  - `src/atboffice/modules/writer/layout/portions.py` (enhance tab stop computation for right alignment & leaders)
  - `tests/unit/writer/test_fields.py` (unit tests for dynamic field updates in pagination, page-count expansion pass)
- **Commands**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/test_fields.py`

## Task 5: Canvas Leader Dots & Hyperlink Navigation
- **Files**:
  - `src/atboffice/modules/writer/views/canvas_view.py` (render leader dots on tab portions, handle link click jumping to bookmark)
  - `tests/gui/test_writer_canvas.py` (test leader dot tab rendering and link navigation)
- **Commands**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_writer_canvas.py`

## Task 6: Full Verification & Regression Gate
- **Commands**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/ tests/gui/test_writer_canvas.py -v`

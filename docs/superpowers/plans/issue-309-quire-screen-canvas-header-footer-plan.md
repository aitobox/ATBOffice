# Implementation Plan: Issue #309 - Screen Canvas Header & Footer Rendering & Margin Positioning

## Task 1: Write TDD Unit Test Suite
- **File**: `tests/unit/writer/test_header_footer_screen_rendering.py`
- **Scope**:
  - `test_canvas_view_paints_header_and_footer`: Verify `_paint_page_content` draws header and footer text onto the QPainter canvas in `#666666` color.
  - `test_canvas_view_dynamic_page_numbers`: Verify multi-page document with `<PAGE>` and `<NUMPAGES>` renders "Page 1 of 2" on page 1 and "Page 2 of 2" on page 2.
  - `test_canvas_view_different_first_page`: Verify `title_pg` renders first page header on page 1 and default header on subsequent pages.
  - `test_canvas_view_even_odd_headers`: Verify `evenAndOddHeaders` setting renders default header on odd pages and even header on even pages.
  - `test_canvas_view_no_overlap_with_body`: Verify `page.body_top >= page.header.y + page.header.height` and `page.footer.y >= page.body_top + page.body_height`.
- **Command**: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/test_header_footer_screen_rendering.py -v`
- **Expected initial result**: FAIL (since screen canvas does not yet paint headers/footers).

## Task 2: Enhance Pagination Engine (`pagination.py`)
- **File**: `src/atboffice/modules/writer/layout/pagination.py`
- **Changes**:
  - Support `evenAndOddHeaders` in `doc.settings`.
  - Fix `ftr_y` / `footer.y` positioning: `y = max(0.0, sect.pg_h - sect.ftr - cur_y)`.
  - In `layout_hf_story`, clone and evaluate dynamic fields (`PAGE`, `NUMPAGES`, `SECTIONPAGES`) for the active `page_number` and `total_pages`.
  - In `paginate_document`, ensure Pass 2 re-evaluates headers/footers with stabilized `total_pages`.

## Task 3: Implement Screen Canvas Painting (`canvas_view.py`)
- **File**: `src/atboffice/modules/writer/views/canvas_view.py`
- **Changes**:
  - Implement `_paint_header_footer(painter, page_rect, page, hf, is_header)` method.
  - Render header and footer lines and portions in `#666666` subdued color.
  - Support zoom scaling for positions, text font sizes, baseline, underlines, and tabs.
  - Invoke `_paint_header_footer` for `page.header` and `page.footer` inside `_paint_page_content`.
  - Add fallback token resolution for `PAGE` and `NUMPAGES` if present in text portions.

## Task 4: Full Verification and Regression Testing
- **Commands**:
  - `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/test_header_footer_screen_rendering.py -v`
  - `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/ -v`
- **Expected result**: 100% PASS with zero regressions.

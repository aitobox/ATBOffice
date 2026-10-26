# Implementation Plan: Quire Dynamic Multi-Page Pagination & Flow Engine (Issue #25)

## Overview
Implement the full multi-page flow and pagination engine in `src/atboffice/modules/writer/layout/pagination.py` and comprehensive test suite in `tests/unit/writer/test_pagination.py`.

---

### Task 1: Core Pagination Data Models & Number Formatting
- **File**: `src/atboffice/modules/writer/layout/pagination.py`
- **Details**:
  - Define `PageFragment`: holds line indices `[start, end]`, placed lines, bounding box, spacing before/after, character offsets.
  - Define `ColumnFrame`: represents a column layout container on a region with `(left, top, width, height, used_height, fragments)`.
  - Define `PageRegion`: represents a section region on a page with multi-column support.
  - Define `PageHeaderFooter`: represents header or footer layout box and rendered fragments.
  - Define `Page`: represents physical page with geometry, margins, headers/footers, and regions.
  - Define `PaginationResult`: collection of pages, page counts, timing.
  - Implement `format_number(n: int, fmt: str) -> str` supporting `decimal`, `lowerRoman`, `upperRoman`, `lowerLetter`, `upperLetter`, `decimalZero`, `ordinal`.
- **Test Command**: `PYTHONPATH=src pytest tests/unit/writer/test_pagination.py -k test_pagination_models`

---

### Task 2: Header & Footer Resolution & Margins Adaptation
- **File**: `src/atboffice/modules/writer/layout/pagination.py`
- **Details**:
  - Implement `resolve_page_type(sect: SectionProperties, first_of_section: bool, page_number: int, even_odd_settings: bool) -> str` returning `'first'`, `'even'`, or `'default'`.
  - Implement `get_hf_story(sections: list[dict], sect_idx: int, kind: str, page_type: str, hf_dict: dict) -> Story | None`.
  - Implement `layout_header_footer(...) -> PageHeaderFooter`:
    - Layout paragraphs using `portions.layout_paragraph(...)`.
    - Calculate height of header/footer content.
  - Compute adjusted page margins:
    - If header height `hh > 0` and `sect.hdr + hh > sect.mt`: `body_top = sect.hdr + hh`.
    - If footer height `fh > 0` and `sect.ftr + fh > sect.mb`: `body_bottom_gap = sect.ftr + fh`.
- **Test Command**: `PYTHONPATH=src pytest tests/unit/writer/test_pagination.py -k test_header_footer`

---

### Task 3: Widow / Orphan Control, Line Splitting & Keep Chains
- **File**: `src/atboffice/modules/writer/layout/pagination.py`
- **Details**:
  - Line cutoff calculation with `widow_control`:
    - Minimum 2 lines on page bottom (no orphan: if `k == 1` and `nl > 1`, set `k = 0`).
    - Minimum 2 lines on page top (no widow: if `nl - k == 1` and `k >= 2`, set `k = k - 1`).
    - If `k == 1` and `nl > 2`, set `k = 0`.
  - Keep-rules:
    - `page_break_before`: if true and column not empty, force page break before paragraph.
    - `keep_lines`: if true and entire paragraph does not fit, move whole paragraph to next page.
    - `keep_next`: chain paragraphs with keep_next; if the next paragraph cannot place its initial lines, rollback the chain to next page.
- **Test Command**: `PYTHONPATH=src pytest tests/unit/writer/test_pagination.py -k test_widow_orphan_and_keep`

---

### Task 4: Section Breaks & Multi-Page Pagination Flow
- **File**: `src/atboffice/modules/writer/layout/pagination.py`
- **Details**:
  - Section break types:
    - `nextPage`: unconditionally starts a new page.
    - `oddPage`: if current page number is even, add blank padding page.
    - `evenPage`: if current page number is odd, add blank padding page.
    - `continuous`: if same geometry and remaining height in page >= 24 pt, create new region on same page; else start new page.
  - Trailing empty paragraph section break: do not generate spurious trailing blank page.
  - Hard page break (`BreakItem(break_type='page')`) and column break (`BreakItem(break_type='column')`).
- **Test Command**: `PYTHONPATH=src pytest tests/unit/writer/test_pagination.py -k test_section_and_hard_breaks`

---

### Task 5: Dynamic Fields & Two-Pass Pagination
- **File**: `src/atboffice/modules/writer/layout/pagination.py`
- **Details**:
  - Dynamic field evaluation for `PAGE`, `NUMPAGES`, `SECTIONPAGES`.
  - Second pass pagination if total page count changes field representation.
  - Export `paginate_document(doc: Document) -> PaginationResult` in `src/atboffice/modules/writer/layout/__init__.py`.
- **Test Command**: `PYTHONPATH=src pytest tests/unit/writer/test_pagination.py -v`

---

### Task 6: Full Verification & Regression Testing
- **Command**:
  - `PYTHONPATH=src pytest tests/unit/writer/test_pagination.py -v`
  - `PYTHONPATH=src pytest tests/unit/writer/ -v`
  - `PYTHONPATH=src pytest tests/`

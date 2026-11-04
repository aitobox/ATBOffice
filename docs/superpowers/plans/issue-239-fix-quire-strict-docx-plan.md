# Implementation Plan: TASK-705 (Issue #239) - fix(quire): 修复 Strict DOCX 空白及真实排版差异

## Overview
Implement dual Transitional/Strict OpenXML namespaces, structured document tag parsing, revision tracking parsing, textbox content extraction, and header/footer-relative relationship handling in `docx_reader.py`, `omml.py`, and `canvas_view.py`.

---

## Task Breakdown

### Task 1: Write Reproduction Tests in `tests/gui/test_phase7_docx_render.py`
- Test `libreoffice__strict.docx`: assert 7 source text nodes are present in document paragraphs/math runs, and paginate without falling back to empty.
- Test `libreoffice__nested-runs.docx`: assert text box content 'Test text box' is parsed.
- Test `libreoffice__sdt-ignored-footer.docx`: assert footer text 'September 22, 2014' and body sections are parsed.
- Test `poi__headerPic.docx`: assert header image with part-relative relationship is extracted.
- Test `libreoffice__tdf125881.docx`: assert revisions and text are parsed.
- Run tests and verify they fail before implementation (RED).

### Task 2: Implement Strict & Transitional Namespaces and Helpers in `docx_reader.py` & `omml.py`
- Define namespace sets `W_NAMESPACES`, `R_NAMESPACES`, `M_NAMESPACES`, `WP_NAMESPACES`, `A_NAMESPACES`, `PIC_NAMESPACES`.
- Implement `_find_elem`, `_findall_elems`, `_find_desc` helpers.
- Replace hardcoded `{NS_W}` Clark notations with helper calls across styles, numbering, settings, body, paragraphs, tables, runs, and section properties.
- In `omml.py`, support Strict Math namespace `http://purl.oclc.org/ooxml/officeDocument/math`.

### Task 3: Implement SDT, Revision, Textbox, and Part-Relative Rels in `docx_reader.py`
- Implement `_collect_blocks` to recursively parse `<w:sdt>`, `<w:customXml>`, `<w:ins>`, `<w:del>` into story blocks.
- In `_parse_inline_element`, handle `<w:sdt>`, `<w:ins>`, `<w:del>` with `<w:t>` and `<w:delText>`.
- In `_parse_drawing` and `_parse_vml_pict`, extract `<w:txbxContent>` text into inline items, and preserve charts/smartart as annotated visual objects.
- In `_parse_headers_footers`, load part-relative relationships (`pkg.get_relationships(part_path)`) and use them when parsing header/footer drawings.

### Task 4: Run Tests, Verify Parity, and Update Feature Status
- Run `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_docx_render.py tests/unit/corpus/test_word_corpus.py -ra`.
- Verify full test suite passes with exit code 0.
- Update `docs/clone/phase7_features.csv` for DOCX OpenXML Reader Core.

### Task 5: Review and Transition
- Update state to `reviewing` and trigger `atb-github-code-reviewer`.

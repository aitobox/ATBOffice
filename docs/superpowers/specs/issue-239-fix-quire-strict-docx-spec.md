# Specification: TASK-705 (Issue #239) - fix(quire): 修复 Strict DOCX 空白及真实排版差异

## Overview
Quire (Word component) failed to read Strict OpenXML documents (such as `libreoffice__strict.docx`), leaving empty paragraph fallbacks due to hardcoded transitional namespace prefixes (`http://schemas.openxmlformats.org/...`). Additionally, documents containing structured document tags (`<w:sdt>`), inline/block revisions (`<w:ins>`, `<w:del>`), shape text boxes (`<w:txbxContent>`), and header/footer-relative media relationships (`poi__headerPic.docx`) were either partially discarded or lost during parse and render.

This specification addresses these root causes by establishing full Transitional + Strict OpenXML parity across readers, models, layout, and canvas rendering, while preserving lossless roundtrip write capability and preventing silent feature erasure.

---

## Technical Architecture & Changes

### 1. Dual Transitional & Strict Namespace Parity
Support both ISO/IEC 29500 Strict (`http://purl.oclc.org/ooxml/...`) and ECMA-376 Transitional (`http://schemas.openxmlformats.org/...`):
- WordprocessingML: `W_NAMESPACES = { "http://schemas.openxmlformats.org/wordprocessingml/2006/main", "http://purl.oclc.org/ooxml/wordprocessingml/main" }`
- Relationships: `R_NAMESPACES = { "http://schemas.openxmlformats.org/officeDocument/2006/relationships", "http://purl.oclc.org/ooxml/officeDocument/relationships" }`
- Math (OMML): `M_NAMESPACES = { "http://schemas.openxmlformats.org/officeDocument/2006/math", "http://purl.oclc.org/ooxml/officeDocument/math" }`
- DrawingML Main: `A_NAMESPACES = { "http://schemas.openxmlformats.org/drawingml/2006/main", "http://purl.oclc.org/ooxml/drawingml/main" }`
- DrawingML Wordprocessing: `WP_NAMESPACES = { "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing", "http://purl.oclc.org/ooxml/drawingml/wordprocessingDrawing" }`
- DrawingML Picture: `PIC_NAMESPACES = { "http://schemas.openxmlformats.org/drawingml/2006/picture", "http://purl.oclc.org/ooxml/drawingml/picture" }`

Replace hardcoded Clark notation searches `elem.find(f"{{{NS_W}}}tag")` with namespace-aware helper methods (`_find_elem`, `_findall_elems`, `_find_desc`) that match tag names and accept namespace sets or local names.

### 2. Structured Document Tag (`<w:sdt>`) Extraction
- **Block-level SDT**: In body, header/footer, and table cells, traverse `<w:sdt>` -> `<w:sdtContent>` and recursively parse all contained paragraphs and tables (`_collect_blocks`).
- **Inline-level SDT**: In paragraphs, traverse inline `<w:sdt>` -> `<w:sdtContent>` and recursively parse all runs and inline elements.

### 3. Revision Tracking (`<w:ins>`, `<w:del>`) Extraction
- In paragraphs, handle `<w:ins>` and `<w:del>` children:
  - Traverse child runs and parse text (`<w:t>` and `<w:delText>`).
  - Capture revision metadata (author, date, id).

### 4. Text Box and Drawing Content Extraction
- In `<w:drawing>` and `<w:pict>`:
  - Search for `<w:txbxContent>` inside `wsp/txbx` or `shape/textbox`.
  - Extract text box paragraphs into inline runs or text items so text within shapes is fully loaded and searchable.
  - When non-picture drawing objects (e.g. charts, diagrams/SmartArt) are encountered, create a `PictureItem` or annotated object with title/alt_text representing the object's dimensions and location so it enters the document model rather than being silently omitted.

### 5. Header and Footer Part Relationships
- When parsing header/footer parts (`word/header*.xml`, `word/footer*.xml`), load relationships specific to that part (`pkg.get_relationships(part_path)`).
- When resolving image embeds (`r:embed`) or hyperlinks within headers/footers, look up the target in the part-specific relationships dictionary, correctly resolving header pictures (`poi__headerPic.docx`).

### 6. Acceptance Criteria Verification
- Verify `libreoffice__strict.docx`: all 7 text nodes ('Hello world!', 'This is a chart:', 'And this is a smart-art:', 'This is math:', 'A=π', 'r', '2') parsed and laid out.
- Verify `libreoffice__nested-runs.docx`: text box text parsed.
- Verify `libreoffice__sdt-ignored-footer.docx`: sdt footer text and document body sections parsed.
- Verify `poi__headerPic.docx`: header image part resolved.
- Verify `libreoffice__tdf125881.docx`: revisions and text parsed.
- Run test suites: `tests/gui/test_phase7_docx_render.py` and `tests/unit/corpus/test_word_corpus.py`.
- Update `docs/clone/phase7_features.csv` to mark verified status.

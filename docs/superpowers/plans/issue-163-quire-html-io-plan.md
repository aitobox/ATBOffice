# Implementation Plan: Quire HTML Document Bidirectional Import and Semantic Export (html_io)

**Issue**: [#163](https://github.com/aitobox/ATBOffice/issues/163)  
**Spec**: [docs/superpowers/specs/issue-163-quire-html-io-spec.md](docs/superpowers/specs/issue-163-quire-html-io-spec.md)  

---

## Task Breakdown

### Task 1: Write Comprehensive Unit Tests (TDD First)
- **Files**: `tests/modules/writer/test_html_io.py`
- **Actions**:
  1. Define test cases for inline styles: bold, italic, underline, strike, sub/superscript, monospace font, font-size, colors, highlight.
  2. Define test cases for block elements: paragraphs, line breaks, headings 1-6, alignments, margins/indents.
  3. Define test cases for lists: unordered `<ul>`, ordered `<ol>` with various types (`1`, `a`, `A`, `i`, `I`), nested lists.
  4. Define test cases for tables: basic rows/cols, `<th>` header cells, `colspan`, `rowspan`, custom backgrounds and cell alignments.
  5. Define test cases for images: `<img>` with data URIs, dimensions, alt text.
  6. Define test cases for `HtmlWriter` export and full roundtrip (`read -> write -> read`).
  7. Define test cases for `atboffice.vfs.html_io` and `WindowManager.detect_app_type("doc.html")`.
- **Verification**: Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/writer/test_html_io.py -v` (expected to fail until implementation).

### Task 2: Implement `src/atboffice/modules/writer/io/html_io.py`
- **Files**: `src/atboffice/modules/writer/io/html_io.py`
- **Actions**:
  1. Implement CSS style parser: `style_map(style_str)`, unit conversion `pt(val)`, color parser `parse_color(c)`.
  2. Implement `HtmlReader(HTMLParser)` converting HTML elements and attributes to Quire `Document` DOM:
     - Run properties stack for inline formatting.
     - Block processor for paragraphs, headings, blockquotes, code blocks.
     - Nested list handler with proper numbering IDs and levels.
     - Table builder with cell span and rowspan tracking.
     - Image parser creating `PictureItem`.
  3. Implement `HtmlWriter` converting Quire `Document` to semantic, standalone HTML5:
     - Paragraph and run serialization with inline styles.
     - List stacking and structuring (`<ul>` / `<ol>`).
     - Table serialization with colspan/rowspan and cell borders.
     - Embedded picture base64 data URIs.
     - Web page scaffolding (meta, title, styles, body).
  4. Implement `read_html(src)` and `write_html(doc, path=None)`.

### Task 3: Create `src/atboffice/vfs/html_io.py` & Update Package Exports
- **Files**:
  - `src/atboffice/vfs/html_io.py`
  - `src/atboffice/modules/writer/io/__init__.py`
- **Actions**:
  1. Create `src/atboffice/vfs/html_io.py` exposing `HtmlReader`, `HtmlWriter`, `read_html`, `write_html`.
  2. Re-export `HtmlReader`, `HtmlWriter`, `read_html`, `write_html` in `src/atboffice/modules/writer/io/__init__.py`.

### Task 4: Integrate with Window Manager and Shell UI Filters
- **Files**:
  - `src/atboffice/core/window_manager.py`
  - `src/atboffice/ui/shell/quire_window.py`
  - `src/atboffice/ui/shell/start_center.py`
- **Actions**:
  1. Add `.html` and `.htm` to `WindowManager.QUIRE_EXTENSIONS`.
  2. Update `get_file_filter` and `do_save` in `quire_window.py` to support `*.html *.htm`.
  3. Update `open_file` handling in `quire_window.py` if needed for HTML files.
  4. Update `start_center.py` file filters to include `*.html *.htm`.

### Task 5: Execute Test Suite & Verify 100% Passing
- **Command**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/writer/test_html_io.py -v`
- **Command**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/`
- **Check**: Zero regressions, 100% tests pass.

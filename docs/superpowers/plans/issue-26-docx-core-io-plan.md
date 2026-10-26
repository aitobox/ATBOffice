# Implementation Plan: Quire DOCX/DOCM WordprocessingML Core Reader & Lossless Writer (Issue #26)

## Overview
Implement the complete ECMA-376 WordprocessingML reader and lossless writer in `src/atboffice/modules/writer/io/` along with thorough unit and roundtrip tests in `tests/unit/writer/test_docx_io.py`.

---

### Task 1: Module Scaffolding & Exports
- **Files**:
  - `src/atboffice/modules/writer/io/__init__.py`
- **Details**:
  - Export `read_docx`, `write_docx`, `DocxReader`, `DocxWriter`.
  - Provide convenient top-level functions `read_docx(source)` and `write_docx(doc, target=None)`.
- **Test Command**: `PYTHONPATH=src pytest tests/unit/writer/test_docx_io.py -k test_module_exports`

---

### Task 2: Implement DOCX / DOCM Reader (`docx_reader.py`)
- **File**: `src/atboffice/modules/writer/io/docx_reader.py`
- **Details**:
  - Class `DocxReader`:
    - Reads from file path, `io.BytesIO`, or `bytes`.
    - Opens package via `SourcePackage.from_bytes(data)`.
    - Discovers main document part from `_rels/.rels` (Relationship Type `.../officeDocument`, fallback `word/document.xml`).
    - Traverses relationships in `word/_rels/document.xml.rels`.
    - Parses `word/styles.xml`:
      - Extracts `w:docDefaults` (`rPrDefault`, `pPrDefault`).
      - Extracts `w:style` definitions (styles dictionary for paragraphs, characters, tables).
    - Parses `word/settings.xml` into `doc.settings`.
    - Parses `word/fontTable.xml` into `doc.fonts`.
    - Parses `word/document.xml`:
      - Body blocks: `w:p` (Paragraphs) and `w:tbl` (Tables).
      - Trailing `w:sectPr` (SectionProperties: margins, paper size, orientation, columns, header/footer mapping).
      - Paragraph properties `w:pPr`: `pStyle`, `jc`, `spacing`, `ind`, `borders`, `shd`, `tabs`, `keepNext`, `keepLines`, `pageBreakBefore`, `widowControl`, `numPr`, `sectPr`.
      - Inline runs `w:r`: `w:rPr` (`rStyle`, `rFonts`, `b`, `i`, `u`, `color`, `sz`, `highlight`, `strike`, `vertAlign`, `spacing`, `rtl`, `cs`, `lang`), text `w:t` (with xml:space preserve handling), `w:tab`, `w:br`, `w:sym`, `w:fldChar`.
      - Table blocks `w:tbl`: `w:tblPr`, `w:tblGrid`, `w:tr`, `w:tc`.
      - Headers/footers referenced in section properties parsed into `doc.hf`.
    - Stores `_source_pkg` and `_doc_format` on `doc` for lossless incremental saves.
- **Test Command**: `PYTHONPATH=src pytest tests/unit/writer/test_docx_io.py -k test_docx_reader`

---

### Task 3: Implement DOCX / DOCM Lossless Writer (`docx_writer.py`)
- **File**: `src/atboffice/modules/writer/io/docx_writer.py`
- **Details**:
  - Class `DocxWriter`:
    - Handles both edit/roundtrip mode (`doc._source_pkg` exists) and new document creation mode.
    - In edit mode:
      - Uses `PackageWriter(doc._source_pkg)`.
      - Updates `word/document.xml`.
      - Unmodified parts (e.g. `word/vbaProject.bin`, drawings, media, themes) are carried forward byte-for-byte.
    - In new document mode:
      - Builds complete valid OPC package structure (`[Content_Types].xml`, `_rels/.rels`, `word/_rels/document.xml.rels`, `word/document.xml`, `word/styles.xml`, `word/settings.xml`).
    - Enforces strict ECMA-376 schema ordering on `<w:pPr>` and `<w:rPr>` via `enforce_schema_order`.
    - Accurately converts units:
      - Points to twips (`* 20`).
      - Points to half-points (`* 2`).
      - Points to eighth-points (`* 8`) for borders.
    - Serializes Paragraphs, Runs, Tables, Cells, and Sections.
    - Supports saving to file path, `io.BytesIO`, or returning `bytes`.
- **Test Command**: `PYTHONPATH=src pytest tests/unit/writer/test_docx_io.py -k test_docx_writer`

---

### Task 4: Comprehensive Test Suite & Lossless Verification
- **File**: `tests/unit/writer/test_docx_io.py`
- **Details**:
  - Unit tests for:
    - New document creation, paragraph formatting, run properties, and roundtrip assertion.
    - Table serialization and deserialization (grid, borders, cell properties, shading).
    - Strict ECMA-376 schema ordering verification (check order of child tags in serialized XML).
    - DOCM macro preservation: verify `vbaProject.bin` SHA-256 remains 100% identical after editing document text.
    - Lossless unmodified roundtrip: verify byte-for-byte identity of all non-document parts.
- **Test Command**: `PYTHONPATH=src pytest tests/unit/writer/test_docx_io.py -v`

---

### Task 5: Full Regression Testing & State Transition
- **Details**:
  - Run full test suite across the repository to ensure zero regressions.
  - Update `.github-agent-state.yml` to `reviewing`.
  - Automatically chain-invoke `atb-github-code-reviewer`.
- **Command**: `PYTHONPATH=src pytest tests/`

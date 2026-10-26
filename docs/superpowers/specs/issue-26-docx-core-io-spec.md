# Design Specification: Quire DOCX/DOCM WordprocessingML Core Reader & Lossless Writer (Issue #26)

## 1. Overview & Objectives

This specification defines the architecture, data models, XML serialization/deserialization logic, and lossless OPC container integration for Microsoft Word DOCX and DOCM files in Quire (`src/atboffice/modules/writer/io/`).

The DOCX/DOCM I/O subsystem enables:
1. Full deserialization of ECMA-376 (OOXML Transitional) WordprocessingML packages into Quire's `Document` object model (`src/atboffice/modules/writer/models/document.py`).
2. High-fidelity serialization of Quire documents back to valid OOXML `.docx` and `.docm` packages.
3. Lossless preservation: Unmodified parts (e.g. drawings, media, themes, VBA macro projects in `.docm`, custom XML, and unmodified styles) are carried forward byte-for-byte (SHA-256 match) using `PackageWriter` from `atboffice.vfs.opc`.
4. Strict schema ordering: Every generated `<w:pPr>` and `<w:rPr>` strictly follows ECMA-376 schema element sequences using `atboffice.vfs.order.enforce_schema_order`, ensuring Microsoft Word opens the saved documents without any repair prompts or warnings.

---

## 2. Reference Source Analysis

Based on `.vibeoffice`:
- `.vibeoffice/public/quire/js/docx-read.js`:
  - Discovers main document part from `_rels/.rels` (type ending in `officeDocument`).
  - Traverses `word/_rels/document.xml.rels` to resolve styles, settings, fontTable, numbering, header/footer parts, and external hyperlinks.
  - Parses styles: `docDefaults` (`rPrDefault`, `pPrDefault`), paragraph styles, character styles, table styles.
  - Parses document body: iterates `w:p` and `w:tbl`, and processes trailing `w:sectPr`.
  - For paragraphs: parses `w:pPr` (style, jc, spacing, ind, borders, shd, tabs, keepNext, keepLines, widowControl, numPr, sectPr), and inline runs `w:r`, `w:hyperlink`, `w:fldSimple`, bookmarks, etc.
  - For runs: parses `w:rPr` (rStyle, rFonts, b, i, u, color, sz, highlight, strike, vertAlign, etc.) and run content (`w:t`, `w:tab`, `w:br`, `w:sym`, `w:fldChar`).
  - Handles `xml:space="preserve"` on `<w:t>`.
- `.vibeoffice/public/quire/js/docx-write.js`:
  - Formats properties with exact unit conversions:
    - Points to twips: `tw(pt) = round(pt * 20)`
    - Half-points: `hp(pt) = round(pt * 2)`
    - Colors: hex strings without '#' or `'auto'`.
  - Generates `<w:p>` and `<w:pPr>` in strict schema order.
  - Generates `<w:r>` and `<w:rPr>` in strict schema order.
  - Generates tables `<w:tbl>`, rows `<w:tr>`, and cells `<w:tc>`.
  - Generates sections `<w:sectPr>` (page size, page margins, header/footer references).
- `.vibeoffice/public/quire/js/preserve.js`:
  - Retains package reference `doc.pkg` / `_source_pkg`.
  - Distinguishes regenerated parts (`word/document.xml`), merged parts (`word/settings.xml`, `word/fontTable.xml`), and opaque parts (`word/theme/theme1.xml`, `word/media/*`, `word/vbaProject.bin`).
  - Passes unmodified parts through `PackageWriter` unmodified.

---

## 3. Architecture & Module Design

### 3.1 Module Layout
```
src/atboffice/modules/writer/io/
├── __init__.py          # Exports read_docx, write_docx, DocxReader, DocxWriter
├── docx_reader.py       # ECMA-376 WordprocessingML reader
└── docx_writer.py       # ECMA-376 WordprocessingML writer & serializer
```

### 3.2 Unit Conversions (OOXML Standard)
- **Twips (dxa)**: 1 pt = 20 twips (dxa).
  - Used for: margins, paragraph spacing, indentation, column width, line height (twips mode).
- **Half-points (hp)**: 1 pt = 2 hp (e.g. 10.5 pt font = 21 hp).
  - Used for: font size (`w:sz`), character spacing, kerning.
- **Eighth-points**: 1 pt = 8 eighth-points.
  - Used for: border width (`w:sz` in `<w:bottom>`, `<w:top>`, etc.).

### 3.3 Strict XML Namespaces
- `w`: `http://schemas.openxmlformats.org/wordprocessingml/2006/main`
- `r`: `http://schemas.openxmlformats.org/officeDocument/2006/relationships`
- `m`: `http://schemas.openxmlformats.org/officeDocument/2006/math`
- `wp`: `http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing`
- `a`: `http://schemas.openxmlformats.org/drawingml/2006/main`
- `pic`: `http://schemas.openxmlformats.org/drawingml/2006/picture`
- `xml`: `http://www.w3.org/XML/1998/namespace`

---

## 4. Detailed Component Specifications

### 4.1 `DocxReader` (`src/atboffice/modules/writer/io/docx_reader.py`)
- **Initialization & Source Loading**:
  - Accepts `file_path: str | Path`, `stream: io.BytesIO`, or `raw_bytes: bytes`.
  - Uses `SourcePackage.from_bytes(raw_bytes)` to inspect container parts and relationships.
- **Discovery**:
  - Resolves main document part from `_rels/.rels` targeting `.../relationships/officeDocument`. Defaults to `word/document.xml`.
  - Detects content type:
    - `application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml` (.docx)
    - `application/vnd.ms-word.document.macroEnabled.main+xml` (.docm)
    - `application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml` (.dotx)
  - Resolves target relationships from `word/_rels/document.xml.rels`:
    - `styles.xml`, `numbering.xml`, `settings.xml`, `fontTable.xml`, `header*.xml`, `footer*.xml`, `footnotes.xml`, `endnotes.xml`, external hyperlinks.
- **Styles & Defaults**:
  - Parses `word/styles.xml`:
    - `w:docDefaults/w:rPrDefault/w:rPr`: sets default `font`, `sz`, `color`.
    - `w:docDefaults/w:pPrDefault/w:pPr`: sets default `spacing`, `jc`, etc.
    - `w:style`: extracts `styleId`, `type`, `name`, `basedOn`, `pPr`, `rPr`, `tblPr`.
- **Document Structure**:
  - Parses `w:document/w:body`:
    - `w:p`:
      - Parses `w:pPr`:
        - `pStyle`, `jc` (`left`, `center`, `right`, `both`), `spacing` (`before`, `after`, `line`, `lineRule`), `ind` (`left`, `right`, `firstLine`, `hanging`), `borders` (`pBdr`), `shd`, `tabs`, `keepNext`, `keepLines`, `pageBreakBefore`, `widowControl`, `numPr` (`numId`, `ilvl`), `sectPr` (embedded section break).
      - Parses child inline nodes:
        - `w:r`: inline run. Parses `w:rPr` (`rStyle`, `rFonts`, `b`, `i`, `u`, `sz`, `color`, `highlight`, `strike`, `vertAlign`, `spacing`, `rtl`, `cs`, `lang`).
        - `w:t`: text with `xml:space="preserve"`.
        - `w:tab`: tab character -> `TabItem`.
        - `w:br`: line, page, or column break -> `BreakItem`.
        - `w:sym`: special symbol -> `SymbolItem`.
        - `w:noBreakHyphen`: non-breaking hyphen `‑`.
        - `w:softHyphen`: optional soft hyphen `­`.
        - `w:hyperlink`: extracts `r:id` or `w:anchor`, assigns `link={'url': ..., 'anchor': ...}` to contained runs.
        - `w:bookmarkStart` / `w:bookmarkEnd`: `BookmarkStartItem` / `BookmarkEndItem`.
        - `w:fldSimple` / `w:fldChar`: `FieldBeginItem`, `FieldSeparateItem`, `FieldEndItem`.
    - `w:tbl`:
      - Parses `w:tblPr` (`tblStyle`, `jc`, `tblW`, `tblBorders`, `tblCellMar`, `tblLook`).
      - Parses `w:tblGrid/w:gridCol` (column widths in pt).
      - Parses `w:tr`: row properties `w:trPr` (`cantSplit`, `tblHeader`, `trHeight`), cells `w:tc`: `w:tcPr` (`tcW`, `gridSpan`, `vMerge`, `tcBorders`, `shd`, `vAlign`), cell child blocks (paragraphs/tables).
    - Trailing `w:sectPr`:
      - Page size `w:pgSz` (width, height, orientation).
      - Page margins `w:pgMar` (top, right, bottom, left, header, footer, gutter).
      - Header / footer references `w:headerReference`, `w:footerReference` mapped to `doc.hf`.
      - Columns `w:cols`, page number format `w:pgNumType`.
- **Preservation Attachment**:
  - Attaches `_source_pkg` and `_doc_format` (`docx` or `docm`) to `Document`.

### 4.2 `DocxWriter` (`src/atboffice/modules/writer/io/docx_writer.py`)
- **Writing Strategy**:
  - **Incremental / Edit Mode**:
    - When `doc._source_pkg` is present, initialize `PackageWriter(doc._source_pkg)`.
    - Serialize updated `word/document.xml`.
    - If styles or settings changed, replace corresponding parts.
    - Keep all other parts 100% byte-for-byte identical (drawings, themes, media, VBA binary).
  - **Standalone / New Document Mode**:
    - Generate complete OPC package with `[Content_Types].xml`, `_rels/.rels`, `word/_rels/document.xml.rels`, `word/document.xml`, `word/styles.xml`, `word/settings.xml`, `word/fontTable.xml`.
- **Serialization Details**:
  - Constructs XML using clean element building and enforces schema order using `enforce_schema_order`:
    - `wordprocessingml_ppr` ordering:
      `pStyle`, `keepNext`, `keepLines`, `pageBreakBefore`, `framePr`, `widowControl`, `numPr`, `suppressLineNumbers`, `pBdr`, `shd`, `tabs`, `suppressAutoHyphens`, `snapToGrid`, `spacing`, `ind`, `contextualSpacing`, `mirrorIndents`, `jc`, `textDirection`, `textAlignment`, `outlineLvl`, `rPr`, `sectPr`.
    - `wordprocessingml_rpr` ordering:
      `rStyle`, `rFonts`, `b`, `bCs`, `i`, `iCs`, `caps`, `smallCaps`, `strike`, `dstrike`, `outline`, `shadow`, `emboss`, `imprint`, `noProof`, `vanish`, `color`, `spacing`, `w`, `kern`, `position`, `sz`, `szCs`, `highlight`, `u`, `vertAlign`, `rtl`, `cs`, `em`, `lang`.
  - Serializes `w:document/w:body`:
    - Paragraphs `<w:p>` and Tables `<w:tbl>`.
    - Trailing `<w:sectPr>` containing page geometry and header/footer references.
  - Generates `word/_rels/document.xml.rels`:
    - Maps headers/footers to target parts (`header1.xml`, `footer1.xml`, etc.).
    - Maps styles, settings, fontTable, numbering relationships.
    - Maps external hyperlinks with `TargetMode="External"`.

---

## 5. Verification Plan

### 5.1 Unit Tests (`tests/unit/writer/test_docx_io.py`)
1. **New Document Creation & Serialization**:
   - Create a clean `Document` with paragraphs, runs, formatting (bold, italic, color, size, font), and section properties.
   - Write to `.docx` bytes with `DocxWriter`.
   - Read back with `DocxReader` and verify all paragraphs, runs, properties, and styles match.
2. **Table Roundtrip**:
   - Create a document with a table (2x2, custom cell widths, borders, background shading, alignments).
   - Write to `.docx` and read back. Verify grid, rows, cells, and cell properties are accurately reconstructed.
3. **Strict OOXML Schema Ordering**:
   - Verify that generated `<w:pPr>` and `<w:rPr>` elements adhere to ECMA-376 schema ordering (e.g. `pStyle` before `spacing`, `spacing` before `ind`, `ind` before `jc`, `jc` before `rPr`).
4. **DOCM Macro-Enabled Preservation**:
   - Create a realistic `.docm` package containing `vbaProject.bin`, `word/document.xml`, `word/styles.xml`, and drawings.
   - Load with `DocxReader`.
   - Edit one paragraph in the document.
   - Save with `DocxWriter`.
   - Assert:
     - `vbaProject.bin` SHA-256 hash is 100% identical.
     - Unmodified parts (e.g. `word/theme/theme1.xml`, media) have identical SHA-256 hashes.
     - Content type for `word/document.xml` correctly retains `macroEnabled.main+xml`.
     - Edited paragraph is updated and readable.
5. **Lossless Unmodified Roundtrip**:
   - Load a complex `.docx` package.
   - Save without modifications.
   - Verify all non-document parts have 100% matching byte contents.

### 5.2 Verification Commands
- `PYTHONPATH=src pytest tests/unit/writer/test_docx_io.py -v`
- Full repository test pass: `PYTHONPATH=src pytest tests/`

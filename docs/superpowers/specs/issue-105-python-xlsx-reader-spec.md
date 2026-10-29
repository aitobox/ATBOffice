# Specification: Issue #105 — Pure Python XLSX Reader (xlsx_reader.py)

## 1. Overview & Objective
Implement a pure Python, zero-external-dependency Open Packaging Conventions (OPC) XLSX spreadsheet reader for ATBOffice Ledger (`src/atboffice/modules/spreadsheet/io/xlsx_reader.py`). The reader must parse standard Microsoft Excel (.xlsx / .xlsm) archives, reconstituting multi-sheet workbook structures, cell values, formulas, formatting/styles, merged cells, custom column widths, row heights, and visibility flags into `WorkbookModel` and `SheetDataModel`.

## 2. Architecture & Design Principles
- **Zero Third-Party Binary Dependencies**: Utilizes Python standard library `zipfile`, `xml.etree.ElementTree`, and standard types.
- **OPC Package Traversal**:
  1. Inspect root relationship table `_rels/.rels` to discover the primary `officeDocument` target (defaults to `xl/workbook.xml`).
  2. Parse `xl/_rels/workbook.xml.rels` to map relationship IDs (`r:id`) to targets: worksheets, shared strings, styles, themes.
  3. Parse `xl/sharedStrings.xml` to construct the Shared String Table (SST), supporting both plain text `<t>` and rich text runs `<r><t>`.
  4. Parse `xl/styles.xml` to build indexed style definitions (`cellXfs`) containing fonts, fills, borders, alignments, and number formats.
  5. Parse `xl/workbook.xml` to retrieve sheets metadata (name, sheetId, state, r:id) and active tab index.
  6. For each worksheet, parse `xl/worksheets/sheetN.xml`:
     - Grid geometry (custom row heights, column widths, hidden rows/columns).
     - Cell data (values, types: string, number, boolean, date, error, inlineStr; formulas and precalculated results; styles).
     - Merged regions (`<mergeCells>`).
- **Data Model Integration**:
  - Populates `WorkbookModel` with one or more `SheetDataModel` worksheets.
  - Cells are stored as `CellData` instances in sparse mapping `sheet.cells[(row, col)]`.
  - Merged regions are stored in `sheet.merges`.
  - Geometries are configured via `sheet.geometry`.

## 3. Detailed Component Specification

### 3.1 Input Handling
- `read_xlsx(source: str | Path | bytes | BinaryIO, workbook: WorkbookModel | None = None) -> WorkbookModel`
  - Accepts a file path string, `pathlib.Path`, raw byte array (`bytes`), or readable binary buffer.
  - If `workbook` is provided, clears existing sheets and populates it; otherwise instantiates a new `WorkbookModel`.
  - Throws `ValueError` with clear, descriptive messaging if the file is invalid, corrupt, or not a valid XLSX OPC package.

### 3.2 XML Namespace & Relationship Resolution
- Handles both Transitional (`http://schemas.openxmlformats.org/spreadsheetml/2006/main`) and Strict (`http://purl.oclc.org/ooxml/spreadsheetml/main`) namespaces.
- Helper functions strip XML namespaces from tag names to allow robust parsing across schema variants.
- Rel path resolution safely joins base directories with relative target paths (e.g. `xl/` + `worksheets/sheet1.xml` -> `xl/worksheets/sheet1.xml`).

### 3.3 Shared String Table (SST) Parsing
- Iterates `<si>` elements in `xl/sharedStrings.xml`.
- Extracts direct text `<t>` or concatenates child `<r><t>` text chunks.
- Decodes XML character escapes (e.g., `_x000D_`, `_x000A_`, standard XML entities).
- Returns `list[str]` indexed by 0-based shared string index.

### 3.4 Stylesheet (`xl/styles.xml`) Parsing
- **Number Formats (`<numFmts>`)**:
  - Merges standard built-in formats (IDs 0-22, 37-49) with custom `<numFmt numFmtId="..." formatCode="..."/>`.
- **Fonts (`<fonts>`)**:
  - Name (`<name val="..."/>`), size (`<sz val="..."/>`), bold (`<b/>`), italic (`<i/>`), underline (`<u/>`), strikethrough (`<strike/>`), color (`<color rgb="..." theme="..."/>`).
- **Fills (`<fills>`)**:
  - `<patternFill patternType="...">` with `<fgColor>` and `<bgColor>` (hex RGB extraction).
- **Borders (`<borders>`)**:
  - Left, right, top, bottom, and diagonal border styles (`thin`, `medium`, `dashed`, `thick`, `double`, etc.) and colors.
- **Cell Formats (`<cellXfs>`)**:
  - References fontId, fillId, borderId, numFmtId, and inline alignment (`horizontal`, `vertical`, `wrapText`, `textRotation`).
  - Precomputes a map of `xf_index -> FormatDelta` to quickly apply styles to `CellData`.

### 3.5 Worksheet Data (`xl/worksheets/*.xml`) Parsing
- **Columns (`<cols><col min="..." max="..." width="..." customWidth="..." hidden="..."/>`)**:
  - Translates 1-based column indices to 0-based.
  - Converts Excel character width into pixel values (approx. 8 pixels per char width or standard formula `int(width * 7 + 5)`).
  - Records hidden columns in `sheet.geometry.hidden_cols`.
- **Rows (`<row r="..." ht="..." customHeight="..." hidden="...">`)**:
  - Translates 1-based row index to 0-based.
  - Converts point height into pixels (`int(ht * 1.33)` or points directly).
  - Records hidden rows in `sheet.geometry.hidden_rows`.
- **Cells (`<c r="..." t="..." s="...">`)**:
  - Parses coordinate `r` (e.g. "C5" -> row 4, col 2).
  - Type resolution:
    - `t="s"`: lookup value from SST.
    - `t="b"`: parse "1"/"0"/"true"/"false" into `bool`.
    - `t="str"`: string value directly from `<v>`.
    - `t="inlineStr"`: string value from `<is><t>`.
    - `t="e"`: formula error string.
    - `t="d"`: ISO 8601 date.
    - Default (numeric): parses float or int. If `<v>` is absent, value is `None`.
  - Formula `<f>`:
    - Extracts formula text without leading `=`.
    - Assigns to `cell.formula`.
  - Styles:
    - Reads style index `s`, looks up precomputed format, and applies to `CellData`.
- **Merges (`<mergeCells><mergeCell ref="..."/>`)**:
  - Parses range notation (e.g. `A1:B2` or `C3:D10`) and calls `sheet.add_merge(r1, c1, r2, c2)`.

### 3.6 Edge Cases & Robustness
1. Empty workbook or workbook without shared strings / styles.
2. XML containing unescaped entities or BOM.
3. Missing cell coordinates in `<c>` (inferred from previous column).
4. Lowercase and mixed-case file paths inside the ZIP archive.
5. Case-insensitive sheet name conflict prevention when adding sheets to `WorkbookModel`.

## 4. Acceptance Verification
- Full unit test coverage in `tests/modules/spreadsheet/test_xlsx_reader.py`.
- Validation with sample programmatic XLSX archives containing numbers, formulas, strings, styles, merges, and geometry.
- Full project test suite passing with zero regressions.

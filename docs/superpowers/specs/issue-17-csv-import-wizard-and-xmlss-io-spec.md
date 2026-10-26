# Specification: [Ledger] CSV 智能编码识别导入向导与 XML Spreadsheet 2003 读写

- **Issue**: #17
- **Branch**: `agent/issue-17-csv-import-wizard-and-xmlss-io`
- **Module**: `src/atboffice/modules/spreadsheet/io/`, `src/atboffice/modules/spreadsheet/dialogs/`
- **Reference**: `.vibeoffice/public/ledger/js/csv.js`, `.vibeoffice/public/ledger/js/xmlss.js`

---

## 1. Overview & Architecture

This specification defines the implementation of expanded file format support for ATBOffice Ledger:
1. **CSV / TSV / Delimited & Fixed-Width Text I/O (`src/atboffice/modules/spreadsheet/io/csv_io.py`)**:
   - Universal character encoding detection: UTF-8 (with and without BOM), UTF-16LE/BE (with and without BOM), GB18030/GBK (Chinese), and Windows-1252/Latin-1 fallback.
   - Robust RFC 4180 parsing with quotes, multi-line text, escaped quotes (`""`), and consecutive delimiter merging.
   - Delimiter sniffer (comma, tab, semicolon, pipe, space) and fixed-width column break detection.
   - Value conversion conforming to Excel's General rules (Numbers, Dates, Booleans, Strings) and specific column formats ("Text", "Date", "Skip").
   - CSV / TSV export respecting cell formatting (`format_code`) and RFC 4180 quoting.
2. **Text Import Wizard Dialog (`src/atboffice/modules/spreadsheet/dialogs/text_import_wizard.py`)**:
   - Classic Excel 3-step modal dialog with live preview:
     - Step 1: Data type (Delimited vs Fixed width), Start row, Encoding / File origin selector, raw preview.
     - Step 2: Delimiters selection (Tab, Semicolon, Comma, Space, Other), consecutive delimiter merging, text qualifier (`"`, `'`, None), and parsed column table preview.
     - Step 3: Column data format (General, Text, Date, Do not import column/Skip) with interactive column selection and format tagging.
   - Internationalization (`safe_tr`, `retranslate_ui`), keyboard accessibility, and clean cancellation/completion.
3. **XML Spreadsheet 2003 Read / Write (`src/atboffice/modules/spreadsheet/io/xmlss_io.py`)**:
   - Full support for Microsoft XML Spreadsheet 2003 (`SpreadsheetML`, `urn:schemas-microsoft-com:office:spreadsheet`).
   - Bidirectional R1C1 ⇄ A1 formula conversion (handling relative offsets, absolute references, row/col ranges).
   - Reader: parsing `<Workbook>`, `<Styles>`, `<Worksheet>`, `<Table>`, `<Row>`, `<Cell>`, `<Data>`, merged cells (`ss:MergeAcross`, `ss:MergeDown`), sparse indexing (`ss:Index`), and cell formatting.
   - Writer: serializing `SheetDataModel` into clean, valid XMLSS with R1C1 formulas, merged cell tags, styles, and data types (`Number`, `String`, `DateTime`, `Boolean`).

---

## 2. Detailed Technical Design

### 2.1 CSV & Text I/O (`src/atboffice/modules/spreadsheet/io/csv_io.py`)

#### 2.1.1 Encoding Detection (`decode_bytes`)
- **Signatures**:
  - `decode_bytes(b: bytes, encoding: str | None = None) -> tuple[str, str]`
- **Detection Algorithm**:
  1. If `encoding` is provided and not `"auto"`, decode directly using Python's standard codec. Strip leading `\ufeff` if present.
  2. BOM detection:
     - `\xef\xbb\xbf`: UTF-8 (strip BOM, return `("utf-8")`)
     - `\xff\xfe`: UTF-16LE (strip BOM, return `("utf-16le")`)
     - `\xfe\xff`: UTF-16BE (strip BOM, return `("utf-16be")`)
  3. UTF-16 without BOM check:
     - Sample first 2000 bytes. If zero bytes are heavily concentrated on odd positions (`z1 > n / 6 and z0 < n / 50`), decode as `utf-16le`.
     - If concentrated on even positions (`z0 > n / 6 and z1 < n / 50`), decode as `utf-16be`.
  4. Strict UTF-8 trial:
     - Attempt `b.decode("utf-8")`. If successful, return `("utf-8")`.
  5. Chinese GB18030 trial:
     - Attempt `b.decode("gb18030")`. If valid and contains Chinese characters, return `("gb18030")`.
  6. Fallback:
     - Fallback to `"windows-1252"` (or `"latin1"`). Never fail or raise unhandled exceptions.

#### 2.1.2 Delimited & Fixed-Width Parsing
- **Functions**:
  - `parse_delimited(text: str, delims: str = ",", quote: str = '"', merge: bool = False, max_rows: int | None = None) -> list[list[str]]`
  - `parse_fixed_width(text: str, breaks: list[int], max_rows: int | None = None) -> list[list[str]]`
  - `sniff_delimiter(text: str) -> str`
  - `guess_fixed_breaks(text: str) -> list[int]`
- **Parsing Rules**:
  - Full state machine for delimited text: tracks in-quote vs out-of-quote, escaped quotes `""`, handles `\r\n`, `\n`, `\r`.
  - When `merge=True`, runs of consecutive delimiter characters (e.g., multiple spaces or tabs) collapse into a single delimiter, skipping empty adjacent tokens.
  - `sniff_delimiter` tests candidate delimiters `[",", "\t", ";", "|", " "]` against the first 30 non-empty lines, choosing the delimiter with the highest and most consistent column count (> 1).

#### 2.1.3 Value Conversion & Sheet Population
- **Function**:
  - `convert_cell_value(val_str: str, col_type: str = "General") -> Any`
  - `populate_sheet(model: SheetDataModel, rows: list[list[str]], start_row: int = 0, start_col: int = 0, col_formats: list[str] | None = None)`
- **Conversion Semantics**:
  - `col_type == "Skip"`: Column is omitted.
  - `col_type == "Text"`: Value stored as verbatim `str`.
  - `col_type == "General"`:
    - Empty string -> `None`
    - "TRUE" / "FALSE" -> `True` / `False`
    - Numeric string (int, float, scientific notation `1.23e-4`, percentage `12.5%` -> `0.125`, thousands separated `1,234.56`) -> `int` or `float`.
    - Date string matching ISO or common formats -> parsed date or text representation.
    - Otherwise -> verbatim string.

#### 2.1.4 CSV Export
- **Function**:
  - `export_csv(model: SheetDataModel, delimiter: str = ",", quote: str = '"', encoding: str = "utf-8") -> str`
- **Export Semantics**:
  - Scans model for active rows and columns.
  - Formats cell using `model.get_formatted_text(r, c)`.
  - Quotes values containing `delimiter`, `\r`, `\n`, or `quote`. Escapes quotes by doubling them (`"` -> `""`).

---

### 2.2 Text Import Wizard (`src/atboffice/modules/spreadsheet/dialogs/text_import_wizard.py`)

- **Class**: `TextImportWizard(QDialog)`
- **Properties & State**:
  - `bytes_data: bytes`
  - `encoding: str`
  - `data_mode: str` ("delimited" | "fixed")
  - `start_row: int`
  - `delimiters: dict[str, bool]` (tab, semicolon, comma, space, other)
  - `other_char: str`
  - `merge_delimiters: bool`
  - `text_qualifier: str` (`"`, `'`, None)
  - `fixed_breaks: list[int]`
  - `column_formats: dict[int, str]` (col_index -> "General" | "Text" | "Date:YMD" | "Skip")
  - `selected_col_index: int`
- **Step Layout**:
  - Uses `QStackedWidget` with 3 step pages:
    1. **Page 1 (Format & Origin)**:
       - Radio buttons: Delimited vs Fixed width.
       - SpinBox: Start import at row (1 to 9999).
       - ComboBox: File origin (Auto, UTF-8, GB18030, Windows-1252, UTF-16LE, UTF-16BE).
       - Raw text preview widget.
    2. **Page 2 (Delimiters / Breaks)**:
       - If Delimited: Checkboxes for Tab, Semicolon, Comma, Space, Other; QLineEdit for other; Checkbox for merge; ComboBox for qualifier.
       - If Fixed: list of column break offsets.
       - Table preview showing column division.
    3. **Page 3 (Column Data Format)**:
       - Radio buttons: General, Text, Date (with date order dropdown), Skip.
       - Interactive preview `QTableWidget`: Clicking column header or cells selects the column, changes column header to show `[General]`, `[Text]`, `[Skip]`, etc., and updates radios.
  - Navigation bar:
    - `< Back` (disabled on page 0)
    - `Next >` (disabled on page 2)
    - `Finish` (enabled on pages 1 and 2)
    - `Cancel`
- **Result Output**:
  - `get_result_rows() -> list[list[Any]]`
  - `populate_model(model: SheetDataModel, start_row: int = 0, start_col: int = 0)`

---

### 2.3 XML Spreadsheet 2003 I/O (`src/atboffice/modules/spreadsheet/io/xmlss_io.py`)

#### 2.3.1 R1C1 ⇄ A1 Formula Translator
- **Functions**:
  - `from_r1c1(formula: str, r: int, c: int) -> str`
  - `to_r1c1(formula: str, r: int, c: int) -> str`
- **Syntax Supported**:
  - Relative: `R[1]C[2]`, `R[-3]C[-1]`, `RC[1]`, `R[2]C`
  - Absolute: `R1C1`, `R10C5`
  - Mixed: `R1C[2]`, `R[-1]C5`
  - Row / Column ranges: `R1:R5` -> `$1:$5`, `C1:C3` -> `$A:$C`
  - Preserves quoted string literals within formulas (`"..."`).

#### 2.3.2 Reading XMLSS (`read_xmlss`)
- **Function**:
  - `read_xmlss(content: str | bytes, model: SheetDataModel | None = None) -> SheetDataModel`
- **Parsing Logic**:
  - Parses XML using `xml.etree.ElementTree`.
  - Normalizes tag names by removing namespace prefix (`{urn:schemas-microsoft-com:office:spreadsheet}`).
  - Reads `<Styles>`: ID, Font (Bold, Italic, Color, FontName, Size, Underline), NumberFormat (`ss:Format`), Interior (Color, Pattern), Borders, Alignment.
  - Reads first `<Worksheet>` `<Table>`:
    - Reads `<Row ss:Index="N">` (with 1-based sparse index handling).
    - Reads `<Cell ss:Index="M" ss:StyleID="..." ss:Formula="..." ss:MergeAcross="X" ss:MergeDown="Y">`:
      - Handles sparse column positioning.
      - Extracts `<Data ss:Type="Number|String|DateTime|Boolean">`.
      - Converts formulas from R1C1 to A1.
      - Registers merged cell ranges with `model.add_merge`.
      - Applies styles to `CellData`.

#### 2.3.3 Writing XMLSS (`write_xmlss`)
- **Function**:
  - `write_xmlss(model: SheetDataModel, sheet_name: str = "Sheet1") -> str`
- **Serialization Logic**:
  - Builds document root with XML declaration and processing instruction:
    `<?xml version="1.0"?>`
    `<?mso-application progid="Excel.Sheet"?>`
    `<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet" xmlns:html="http://www.w3.org/TR/REC-html40">`
  - Maps unique cell styles into `<Styles>` with stable IDs (`s1`, `s2`, ...).
  - Emits `<Worksheet ss:Name="...">` and `<Table>`.
  - Skips empty rows and columns, emitting `ss:Index` when jumping over empty cells.
  - Emits `ss:MergeAcross` and `ss:MergeDown` for merged origins.
  - Converts formulas from A1 to R1C1 on `ss:Formula`.
  - Formats `<Data ss:Type="...">` matching the value type.

---

## 3. Verification & Acceptance Criteria

1. **Encoding Verification**:
   - Correctly decodes sample bytes with UTF-8 BOM, UTF-16LE BOM, UTF-16BE BOM.
   - Correctly identifies and decodes non-BOM UTF-8 and Chinese GB18030 text without corruption or Mojibake.
   - Robust fallback to Windows-1252 for binary/legacy Western text.
2. **Delimiter & Fixed Width Parsing**:
   - Parses CSV, TSV, semicolon-separated, and space-separated lines.
   - Handles multi-line quotes, embedded commas, and escaped quotes (`""`).
   - Slices fixed-width files correctly given break indices.
3. **CSV Export Roundtrip**:
   - Values with format codes exported accurately (e.g. `$1,234.00`, `12.5%`).
   - Quotes added only when necessary.
4. **Formula Translation (R1C1 ⇄ A1)**:
   - Relative offsets (`R[1]C[1]`), absolute coordinates (`R1C1`), mixed coordinates (`R1C[-1]`).
   - Whole row ranges (`R1:R3`) and column ranges (`C1:C2`).
   - Preserves string literals with `R` or `C` characters inside quotes.
5. **XMLSS Roundtrip**:
   - Reads existing XMLSS files, sets cells, formulas, merges, and styles.
   - Writes XMLSS files that can be read back with 100% data and formula fidelity.
6. **Text Import Wizard UI**:
   - Steps 1 -> 2 -> 3 navigation.
   - Preview update on delimiter change.
   - Interactive column selection and format assignment.
   - Full translation and clean layout in PySide6.
7. **Test Suite**:
   - `pytest tests/unit/spreadsheet/test_csv_and_xmlss.py -v` passes 100%.
   - Full regression test passes with zero regressions.

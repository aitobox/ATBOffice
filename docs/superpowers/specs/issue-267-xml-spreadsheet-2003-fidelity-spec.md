# Specification: XML Spreadsheet 2003 (*.xml) Full Bi-directional Read/Write Fidelity

- **Issue**: #267 (`[compat-2003] feat(ledger): 对齐 .vibeoffice 实现完整的 XML Spreadsheet 2003 (*.xml) 双向读写与保真度 (Step 2 of 3)`)
- **Parent Epic**: #265 (Format 97-2003 Compatibility)
- **Status**: Draft / Approved (>=90% confidence autonomous decision)

---

## 1. Background & Objectives

`.vibeoffice` natively and comprehensively supports Office 2003's open XML format — **XML Spreadsheet 2003 (SpreadsheetML 2003, `*.xml`)** via `ledger/js/xmlss.js` and validates round-trip fidelity with `tests/ledger/xmlss-rt.js`.
In ATBOffice, `src/atboffice/modules/spreadsheet/io/xmlss_io.py` provided an initial single-sheet prototype. To achieve true 1:1 parity with `.vibeoffice` and Excel 2003, `xmlss_io.py` must be upgraded to:
1. Deeply align with `.vibeoffice/public/ledger/js/xmlss.js`.
2. Fully support multi-worksheet read and write (`<Worksheet ss:Name="...">`), including empty worksheets and preserving the active worksheet selection (`<ActiveSheet>` and `<Selected/>`).
3. Support all SpreadsheetML standard data types: `String`, `Number`, `DateTime` (ISO 8601 timestamps mapped to/from Excel serial numbers or dates), `Boolean` (`1`/`0`/`true`/`false`), and `Error` (e.g. `#DIV/0!`, `#VALUE!`, `#N/A`, `#REF!`, `#NAME?`, `#NUM!`, `#NULL!`).
4. Support full bidirectional R1C1 $\leftrightarrow$ A1 formula conversion, including sheet-qualified references (e.g. `'Sheet 2'!R1C1`), whole row/column ranges (`R1:R5`, `C1:C3`), and complex expressions while preserving quoted strings.
5. Support cell merging (`ss:MergeAcross`, `ss:MergeDown`), row heights (`ss:Height`, `ss:Hidden`, `ss:Span`), column widths (`ss:Width`, `ss:Hidden`, `ss:Span`), and cell styles (font, borders, background patterns, alignment, number formats).
6. Implement a round-trip fidelity verification suite (`tests/test_xmlss.py`) patterned after `tests/ledger/xmlss-rt.js`.

---

## 2. Architecture & Design

### 2.1 R1C1 $\leftrightarrow$ A1 Conversion Engine

#### `from_r1c1(text: str, r: int, c: int) -> str`
- Converts R1C1 formula expressions into A1 expressions without leading `=`.
- Accurately parses:
  - String literals in double quotes `"` and sheet names enclosed in single quotes `'`.
  - Sheet prefixes: `Sheet1!R[1]C[1]` or `'My Sheet'!R1C1` $\rightarrow$ `Sheet1!B2` or `'My Sheet'!$A$1`.
  - Cell references: `R[m]C[n]` (relative), `RmCn` (absolute), `RC[n]` (current row), `R[m]C` (current col).
  - Row ranges: `R1:R5` $\rightarrow$ `$1:$5`, `R[-2]:R[-1]` $\rightarrow$ `1:2`.
  - Column ranges: `C1:C3` $\rightarrow$ `$A:$C`, `C[-1]:C[1]` $\rightarrow$ `B:D`.
  - Area ranges: `R1C1:R5C5` $\rightarrow$ `$A$1:$E$5`.
  - Normalizes duplicate spans (e.g. `1:1:3:3` $\rightarrow$ `1:3`).

#### `to_r1c1(formula: str, r: int, c: int) -> str`
- Converts A1 formulas into R1C1 expressions prefixed with `=`.
- Preserves quoted string literals.
- Handles:
  - Sheet prefixes: `Sheet1!A1` $\rightarrow$ `Sheet1!R...C...`, `'My Sheet'!$A$1` $\rightarrow$ `'My Sheet'!R1C1`.
  - Area ranges: `$A$1:$B$5` or `A1:B2` $\rightarrow$ `R...C...:R...C...`.
  - Whole column ranges: `A:B` or `$A:$C` $\rightarrow$ `C...:C...`.
  - Whole row ranges: `1:5` or `$1:$10` $\rightarrow$ `R...:R...`.
  - Single cell references: `A1` or `$B$2` $\rightarrow$ `R...C...`.

### 2.2 Data Types & Value Coercion

In XML Spreadsheet 2003:
- `<Data ss:Type="String">text</Data>` $\rightarrow$ `str`.
- `<Data ss:Type="Number">123.45</Data>` $\rightarrow$ `int` or `float`.
- `<Data ss:Type="Boolean">1</Data>` $\rightarrow$ `bool` (`True` if `"1"` or `"true"` case-insensitively, else `False`).
- `<Data ss:Type="DateTime">2003-05-12T10:30:00.000</Data>`:
  - Parse ISO 8601 datetime strings using regex or `datetime.fromisoformat`.
  - Compute Excel serial number using `date_to_serial` from `atboffice.modules.spreadsheet.calc.coercion` plus fraction of the day.
  - On write: if a cell has a datetime or date, or number with date number format, format as ISO 8601 string: `YYYY-MM-DDTHH:MM:SS.sss`.
- `<Data ss:Type="Error">#DIV/0!</Data>`:
  - Parse as `ExcelError` or error string.
  - On write: if cell value is an `ExcelError` or starts with `#` matching standard error names, output `<Data ss:Type="Error">...</Data>`.

### 2.3 Multi-Worksheet Model Integration

- **`read_xmlss(content: str | bytes, model: SheetDataModel | WorkbookModel | None = None, return_workbook: bool = False) -> SheetDataModel | WorkbookModel`**:
  - If `isinstance(model, WorkbookModel)`:
    - Populates `model` with all `<Worksheet>`s parsed from the XML.
    - Sets active sheet index according to `<ActiveSheet>` or `<WorksheetOptions><Selected/></WorksheetOptions>`.
    - Returns `model`.
  - If `isinstance(model, SheetDataModel)`:
    - Populates `model` with the first (or active) worksheet in the workbook for backward compatibility.
    - Returns `model`.
  - If `model is None`:
    - If `return_workbook is True`: returns a new `WorkbookModel` containing all worksheets.
    - If `return_workbook is False`: returns a `SheetDataModel` of the active/first sheet, with `model.extra["workbook"]` pointing to the full `WorkbookModel`.
- **`read_xmlss_workbook(content: str | bytes) -> WorkbookModel`**:
  - High-level convenience function: always returns a fully populated `WorkbookModel`.
- **`write_xmlss(model: SheetDataModel | WorkbookModel, sheet_name: str = "Sheet1") -> str`**:
  - Accepts either a single `SheetDataModel` or a multi-sheet `WorkbookModel`.
  - If `WorkbookModel`:
    - Generates `<Workbook>` with `<DocumentProperties>` and `<ExcelWorkbook><ActiveSheet>...</ActiveSheet></ExcelWorkbook>`.
    - Unifies styles across all worksheets.
    - Emits `<Worksheet ss:Name="...">` for each worksheet in `model.sheets` (including empty sheets).
    - Preserves per-sheet row heights, column widths, hidden rows/columns, merges, and freeze panes.

### 2.4 Cell Merges, Column Widths, and Row Heights

- **Column Widths & Hidden Columns**:
  - Read: `<Column ss:Index="c" ss:Width="w" ss:Hidden="1" ss:Span="n"/>`.
    - Conversion: `w` in points $\rightarrow$ pixels: `px = int(round(w / 0.75))`.
    - Assign to `sheet.geometry.set_col_width(col, px)` for `col` through `col + n`.
    - If `ss:Hidden == "1"`, add columns to `sheet.geometry.hidden_cols`.
  - Write: Emit `<Column ss:Index="..." ss:Width="..." ss:Hidden="1"/>` for any columns with custom widths or hidden status.
- **Row Heights & Hidden Rows**:
  - Read: `<Row ss:Index="r" ss:Height="h" ss:Hidden="1" ss:Span="n"/>`.
    - Conversion: `h` in points $\rightarrow$ pixels: `px = int(round(h / 0.75))`.
    - Assign to `sheet.geometry.set_row_height(row, px)` for `row` through `row + n`.
    - If `ss:Hidden == "1"`, add rows to `sheet.geometry.hidden_rows`.
  - Write: Emit `<Row ss:Index="..." ss:Height="..." ss:Hidden="1">` for rows with custom heights, hidden state, or non-empty cells.
- **Cell Merges**:
  - Read: `ss:MergeAcross="ma"` and `ss:MergeDown="md"`.
    - Registers region `(r, c, r + md, c + ma)` in `sheet.merges`.
  - Write: Top-left cell emits `ss:MergeAcross` and/or `ss:MergeDown`; covered cells in the merged region are skipped.

### 2.5 Style Parity

- Full alignment with `.vibeoffice` styles:
  - Font: `Bold`, `Italic`, `Underline` (`Single`, `Double`, `SingleAccounting`, `DoubleAccounting`), `StrikeThrough`, `VerticalAlign` (`Superscript`, `Subscript`), `Color`, `FontName`, `Size`.
  - Interior: `Color`, `Pattern` (`Solid`, `Gray50`, etc.), `PatternColor`.
  - Alignment: `Horizontal`, `Vertical`, `WrapText`, `ShrinkToFit`, `Indent`, `Rotate`.
  - Borders: `Top`, `Bottom`, `Left`, `Right`, `DiagonalLeft`, `DiagonalRight`, with line styles (`Continuous`, `Dash`, `Dot`, `Double`, etc.) and weights.
  - NumberFormat: named formats (`General`, `Currency`, `Short Date`, `Percent`, etc.) and custom format codes.

---

## 3. Test & Verification Plan

1. **`tests/unit/spreadsheet/test_csv_and_xmlss.py`**:
   - Ensure all 18 existing tests continue to pass with zero regressions.
2. **`tests/test_xmlss.py`**:
   - Test R1C1 $\leftrightarrow$ A1 bidirectional conversion (relative, absolute, whole row/column, cross-sheet references).
   - Test multi-worksheet read and write (multiple sheets, empty sheets, active sheet selection).
   - Test all data types (`String`, `Number`, `Boolean`, `DateTime`, `Error`).
   - Test geometry & merges (column widths, row heights, hidden rows/columns, merges across/down).
   - Test styles (fonts, alignments, borders, background patterns, number formats).
   - Test round-trip fidelity: `SheetDataModel` and `WorkbookModel` serialize to XML and deserialize back with identical values, formulas, geometry, and styles.

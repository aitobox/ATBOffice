# Implementation Plan: XML Spreadsheet 2003 (*.xml) Full Bi-directional Read/Write Fidelity

- **Issue**: #267
- **Target Branch**: `agent/issue-267-xml-spreadsheet-2003`
- **Spec**: `docs/superpowers/specs/issue-267-xml-spreadsheet-2003-fidelity-spec.md`
- **Status**: Ready for execution

---

## Task Breakdown

### Task 1: R1C1 $\leftrightarrow$ A1 Conversion Engine Upgrade
- **Files**:
  - `src/atboffice/modules/spreadsheet/io/xmlss_io.py`
  - `tests/test_xmlss.py`
- **Changes**:
  - In `from_r1c1`:
    - Support quoted sheet names `'Sheet 1'!R1C1` and unquoted sheet names `Sheet1!R[1]C[1]`.
    - Support row ranges `R1:R5` $\rightarrow$ `$1:$5`, column ranges `C1:C3` $\rightarrow$ `$A:$C`.
    - Support area ranges `R1C1:R5C5` $\rightarrow$ `$A$1:$E$5`.
    - Simplify redundant duplicated spans like `1:1:3:3` $\rightarrow$ `1:3`.
  - In `to_r1c1`:
    - Support sheet-prefixed references `Sheet1!A1`, `'Quarter 1'!$A$1`.
    - Support whole column ranges `A:B`, `$C:$E`.
    - Support whole row ranges `1:10`, `$2:$5`.
    - Support area ranges `A1:B5`, `$A$1:$D$10`.
    - Retain string literals in quotes.
- **Verification**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_xmlss.py -k "r1c1"`

---

### Task 2: Reader Enhancements (Types, Multi-Sheet, Geometry, Styles)
- **Files**:
  - `src/atboffice/modules/spreadsheet/io/xmlss_io.py`
  - `tests/test_xmlss.py`
- **Changes**:
  - Support reading all data types in `<Data ss:Type="...">`:
    - `String`, `Number`, `Boolean` (`1`/`0`/`true`/`false`), `DateTime` (ISO string $\rightarrow$ serial date / datetime), `Error` (`#DIV/0!`, `#VALUE!`, `#N/A`, `#REF!`, `#NAME?`, `#NUM!`, `#NULL!`).
  - Support reading multiple `<Worksheet>` elements:
    - Empty worksheets (no `<Row>` or `<Table>`).
    - Parse `<ActiveSheet>` and `<Selected/>` to determine active sheet index.
  - Support reading `<Column>` geometry (`ss:Width`, `ss:Hidden`, `ss:Span`) and `<Row>` geometry (`ss:Height`, `ss:Hidden`, `ss:Span`).
  - Support comprehensive style parsing:
    - Font: `Bold`, `Italic`, `Underline`, `StrikeThrough`, `VerticalAlign`, `Color`, `FontName`, `Size`.
    - Interior: `Color`, `Pattern`, `PatternColor`.
    - Alignment: `Horizontal`, `Vertical`, `WrapText`, `ShrinkToFit`, `Indent`, `Rotate`.
    - Borders: `Top`, `Bottom`, `Left`, `Right`, `DiagonalLeft`, `DiagonalRight`.
    - NumberFormat: format code.
  - Support `read_xmlss(content, model=..., return_workbook=...)` and `read_xmlss_workbook(content)`.
- **Verification**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_xmlss.py -k "read"`

---

### Task 3: Writer Enhancements (WorkbookModel, Multi-Sheet, Geometry, Types, Styles)
- **Files**:
  - `src/atboffice/modules/spreadsheet/io/xmlss_io.py`
  - `tests/test_xmlss.py`
- **Changes**:
  - Allow `write_xmlss(model: SheetDataModel | WorkbookModel, sheet_name: str = "Sheet1")`:
    - If `WorkbookModel`, loop over all `model.sheets`.
    - Emit `<ActiveSheet>{model.active_sheet_index}</ActiveSheet>`.
    - For each worksheet: emit `<Worksheet ss:Name="...">`, `<Table>` with custom `<Column>` widths, `<Row>` heights, and cell merges.
    - If active sheet, emit `<WorksheetOptions><Selected/></WorksheetOptions>`.
  - Emit data types:
    - `Boolean` $\rightarrow$ `<Data ss:Type="Boolean">1</Data>`
    - `Number` $\rightarrow$ `<Data ss:Type="Number">...</Data>`
    - `DateTime` $\rightarrow$ `<Data ss:Type="DateTime">YYYY-MM-DDTHH:MM:SS.sss</Data>`
    - `Error` $\rightarrow$ `<Data ss:Type="Error">#DIV/0!</Data>`
    - `String` $\rightarrow$ `<Data ss:Type="String">...</Data>`
  - Emit complete `<Style>` definitions for fonts (underline, strikethrough, vertical align, color, font name, size), interior (pattern, pattern color, color), alignment (shrink to fit, indent, rotate, vertical text), borders, and number formats.
- **Verification**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_xmlss.py -k "write"`

---

### Task 4: UI Shell Integration for Multi-Sheet XMLSS
- **Files**:
  - `src/atboffice/ui/shell/ledger_window.py`
- **Changes**:
  - When opening `.xml`, `.xmlss`, or XML-markup `.xls`, load with `read_xmlss_workbook` (or `read_xmlss(data, return_workbook=True)`) so all worksheets in the file are loaded into the ledger window.
- **Verification**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/ -k "xmlss"`

---

### Task 5: Round-Trip Fidelity Test Suite
- **Files**:
  - `tests/test_xmlss.py`
  - `tests/unit/spreadsheet/test_csv_and_xmlss.py`
- **Changes**:
  - Construct comprehensive round-trip test:
    - Multi-sheet workbook with 3 sheets (Data Sheet, Formatted Sheet, Empty Sheet).
    - Diverse cell values (int, float, bool, string, date, error).
    - R1C1 formulas (local and cross-sheet).
    - Row heights and column widths.
    - Merged cells.
    - Rich styles (fonts, alignments, borders, background patterns, number formats).
    - Write to XMLSS $\rightarrow$ read back $\rightarrow$ assert complete equivalence.
- **Verification**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_xmlss.py -v`
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/spreadsheet/test_csv_and_xmlss.py -v`

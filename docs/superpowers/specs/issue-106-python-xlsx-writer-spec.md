# Specification: Pure Python XLSX Writer (xlsx_writer.py) & Workbook Serialization

## 1. Overview & Objective
This specification defines the architectural and algorithmic implementation of a pure Python XLSX writer (`xlsx_writer.py`) for ATBOffice Ledger.
Previously, ATBOffice could read `.xlsx` files via `xlsx_reader.py`, but lacked the ability to serialize, save, or export workbooks to OOXML `.xlsx` format.
This implementation provides standard ECMA-376 (SpreadsheetML) serialization directly from `WorkbookModel`, producing files that open cleanly in Microsoft Excel, Apple Numbers, WPS Office, and LibreOffice Calc. In addition, it integrates with `atboffice.vfs.opc.PackageWriter` to support Part-level Carry (retaining untouched sheets, macros, media, themes, and extensions from original packages).

---

## 2. Requirements & Acceptance Criteria
1. **Core API Contract**:
   ```python
   def write_xlsx(
       workbook: WorkbookModel,
       output_path: str | Path | BinaryIO | None = None,
       source_opc: SourcePackage | bytes | str | Path | None = None,
   ) -> bytes:
       ...
   ```
   - Accepts a `WorkbookModel` instance.
   - If `output_path` is a filesystem path (`str` or `Path`), atomically writes the generated package to disk.
   - If `output_path` is a binary stream (e.g. `io.BytesIO`), writes the bytes into the stream.
   - Returns the complete serialized ZIP bytes in all scenarios.
   - If `source_opc` is provided, carries forward any parts not modified or overwritten.

2. **Standard Package Structure (ECMA-376 Transitional)**:
   - `[Content_Types].xml`: Content type mappings with proper Defaults (`rels`, `xml`) and Overrides for all parts.
   - `_rels/.rels`: Package root relationships pointing to `xl/workbook.xml`, `docProps/core.xml`, `docProps/app.xml`.
   - `docProps/core.xml`: Dublin Core and OpenXML metadata (`created`, `modified`, `creator`).
   - `docProps/app.xml`: Extended application properties (`Application="ATBOffice Ledger"`, worksheet titles).
   - `xl/workbook.xml`: Workbook structure, views, active tab, and worksheet definitions with relationship IDs.
   - `xl/_rels/workbook.xml.rels`: Relationships pointing to worksheets, `styles.xml`, `sharedStrings.xml`, and `theme/theme1.xml`.
   - `xl/theme/theme1.xml`: Standard Office theme palette and font definitions.
   - `xl/styles.xml`: Unified stylesheet containing fonts, fills, borders, number format definitions, and XF records.
   - `xl/sharedStrings.xml`: Deduplicated shared string table (SST) preserving whitespace.
   - `xl/worksheets/sheet{N}.xml`: Valid SpreadsheetML worksheets adhering to strict schema sequence.

3. **Feature Support in Worksheets**:
   - Multiple sheets with custom names and active tab synchronization.
   - Cell data types: string (SST lookup), number (integer/float), boolean (`1`/`0`), error (`#NUM!`, `#VALUE!`, etc.), formula.
   - Formulas: `<f>SUM(A1:A10)</f>` with cached computed values `<v>...</v>`.
   - Column custom widths (`<cols><col min="..." max="..." width="..." customWidth="1"/></cols>`).
   - Row custom heights (`<row r="..." ht="..." customHeight="1">`).
   - Cell styles & formatting: bold, italic, underline, strike, font family, font size, fg/bg color, number format codes, text alignment (horizontal, vertical, wrapText).
   - Merged cell regions (`<mergeCells><mergeCell ref="A1:B3"/></mergeCells>`).

4. **Robustness & Edge Cases**:
   - Empty workbook or sheet with zero cells.
   - XML character escaping (`&`, `<`, `>`, `"`, `'`) and control character encoding (`_x000D_`).
   - Preservation of leading/trailing spaces via `xml:space="preserve"`.
   - 100% round-trip fidelity (`read_xlsx(write_xlsx(wb))`).

---

## 3. Architecture & Data Flow

```
[WorkbookModel]
      │
      ├─► Step 1: Collect & Deduplicate Shared Strings (SST)
      │
      ├─► Step 2: Build Stylesheet & Index Formats (StyleManager)
      │           ├── Fonts, Fills, Borders, NumFmts
      │           └── CellXfs (maps CellData format -> style ID)
      │
      ├─► Step 3: Serialize Worksheets (sheet1.xml, sheet2.xml, ...)
      │           ├── Dimension & SheetViews (activeTab)
      │           ├── Column widths & Row heights
      │           ├── Row/Cell data (<c r="..." s="..." t="..."><v>...</v></c>)
      │           └── Merged cell ranges (<mergeCells>)
      │
      ├─► Step 4: Serialize Workbook Parts
      │           ├── xl/workbook.xml & xl/_rels/workbook.xml.rels
      │           ├── xl/styles.xml & xl/sharedStrings.xml
      │           ├── xl/theme/theme1.xml
      │           └── docProps/core.xml & docProps/app.xml
      │
      ├─► Step 5: Package Assembly via PackageWriter
      │           ├── Carry untouched parts if source_opc provided
      │           └── Generate [Content_Types].xml & _rels/.rels
      │
      ▼
[Serialized .xlsx Bytes / File on Disk]
```

---

## 4. Component Details

### 4.1 Shared String Table (SST) Builder
Collects every unique string across all cells in all worksheets:
- Maps `text -> sst_index`.
- Escapes XML special characters (`&amp;`, `&lt;`, `&gt;`, `&quot;`, `&apos;`).
- Adds `xml:space="preserve"` if string begins or ends with whitespace or contains newlines.
- Emits `<sst xmlns="..." count="{total}" uniqueCount="{unique}">...<si><t>...</t></si></sst>`.

### 4.2 StyleManager (Stylesheet Builder)
Maps cell styling attributes from `CellData` to OOXML style indices:
- **Fonts**: Deduplicates based on `(name, size, bold, italic, underline, strike, color)`.
- **Fills**:
  - Fill 0: `<fill><patternFill patternType="none"/></fill>` (mandatory baseline).
  - Fill 1: `<fill><patternFill patternType="gray125"/></fill>` (mandatory baseline).
  - Fill 2+: Solid fills `<fill><patternFill patternType="solid"><fgColor rgb="FF..."/><bgColor rgb="FF..."/></patternFill></fill>`.
- **Borders**: Deduplicates based on `(left, right, top, bottom, diagonal)`. Index 0 is empty border.
- **Number Formats**: Standard formats (0, 1, 2, 9, 10, etc.) map to builtin IDs. Custom format codes allocate `numFmtId >= 164`.
- **CellXfs**:
  - Index 0: Normal default style.
  - Generates `<xf numFmtId="..." fontId="..." fillId="..." borderId="..." applyNumberFormat="1" ...><alignment .../></xf>`.

### 4.3 Worksheet Serializer
Iterates through cells sorted by row then column (`r, c`):
- Computes bounding dimension (e.g. `A1:D15` or `A1`).
- Emits XML adhering strictly to ECMA-376 element order:
  1. `<dimension ref="..."/>`
  2. `<sheetViews><sheetView ... workbookViewId="0"/></sheetViews>`
  3. `<sheetFormatPr defaultRowHeight="20"/>`
  4. `<cols>` (if custom column widths exist)
  5. `<sheetData>` (rows and cells)
  6. `<mergeCells count="...">` (if merges exist)
  7. `<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>`

### 4.4 OPC Packaging & Part-Level Carry
Using `atboffice.vfs.opc.PackageWriter`:
- If `source_opc` is provided, initialize `PackageWriter(source_package=source_opc)`.
- Replace `xl/workbook.xml`, `xl/styles.xml`, `xl/sharedStrings.xml`, and worksheet parts.
- Existing custom parts (VBA macros `xl/vbaProject.bin`, drawings, charts, custom XML) are retained unchanged.

---

## 5. Verification Plan
- Unit test suite: `tests/modules/spreadsheet/test_xlsx_writer.py`
  1. Simple workbook generation with strings, numbers, booleans, and formulas.
  2. Multi-sheet workbook with custom sheet names and active tab selection.
  3. Formatting: fonts (bold, italic, size, colors), fills, borders, alignments, and number formats.
  4. Merged cell regions serialization and bounds checking.
  5. Custom column widths and row heights serialization.
  6. Round-trip test: `read_xlsx` -> `write_xlsx` -> `read_xlsx` verifying 100% data and structure fidelity.
  7. Part-level carry test with `source_opc`.
  8. Streaming and file-saving I/O modes.

# Implementation Plan: Pure Python XLSX Writer (xlsx_writer.py)

## Objective
Implement `src/atboffice/modules/spreadsheet/io/xlsx_writer.py` with full OOXML ECMA-376 serialization support, multi-sheet workbook generation, styles, formulas, merges, and part-level carry via `PackageWriter`.

---

## Tasks

### Task 1: TDD Test Suite Creation
- **File**: `tests/modules/spreadsheet/test_xlsx_writer.py`
- **Actions**:
  1. Test minimal single-sheet workbook writing and reading back with `read_xlsx`.
  2. Test multi-sheet workbook with custom sheet names and active tab index.
  3. Test various cell types: integers, floats, booleans, error values, formulas with cached values.
  4. Test cell formatting: font family, font size, bold, italic, underline, strike, text colors, background colors, borders, alignments, and number formats.
  5. Test merged cell ranges persistence.
  6. Test custom column widths and row heights.
  7. Test round-trip fidelity with an existing XLSX file / bytes.
  8. Test part-level carry with `source_opc`.
  9. Test file writing to disk path and stream.

### Task 2: Core Serialization Components in `xlsx_writer.py`
- **File**: `src/atboffice/modules/spreadsheet/io/xlsx_writer.py`
- **Actions**:
  1. XML string escaping, unicode surrogate/control char handling (`_x000D_`), and whitespace preservation (`xml:space="preserve"`).
  2. `SharedStringsManager`: collects unique strings across sheets, deduplicates, and generates `xl/sharedStrings.xml`.
  3. `StyleManager`: extracts and deduplicates fonts, fills (including patternType none & gray125), borders, and number formats (standard and custom >= 164), building `xl/styles.xml`.

### Task 3: Worksheet Serialization
- **File**: `src/atboffice/modules/spreadsheet/io/xlsx_writer.py`
- **Actions**:
  1. Implement `_serialize_worksheet(sheet: SheetDataModel, style_manager: StyleManager, sst_manager: SharedStringsManager, is_active: bool) -> bytes`.
  2. Calculate bounding dimension (`A1:D10` or `A1`).
  3. Emit `<sheetViews><sheetView tabSelected="1" workbookViewId="0"/></sheetViews>`.
  4. Emit `<cols>` for custom column widths.
  5. Emit `<sheetData>` containing `<row>` and `<c>` elements with correct types (`s`, `b`, `e`, etc.), formula (`<f>`), and cached values (`<v>`).
  6. Emit `<mergeCells>` for merged cell areas.

### Task 4: Workbook Assembly & Packaging
- **File**: `src/atboffice/modules/spreadsheet/io/xlsx_writer.py`
- **Actions**:
  1. Implement `_serialize_workbook(workbook: WorkbookModel, sheet_rids: list[str]) -> bytes`.
  2. Implement package assembly leveraging `PackageWriter` and `SourcePackage`.
  3. Implement `write_xlsx(workbook: WorkbookModel, output_path: str | Path | BinaryIO | None = None, source_opc: SourcePackage | bytes | str | Path | None = None) -> bytes`.
  4. Handle atomic writing to disk or streaming.

### Task 5: Export Integration
- **File**: `src/atboffice/modules/spreadsheet/io/__init__.py`
- **Actions**:
  1. Export `write_xlsx` in `__all__`.

### Task 6: Comprehensive Verification
- **Commands**:
  1. `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/test_xlsx_writer.py -v`
  2. `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/test_xlsx_reader.py -v`
  3. `PYTHONPATH=src conda run -n ATBOffice pytest tests/ -v`

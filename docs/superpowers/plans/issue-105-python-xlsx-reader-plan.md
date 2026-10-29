# Implementation Plan: Pure Python XLSX Reader (Issue #105)

## Objective
Implement `src/atboffice/modules/spreadsheet/io/xlsx_reader.py` with full OOXML spreadsheet parsing capabilities and add comprehensive test suite `tests/modules/spreadsheet/test_xlsx_reader.py`.

## Tasks

### Task 1: Create Test Suite (TDD - Test First)
- **File**: `tests/modules/spreadsheet/test_xlsx_reader.py`
- **Description**:
  - Build helper function to create minimal valid `.xlsx` ZIP in memory.
  - Test 1: Minimal XLSX parsing (single sheet, numbers, text).
  - Test 2: Shared string table (SST) parsing with plain text and rich text runs.
  - Test 3: Data types: boolean, numbers (int, float), date, error, inline strings.
  - Test 4: Formulas and precalculated cached values.
  - Test 5: Cell styles: bold, italic, font family, font size, fg/bg color, number format, border, alignment.
  - Test 6: Multi-sheet workbook reading with sheet names, sheet ordering, active sheet tab.
  - Test 7: Merged cells restoration (`sheet.merges`).
  - Test 8: Custom geometry: row heights, column widths, hidden rows and columns.
  - Test 9: Robustness against malformed or non-zip inputs (raises ValueError).
- **Verification**: Run `pytest tests/modules/spreadsheet/test_xlsx_reader.py` and confirm `ImportError` or failure.

### Task 2: Implement XLSX Reader Module
- **File**: `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`
- **Description**:
  - Implement `_clean_tag(tag: str) -> str` to strip namespaces.
  - Implement `_resolve_rel_path(base_dir: str, target: str) -> str`.
  - Implement `_parse_rels(zip_file: zipfile.ZipFile, rels_path: str) -> dict[str, tuple[str, str]]`.
  - Implement `_parse_shared_strings(xml_bytes: bytes) -> list[str]`.
  - Implement `_parse_styles(xml_bytes: bytes) -> list[FormatDelta]`.
  - Implement `_parse_worksheet(xml_bytes: bytes, sheet: SheetDataModel, sst: list[str], style_deltas: list[FormatDelta])`.
  - Implement `read_xlsx(source: str | Path | bytes | BinaryIO, workbook: WorkbookModel | None = None) -> WorkbookModel`.
- **Verification**: Run `pytest tests/modules/spreadsheet/test_xlsx_reader.py` and confirm all tests pass.

### Task 3: Export in io package `__init__.py`
- **File**: `src/atboffice/modules/spreadsheet/io/__init__.py`
- **Description**:
  - Re-export `read_xlsx` from `xlsx_reader.py`.
- **Verification**: Check imports from package level.

### Task 4: Full Repository Test Suite & Linter Check
- **Commands**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/test_xlsx_reader.py -v`
  - `PYTHONPATH=src conda run -n ATBOffice ruff check .`
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/`
- **Verification**: Ensure 100% pass and clean linter.

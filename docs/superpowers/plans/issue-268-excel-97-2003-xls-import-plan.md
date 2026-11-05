# Implementation Plan: Excel 97-2003 (.xls) Binary Read-Only Import and Graceful Fallback

- **Issue**: #268 (`[compat-2003] feat(ledger-io): 基于 Python 生态实现 Excel 97-2003 (.xls) 二进制只读导入与优雅回退 (Step 3 of 3)`)
- **Parent Epic**: #265 (Format 97-2003 Compatibility)
- **Specification**: `docs/superpowers/specs/issue-268-excel-97-2003-xls-import-spec.md`
- **Status**: Approved (>=90% confidence autonomous decision)

---

## Task Breakdown & Execution Steps

### Task 1: Declare xlrd Dependency in `pyproject.toml`
- **File**: `pyproject.toml`
- **Action**: Add `"xlrd>=2.0.1"` to the `dependencies` list.
- **Verification**: Run `python -m pip check` or verify parse.

### Task 2: Implement `.xls` Binary Reader Module (`src/atboffice/modules/spreadsheet/io/xls_reader.py`)
- **File**: `src/atboffice/modules/spreadsheet/io/xls_reader.py`, `src/atboffice/modules/spreadsheet/io/__init__.py`
- **Action**:
  - Implement `is_xls_supported() -> bool` with defensive `try...except ImportError`.
  - Implement `read_xls(source, workbook=None) -> WorkbookModel`:
    - Handles paths, bytes, and binary file-like objects.
    - Defensive workbook opening: attempt `formatting_info=True`, fall back to `formatting_info=False` on `NotImplementedError` or other BIFF version limitations.
    - Map sheets to `SheetDataModel` with original sheet names.
    - Map cell types:
      - `XL_CELL_NUMBER`: integer or float.
      - `XL_CELL_TEXT`: unicode string.
      - `XL_CELL_DATE`: compute datetime using `xlrd.xldate_as_datetime(val, datemode)`; store ISO formatted date/datetime string with corresponding format code.
      - `XL_CELL_BOOLEAN`: boolean True/False.
      - `XL_CELL_ERROR`: standard Excel error text (`#DIV/0!`, `#N/A`, etc.).
      - `XL_CELL_EMPTY` / `XL_CELL_BLANK`: empty cell.
    - Map merged cell ranges from half-open `[rlo, rhi)`, `[clo, chi)` to inclusive `(rlo, clo, rhi - 1, chi - 1)` in `sheet_model.merges`.
    - Map column widths from 1/256th character units to pixels.
    - Map row heights from twips to pixels.
    - Map styles (font bold, italic, underline, family, size, colors, alignments, number format strings).
  - Export `read_xls` and `is_xls_supported` in `src/atboffice/modules/spreadsheet/io/__init__.py`.
- **Verification**: Unit tests in Task 3.

### Task 3: Unit Tests for `.xls` Reader (`tests/test_xls.py`)
- **File**: `tests/test_xls.py`
- **Action**:
  - Test reading real corpus files (`tests/docs/excel/xls/poi__tile-range-test.xls`, `tests/docs/excel/xls/libreoffice__AutoFilter.xls`, `tests/docs/excel/xls/libreoffice__PPMT.xls`).
  - Verify sheet names, dimensions, cell types, values, merged cells, and geometries.
  - Verify graceful handling when input is invalid or corrupt.
  - Verify behavior when `is_xls_supported()` is monkeypatched to `False`.
- **Verification**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_xls.py -v`.

### Task 4: Integrate `.xls` Reader into `LedgerWindow` and Update Guidance Flow
- **Files**:
  - `src/atboffice/vfs/crypto.py`: update `inspect_file_format` to support `allow_excel97: bool = False`. If `allow_excel97=True`, genuine non-disguised `.xls` documents are permitted through without rejection.
  - `src/atboffice/ui/shell/ledger_window.py`:
    - In `do_open`:
      - For `.xls` / `.xlt` files:
        - Check if file is disguised (e.g. Word/PowerPoint). If so, reject with disguised warning.
        - If `is_xls_supported()` is True:
          - Call `read_xls(path)`.
          - On success, set workbook and show gentle status bar notice:
            `self.status_bar.showMessage(safe_tr("已成功导入 Excel 97–2003 (.xls) 工作簿。旧版格式不支持所有现代功能，建议另存为 .xlsx 格式。"), 10000)`
          - On failure/unsupported, fall back gracefully to `self.check_legacy_or_disguised_file(path, "ledger")`.
        - If `is_xls_supported()` is False:
          - Call `self.check_legacy_or_disguised_file(path, "ledger")`.
  - `tests/gui/test_phase7_open_contract.py`:
    - Update `test_ledger_legacy_xls_rejected_with_guidance` to test rejection when `is_xls_supported()` is False (verifying the fallback contract).
    - Add `test_ledger_legacy_xls_opened_with_reader` to test successful opening, status bar notice, and transactional state when `is_xls_supported()` is True.
- **Verification**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_phase7_open_contract.py -v`.

### Task 5: Full Test Suite Verification & Quality Gate
- **Action**: Run all tests across the repository:
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/`
  Ensure all tests pass with zero regressions.
- **State Transition**: Set state to `reviewing` and trigger `atb-github-code-reviewer`.

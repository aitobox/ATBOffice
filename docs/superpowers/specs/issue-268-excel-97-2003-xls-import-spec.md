# Specification: Excel 97-2003 (.xls) Binary Read-Only Import and Graceful Fallback

- **Issue**: #268 (`[compat-2003] feat(ledger-io): 基于 Python 生态实现 Excel 97-2003 (.xls) 二进制只读导入与优雅回退 (Step 3 of 3)`)
- **Parent Epic**: #265 (Format 97-2003 Compatibility)
- **Status**: Draft / Approved (>=90% confidence autonomous decision)

---

## 1. Background & Objectives

In `.vibeoffice`, the browser-based environment prevented direct binary `.xls` parsing without heavy dependencies. `.vibeoffice` provided an informative conversion guidance dialog while architecting an extension hook `L.xls.read`:
```javascript
if (e.code === 'xls') {
  ui.busy(false);
  if (L.xls && L.xls.read) {
    w = await L.xls.read(bytes);
    type = 'xls';
  } else {
    throw Object.assign(new Error(L.t(
      "'{0}' is a binary Excel 97–2003 workbook (.xls). Ledger opens .xlsx, .xlsm, .csv and XML Spreadsheet 2003 files. Open it in Excel or LibreOffice and save it as .xlsx first.",
      name
    )), { code: 'xls' });
  }
}
```

In the ATBOffice Python desktop environment, we leverage Python's mature, secure, pure-Python open-source ecosystem (`xlrd >= 2.0.1`) to provide native, read-only import of Excel 97–2003 (`.xls`) workbooks into Ledger.

### Core Objectives
1. **Native .xls Reader (`xls_reader.py`)**: Implement a robust, read-only `.xls` parser in `src/atboffice/modules/spreadsheet/io/xls_reader.py` that parses BIFF8/BIFF7/BIFF5 workbooks into ATBOffice's `WorkbookModel` and `SheetDataModel`.
2. **Multi-Sheet & Data Type Fidelity**: Accurately extract all worksheets, numbers, strings, booleans, dates (using Excel workbook datemode: 1900 vs 1904 date system), error values (`#DIV/0!`, `#N/A`, etc.), merged cell ranges, column widths, and row heights.
3. **Graceful Fallback & Zero Crash**:
   - If `xlrd` is missing or uninstalled, the application does not crash. It seamlessly falls back to Step 1's standard `.vibeoffice` conversion guidance dialog.
   - If an `.xls` file is password-protected or encrypted, it safely triggers standard guidance or password notification rather than an unhandled traceback.
   - If an `.xls` file is corrupted or unparseable, it rolls back transactionally and presents informative guidance.
4. **Gentle User Experience Notice**: Once an `.xls` file is loaded, inform the user with a gentle notice (via status bar) recommending saving as modern `.xlsx` format.
5. **Dependency Declaration**: Include `xlrd>=2.0.1` in `pyproject.toml` dependencies while wrapping all imports defensively.
6. **Comprehensive Automated Tests**: Add `tests/test_xls.py` verifying real corpus files, multi-sheet structures, cell data types, merged cells, and fallback mechanics.

---

## 2. Architecture & Design

### 2.1 Reader Module: `src/atboffice/modules/spreadsheet/io/xls_reader.py`

#### 2.1.1 Availability Check
```python
def is_xls_supported() -> bool:
    """Return True if xlrd is installed and functional in the current environment."""
```

#### 2.1.2 Main Reader Function
```python
def read_xls(
    source: str | Path | bytes | BinaryIO,
    workbook: WorkbookModel | None = None,
) -> WorkbookModel:
    """Read a binary Excel 97-2003 (.xls) workbook into a WorkbookModel."""
```

#### 2.1.3 Extraction Details
- **Workbook & Sheets**:
  - Open via `xlrd.open_workbook(filename=..., file_contents=..., formatting_info=True)`.
  - If `formatting_info=True` raises `NotImplementedError` (e.g. BIFF5 files), retry with `formatting_info=False`.
  - Iterate `book.sheets()`; for each sheet, create `SheetDataModel(name=sheet.name)`.
- **Cell Data Mapping**:
  - `XL_CELL_TEXT`: `str(cell.value)`
  - `XL_CELL_NUMBER`: integer if `val.is_integer()` else float
  - `XL_CELL_BOOLEAN`: `bool(cell.value)`
  - `XL_CELL_DATE`: compute `datetime` using `xlrd.xldate_as_datetime(cell.value, book.datemode)`. Store formatted date/datetime string or serial number with date format code.
  - `XL_CELL_ERROR`: convert error code to standard Excel error string using `xlrd.error_text_from_code` (e.g. `#DIV/0!`, `#N/A`, `#VALUE!`, `#REF!`, `#NAME?`, `#NUM!`, `#NULL!`).
  - `XL_CELL_EMPTY` / `XL_CELL_BLANK`: ignored or empty cell data.
- **Merged Cells**:
  - `sheet.merged_cells`: List of `(rlo, rhi, clo, chi)`.
  - In `xlrd`, bounds are half-open `[rlo, rhi)`, `[clo, chi)`.
  - Convert to ATBOffice inclusive bounds: `(rlo, clo, rhi - 1, chi - 1)`.
  - Add to `sheet_model.merges`.
- **Dimensions & Geometry**:
  - Column widths: `sheet.colinfo_map` (units of 1/256 char width converted to pixels via standard DPI ratio: `int(round(width / 256.0 * 8.0))`).
  - Row heights: `sheet.rowinfo_map` (units of twips, 1/20 pt converted to pixels: `int(round(twips / 20.0 / 0.75))`).
- **Formatting & Styles (when formatting_info is enabled)**:
  - Extract font properties: bold, italic, underline, font family, font size, font color.
  - Extract alignment: horizontal alignment, vertical alignment, text wrap.
  - Extract number format code: retrieve string format from `book.format_map[xf.format_key].format_str`.

---

### 2.2 Integration in `LedgerWindow` (`src/atboffice/ui/shell/ledger_window.py`)

#### 2.2.1 File Inspection & Format Gate
In `ledger_window.py`:
1. Check if the file is a disguised Word or PowerPoint document (e.g. `ole_fmt in {"word97", "powerpoint97"}`). If disguised, reject with clear guidance dialog as before.
2. If `ext in {".xls", ".xlt"}`:
   - Check if the file is actually an XML Spreadsheet 2003 or HTML table starting with `<`. If so, route to `read_xmlss_workbook`.
   - If it is binary:
     - Check `is_xls_supported()`. If `False`, call `self.check_legacy_or_disguised_file(path, "ledger")` to present the original .vibeoffice conversion guidance dialog.
     - If `True`, invoke `read_xls(path)`.
     - Upon successful load:
       - Update UI transactionally.
       - Present gentle notice:
         `self.status_bar.showMessage(safe_tr("已成功导入 Excel 97–2003 (.xls) 工作簿。旧版格式不支持所有现代功能，建议另存为 .xlsx 格式。"), 10000)`
     - If `read_xls` fails (e.g. encrypted or corrupted):
       - If encrypted: show standard password/encryption guidance.
       - If corrupt/unsupported: fall back gracefully to the standard conversion guidance.

---

### 2.3 Dependency Configuration (`pyproject.toml`)

Add `xlrd>=2.0.1` to `dependencies` in `pyproject.toml`:
```toml
dependencies = [
    "PySide6>=6.6",
    "cryptography>=42.0",
    "xlrd>=2.0.1",
]
```
This ensures all standard installations and GitHub Actions CI automatically provide `.xls` reading capabilities.

---

### 2.4 Testing Strategy (`tests/test_xls.py`)

1. **Unit Tests for `read_xls`**:
   - Parse real `.xls` files from `tests/docs/excel/xls/`:
     - `poi__tile-range-test.xls` (multi-sheet, floating point numbers)
     - `libreoffice__AutoFilter.xls` (text, numbers, structure)
     - `libreoffice__PPMT.xls` (financial formulas & evaluated values)
   - Test data type conversions (numbers, strings, dates, booleans, error codes).
   - Test merged cell range conversion from half-open to inclusive bounds.
   - Test fallback to `formatting_info=False` when unsupported by file BIFF version.
2. **Fallback & Error Handling Tests**:
   - Test when `is_xls_supported()` is monkeypatched to `False`: system raises clean warning or fallback.
   - Test opening corrupt/truncated bytes.
3. **GUI / Window Integration Tests**:
   - Test `LedgerWindow.open_file` with an `.xls` file: loads workbook into `spreadsheet_view`, updates title, displays status bar gentle warning.
   - Test `test_phase7_open_contract.py` compatibility: ensure existing contracts pass and both fallback and success paths are verified.

---

## 3. Implementation Plan Summary

- **Task 1**: Update `pyproject.toml` to include `xlrd>=2.0.1`.
- **Task 2**: Implement `src/atboffice/modules/spreadsheet/io/xls_reader.py` with full cell data type, multi-sheet, merged cells, and style mapping.
- **Task 3**: Update `src/atboffice/vfs/crypto.py` and `src/atboffice/ui/shell/ledger_window.py` to support opening `.xls` when available with graceful fallback and gentle user notification.
- **Task 4**: Write comprehensive unit and integration tests in `tests/test_xls.py` and update open contract tests.
- **Task 5**: Verify entire test suite with `PYTHONPATH=src conda run -n ATBOffice pytest tests/`.

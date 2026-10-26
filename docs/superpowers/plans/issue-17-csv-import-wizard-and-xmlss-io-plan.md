# [Ledger] CSV 智能编码识别导入向导与 XML Spreadsheet 2003 读写 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement universal encoding-aware CSV/text I/O, a 3-step Text Import Wizard dialog, and complete XML Spreadsheet 2003 reading and writing for ATBOffice Ledger.

**Architecture:** A modular I/O subsystem in `src/atboffice/modules/spreadsheet/io/` providing `csv_io.py` (BOM sniffing, UTF-8/GB18030/CP1252/UTF-16 decoding, RFC-4180 parsing, and formatting-aware CSV export) and `xmlss_io.py` (R1C1 ⇄ A1 formula conversion, XMLSS reader/writer), paired with `src/atboffice/modules/spreadsheet/dialogs/text_import_wizard.py` (3-step classic wizard with interactive live previews and i18n).

**Tech Stack:** Python 3.12+, PySide6 (Qt6), `pytest`, `pytest-qt`, `xml.etree.ElementTree`.

**Spec:** `docs/superpowers/specs/issue-17-csv-import-wizard-and-xmlss-io-spec.md`

## Global Constraints
- Target branch: `agent/issue-17-csv-import-wizard-and-xmlss-io`
- Python version: 3.12+ with full type annotations.
- i18n is Mandatory: 100% of dialog UI strings wrapped in `safe_tr()` / `tr()`, with `retranslate_ui()` implemented.
- Robustness: handle missing files, corrupted encodings, unbalanced quotes, sparse rows/cols in XMLSS without throwing uncaught exceptions.
- Verification command: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/spreadsheet/test_csv_and_xmlss.py -v`

---

### Task 1: Encoding Detection, Delimiter Sniffing, and Fixed-Width Breaks

**Files:**
- Create: `src/atboffice/modules/spreadsheet/io/__init__.py`
- Create: `src/atboffice/modules/spreadsheet/io/csv_io.py`
- Create: `tests/unit/spreadsheet/test_csv_and_xmlss.py`

**Interfaces:**
- Produces:
  - `decode_bytes(b: bytes, encoding: str | None = None) -> tuple[str, str]`
  - `sniff_delimiter(text: str) -> str`
  - `guess_fixed_breaks(text: str) -> list[int]`

- [ ] **Step 1: Write the failing tests for Task 1**
  Write tests in `tests/unit/spreadsheet/test_csv_and_xmlss.py` covering BOM detection (UTF-8, UTF-16LE, UTF-16BE), UTF-16 without BOM heuristic, Chinese GB18030 detection, Windows-1252 fallback, `sniff_delimiter` for comma, tab, semicolon, space, and `guess_fixed_breaks`.

- [ ] **Step 2: Run test to verify it fails**
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/spreadsheet/test_csv_and_xmlss.py -k "test_decode or test_sniff or test_breaks" -v`
  Expected: FAIL with `ModuleNotFoundError` or missing symbols.

- [ ] **Step 3: Implement minimal code for Task 1**
  Create `src/atboffice/modules/spreadsheet/io/__init__.py` and implement `decode_bytes`, `sniff_delimiter`, and `guess_fixed_breaks` in `src/atboffice/modules/spreadsheet/io/csv_io.py`.

- [ ] **Step 4: Run test to verify it passes**
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/spreadsheet/test_csv_and_xmlss.py -k "test_decode or test_sniff or test_breaks" -v`
  Expected: PASS.

- [ ] **Step 5: Commit**
  `git add src/atboffice/modules/spreadsheet/io/ tests/unit/spreadsheet/test_csv_and_xmlss.py && git commit -m "feat(io): implement encoding detection and delimiter sniffing"`

---

### Task 2: Delimited & Fixed-Width Parsing, Value Conversion, Sheet Population, and CSV Export

**Files:**
- Modify: `src/atboffice/modules/spreadsheet/io/csv_io.py`
- Modify: `tests/unit/spreadsheet/test_csv_and_xmlss.py`

**Interfaces:**
- Consumes: `SheetDataModel` from `atboffice.modules.spreadsheet.models.sheet_model`
- Produces:
  - `parse_delimited(text: str, delims: str = ",", quote: str = '"', merge: bool = False, max_rows: int | None = None) -> list[list[str]]`
  - `parse_fixed_width(text: str, breaks: list[int], max_rows: int | None = None) -> list[list[str]]`
  - `convert_cell_value(val_str: str, col_type: str = "General") -> Any`
  - `populate_sheet(model: SheetDataModel, rows: list[list[str]], start_row: int = 0, start_col: int = 0, col_formats: list[str] | None = None)`
  - `export_csv(model: SheetDataModel, delimiter: str = ",", quote: str = '"', encoding: str = "utf-8") -> str`

- [ ] **Step 1: Write failing tests for parsing, conversion, and export**
  Add unit tests testing:
  - RFC 4180 parsing with quotes, internal newlines, escaped `""`, trailing commas.
  - `merge=True` behavior (consecutive spaces/tabs treated as single delimiter).
  - Fixed-width column slicing.
  - General value conversion (empty -> None, "TRUE" -> True, int, float, scientific, percent, currency, date, text).
  - Populating `SheetDataModel` from rows.
  - `export_csv` with formatted numbers and proper quoting.

- [ ] **Step 2: Run tests to verify failure**
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/spreadsheet/test_csv_and_xmlss.py -k "test_parse or test_convert or test_export" -v`
  Expected: FAIL with missing functions.

- [ ] **Step 3: Implement minimal code for Task 2**
  Implement `parse_delimited`, `parse_fixed_width`, `convert_cell_value`, `populate_sheet`, and `export_csv` in `src/atboffice/modules/spreadsheet/io/csv_io.py`.

- [ ] **Step 4: Run tests to verify pass**
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/spreadsheet/test_csv_and_xmlss.py -k "test_parse or test_convert or test_export" -v`
  Expected: PASS.

- [ ] **Step 5: Commit**
  `git add src/atboffice/modules/spreadsheet/io/csv_io.py tests/unit/spreadsheet/test_csv_and_xmlss.py && git commit -m "feat(io): implement delimited parsing, value conversion, and csv export"`

---

### Task 3: XML Spreadsheet 2003 (SpreadsheetML) Read & Write with R1C1 ⇄ A1 Translation

**Files:**
- Create: `src/atboffice/modules/spreadsheet/io/xmlss_io.py`
- Modify: `tests/unit/spreadsheet/test_csv_and_xmlss.py`

**Interfaces:**
- Produces:
  - `from_r1c1(formula: str, r: int, c: int) -> str`
  - `to_r1c1(formula: str, r: int, c: int) -> str`
  - `read_xmlss(content: str | bytes, model: SheetDataModel | None = None) -> SheetDataModel`
  - `write_xmlss(model: SheetDataModel, sheet_name: str = "Sheet1") -> str`

- [ ] **Step 1: Write failing tests for XMLSS and R1C1**
  Add unit tests testing:
  - `from_r1c1` with relative `R[-1]C[2]`, absolute `R1C1`, whole row `R1:R3`, whole col `C1:C2`, quoted text with `R`/`C`.
  - `to_r1c1` with relative `A1` from `(2, 2)`, absolute `$A$1`, ranges `A1:B5`.
  - XMLSS reading with styles (font bold, italic, colors), formulas, merged cells (`MergeAcross`, `MergeDown`), sparse indexes (`ss:Index`).
  - XMLSS writing and roundtrip verification (write model -> read back -> assert data, formula, and merges match).

- [ ] **Step 2: Run tests to verify failure**
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/spreadsheet/test_csv_and_xmlss.py -k "test_r1c1 or test_xmlss" -v`
  Expected: FAIL with missing functions.

- [ ] **Step 3: Implement minimal code for Task 3**
  Implement `from_r1c1`, `to_r1c1`, `read_xmlss`, and `write_xmlss` in `src/atboffice/modules/spreadsheet/io/xmlss_io.py`.

- [ ] **Step 4: Run tests to verify pass**
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/spreadsheet/test_csv_and_xmlss.py -k "test_r1c1 or test_xmlss" -v`
  Expected: PASS.

- [ ] **Step 5: Commit**
  `git add src/atboffice/modules/spreadsheet/io/xmlss_io.py tests/unit/spreadsheet/test_csv_and_xmlss.py && git commit -m "feat(io): implement XMLSS 2003 reader, writer, and R1C1 translation"`

---

### Task 4: 3-Step Text Import Wizard Dialog

**Files:**
- Create: `src/atboffice/modules/spreadsheet/dialogs/text_import_wizard.py`
- Modify: `tests/unit/spreadsheet/test_csv_and_xmlss.py`

**Interfaces:**
- Produces:
  - `TextImportWizard(QDialog)`
    - `__init__(bytes_data: bytes, file_name: str = "", parent: QWidget | None = None)`
    - `get_result_rows() -> list[list[Any]]`
    - `populate_model(model: SheetDataModel, start_row: int = 0, start_col: int = 0)`
    - `retranslate_ui()`

- [ ] **Step 1: Write failing tests for TextImportWizard**
  Add unit tests in `tests/unit/spreadsheet/test_csv_and_xmlss.py` testing:
  - Dialog instantiation with sample CSV and fixed-width bytes.
  - Page navigation: initial page is 0 (Back disabled, Next enabled), navigate to page 1, navigate to page 2 (Next disabled, Finish enabled).
  - Changing delimiter triggers preview update.
  - Changing column format in step 3 (selecting column and setting format to Text/Date/Skip).
  - Calling `get_result_rows()` and `populate_model()`.
  - `retranslate_ui()` runs cleanly without throwing.

- [ ] **Step 2: Run tests to verify failure**
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/spreadsheet/test_csv_and_xmlss.py -k "test_text_import_wizard" -v`
  Expected: FAIL with `ModuleNotFoundError` or missing class.

- [ ] **Step 3: Implement minimal code for Task 4**
  Implement `TextImportWizard` in `src/atboffice/modules/spreadsheet/dialogs/text_import_wizard.py` with `safe_tr()`, `retranslate_ui()`, step pages, and preview updates.

- [ ] **Step 4: Run tests to verify pass**
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/spreadsheet/test_csv_and_xmlss.py -k "test_text_import_wizard" -v`
  Expected: PASS.

- [ ] **Step 5: Commit**
  `git add src/atboffice/modules/spreadsheet/dialogs/text_import_wizard.py tests/unit/spreadsheet/test_csv_and_xmlss.py && git commit -m "feat(ui): implement classic 3-step Text Import Wizard dialog"`

---

### Task 5: End-to-End Verification and Regression Suite

**Files:**
- Modify: `tests/unit/spreadsheet/test_csv_and_xmlss.py`

- [ ] **Step 1: Run complete `test_csv_and_xmlss.py` suite**
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/spreadsheet/test_csv_and_xmlss.py -v`
  Expected: 100% pass.

- [ ] **Step 2: Run entire project test suite to verify zero regressions**
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/ -v`
  Expected: All tests pass (except any known pre-existing failure documented in AGENTS.md).

- [ ] **Step 3: Final verification and state transition to `reviewing`**
  Run `python3 scripts/github_agent_helper.py set-state --state reviewing` and hand off to `atb-github-code-reviewer`.

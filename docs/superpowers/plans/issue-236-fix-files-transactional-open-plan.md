# Implementation Plan: TASK-702: fix(files): 修复假成功并事务化文件打开 (Issue #236)

## Overview
Implement transactional document opening across ATBOffice's three application windows (`QuireWindow`, `LedgerWindow`, `LecternWindow`), eliminating false-success on unsupported/unhandled file formats, rejecting legacy binary formats (`.doc`, `.xls`, `.ppt`) with informative guidance, integrating Quire readers for RTF, Markdown, and plain text, handling password prompt cancellation gracefully, and guaranteeing 100% state rollback on any parsing or binding error.

---

## Tasks

### Task 1: Create Automated Contract Tests
- **Target File**: `tests/gui/test_phase7_open_contract.py`
- **Actions**:
  1. Add test cases for legacy binary format rejection (`.doc` in Quire, `.xls` in Ledger, `.ppt` in Lectern). Verify `open_file` returns `False`, informative dialog is displayed, and previous `current_file_path`, `is_modified`, and model remain intact.
  2. Add test cases for corrupted/disguised file rejection (e.g. invalid zip `.docx`, non-xml `.xlsx`). Verify `open_file` returns `False` and window state is preserved.
  3. Add test cases for password cancellation: user clicking Cancel on password prompt returns `False` cleanly without critical error dialog, preserving document state.
  4. Add test cases for binding exception: mock view raising exception during model load triggers rollback to original model.
  5. Add test cases for valid samples of all promised extensions:
     - Quire: `.docx`, `.html`, `.rtf`, `.md`, `.txt`
     - Ledger: `.xlsx`, `.xlsm`, `.csv`, `.tsv`, `.xml`
     - Lectern: `.pptx`
- **Verification Command**:
  `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_open_contract.py -ra`
  (Expected output: initial failures on unsupported format handling and missing RTF/MD reader bindings).

### Task 2: Enhance Base Window with Transactional & Crypto Helpers
- **Target File**: `src/atboffice/ui/shell/base_window.py`
- **Actions**:
  1. Add helper method `prompt_password(title: str, prompt_text: str) -> tuple[str | None, bool]` to prompt for file password using `QInputDialog` with `Password` echo mode.
  2. Add helper method `handle_encrypted_package(path: Path) -> bytes | None` that uses `atboffice.vfs.crypto` to detect and decrypt password-protected packages. If user cancels, return `None` (cancelled); if bad password, show warning and return `None`.
  3. Refactor `open_file(file_path)` to distinguish user cancellation (silent abort) from true open failure, ensuring clean abort without false critical dialogs.
- **Verification Command**:
  `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_file_safety_regression.py -ra`

### Task 3: Transactional Open and Reader Integration in Quire
- **Target File**: `src/atboffice/ui/shell/quire_window.py`
- **Actions**:
  1. Update `get_file_filter()` to explicitly list all supported formats (`.docx`, `.docm`, `.dotx`, `.html`, `.htm`, `.rtf`, `.md`, `.markdown`, `.txt`) and legacy `.doc`.
  2. In `do_open(path)`:
     - Check for legacy binary `.doc` (via extension or OLE magic bytes with WordDocument stream): display informative conversion message and return `False`.
     - Check for encrypted package: decrypt if necessary.
     - Dispatch by format:
       - `.docx`, `.docm`, `.dotx`: `read_docx`
       - `.html`, `.htm`: `read_html`
       - `.rtf`: `RtfReader().read`
       - `.md`, `.markdown`: `MarkdownReader().read`
       - `.txt`: construct `Document` with lines wrapped in `Paragraph` and `TextItem`
     - Reject unknown extensions (`return False`).
     - Save previous document reference, execute `self.writer_view.canvas_view.set_document(candidate_doc)` inside `try...except`, roll back on exception.
- **Verification Command**:
  `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_open_contract.py -k "test_quire" -ra`

### Task 4: Transactional Open and New Workbook Dispatch in Ledger
- **Target Files**:
  - `src/atboffice/ui/shell/ledger_window.py`
  - `src/atboffice/modules/spreadsheet/view.py`
- **Actions**:
  1. In `src/atboffice/modules/spreadsheet/view.py`:
     - In `workbook.setter`, safely disconnect signals from previous workbook if present before connecting new workbook signals.
  2. In `src/atboffice/ui/shell/ledger_window.py`:
     - Update `get_file_filter()` to include `.xlsx`, `.xlsm`, `.csv`, `.tsv`, `.xml`, `.xmlss`, and `.xls`.
     - In `do_open(path)`:
       - Check for legacy binary `.xls` (via extension or OLE magic bytes): display informative conversion message and return `False`.
       - Check for encrypted package: decrypt if necessary.
       - Dispatch by format:
         - `.xlsx`, `.xlsm`: `read_xlsx`
         - `.csv`, `.tsv`: create new `WorkbookModel()`, parse via `read_csv` into first sheet.
         - `.xml`, `.xmlss`: create new `WorkbookModel()`, parse via `read_xmlss`.
       - Reject unknown extensions (`return False`).
       - Save previous workbook reference, assign `self.spreadsheet_view.workbook = candidate_wb` inside `try...except`, roll back on exception.
- **Verification Command**:
  `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_open_contract.py -k "test_ledger" -ra`

### Task 5: Transactional Open in Lectern
- **Target File**: `src/atboffice/ui/shell/lectern_window.py`
- **Actions**:
  1. Update `get_file_filter()` to list supported `.pptx`, `.ppsx`, `.potx` and legacy `.ppt`.
  2. In `do_open(path)`:
     - Check for legacy binary `.ppt` (via extension or OLE magic bytes): display informative conversion message and return `False`.
     - Check for encrypted package: decrypt if necessary.
     - Dispatch by format:
       - `.pptx`, `.ppsx`, `.potx`: `read_pptx`
     - Reject unknown extensions (`return False`).
     - Save previous presentation reference, assign `self.presentation_view.load_presentation(candidate_pres)` inside `try...except`, roll back on exception.
- **Verification Command**:
  `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_open_contract.py -k "test_lectern" -ra`

### Task 6: Full Verification Suite
- **Actions**:
  1. Run targeted contract tests:
     `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_open_contract.py tests/gui/test_file_safety_regression.py -ra`
  2. Run all existing GUI and unit test files to guarantee zero regressions:
     `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`
- **Acceptance Criteria**: Exit code 0, all tests pass.

### Task 7: Update Phase 7 Matrix & Transition to Review
- **Target Files**:
  - `docs/clone/phase7_features.csv` (or `features.csv`)
  - `.github-agent-state.yml`
- **Actions**:
  1. Record evidence in `phase7_features.csv` for TASK-702.
  2. Transition state to `reviewing` via `python3 scripts/github_agent_helper.py set-state --state reviewing`.

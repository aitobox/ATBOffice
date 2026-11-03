# Specification: TASK-702: fix(files): 修复假成功并事务化文件打开 (Issue #236)

## 1. Overview & Problem Statement

### 1.1 Context
In ATBOffice, opening documents across the three primary application windows (`QuireWindow`, `LedgerWindow`, `LecternWindow`) suffered from critical false-success and state-corruption defects:
1. **False Success ("假成功") on Unhandled Formats**:
   In `quire_window.py`, `ledger_window.py`, and `lectern_window.py`, the `do_open(path)` implementations fell through to `return True` when encountering unsupported or unhandled file extensions (such as legacy binary `.doc`, `.xls`, `.ppt`, or unrecognized extensions). Because `do_open` returned `True`, `BaseOfficeWindow.open_file` assumed the document was loaded successfully. It updated `self.current_file_path` to the target path, cleared `is_modified` to `False`, updated the window title, and registered the file in the recent files list—leaving the existing canvas/grid/slide view completely untouched. Users were misled into believing the file had opened properly.
2. **Non-Transactional In-Place Mutation**:
   In `ledger_window.py`, opening `.csv`/`.tsv` and `.xml`/`.xmlss` mutated the existing in-memory `spreadsheet_view.model` or `spreadsheet_view.workbook` in-place. If parsing or validation failed midway, the active document was left in a corrupted, half-mutated state.
3. **Missing Reader Integrations**:
   Quire possessed implemented reader modules for RTF (`rtf_io.py`) and Markdown (`markdown_io.py`), as well as plain text, but `quire_window.py:do_open` did not wire them into the document loading workflow.
4. **Lack of Clear Format & Error Categorization**:
   Unknown formats, extension disguises (e.g. non-ZIP files named `.docx` or `.xlsx`), binary OLE compound files (`.doc`, `.xls`, `.ppt`), and password cancellations were not differentiated. Cancelling a password dialog resulted in ugly crashes or generic error dialogs rather than a clean abort.
5. **No Binding Rollback**:
   If an exception occurred during UI binding (e.g. setting the model into the view), previous document state was not preserved.

### 1.2 Target Deliverables
- `src/atboffice/ui/shell/base_window.py`: Transactional open wrapper, password prompt & cancellation handling, format detection helpers.
- `src/atboffice/ui/shell/quire_window.py`: Full format dispatch (`.docx`, `.docm`, `.dotx`, `.html`, `.htm`, `.rtf`, `.md`, `.markdown`, `.txt`), legacy `.doc` rejection with informative message, transactional parse & bind.
- `src/atboffice/ui/shell/ledger_window.py`: Full format dispatch (`.xlsx`, `.xlsm`, `.csv`, `.tsv`, `.xml`, `.xmlss`), legacy `.xls` rejection with informative message, transactional new workbook creation & bind.
- `src/atboffice/ui/shell/lectern_window.py`: Full format dispatch (`.pptx`, `.ppsx`, `.potx`), legacy `.ppt` rejection with informative message, transactional parse & bind.
- `src/atboffice/modules/spreadsheet/view.py`: Clean signal disconnection and reconnection when binding new workbook model, ensuring no dangling signals.
- `tests/gui/test_phase7_open_contract.py`: Comprehensive test suite verifying transactional open, legacy format rejection, password cancellation, corrupted file rejection, rollback on binding failure, and successful loading for all promised extensions.

---

## 2. Architecture & Design Details

### 2.1 File Format Dispatch & Magic Bytes Detection
To prevent disguised file attacks or confusing errors, file inspection combines extension checks with binary magic signatures:
- **ZIP Header**: `b"PK\x03\x04"` — expected for modern OOXML (`.docx`, `.xlsx`, `.pptx`).
- **CFB / OLE Header**: `b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"` — indicates either password-encrypted OOXML packages (checked via `is_encrypted_package`) or legacy binary 97–2003 Office formats (`.doc`, `.xls`, `.ppt`).
- **RTF Header**: `b"{\\rtf"` — Rich Text Format.
- **XML Header**: `b"<?xml"` or `<` with optional UTF-8 BOM.
- **Text / CSV / Markdown**: UTF-8 / ASCII text stream.

### 2.2 Error and Rejection Categorization
1. **Password-Protected Documents & Cancellation**:
   - Detect encrypted OOXML container via `atboffice.vfs.crypto.is_encrypted_package(path)`.
   - Prompt user for password using `QInputDialog.getText(..., EchoMode.Password)`.
   - If user cancels the prompt (`ok is False`):
     - Silently abort open.
     - Retain current file path, dirty flag, undo history, and document content.
     - Return `False` (no error dialog shown).
   - If password is provided:
     - Decrypt inner package bytes via `decrypt_package(raw, passcode=...)`.
     - If password is incorrect (`ValueError("Invalid password")`):
       - Display localized warning dialog: `safe_tr("密码不正确，无法打开文档。")`.
       - Retain all previous state and return `False`.
2. **Legacy Binary Formats (Word 97–2003 `.doc`, Excel 97–2003 `.xls`, PowerPoint 97–2003 `.ppt`)**:
   - Recognized by extension or OLE stream signatures.
   - Display localized informative warning dialog:
     - For `.doc`: `safe_tr("“{name}”是旧版二进制 Word 97–2003 文档 (.doc)。Quire 原生支持 .docx、.html、.rtf、.md 和纯文本文件。请在 Word 或 LibreOffice 中将其另存为 .docx 格式后再打开。")`
     - For `.xls`: `safe_tr("“{name}”是旧版二进制 Excel 97–2003 工作簿 (.xls)。Ledger 原生支持 .xlsx、.xlsm、.csv、.tsv 和 XML 电子表格。请在 Excel 或 LibreOffice 中将其另存为 .xlsx 格式后再打开。")`
     - For `.ppt`: `safe_tr("“{name}”是旧版二进制 PowerPoint 97–2003 演示文稿 (.ppt)。Lectern 原生支持 .pptx 演示文稿。请在 PowerPoint 或 LibreOffice 中将其另存为 .pptx 格式后再打开。")`
   - Retain all previous state and return `False`.
3. **Corrupted / Incompatible / Disguised Files**:
   - If a file has a supported extension but invalid format (e.g. non-ZIP `.docx`, corrupted ZIP, invalid XML syntax, truncated file):
   - Display localized critical dialog: `safe_tr("无法打开文件“{path}”：文件已损坏或格式不兼容。\n{details}")`
   - Retain all previous state and return `False`.
4. **Unsupported / Unknown Extensions**:
   - If extension is not recognized by the module:
   - Display localized critical dialog: `safe_tr("不支持的文件格式：{ext}。")`
   - Return `False`.

### 2.3 Transactional Parse & Binding Contract
In each window (`QuireWindow`, `LedgerWindow`, `LecternWindow`):
1. **Parse to Candidate Model**:
   - Do NOT touch existing canvas/model during parsing.
   - Parse into a candidate object:
     - Quire: `candidate_doc = ...`
     - Ledger: `candidate_wb = ...`
     - Lectern: `candidate_pres = ...`
2. **Transactional Binding with Rollback**:
   - Save references to old model / document.
   - In a `try...except` block, bind the candidate model to the view:
     - Quire: `self.writer_view.canvas_view.set_document(candidate_doc)`
     - Ledger: `self.spreadsheet_view.workbook = candidate_wb`
     - Lectern: `self.presentation_view.load_presentation(candidate_pres)`
   - If binding fails (raises exception):
     - Restore old model / document.
     - Display critical dialog.
     - Return `False`.
3. **Commit State**:
   - Only when candidate model is parsed and bound without error:
     - `self.current_file_path = path`
     - `self.set_modified(False)`
     - `self.update_window_title()`
     - `wm.recent_files.add_file(path, app_type)`
     - Return `True`.

### 2.4 Quire Readers Integration
- `.docx`, `.docm`, `.dotx`: `read_docx(path)` (handles decrypted bytes via `io.BytesIO` or `path`).
- `.html`, `.htm`: `read_html(path)`.
- `.rtf`: `RtfReader().read(path.read_bytes())`.
- `.md`, `.markdown`: `MarkdownReader().read(path.read_text(encoding="utf-8"))`.
- `.txt`: Convert text lines into `Document(main=Story(blocks=[Paragraph(runs=[TextItem(text=line)])]))`.

### 2.5 Ledger Readers Integration
- `.xlsx`, `.xlsm`: `read_xlsx(path)` (or from decrypted bytes).
- `.csv`, `.tsv`:
  Create a brand new `WorkbookModel()`, create initial sheet, call `read_csv(path, model=new_sheet, delimiter=delimiter)`.
  Bind `self.spreadsheet_view.workbook = new_wb`.
- `.xml`, `.xmlss`:
  Create a brand new `WorkbookModel()`, call `read_xmlss(path, workbook=new_wb)`.
  Bind `self.spreadsheet_view.workbook = new_wb`.

### 2.6 Lectern Readers Integration
- `.pptx`, `.ppsx`, `.potx`: `read_pptx(path)` (or from decrypted bytes).

---

## 3. Verification & Acceptance Plan
1. **Test Suite `tests/gui/test_phase7_open_contract.py`**:
   - Test legacy binary `.doc`, `.xls`, `.ppt` rejection with informative dialog and zero state mutation.
   - Test corrupted ZIP / invalid file rejection with zero state mutation.
   - Test password cancellation: prompt cancelled returns `False` cleanly without error dialog and with state preserved.
   - Test wrong password: shows warning and preserves state.
   - Test binding failure rollback: mock view setter raising exception verifies old document/workbook is retained and path unchanged.
   - Test successful loading for each supported extension across all three modules:
     - Quire: `.docx`, `.html`, `.rtf`, `.md`, `.txt`
     - Ledger: `.xlsx`, `.xlsm`, `.csv`, `.tsv`, `.xml`
     - Lectern: `.pptx`
   - Test state preservation: dirty flag, undo history, file path, recent files are untouched on failure.
2. **Regression Suite**:
   - `tests/gui/test_file_safety_regression.py` must pass with zero failures.
   - Project-wide test suite must pass with zero regressions.

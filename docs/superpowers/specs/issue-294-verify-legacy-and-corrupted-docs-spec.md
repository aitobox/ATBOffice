# Technical Specification: Issue #294 - 验证旧版与异常文档的真实打开和错误提示

## 1. Problem Statement & Audit Context
During the 2026-11-06 audit of the 150-file corpus (`tests/docs/expectations.json`):
1. **Extension-Based Skipping in Audit Core (`src/atboffice/deep/audit/core.py`)**:
   - `_execute_file_audit_worker` skipped all 75 `.doc`, `.xls`, and `.ppt` files purely by checking `if ext in (".doc", ".xls", ".ppt"):` without executing the real GUI open path.
   - Stage 3 (`render`) in `_execute_file_audit_worker` hardcoded `stages["render"] = "ok"` without executing any rendering, violating the rule that skipped or unexecuted rendering must never be marked as `"ok"`.
2. **XLS Import vs. Corrupt/XML-Disguised Files in `LedgerWindow` & `WindowManager`**:
   - Among the 25 `.xls` files in `tests/docs/excel/xls/`:
     - 22 binary `.xls` workbooks are valid BIFF8 files that import cleanly via `read_xls` (including `poi__51535.xls` after the sparse traversal optimization in #293).
     - 1 `.xls` file (`libreoffice__tdf158483.xls`) is actually an XML Spreadsheet 2003 (`<?xml ...><ss:Workbook...`) disguised with a `.xls` extension, which must be dispatched via the GUI/XMLSS reader (`read_xmlss_workbook`).
     - 2 `.xls` files (`libreoffice__CVE-2010-1246-1.xls` and `libreoffice__crash-5.xls`) are corrupted/malformed payloads that fail `read_xls`. Previously, `LedgerWindow.do_open` caught `Exception` and fell back to `check_legacy_or_disguised_file(..., allow_excel97=False)`, displaying a misleading "unsupported legacy format" warning instead of reporting that the file is corrupted/unreadable.
3. **Missing Read-Only Save Constraint on Imported `.xls` Files**:
   - Binary `.xls` (`.xls`/`.xlt`) is an import-only legacy format (ATBOffice does not have a binary BIFF8 writer).
   - Previously, `LedgerWindow.do_save` fell through to `path.touch(exist_ok=True); return True` for `.xls` paths, which could overwrite an imported `.xls` file with a 0-byte file if `save_file()` was invoked.
   - Similarly, `QuireWindow.do_save` and `LecternWindow.do_save` ended with `path.touch(exist_ok=True); return True` instead of rejecting unsupported legacy binary save targets (`.doc`, `.ppt`).
4. **Duplicate Open & Recent Files Pollution in `WindowManager`**:
   - `WindowManager.open_quire`, `open_ledger`, and `open_lectern` passed `file_path=path` to the window constructor (which already invoked `open_file(path)`), and then checked `if win.current_file_path != resolved: win.open_file(path)`—causing failed opens to execute twice and unconditionally adding failed file paths to `recent_files`.
   - `WindowManager.detect_app_type` also lacked content sniffing for XML files disguised with legacy extensions (e.g. `.xls` or `.doc` containing XML Spreadsheet or Word/HTML markup) and missing extensions (`.xlsm`, `.xml`, `.xmlss`, `.docm`, `.pptm`).

## 2. Requirements & Acceptance Criteria
1. **Isolated Real-Open Audit of All 75 Legacy + Encrypted + Corrupt Corpus Files**:
   - Execute the real GUI document open path (`WindowManager` / `QuireWindow` / `LedgerWindow` / `LecternWindow`) inside an isolated subprocess with hard timeout enforcement (`IsolatedRealOpenRunner` / `audit_real_open_file` / `audit_legacy_and_abnormal_corpus`).
   - Record per-file results distinguishing:
     - `imported` (successfully imported into document model and verified via offscreen render, e.g. 22 binary `.xls` + 1 XMLSS `.xls`),
     - `rejected` (with sub-classification `unsupported_format`, `corrupt`, or `encrypted` and captured warning/critical dialog messages),
     - `cancelled` (user cancelled password prompt on encrypted document with zero error dialogs),
     - `timeout` (worker exceeded hard timeout and was terminated),
     - `crash` (worker exited abnormally with non-zero exit code).
2. **XLS Read-Only Constraint, XML-Disguised Extension Dispatch, and Accurate Error Prompts**:
   - **XLS Read-Only Constraint**: Imported binary `.xls`/`.xlt` files must be marked `is_read_only_import = True`. Attempting in-place `save_file()` or saving to a `.xls`/`.xlt` target must be blocked with a clear warning guiding the user to save as `.xlsx`, preserving the original `.xls` file on disk intact.
   - **XML-Disguised Extension Dispatch**: `WindowManager.detect_app_type` and window `do_open` methods must inspect leading bytes for XML/HTML markup (including UTF-8 BOM / UTF-16 BOM / `<Workbook` / `<ss:Workbook` / `progid="Excel.Sheet"` / `<html` / `w:wordDocument`) so disguised `.xls` / `.doc` / `.xml` files route to the proper reader.
   - **Accurate Prompts for DOC/PPT, Encrypted, and Corrupt Files**:
     - Legacy `.doc` and `.ppt` files show format conversion guidance (`QMessageBox.warning`).
     - Encrypted packages (`poi__protected_agile.docx`) prompt for a password; cancelling aborts silently without error dialogs (`cancelled`), while an invalid password shows an explicit wrong-password warning (`QMessageBox.warning`).
     - Corrupted `.xlsx` and corrupted `.xls` files (`libreoffice__CVE-2010-1246-1.xls`, `libreoffice__crash-5.xls`, `poi__clusterfuzz...xlsx`) show an accurate corrupt/unreadable error dialog (`QMessageBox.critical`) rather than claiming `.xls` is unsupported.
3. **Honest Render Stage Reporting & Automated Regression Suite**:
   - In `src/atboffice/deep/audit/core.py`, `stages["render"]` must NEVER be marked `"ok"` when rendering is skipped or not executed (`execute_render=False` -> `stages["render"] = "skip"`). When `execute_render=True`, offscreen rendering (`QImage` grab) must actually run and verify non-empty dimensions before reporting `"ok"`.
   - Add automated unit and GUI regression tests covering process isolation, timeout termination, crash capture, XLS read-only protection, XML-disguised `.xls` dispatch, and all 77 legacy/encrypted/corrupt corpus files.

## 3. Architecture & Detailed Design

### 3.1 Window Open Dispatch & Read-Only Legacy XLS Protection
- **`src/atboffice/core/window_manager.py`**:
  - Expand extension sets (`QUIRE_EXTENSIONS`, `LEDGER_EXTENSIONS`, `LECTERN_EXTENSIONS`) and add XML/HTML header sniffing in `detect_app_type(path)` so XML Spreadsheet 2003 files (whether `.xml`, `.xmlss`, or disguised `.xls`/`.doc`) route to `"ledger"`, and HTML/WordML disguised files route to `"quire"`.
  - Fix `open_quire`, `open_ledger`, and `open_lectern` so `open_file(path)` is invoked at most once and `self.recent_files.add_file` is only called when `win.current_file_path == resolved`.
- **`src/atboffice/ui/shell/ledger_window.py`**:
  - Track `self.is_read_only_import: bool = False` (set to `True` when opening binary `.xls`/`.xlt` files, reset to `False` on `new_file` or native read-write formats).
  - Override/guard `save_file` and `do_save`:
    - Reject saving to `.xls` / `.xlt` targets in `do_save` (return `False` instead of `path.touch()`).
    - In `save_file`, if `file_path is None` and (`self.is_read_only_import` or `self.current_file_path.suffix.lower() in {".xls", ".xlt"}`), or if an explicit target path ends with `.xls`/`.xlt`, emit `QMessageBox.warning` explaining the read-only import constraint and recommending `.xlsx`, returning `False` without modifying the disk file.
  - In `do_open`, when `is_binary_xls` and `is_xls_supported()` is `True`, if `read_xls(path)` raises an exception (other than `InterruptedError` or `PermissionError`), raise a `ValueError` with corrupt/unreadable details instead of calling `check_legacy_or_disguised_file(..., allow_excel97=False)`, allowing `BaseOfficeWindow.open_file` to present the accurate corrupt file critical dialog.
- **`src/atboffice/ui/shell/quire_window.py` & `src/atboffice/ui/shell/lectern_window.py`**:
  - Support XML/HTML disguised `.doc` in `QuireWindow.do_open` (when a `.doc` file starts with `<` HTML/XML markup).
  - Ensure `do_save` in `QuireWindow` and `LecternWindow` rejects legacy binary extensions (`.doc`, `.dot`, `.ppt`, `.pps`, `.pot`) by returning `False`.

### 3.2 Isolated Real-Open Audit & True Render Stage in `src/atboffice/deep/audit/core.py`
- **`_render_model_offscreen(app: str, model: Any) -> bool`**:
  - Uses `QT_QPA_PLATFORM=offscreen` and renders the parsed document/workbook/presentation in its respective view (`WriterCanvasView`, `SpreadsheetView`, `PresentationView`) via `.grab().toImage()`, returning `True` only if `!img.isNull() and img.width() > 0 and img.height() > 0`.
- **`_execute_file_audit_worker`**:
  - Accepts `execute_render: bool = False` (or `True` when requested).
  - Never fabricates `stages["render"] = "ok"` when rendering is skipped: if `execute_render` is `False`, `stages["render"] = "skip"`; if `execute_render` is `True`, runs `_render_model_offscreen` and records `"ok"` or `"fail"`.
  - For `.doc`, `.xls`, `.ppt`, encrypted, and corrupt files, also records real-open verification metadata (`real_open`) via `_inspect_or_open_in_gui`.
- **`IsolatedRealOpenRunner` & `audit_real_open_file` & `audit_legacy_and_abnormal_corpus`**:
  - Runs the real window open path (`QuireWindow.open_file`, `LedgerWindow.open_file`, `LecternWindow.open_file`) in a `spawn` subprocess with hard timeout termination.
  - Captures all `QMessageBox.warning` / `QMessageBox.critical` dialogs and `QInputDialog.getText` prompts.
  - Classifies each file into `imported`, `rejected` (`unsupported_format` / `corrupt` / `encrypted`), `cancelled`, `timeout`, or `crash`.
  - Verifies offscreen rendering (`stages["render"] = "ok"`) ONLY when `open_ok` is `True` and offscreen widget grab succeeds; otherwise sets `stages["render"] = "skip"`.

## 4. Implementation Task List
- [x] Task 1: 修复 WindowManager 打开分发（避免失败时重复调用 open_file 与污染 recent_files，支持 XML 伪装扩展名内容识别）
- [x] Task 2: 为 LedgerWindow 实现 XLS 导入只读保存约束，并修复损坏 XLS 文件的错误提示与 Quire/Lectern 旧格式保存拦截
- [x] Task 3: 重构 `src/atboffice/deep/audit/core.py`，禁止将跳过或未执行的 render 标为 ok，并实现进程隔离的真实 GUI 打开审计器 (`IsolatedRealOpenRunner` / `audit_real_open_file`)
- [x] Task 4: 对 75 个旧格式及加密、损坏样例（共 77 个非标准 OOXML 样例）运行隔离真实打开路径验证并校准期望契约
- [x] Task 5: 编写完整的单元测试与 GUI 回归测试（涵盖 XLS 只读约束、XML 伪装分发、DOC/PPT/加密/损坏提示、超时/崩溃进程隔离及 77 样例全量核验）
- [x] Task 6: 执行 grill-me 压力审计与测试套件回归验证

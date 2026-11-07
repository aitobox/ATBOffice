# Implementation Plan: Issue #294 - 验证旧版与异常文档的真实打开和错误提示

## Chunk 1: Window Open Dispatch, XML-Disguised Routing & XLS Read-Only Constraint
**Files Modified**:
- `src/atboffice/core/window_manager.py`
- `src/atboffice/vfs/crypto.py`
- `src/atboffice/ui/shell/ledger_window.py`
- `src/atboffice/ui/shell/quire_window.py`
- `src/atboffice/ui/shell/lectern_window.py`

**Steps**:
1. Update `WindowManager.detect_app_type`:
   - Add `.docm`, `.dot`, `.dotx`, `.md`, `.markdown` to `QUIRE_EXTENSIONS`, `.xlsm`, `.xlt`, `.xltx`, `.xml`, `.xmlss` to `LEDGER_EXTENSIONS`, and `.pptm`, `.ppsx`, `.potx`, `.pps`, `.pot` to `LECTERN_EXTENSIONS`.
   - Inspect leading bytes of existing files when extension is `.xml`, `.xls`, `.xlt`, `.doc`, or `.dot`:
     - If XML markup contains `urn:schemas-microsoft-com:office:spreadsheet`, `progid="Excel.Sheet"`, `<Workbook`, or `<ss:Workbook`, route to `"ledger"`.
     - If XML/HTML markup contains `<w:wordDocument`, `progid="Word.Document"`, or `<html`, route to `"quire"`.
2. Fix `WindowManager.open_quire`, `open_ledger`, `open_lectern`:
   - Instantiate the window with `file_path=None` and call `win.open_file(path)` once if `path is not None`.
   - Only register in `self.recent_files` if `opened` is `True` and `win.current_file_path == resolved`.
3. Update `LedgerWindow`:
   - Initialize `self.is_read_only_import: bool = False`.
   - In `do_open`:
     - Detect XML markup for `.xls`/`.xlt` (supporting UTF-8, UTF-8 BOM, UTF-16 LE/BE BOM) and dispatch to `read_xmlss_workbook`.
     - When `is_binary_xls` and `is_xls_supported()` is `True`, if `read_xls(path)` fails with an exception (other than `InterruptedError` / `PermissionError`), raise `ValueError` so `BaseOfficeWindow.open_file` reports a corrupt/incompatible file (`QMessageBox.critical`) rather than claiming `.xls` format is unsupported.
     - Set `self.is_read_only_import = bool(is_binary_xls)` on successful open, and reset to `False` in `new_file()`.
   - Enforce read-only constraint on `.xls`/`.xlt`:
     - Override `save_file`: if saving in-place (`file_path is None`) when `self.is_read_only_import` or `self.current_file_path.suffix.lower() in {".xls", ".xlt"}`, or if explicit `file_path` ends with `.xls`/`.xlt`, show `QMessageBox.warning` explaining that `.xls` is a read-only import format and must be saved as `.xlsx`, and return `False` without modifying the disk file.
     - In `do_save`: return `False` for `.xls`/`.xlt` (and any unsupported extension) instead of `path.touch()`.
4. Update `QuireWindow` & `LecternWindow`:
   - Allow XML/HTML disguised `.doc` files (starting with `<`) to pass `inspect_file_format` and parse via `read_html` in `QuireWindow.do_open`.
   - Reject `.doc`/`.dot` in `QuireWindow.do_save` and `.ppt`/`.pps`/`.pot` in `LecternWindow.do_save` by returning `False`.

## Chunk 2: True Render Stage & Isolated Real-Open Audit in `src/atboffice/deep/audit/core.py`
**Files Modified**:
- `src/atboffice/deep/audit/core.py`
- `src/atboffice/deep/audit/__init__.py`
- `tests/docs/expectations.json`

**Steps**:
1. Implement `_render_model_offscreen(app: str, model: Any) -> bool` in `src/atboffice/deep/audit/core.py`:
   - Ensures `QT_QPA_PLATFORM=offscreen` and `QApplication` instance.
   - Binds model to `WriterCanvasView` / `SpreadsheetView` / `PresentationView`, resizes to `800x600`, grabs a `QImage`, and verifies `!img.isNull() and img.width() > 0 and img.height() > 0`.
2. Fix Stage 3 (`render`) in `_execute_file_audit_worker`:
   - Add `execute_render: bool = True` parameter to `IsolatedFileRunner.run` and `audit_corpus_file`.
   - When `execute_render=True`, run `_render_model_offscreen(app, model)` and set `stages["render"] = "ok"` ONLY if rendering succeeds (otherwise `"fail"`).
   - When `execute_render=False`, set `stages["render"] = "skip"` (NEVER `"ok"`).
3. Implement `IsolatedRealOpenRunner`, `audit_real_open_file`, and `audit_legacy_and_abnormal_corpus` in `src/atboffice/deep/audit/core.py`:
   - Executes real GUI open path (`WindowManager.detect_app_type` + `QuireWindow.open_file` / `LedgerWindow.open_file` / `LecternWindow.open_file`) in an isolated `spawn` process with hard timeout enforcement.
   - Captures `QMessageBox.warning`, `QMessageBox.critical`, and `QInputDialog.getText` interactions.
   - Classifies outcomes into:
     - `imported` (22 binary `.xls` + 1 XML `.xls` `libreoffice__tdf158483.xls`, verifying `read_only` flag and real offscreen render `stages["render"] == "ok"`),
     - `rejected` (`rejection_kind` in `{"unsupported_format", "corrupt", "encrypted"}`, `stages["render"] == "skip"`),
     - `cancelled` (password prompt cancelled cleanly with 0 error dialogs, `stages["render"] == "skip"`),
     - `timeout` (process killed after timeout, `terminated=True`),
     - `crash` (non-zero process exit code).
4. Enrich `tests/docs/expectations.json` with authoritative `real_open` expectations for all 77 non-valid files (`imported` vs `rejected` + `rejection_kind` + `dispatched_format`) while preserving existing `category` fields.

## Chunk 3: Automated Unit & GUI Regression Tests
**Files Created / Modified**:
- `tests/gui/test_issue294_legacy_and_abnormal_open.py`
- `tests/unit/test_audit_core.py`
- `tests/test_phase7_corpus_runner.py`

**Verification Commands**:
```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src /opt/homebrew/anaconda3/envs/ATBOffice/bin/python -m pytest tests/gui/test_issue294_legacy_and_abnormal_open.py tests/gui/test_phase7_open_contract.py tests/gui/test_window_manager_open_file.py tests/unit/test_audit_core.py tests/test_phase7_corpus_runner.py -v
```

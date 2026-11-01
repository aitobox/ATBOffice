# Implementation Plan: Issue #191 - 保护保存失败与关闭取消时的未保存数据

## Overview
Implement atomic saving, safe opening, corrupted file detection, overwrite confirmation, and close lifecycle protection across `BaseOfficeWindow`, `QuireWindow`, `LedgerWindow`, `LecternWindow`, and `WindowManager`. Follow strict TDD to guarantee zero data loss and 100% test pass.

---

## Tasks

### Task 1: Write Automated Regression Tests for File Safety Failure Paths (TDD Red)
- **File**: `tests/gui/test_file_safety_regression.py`
- **Actions**:
  - Test 1: `test_atomic_save_preserves_original_file_on_save_error`: existing target file on disk must not be modified or truncated when `do_save` throws an exception.
  - Test 2: `test_save_permission_error_preserves_dirty_state`: permission error shows distinct message, retains `is_modified=True`, and leaves document in memory.
  - Test 3: `test_overwrite_prompt_cancel_preserves_existing_file_and_state`: when target exists and user declines overwrite, existing file is untouched, save returns `False`, `is_modified=True`.
  - Test 4: `test_open_corrupted_file_preserves_current_document`: corrupted file fails `do_open`, does not update `current_file_path`, preserves existing document and dirty flag.
  - Test 5: `test_close_event_cancel_aborts_shutdown_cleanly`: cancelling close event maintains window and modifications.
  - Test 6: `test_three_modules_save_and_reopen_roundtrip`: Quire, Ledger, and Lectern save and reopen with consistent document contents.
- **Verification**: Run `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_file_safety_regression.py -v` to confirm failure on unpatched code.

### Task 2: Implement Atomic Save, Rollback & Overwrite Guard in `BaseOfficeWindow`
- **File**: `src/atboffice/ui/shell/base_window.py`
- **Actions**:
  - Add `confirm_overwrite: bool = True` to `save_file`.
  - If `target.exists()` and `target != self.current_file_path` and `confirm_overwrite`: prompt `QMessageBox.warning` asking whether to overwrite; if user declines, return `False`.
  - Implement atomic file staging:
    - Target directory validation & creation: `target.parent.mkdir(parents=True, exist_ok=True)`.
    - Stage into a temporary file in `target.parent` (e.g. `tempfile.NamedTemporaryFile` in target.parent).
    - Call `self.do_save(staged_temp_path)`.
    - If `do_save` fails or raises: clean up temp file, keep existing `target` intact, display localized error dialog (special handling for `PermissionError`), retain `is_modified=True`, return `False`.
    - On success: `os.replace(staged_temp_path, target)`.
  - Add `do_open(self, path: Path) -> bool` virtual hook.
  - Update `open_file`: only update `self.current_file_path` and `self.set_modified(False)` if `self.do_open(path)` succeeds. If corrupted or exception raised, show critical dialog and return `False`.
  - Enhance `closeEvent`: call `drain_event_loop(2)` after emitting `window_closed`.

### Task 3: Implement Real Document IO and Error Handling in Subclass Windows
- **Files**:
  - `src/atboffice/ui/shell/quire_window.py`:
    - Implement `do_save(path)` using `write_docx` for `.docx`, `write_html` for `.html`.
    - Implement `do_open(path)` using `read_docx` for `.docx`, `read_html` for `.html`, validating file integrity.
  - `src/atboffice/ui/shell/ledger_window.py`:
    - Implement `do_save(path)` using `write_xlsx` for `.xlsx`, `write_csv` for `.csv`, `write_xmlss` for `.xml`.
    - Implement `do_open(path)` using `read_xlsx` for `.xlsx`, `read_csv` for `.csv`, `read_xmlss` for `.xml`.
  - `src/atboffice/ui/shell/lectern_window.py`:
    - Add `@property def presentation(self) -> Presentation`.
    - Implement `do_save(path)` using `write_pptx` for `.pptx`.
    - Implement `do_open(path)` using `read_pptx` for `.pptx`.

### Task 4: Localized UI Text and 7-Language Translations
- **Files**:
  - `src/atboffice/locale/` (and inline safe_tr dictionary if applicable)
  - Ensure all new strings (`文件“{name}”已存在。\n是否替换现有文件？`, `无法保存文件“{target}”：权限不足，无法写入目标目录或文件。`, `无法打开文件“{path}”：文件已损坏或格式不兼容。`) have translations in zh_CN, zh_TW, en, ja, de, fr, es.

### Task 5: Verification & Diff Checklist Documentation
- **Files**:
  - `tests/gui/test_file_safety_regression.py`
  - `tests/test_base_office_window.py`
  - `docs/clone/CLONE_DIFF.md`
- **Actions**:
  - Run regression test suite and full unit tests.
  - Update `docs/clone/CLONE_DIFF.md` under `TASK-502` with verified test results and evidence.

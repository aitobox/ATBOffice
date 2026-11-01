# Design Specification: Issue #191 - 保护保存失败与关闭取消时的未保存数据

## Overview
This specification details the design for Issue #191 ([Phase 5] 保护保存失败与关闭取消时的未保存数据, Step 3 of 13 for Epic #188).
It establishes enterprise-grade data safety across all ATBOffice shell windows (`BaseOfficeWindow`, `QuireWindow`, `LedgerWindow`, `LecternWindow`) and `WindowManager`:
1. Guaranteed atomic file saving (write-to-temp-then-replace) so existing files on disk are never corrupted or truncated if saving fails mid-stream.
2. Complete preservation of in-memory document state and dirty flags (`is_modified=True`) whenever saving fails, closing is cancelled, or overwrite is declined.
3. Explicit detection and localized messaging for permission errors (`PermissionError`), disk/serialization failures, and existing target overwrite prompts.
4. Safe file opening with corrupted-file detection (`do_open` hook) that leaves the active document and file path untouched if an opened file is damaged.
5. Robust close lifecycle with event-loop draining and cancellation safeguards.
6. Full i18n support (`safe_tr()` / `retranslate_ui`) with translations in all 7 supported languages.

---

## 1. Architectural Changes

### 1.1 Atomic Save & Rollback Architecture (`BaseOfficeWindow.save_file`)
Currently, `save_file` calls `self.do_save(target)` directly with the target path. If `do_save` fails midway, the existing file on disk is truncated or corrupted.

**New Atomic Save Protocol**:
```
User calls save_file(target)
         │
         ▼
[Check Overwrite Confirmation] (If target exists, target != current_file_path, and confirm_overwrite)
         ├─► User Declines: Return False (State preserved, target untouched)
         ▼ User Confirms or same file
[Create Temporary Staging File] in target.parent: .~{target.name}.tmp.{uuid}
         │
         ▼
[Call do_save(temp_path)]
         ├─► Exception / Returns False:
         │   1. Clean up temporary staging file
         │   2. Keep existing target file 100% UNTOUCHED
         │   3. Keep in-memory document intact and self.is_modified = True
         │   4. Keep self.current_file_path unchanged
         │   5. Show localized error dialog (distinguishing PermissionError vs IO/Format error)
         │   6. Return False
         │
         ▼ Returns True
[Atomic Replace]: os.replace(temp_path, target)
         │
         ▼
[Update Window State]:
  self.current_file_path = target
  self.set_modified(False)
  self.update_window_title()
  Add to recent files
  Return True
```

### 1.2 Corrupted File Protection (`BaseOfficeWindow.open_file`)
Currently, `open_file` updates `current_file_path` and `is_modified=False` before checking whether subclass document parsing succeeds.

**New Safe Open Protocol**:
```
User calls open_file(path)
         │
         ▼
[maybe_save_prompt()] (Save / Discard / Cancel)
         ├─► Cancel: Return False (Keep current doc)
         ▼ Discard or Saved
[Check Path Exists & Is File]
         ├─► Missing: Show critical dialog, Return False
         ▼
[Call Subclass Hook do_open(resolved_path)]
         ├─► Raises Exception or Returns False:
         │   1. Show localized critical dialog: "无法打开文件“{path}”：文件已损坏或格式不兼容。"
         │   2. Do NOT change self.current_file_path
         │   3. Do NOT clear self.is_modified
         │   4. Return False
         │
         ▼ Returns True
[Commit Open]:
  self.current_file_path = resolved_path
  self.set_modified(False)
  self.update_window_title()
  Add to recent files
  Return True
```

### 1.3 Subclass IO Hooks (`QuireWindow`, `LedgerWindow`, `LecternWindow`)
Each document window provides dedicated `do_save(path)` and `do_open(path)` implementations:
- **Quire (`quire_window.py`)**:
  - `do_save`:
    - `.docx`, `.docm`, `.dotx`: `from atboffice.modules.writer.io.docx_writer import write_docx; write_docx(doc, path)`
    - `.html`, `.htm`: `from atboffice.modules.writer.io.html_io import write_html; write_html(doc, path)`
    - fallback / text: fallback serialization
  - `do_open`:
    - `.docx`, `.docm`: `from atboffice.modules.writer.io.docx_reader import read_docx; doc = read_docx(path); update canvas`
    - `.html`, `.htm`: `from atboffice.modules.writer.io.html_io import read_html; doc = read_html(path); update canvas`
    - Raises error on corrupted zip/invalid xml to trigger safe rollback.
- **Ledger (`ledger_window.py`)**:
  - `do_save`:
    - `.xlsx`, `.xlsm`: `from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx; write_xlsx(workbook, path)`
    - `.csv`, `.tsv`: `from atboffice.modules.spreadsheet.io.csv_io import write_csv; write_csv(model, path)`
    - `.xml`, `.xmlss`: `from atboffice.modules.spreadsheet.io.xmlss_io import write_xmlss; write_xmlss(workbook, path)`
  - `do_open`:
    - `.xlsx`, `.xlsm`: `from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx; wb = read_xlsx(path); update view`
    - `.csv`, `.tsv`: `from atboffice.modules.spreadsheet.io.csv_io import read_csv; read_csv(path, model)`
    - `.xml`, `.xmlss`: `from atboffice.modules.spreadsheet.io.xmlss_io import read_xmlss; read_xmlss(path, workbook)`
- **Lectern (`lectern_window.py`)**:
  - `do_save`:
    - `.pptx`: `from atboffice.modules.presentation.io.pptx_writer import write_pptx; write_pptx(presentation, path)`
  - `do_open`:
    - `.pptx`: `from atboffice.modules.presentation.io.pptx_reader import read_pptx; pres = read_pptx(path); load presentation`

### 1.4 Close Lifecycle & Event Loop Draining
- `BaseOfficeWindow.closeEvent`:
  - When `maybe_save_prompt()` returns `False`:
    - Call `event.ignore()`
    - Window and dirty state preserved
  - When `maybe_save_prompt()` returns `True`:
    - Execute any before-close callbacks
    - `event.accept()`
    - Emit `window_closed(self)`
    - Call `drain_event_loop(2)` to ensure deferred deletions (`deleteLater`) do not conflict with subsequent operations.

---

## 2. Localization (i18n) Requirements
All newly added or refined dialog messages must use `safe_tr()`:
- `safe_tr("文件“{name}”已存在。\n是否替换现有文件？")`
- `safe_tr("无法保存文件“{target}”：权限不足，无法写入目标目录或文件。")`
- `safe_tr("无法打开文件“{path}”：文件已损坏或格式不兼容。")`
- `safe_tr("无法打开文件“{path}”：文件已损坏或格式不兼容。\n{exc}")`

Add translations for English, Chinese (Simplified), Chinese (Traditional), Japanese, French, German, and Spanish in the locale catalog / `safe_tr` fallback.

---

## 3. Verification & Test Plan
1. **Unit tests in `tests/test_base_office_window.py` and `tests/gui/test_file_safety_regression.py`**:
   - `test_atomic_save_protects_existing_file_on_failure`: verify existing file content is unchanged when `do_save` throws `OSError` or `RuntimeError`.
   - `test_save_permission_error_preserves_dirty_state`: verify `PermissionError` shows specific permission message, preserves `is_modified=True`, and leaves path unchanged.
   - `test_save_as_overwrite_prompt_cancel`: verify user declining overwrite preserves original file, keeps `is_modified=True`, and aborts save.
   - `test_open_corrupted_file_preserves_current_document`: verify invalid file payload does not overwrite active document, does not update `current_file_path`, and shows corruption dialog.
   - `test_close_cancel_preserves_all_content`: verify cancel in `closeEvent` leaves window and modifications completely intact.
   - `test_save_reopen_roundtrip_all_modules`: verify Quire (`.docx`, `.html`), Ledger (`.xlsx`), and Lectern (`.pptx`) roundtrip accurately.

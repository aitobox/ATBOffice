# Legacy Office 2003 (.doc / .xls / .ppt) High-Fidelity Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable high-fidelity, read-only import of Office 97–2003 binary documents (`.doc`, `.dot`, `.xls`, `.xlt`, `.ppt`, `.pps`, `.pot`) across Quire, Ledger, and Lectern via a bundled, file-pruned headless LibreOffice engine (Approach B1-a), forcing users to Save As modern OOXML formats (`.docx`, `.xlsx`, `.pptx`).

**Architecture:** A new `legacy_converter` service in `src/atboffice/vfs/` locates the bundled `vendor/lo_headless` binary (or system `soffice` in dev mode), pre-decrypts password-protected OLE2 files via `msoffcrypto-tool`, runs `soffice --headless --convert-to` in an isolated temporary profile/output directory off the Qt UI thread with timeout and cancellation support, and feeds the resulting OOXML bytes into ATBOffice's existing `read_docx` / `read_xlsx` / `read_pptx` readers (keeping `xlrd` as a zero-dependency fallback for `.xls`). A shared `is_read_only_import` lifecycle in `BaseOfficeWindow` blocks overwriting legacy files and redirects Save As to modern extensions, while offline pruning/fetch scripts (`scripts/vendor/`) and Nuitka build hooks (`scripts/build/`) package, verify GPL-free compliance, and sign the three-platform artifacts.

**Tech Stack:** Python 3.12+, PySide6 (Qt6), `msoffcrypto-tool`, `xlrd`, Nuitka, pytest / pytest-qt, GitHub Actions.

**Spec:** [2026-11-15-legacy-office-2003-import-design.md](file:///Users/brainzhang/work/aitobox/ATBOffice/docs/superpowers/specs/2026-11-15-legacy-office-2003-import-design.md)

## Global Constraints

- Legacy formats (`.doc`, `.dot`, `.xls`, `.xlt`, `.ppt`, `.pps`, `.pot`) are strictly **read-only import**; saving back to any legacy extension is forbidden and `do_save()` must return `False`.
- Never execute VBA macros from legacy files.
- Never link LibreOfficeKit in-process; always invoke `soffice` as an isolated subprocess (`-env:UserInstallation=...`) with a 60.0s default timeout and guaranteed temporary directory cleanup.
- Bundled `vendor/lo_headless` must contain **zero GPL components** (no `poppler`, no `xpdfimport`, no `pdfimport`, no MySQL/MariaDB SDBC) and **zero macOS/desktop registration metadata** (no `.app` wrapper, no `CFBundleDocumentTypes`, no `.desktop`, no QuickLook/Explorer shell extensions).
- Never display the "LibreOffice" trademark or logo in ATBOffice UI; use neutral attribution in `LicenseDialog` (`MPL-2.0 / LGPL-3.0+`) pointing to the pinned upstream TDF source version.
- Every UI string must use `safe_tr()` with translations added to all 9 locale catalogs in `src/atboffice/resources/locale/`.
- Release builds (`scripts/build/build_*.py`) must fail if `vendor/lo_headless` is missing or fails SHA256 verification unless `--allow-missing-converter` is explicitly passed.
- PR CI (`.github/workflows/ci.yml`) must remain converter-free; real `soffice` tests must skip cleanly when `is_legacy_converter_available()` is `False`.

## Review Focus

- **Save As default extension on read-only legacy imports:** Opening `foo.doc` / `bar.xls` / `baz.ppt` and calling `save_file_as()` must pre-fill `foo.docx` / `bar.xlsx` / `baz.pptx` (never the legacy extension) and default to modern writeable filters (pinned in Task 3).
- **Disguised legacy OLE2 files (e.g., binary `.doc` renamed to `.docx`):** Opening a disguised binary OLE2 in the matching app must route through `legacy_converter` instead of crashing in `read_docx`/`read_xlsx`/`read_pptx` as a corrupt ZIP, while cross-app mismatches (`word97` in Ledger) must still reject (pinned in Task 2 and Task 4).
- **Symlinks, spaces, and CJK characters in source paths:** Staging input files into `temp_dir/in/` must preserve symlinks/CJK/spaces safely and bind `current_file_path` to the resolved original path on success without polluting `recent_files` on failure (pinned in Task 1 and Task 4).
- **Encrypted legacy OLE2 cancel vs wrong password:** Cancelling the password prompt must raise `FileOpenCancelled` silently with zero error dialogs; an invalid password must display one warning (`FileOpenWarningHandled`) and never spawn `soffice` (pinned in Task 1 and Task 4).
- **Subprocess hang, crash, 0-byte output, or user cancellation:** Timeout, non-zero exit, empty output, or cancelling the progress dialog must terminate the `soffice` process group, clean up temp directories, and preserve the previous open document intact (pinned in Task 1 and Task 3).

---

### Task 1: Legacy Conversion Service & Encrypted OLE2 Pre-Decryption

**Files:**
- Modify: `pyproject.toml:11-16`
- Create: `src/atboffice/vfs/legacy_converter.py`
- Test: `tests/unit/vfs/test_legacy_converter.py`

**Interfaces:**
- Consumes: `msoffcrypto` (`msoffcrypto.OfficeFile`), `sys.frozen` / `sys._MEIPASS` / `Path`, `subprocess.Popen`
- Produces:
  - `class LegacyConversionError(RuntimeError)`
  - `class LegacyConverterUnavailableError(LegacyConversionError)`
  - `class LegacyEncryptedError(LegacyConversionError)`
  - `class LegacyConversionCancelled(LegacyConversionError)`
  - `find_converter_executable() -> Path | None`
  - `is_legacy_converter_available() -> bool`
  - `is_legacy_ole_encrypted(path_or_bytes: bytes | str | Path) -> bool`
  - `decrypt_legacy_ole(path_or_bytes: bytes | str | Path, password: str) -> bytes`
  - `legacy_target_extension(ole_format: str) -> Literal["docx", "xlsx", "pptx"] | None`
  - `convert_legacy_to_ooxml(input_path: Path, target_ext: Literal["docx", "xlsx", "pptx"], *, password_provider: Callable[[str], str | None] | None = None, cancel_event: threading.Event | None = None, timeout_seconds: float = 60.0) -> bytes`

- [ ] **Step 1: Write failing unit tests for converter discovery, subprocess isolation, encryption, CJK paths, timeout, and cancellation**

Create `tests/unit/vfs/test_legacy_converter.py` covering:
- `test_find_converter_executable_env_override(monkeypatch, tmp_path)`: creates dummy executable at `tmp_path / "soffice"`, sets `ATBOFFICE_CONVERTER_PATH`, asserts `find_converter_executable() == dummy.resolve()` and `is_legacy_converter_available() is True`.
- `test_find_converter_executable_bundled_layout(monkeypatch, tmp_path)`: simulates bundled layout (`vendor/lo_headless/MacOS/soffice`, `vendor/lo_headless/program/soffice`, `vendor/lo_headless/program/soffice.exe`) with `monkeypatch` on platform/base path and verifies bundled priority over `PATH`.
- `test_convert_legacy_to_ooxml_isolated_profile_and_cjk_path(monkeypatch, tmp_path)`: inputs `tmp_path / "财务 报告 (2003).doc"`, mocks `subprocess.Popen` to assert `--headless`, `--nologo`, `--nodefault`, `--nofirststartwizard`, `--nolockcheck`, `--norestore`, `-env:UserInstallation=file://...`, `--convert-to docx`, `--outdir`, writes fake `.docx` bytes into `--outdir`, verifies returned bytes and that the temp root directory is deleted after return.
- `test_convert_legacy_to_ooxml_encrypted_cancel_and_wrong_password(monkeypatch, tmp_path)`: mocks `is_legacy_ole_encrypted` returning `True`; verifies `password_provider` returning `None` raises `LegacyConversionCancelled` without calling `Popen`; verifies `decrypt_legacy_ole` raising `LegacyEncryptedError` propagates without calling `Popen`; verifies valid password decrypts to staged file before calling `Popen`.
- `test_convert_legacy_to_ooxml_timeout_cancel_and_empty_output(monkeypatch, tmp_path)`: verifies hung process raises `LegacyConversionError` on `timeout_seconds=0.05` with process kill called and temp dir cleaned; verifies pre-set `cancel_event` terminates process and raises `LegacyConversionCancelled`; verifies 0-byte output file raises `LegacyConversionError`.

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/vfs/test_legacy_converter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atboffice.vfs.legacy_converter'`.

- [ ] **Step 3: Add `msoffcrypto-tool>=5.4.0` to `pyproject.toml` and install in `ATBOffice` env**

Modify `pyproject.toml` `dependencies` list to add `"msoffcrypto-tool>=5.4.0"`, and run `conda run -n ATBOffice python -m pip install "msoffcrypto-tool>=5.4.0"`.

- [ ] **Step 4: Implement `src/atboffice/vfs/legacy_converter.py`**

Implement the produced interfaces with these pinned behaviors:
- `find_converter_executable()`:
  1. Check `os.environ.get("ATBOFFICE_CONVERTER_PATH")`; if set and points to an existing file (or executable inside a dir), return it. If set to empty string `""`, treat as explicitly disabled and return `None` (unless system fallback is requested? No: empty string `ATBOFFICE_CONVERTER_PATH=""` forces unavailable for clean deterministic testing!).
  2. Check bundled locations relative to executable/app root (`Contents/Resources/vendor/lo_headless/MacOS/soffice` on macOS, `vendor/lo_headless/program/soffice` on Linux, `vendor/lo_headless/program/soffice.exe` on Windows).
  3. Only when not running frozen (`not getattr(sys, "frozen", False)`), fallback to `shutil.which("soffice")` or standard macOS/Linux/Windows LibreOffice paths (`/Applications/LibreOffice.app/Contents/MacOS/soffice`).
- `is_legacy_ole_encrypted` / `decrypt_legacy_ole`: wrap `msoffcrypto.OfficeFile` on `BytesIO` or file handle; call `is_encrypted()` safely (returning `False` on non-OLE/unparseable headers); raise `LegacyEncryptedError` on invalid password or decryption failure.
- `convert_legacy_to_ooxml`:
  - Raise `LegacyConverterUnavailableError` if `find_converter_executable()` is `None`.
  - Use `tempfile.TemporaryDirectory(prefix="atboffice_legacy_")` with subdirs `profile`, `in`, `out`.
  - If `is_legacy_ole_encrypted(input_path)`: require `password_provider`; if `None` or returns `None`, raise `LegacyConversionCancelled`; decrypt bytes via `decrypt_legacy_ole` and write to `in_dir / f"doc{input_path.suffix.lower() or '.bin'}"`; otherwise `shutil.copy2(input_path, staged_in)`. (Copy avoids `soffice` mutating/locking original file or choking on special characters/symlinks.)
  - Launch `subprocess.Popen` with `start_new_session=True` (POSIX) or `creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP` (Windows).
  - Poll in short intervals (e.g. `0.05s`) checking `cancel_event` and `timeout_seconds`; terminate/kill the entire process group (`os.killpg` on POSIX, `proc.kill()` on Windows) on cancel or timeout.
  - Locate `<staged_stem>.<target_ext>` in `out_dir`; verify `stat().st_size > 0`; read and return `bytes`.

- [ ] **Step 5: Run tests to verify pass**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/vfs/test_legacy_converter.py -v`
Expected: PASS (all mocked unit tests pass; optional real `soffice` test passes or skips if `soffice` absent).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/atboffice/vfs/legacy_converter.py tests/unit/vfs/test_legacy_converter.py
git commit -m "feat(vfs): add isolated legacy Office conversion service and OLE2 decryption"
```

---

### Task 2: Format Sniffing & Disguised Legacy Routing (`vfs/crypto.py`)

**Files:**
- Modify: `src/atboffice/vfs/crypto.py:677-884`
- Modify: `src/atboffice/vfs/__init__.py` (verify exports)
- Test: `tests/unit/vfs/test_ole_detection.py`

**Interfaces:**
- Consumes: `atboffice.vfs.crypto.FileFormatInspection`, `detect_ole_format`, `is_ole_compound_file`
- Produces:
  - Updated `inspect_file_format(path_or_bytes: bytes | str | Path, expected_app: str | None = None, allow_excel97: bool = False, allow_legacy_conversion: bool = False) -> FileFormatInspection`

- [ ] **Step 1: Write failing tests in `tests/unit/vfs/test_ole_detection.py`**

Append tests to `tests/unit/vfs/test_ole_detection.py`:
- `test_inspect_file_format_allows_matching_legacy_and_disguised_when_converter_enabled(tmp_path)`:
  - When `allow_legacy_conversion=True`:
    - `word97` `.doc` AND disguised `word97` `.docx` opened with `expected_app="quire"` return `should_reject is False`, `ole_format == "word97"`, `is_disguised` accurate (`False` for `.doc`, `True` for `.docx`).
    - `excel97` `.xls` AND disguised `excel97` `.xlsx` opened with `expected_app="ledger"` return `should_reject is False`, `ole_format == "excel97"`.
    - `powerpoint97` `.ppt` AND disguised `powerpoint97` `.pptx` opened with `expected_app="lectern"` return `should_reject is False`, `ole_format == "powerpoint97"`.
  - Cross-app mismatch (`powerpoint97` opened in `quire`, `word97` opened in `ledger`, `excel97` opened in `lectern`) STILL returns `should_reject is True` (`guidance_message is not None`) even when `allow_legacy_conversion=True`.
  - Non-OLE bogus `.doc` / `.ppt` (not XML/HTML/RTF) with `allow_legacy_conversion=True`: `should_reject` remains `True` (or falls through to corrupt? Wait: check existing behavior! In `crypto.py` lines 710-739, a non-OLE, non-HTML/RTF `.doc` file previously returned `guidance_message="...旧版二进制 Word..."`. If it's NOT OLE and NOT HTML/RTF, it's either corrupt or arbitrary text/binary; with `allow_legacy_conversion=True`, returning `should_reject=False` lets `do_open` treat it as corrupt/unreadable instead of falsely saying "unsupported format"!). Assert `should_reject is True` ONLY when `allow_legacy_conversion=False`, and `should_reject is False` for non-OLE `.doc`/`.ppt` when `allow_legacy_conversion=True` so corrupt `.doc`/`.ppt` gets proper corrupt error handling.

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/vfs/test_ole_detection.py -v`
Expected: FAIL with `TypeError: inspect_file_format() got an unexpected keyword argument 'allow_legacy_conversion'`.

- [ ] **Step 3: Update `inspect_file_format` in `src/atboffice/vfs/crypto.py`**

Modify `inspect_file_format` signature to add `allow_legacy_conversion: bool = False`:
- When `not is_ole`: if `allow_legacy_conversion` is `True` for matching `app` and legacy ext (`.doc`/`.dot` in `quire`, `.xls`/`.xlt` in `ledger`, `.ppt`/`.pps`/`.pot` in `lectern`), do not emit unsupported-format rejection (`guidance_message=None`).
- When `is_ole` and `not is_enc`:
  - Keep all cross-app mismatch rejections untouched (`powerpoint97` in `quire`, `word97` in `ledger`, etc.).
  - When `ole_fmt` matches `app` (`word97` + `quire`, `excel97` + `ledger`, `powerpoint97` + `lectern`): if `allow_legacy_conversion` is `True` (or `allow_excel97` for non-disguised `excel97`), set `guidance_message = None` while preserving `is_disguised` and `ole_format`.
  - Keep existing default `allow_legacy_conversion=False` so all legacy tests in `test_ole_detection.py` remain green.

- [ ] **Step 4: Run tests to verify pass**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/vfs/test_ole_detection.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/vfs/crypto.py tests/unit/vfs/test_ole_detection.py
git commit -m "feat(vfs): support legacy conversion routing in inspect_file_format"
```

---

### Task 3: Unified Read-Only Import, Save Guard & Async Progress in `BaseOfficeWindow`

**Files:**
- Modify: `src/atboffice/ui/shell/base_window.py:41-66,129-138,250-269,515-641`
- Modify: `src/atboffice/resources/locale/*.json` (all 9 locale files: `zh-CN`, `zh-Hant`, `en`, `ja`, `ko`, `fr`, `de`, `es`, `ru`)
- Test: `tests/gui/test_base_window_legacy_import.py`

**Interfaces:**
- Consumes: `atboffice.vfs.crypto.inspect_file_format`, `FileFormatInspection`, `atboffice.vfs.legacy_converter.*`
- Produces on `BaseOfficeWindow`:
  - `self.is_read_only_import: bool` (initialized `False`, reset in `new_file()` / `load_template()`, cleared on successful modern `save_file()`)
  - `self.imported_dispatched_format: str | None` (initialized `None`, reset in `new_file()` / `load_template()`, set by subclasses when importing legacy/disguised formats, e.g. `"doc_converted"`, `"xls_converted"`, `"xls_binary"`, `"ppt_converted"`)
  - `self.legacy_extensions: frozenset[str]` (class/instance default `frozenset({".doc", ".dot", ".xls", ".xlt", ".ppt", ".pps", ".pot"})`)
  - `self.modern_save_extension: str` (overridden by subclasses: `".docx"`, `".xlsx"`, `".pptx"`)
  - `get_save_file_filter(self) -> str` (defaults to `get_file_filter()`, overridden by subclasses to put modern writeable format first and exclude read-only legacy formats)
  - `check_legacy_or_disguised_file(self, path: Path, app_name: str, allow_excel97: bool = False, allow_legacy_conversion: bool = False) -> FileFormatInspection`
  - `convert_legacy_file_with_progress(self, path: Path, target_ext: Literal["docx", "xlsx", "pptx"]) -> bytes`
  - `save_file()` read-only guard: blocks saving to any extension in `self.legacy_extensions` (or in-place save when `self.is_read_only_import and target == self.current_file_path`), prompts user with option to immediately invoke `save_file_as()`.
  - `save_file_as()` default path swap: when `self.is_read_only_import` and `self.current_file_path` has a legacy suffix (or `self.modern_save_extension` is set and suffix is in `legacy_extensions`), pre-fills `with_suffix(self.modern_save_extension)` and uses `self.get_save_file_filter()`.

- [ ] **Step 1: Write failing GUI tests in `tests/gui/test_base_window_legacy_import.py`**

Test cases:
- `test_base_window_readonly_save_guard_and_save_as_default_extension(qtbot, monkeypatch, tmp_path)`:
  - Create subclass of `BaseOfficeWindow` with `modern_save_extension = ".docx"` and `get_save_file_filter = lambda: "Word (*.docx)"`.
  - Set `current_file_path = tmp_path / "memo.doc"`, `is_read_only_import = True`, `set_modified(True)`.
  - Verify `save_file()` returns `False`, shows warning dialog, and does NOT overwrite `memo.doc`.
  - Verify clicking "Save As" button in warning (mocked `QMessageBox` returning `AcceptRole`/Yes) triggers `save_file_as()` where `QFileDialog.getSaveFileName` receives `str(tmp_path / "memo.docx")` as initial path and `"Word (*.docx)"` as filter, and saving to `memo.docx` clears `is_read_only_import` to `False`.
- `test_convert_legacy_file_with_progress_cancel_and_encrypted_prompt(qtbot, monkeypatch, tmp_path)`:
  - Mock `convert_legacy_to_ooxml` to wait on `cancel_event` and raise `LegacyConversionCancelled`; verify progress cancellation raises `FileOpenCancelled` cleanly with zero critical dialogs.
  - Mock `convert_legacy_to_ooxml` invoking `password_provider` returning `None`; verify `FileOpenCancelled` is raised.
  - Mock `convert_legacy_to_ooxml` raising `LegacyEncryptedError`; verify warning dialog + `FileOpenWarningHandled` is raised.
  - Mock `convert_legacy_to_ooxml` returning valid bytes; verify bytes are returned and UI stays responsive.

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_base_window_legacy_import.py -v`
Expected: FAIL (missing `modern_save_extension`, `get_save_file_filter`, `convert_legacy_file_with_progress`, and read-only guard on `BaseOfficeWindow`).

- [ ] **Step 3: Implement unified read-only import, Save guard, Save As suffix rewrite, and async `QThread` progress conversion in `src/atboffice/ui/shell/base_window.py`**

Key implementation rules:
- In `convert_legacy_file_with_progress`:
  - Handle password prompting cleanly on the **main Qt thread** before spawning the background `QThread` if `is_legacy_ole_encrypted(path)` is `True` (so `QInputDialog` is never called from a worker thread! Pass the pre-collected password via a one-shot `password_provider=lambda _name: collected_pwd` to `convert_legacy_to_ooxml`).
  - Run `convert_legacy_to_ooxml` in a `QThread` worker with a local `QEventLoop` + cancellable `QProgressDialog` (in `PYTEST_CURRENT_TEST` or when `QProgressDialog` is not desired/headless, skip blocking modal UI spin if needed while still respecting `cancel_event` and `QThread` completion).
  - Translate `LegacyConversionCancelled` -> `FileOpenCancelled`, `LegacyEncryptedError` -> warning dialog + `FileOpenWarningHandled`, `LegacyConverterUnavailableError` -> warning dialog + `FileOpenWarningHandled`, other `LegacyConversionError` -> `ValueError` (handled by `open_file` critical dialog).
- In `save_file()`:
  - Check `target.suffix.lower() in self.legacy_extensions`: warn with `QMessageBox` containing `"Yes"` (立即另存为) / `"No"` (取消) or compatible standard buttons so existing tests mocking `QMessageBox.warning` (which ignore extra args and return `None` or `StandardButton`) still see `save_file()` return `False` safely without crashing! Specifically: if mock returns `QMessageBox.StandardButton.Yes`, call `return self.save_file_as()`, otherwise `return False`.
- Add idiomatic translations for all new `safe_tr(...)` strings across all 9 JSON catalogs in `src/atboffice/resources/locale/`.

- [ ] **Step 4: Run tests to verify pass (including existing i18n tests)**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_base_window_legacy_import.py tests/test_i18n_phase6.py tests/core/test_i18n.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/ui/shell/base_window.py src/atboffice/resources/locale/*.json tests/gui/test_base_window_legacy_import.py
git commit -m "feat(ui): add unified read-only import guard and async legacy conversion to BaseOfficeWindow"
```

---

### Task 4: Quire, Ledger, Lectern & StartCenter Legacy Import Wiring

**Files:**
- Modify: `src/atboffice/ui/shell/quire_window.py:657-810`
- Modify: `src/atboffice/ui/shell/ledger_window.py:377-568`
- Modify: `src/atboffice/ui/shell/lectern_window.py:2141-2230`
- Modify: `src/atboffice/ui/shell/start_center.py:690-705`
- Modify: `src/atboffice/resources/locale/*.json` (any new filter/status bar strings across 9 locales)
- Test: `tests/gui/test_legacy_import_modules.py`

**Interfaces:**
- Consumes: `BaseOfficeWindow.check_legacy_or_disguised_file`, `convert_legacy_file_with_progress`, `is_read_only_import`, `is_legacy_converter_available`
- Produces:
  - `QuireWindow`: `modern_save_extension = ".docx"`, `get_save_file_filter()`, `do_open()` handling binary `.doc`/`.dot` and disguised `word97` via `convert_legacy_file_with_progress(..., "docx")` -> `read_docx()`, setting `is_read_only_import = True` and status bar message.
  - `LedgerWindow`: `modern_save_extension = ".xlsx"`, `get_save_file_filter()`, `do_open()` preferring `convert_legacy_file_with_progress(..., "xlsx")` -> `read_xlsx()` when converter available for binary `.xls`/`.xlt` or disguised `excel97`, falling back to `read_xls()` when converter unavailable or fails (unless encrypted/cancelled). Remove duplicate `save_file` override in favor of `BaseOfficeWindow.save_file` (or keep compatible delegate).
  - `LecternWindow`: `modern_save_extension = ".pptx"`, `get_save_file_filter()`, `do_open()` handling `.ppt`/`.pps`/`.pot` and disguised `powerpoint97` via `convert_legacy_file_with_progress(..., "pptx")` -> `read_pptx()`, setting `is_read_only_import = True` and status bar message.
  - `QuireWindow.get_file_filter()` & `LecternWindow.get_file_filter()` & `StartCenter` open filter include `.doc *.dot` / `.ppt *.pps *.pot` in "所有支持的格式".

- [ ] **Step 1: Write failing GUI tests in `tests/gui/test_legacy_import_modules.py`**

Test cases (using mocked `convert_legacy_file_with_progress` returning minimal valid `.docx` / `.xlsx` / `.pptx` bytes created via existing writers or test fixtures):
- `test_quire_opens_binary_and_disguised_doc_as_readonly_and_saves_as_docx(qtbot, monkeypatch, tmp_path)`:
  - Create OLE2 mock `.doc` and disguised `.docx` (`WordDocument` stream); mock `is_legacy_converter_available` -> `True` and `convert_legacy_file_with_progress` -> valid `.docx` bytes.
  - Assert `win.open_file()` returns `True`, `win.is_read_only_import is True`, content matches converted `.docx`, `win.save_file()` returns `False`, and `win.save_file(tmp_path / "out.docx", confirm_overwrite=False)` returns `True` and clears `is_read_only_import`.
- `test_lectern_opens_binary_and_disguised_ppt_as_readonly_and_saves_as_pptx(qtbot, monkeypatch, tmp_path)`:
  - Same flow for `.ppt` and disguised `.pptx` (`PowerPoint Document` stream) -> `read_pptx()`, `is_read_only_import is True`, overwrite blocked, Save As `.pptx` succeeds.
- `test_ledger_xls_uses_converter_when_available_and_falls_back_to_xlrd(qtbot, monkeypatch, tmp_path)`:
  - Copy `tests/docs/excel/xls/libreoffice__AutoFilter.xls` to `tmp_path`.
  - When converter available and succeeds: assert `convert_legacy_file_with_progress` is called with `"xlsx"` and `is_read_only_import is True`.
  - When converter raises non-cancel/non-encrypted error (or unavailable): assert seamless fallback to `read_xls()`, `win.open_file()` still returns `True`, `is_read_only_import is True`.
- `test_file_filters_include_legacy_extensions(qtbot)`:
  - Verify `QuireWindow().get_file_filter()` includes `*.doc` in the first filter entry, `LecternWindow().get_file_filter()` includes `*.ppt`, and `QuireWindow().get_save_file_filter()` / `LecternWindow().get_save_file_filter()` / `LedgerWindow().get_save_file_filter()` exclude `.doc`/`.ppt`/`.xls`.

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_legacy_import_modules.py -v`
Expected: FAIL

- [ ] **Step 3: Wire `QuireWindow`, `LedgerWindow`, `LecternWindow`, `StartCenter`, and locale JSONs**

Important implementation details:
- In `QuireWindow.do_open()`:
  - Check `html`/`rtf` header sniffing FIRST so HTML/RTF disguised as `.doc` continues using fast native `read_html` / `RtfReader` with `is_read_only_import = False`.
  - Call `insp = self.check_legacy_or_disguised_file(path, "quire", allow_legacy_conversion=is_legacy_converter_available())`.
  - If `insp.is_ole and insp.ole_format == "word97"`: call `converted_bytes = self.convert_legacy_file_with_progress(path, "docx")` -> `read_docx(converted_bytes)`, and set `self.is_read_only_import = True` + status bar message after UI binding succeeds (remember transactional rollback!).
- In `LedgerWindow.do_open()`:
  - Keep XMLSS detection (`is_xml_markup`) first.
  - Pass `allow_legacy_conversion=is_legacy_converter_available()` alongside `allow_excel97=is_binary_xls and is_xls_supported()`.
  - If `insp.is_ole and insp.ole_format == "excel97"` (covers both `.xls/.xlt` and disguised `excel97` `.xlsx`): if `is_legacy_converter_available()`, try `convert_legacy_file_with_progress(path, "xlsx")` -> `read_xlsx(converted_bytes)`; catch non-cancelled/non-encrypted `Exception` and fall back to `read_xls(path)` if `!insp.is_disguised and is_xls_supported()`, otherwise re-raise.
  - Note: In `BaseOfficeWindow.open_file()`, `self.is_read_only_import` should only be set on `do_open` success (keep transactional rollback if UI binding fails).
- In `LecternWindow.do_open()`:
  - Call `insp = self.check_legacy_or_disguised_file(path, "lectern", allow_legacy_conversion=is_legacy_converter_available())`.
  - If `insp.is_ole and insp.ole_format == "powerpoint97"`: convert via `convert_legacy_file_with_progress(path, "pptx")` -> `read_pptx(converted_bytes)` and set `self.is_read_only_import = True` + status bar message.
- Update `StartCenter` open filter to include `*.dot`, `*.xlt`, `*.pps`, `*.pot` alongside `*.doc`, `*.xls`, `*.ppt`.
- Update all 9 locale JSONs for any new strings.

- [ ] **Step 4: Run tests to verify pass**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_legacy_import_modules.py tests/test_start_center_ui.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/ui/shell/quire_window.py src/atboffice/ui/shell/ledger_window.py src/atboffice/ui/shell/lectern_window.py src/atboffice/ui/shell/start_center.py src/atboffice/resources/locale/*.json tests/gui/test_legacy_import_modules.py
git commit -m "feat(shell): wire legacy Office 2003 import across Quire, Ledger, Lectern, and StartCenter"
```

---

### Task 5: Audit Pipeline & Dual-Mode Regression Integration (`deep/audit/core.py` & Issue #294 Tests)

**Files:**
- Modify: `src/atboffice/deep/audit/core.py:166-235,675-715`
- Modify: `tests/gui/test_issue294_legacy_and_abnormal_open.py:150-240`
- Modify: `tests/docs/expectations.json` (add optional `converter_expectations` metadata for `.doc`/`.ppt` or keep `expectations` clean — check how `CorpusExpectations` parses it first!)

**Interfaces:**
- Consumes: `atboffice.vfs.legacy_converter.is_legacy_converter_available`
- Produces:
  - `_probe_legacy_open_outcome` and `audit_real_open_file` reporting `dispatched_format = f"{ext.lstrip('.')}_converted"` (or `"xls_converted"` / `"doc_converted"` / `"ppt_converted"`) and `read_only = True` when imported via converter.
  - Dual-mode assertions in `tests/gui/test_issue294_legacy_and_abnormal_open.py` keyed on `is_legacy_converter_available()`.

- [ ] **Step 1: Read `CorpusExpectations` in `src/atboffice/deep/audit/core.py` and write failing test**

Inspect `CorpusExpectations` in `src/atboffice/deep/audit/core.py` so `expectations.json` schema stays compatible. Add test in `tests/gui/test_issue294_legacy_and_abnormal_open.py` (or a dedicated test `test_audit_probe_reports_converter_mode`) verifying:
- When `ATBOFFICE_CONVERTER_PATH=""` (no converter), all existing 77-file assertions (`imported == 23`, `unsupported_format == 50`, `corrupt == 3`) pass identically.
- When `is_legacy_converter_available()` is `True` (or mocked/real converter), `audit_real_open_file` on a `.doc` and `.ppt` sample returns `outcome == "imported"`, `read_only is True`, `dispatched_format in ("doc_converted", "ppt_converted")`, and `stages["render"] == "ok"`.

- [ ] **Step 2: Run test to verify failure**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_issue294_legacy_and_abnormal_open.py -v`
Expected: FAIL on new converter-mode test.

- [ ] **Step 3: Update `src/atboffice/deep/audit/core.py` and `tests/gui/test_issue294_legacy_and_abnormal_open.py`**

- In `audit_real_open_file`: when `open_ok` and `read_only` is `True`:
  - `ledger`: `"xls_binary"` (if `xlrd` fallback) or `"xls_converted"` (check window attribute `imported_dispatched_format` set by `do_open` so audit never guesses!).
  - `quire`: `"doc_converted"` if `is_read_only_import`, else `"html_or_rtf_disguised"` / `ext`.
  - `lectern`: `"ppt_converted"` if `is_read_only_import`, else `ext`.
- In `test_issue294_legacy_and_abnormal_open.py`:
  - Pin `ATBOFFICE_CONVERTER_PATH=""` via `monkeypatch` on the no-converter 77-file baseline test (so even a developer machine with LibreOffice installed doesn't spuriously fail the no-converter baseline assertions!), AND add a `@pytest.mark.skipif(not is_legacy_converter_available(), reason="requires soffice")` real-converter corpus test verifying `.doc`, `.xls`, and `.ppt` samples import and render end-to-end! (Also verify `test_xml_disguised_as_xls_and_doc_dispatched_via_window_manager` sets `ATBOFFICE_CONVERTER_PATH=""` for its failed-open assertion or tests both modes cleanly.)

- [ ] **Step 4: Run tests to verify pass**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_issue294_legacy_and_abnormal_open.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/deep/audit/core.py tests/gui/test_issue294_legacy_and_abnormal_open.py
git commit -m "feat(audit): support converter-backed legacy open reporting and dual-mode corpus tests"
```

---

### Task 6: B1-a Vendor Pruning, Fetch Manifest & Compliance Guard Scripts

**Files:**
- Create: `scripts/vendor/lo_headless_manifest.json`
- Create: `scripts/vendor/prune_libreoffice.py`
- Create: `scripts/vendor/fetch_lo_headless.py`
- Test: `tests/unit/test_vendor_pruning.py`

**Interfaces:**
- Consumes: TDF official unpacked runtime or hosted pre-pruned archive URLs from `lo_headless_manifest.json`
- Produces:
  - `scripts/vendor/lo_headless_manifest.json`: schema with `libreoffice_version`, `upstream_source_url`, `license` (`"MPL-2.0 / LGPL-3.0+"`), and `platforms` (`macos-arm64`, `linux-x86_64`, `windows-x64`) each with `archive_name`, `url`, `sha256`.
  - `prune_libreoffice_tree(source_root: Path, dest_root: Path, platform_name: str) -> list[str]` (copies runtime, strips banned GPL/desktop-registration/GUI bloat, validates license file presence, returns removed/kept summary or raises `ComplianceError` on banned leftovers).
  - `verify_lo_headless_compliance(root: Path, platform_name: str) -> None` (scans file tree for banned patterns: `poppler`, `xpdfimport`, `pdfimport`, `sdbc_mysql`, `sdbc_mariadb`, `.qlgenerator`, `.mdimporter`, `.desktop`, `CFBundleDocumentTypes` in any plist, `.app` root suffix).
  - `fetch_lo_headless(platform_name: str, dest_dir: Path, *, manifest_path: Path = ..., cache_dir: Path | None = None, local_archive: Path | None = None) -> Path` (downloads or uses cached/local archive, verifies SHA256 strictly, extracts into `dest_dir`, runs `verify_lo_headless_compliance`).

- [ ] **Step 1: Write failing unit tests in `tests/unit/test_vendor_pruning.py`**

Test cases:
- `test_prune_libreoffice_strips_gpl_and_desktop_metadata_and_keeps_licenses(tmp_path)`: builds a mock unpacked LibreOffice directory tree containing `program/soffice`, `program/libpoppler.so`, `program/xpdfimport`, `program/pdfimport.uno.so`, `share/xdg/writer.desktop`, `Resources/en.lproj/`, `Contents/Info.plist` (with `CFBundleDocumentTypes`), `LICENSE`, `NOTICE`; runs `prune_libreoffice_tree(src, dst, "macos-arm64")`; asserts `soffice` and `LICENSE` exist, banned GPL/desktop files are gone, `dst.name != "LibreOffice.app"`, and `verify_lo_headless_compliance` passes.
- `test_verify_lo_headless_compliance_rejects_gpl_or_cfbundle_leftovers(tmp_path)`: plants `libpoppler.dylib` or `Info.plist` containing `CFBundleDocumentTypes`; asserts `verify_lo_headless_compliance` raises `RuntimeError`/`ValueError`.
- `test_fetch_lo_headless_verifies_sha256_and_rejects_mismatch(tmp_path)`: creates a `.tar.gz` archive of compliant dummy `lo_headless`, writes temp manifest with valid vs corrupted SHA256; verifies valid hash extracts and passes compliance, and corrupted hash raises `ValueError` without leaving partial output in `dest_dir`.

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/test_vendor_pruning.py -v`
Expected: FAIL with `ModuleNotFoundError` / missing scripts.

- [ ] **Step 3: Implement `lo_headless_manifest.json`, `prune_libreoffice.py`, and `fetch_lo_headless.py`**

- `lo_headless_manifest.json`: pin exact upstream LibreOffice version (e.g. `24.8.4` or current pinned TDF LTS/Fresh version with exact `downloadarchive.documentfoundation.org` source tarball URL) and placeholder/configured release asset URLs + SHA256 fields (with clear validation in `fetch_lo_headless.py` if SHA256 is unset `"TBD"` unless `--local-archive` is supplied, so incomplete manifests fail loudly during release builds!).
- `prune_libreoffice.py`: CLI supporting `--input`, `--output`, `--platform` (`macos-arm64`, `linux-x86_64`, `windows-x64`), `--smoke-test` (runs `soffice --headless --convert-to` on minimal test files if host OS matches).
- `fetch_lo_headless.py`: CLI & Python API supporting `--platform`, `--dest`, `--local-archive`, `--cache-dir`, SHA256 verification, atomic extraction, and post-extract `verify_lo_headless_compliance()`.

- [ ] **Step 4: Run tests to verify pass**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/test_vendor_pruning.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/vendor/ tests/unit/test_vendor_pruning.py
git commit -m "feat(vendor): add B1-a LibreOffice pruning, fetch manifest, and GPL/metadata compliance checks"
```

---

### Task 7: Nuitka Packaging, Workflows & OSS License Dialog Integration

**Files:**
- Modify: `scripts/build/common.py:1-85`
- Modify: `scripts/build/build_macos.py:190-330`
- Modify: `scripts/build/build_linux.py:49-195`
- Modify: `scripts/build/build_windows.py:49-108`
- Modify: `.github/workflows/release.yml:32-175`
- Modify: `.github/workflows/corpus-audit.yml:44-88`
- Modify: `src/atboffice/ui/dialogs/license_dialog.py:38-340`
- Modify: `src/atboffice/resources/locale/*.json` (license attribution string translations if any)
- Test: `tests/unit/test_build_vendor_integration.py`

**Interfaces:**
- Consumes: `scripts/vendor/fetch_lo_headless.py` (`fetch_lo_headless`, `verify_lo_headless_compliance`), `scripts/vendor/lo_headless_manifest.json`
- Produces:
  - `inject_vendor_converter(target_dir: Path, platform_name: str, *, converter_dir: Path | None = None, allow_missing: bool = False) -> Path | None` (helper in `scripts/build/common.py` called by `build_macos.py`, `build_linux.py`, `build_windows.py`)
  - CLI flags on `build_macos.py`, `build_linux.py`, `build_windows.py`: `--converter-dir` (local pre-extracted `lo_headless` path) and `--allow-missing-converter` (defaults to `False` so missing/unconfigured vendor fails loudly!)
  - `sign_macho_tree(root: Path, identity: str, keychain_path: Path | None)` in `build_macos.py` signing all Mach-O binaries/dylibs inside `vendor/lo_headless` bottom-up before signing `ATBOffice.app`
  - `OSS_COMPONENTS` entries in `license_dialog.py` for `"Document Format Conversion Engine (based on LibreOffice)"` (`MPL-2.0 / LGPL-3.0+`) and `"msoffcrypto-tool"` (`MIT License`)

- [ ] **Step 1: Write failing tests in `tests/unit/test_build_vendor_integration.py`**

Test cases:
- `test_inject_vendor_converter_requires_converter_by_default(tmp_path)`: calling `inject_vendor_converter(tmp_path, "linux-x86_64", converter_dir=None, allow_missing=False)` when manifest has unconfigured URL/`TBD` raises `RuntimeError`; passing `allow_missing=True` returns `None` cleanly.
- `test_inject_vendor_converter_copies_and_verifies_compliance(tmp_path)`: copies a compliant dummy `lo_headless` dir into `tmp_path / "vendor" / "lo_headless"` and fails if a banned file (`poppler`) is present.
- `test_license_dialog_includes_conversion_engine_without_trademark_misuse(qtbot)`: instantiates `LicenseDialog()`, asserts `"Document Format Conversion Engine"` and `"msoffcrypto-tool"` appear in `OSS_COMPONENTS`, `MPL` and `LGPL` appear in license text, and component `name` is not bare `"LibreOffice"`.

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/test_build_vendor_integration.py -v`
Expected: FAIL

- [ ] **Step 3: Implement packaging hooks, workflow updates, and `LicenseDialog` entries**

- `scripts/build/common.py`: add `inject_vendor_converter(...)` using `fetch_lo_headless` or local `--converter-dir`, running `verify_lo_headless_compliance`.
- `scripts/build/build_macos.py`: inject into `app_bundle / "Contents" / "Resources" / "vendor" / "lo_headless"`; update `sign_app_bundle()` to find and `codesign --force --options runtime --timestamp` nested Mach-O `.dylib` / executables inside `vendor/lo_headless` before signing `ATBOffice.app`.
- `scripts/build/build_linux.py`: inject into `appdir / "usr" / "bin" / "vendor" / "lo_headless"`.
- `scripts/build/build_windows.py`: inject into `dist_dir / "vendor" / "lo_headless"`.
- `.github/workflows/release.yml`: add cache + smoke-verification step on packaged artifacts (checking `vendor/lo_headless` exists in unpacked/mounted output and converts minimal `.doc/.xls/.ppt` fixtures).
- `.github/workflows/corpus-audit.yml`: fetch `lo_headless` (or install converter) and set `ATBOFFICE_CONVERTER_PATH` before running `scripts/run_corpus_audit.py`.
- `src/atboffice/ui/dialogs/license_dialog.py`: add `OSSComponent` entries for `"Document Format Conversion Engine (based on LibreOffice)"` (`MPL-2.0 / LGPL-3.0+`, linking to pinned TDF upstream source archive URL) and `"msoffcrypto-tool"` (`MIT License`).

- [ ] **Step 4: Run tests and full test suite verification**

Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/test_build_vendor_integration.py tests/unit/vfs/test_legacy_converter.py tests/unit/vfs/test_ole_detection.py tests/gui/test_base_window_legacy_import.py tests/gui/test_legacy_import_modules.py tests/gui/test_issue294_legacy_and_abnormal_open.py tests/unit/test_vendor_pruning.py -v`
And lint check: `conda run -n ATBOffice ruff check src/atboffice/vfs/legacy_converter.py src/atboffice/vfs/crypto.py src/atboffice/ui/shell/ src/atboffice/ui/dialogs/license_dialog.py scripts/vendor/ scripts/build/`
Expected: PASS with zero ruff errors.

- [ ] **Step 5: Commit**

```bash
git add scripts/build/ .github/workflows/release.yml .github/workflows/corpus-audit.yml src/atboffice/ui/dialogs/license_dialog.py tests/unit/test_build_vendor_integration.py
git commit -m "build: integrate B1-a converter packaging, workflows, and OSS license notices"
```

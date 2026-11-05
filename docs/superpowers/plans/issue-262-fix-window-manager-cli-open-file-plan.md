# Implementation Plan: Fix WindowManager and CLI Document Open Flow (Issue #262)

## Task 1: Write Targeted TDD Tests (Tests First)
- Create `tests/gui/test_window_manager_open_file.py`:
  - `test_window_manager_open_quire_loads_content(tmp_path, qtbot)`:
    - Create a test `.docx` file with non-empty paragraph text using `write_docx`.
    - Call `win = WindowManager.get_instance().open_quire(docx_path)`.
    - Verify `win.current_file_path == docx_path.resolve()`.
    - Verify central canvas `writer_view.canvas_view.doc` contains the expected text.
  - `test_window_manager_open_ledger_loads_content(tmp_path, qtbot)`:
    - Create a test `.xlsx` (or `.csv`) file with cell content.
    - Call `win = WindowManager.get_instance().open_ledger(file_path)`.
    - Verify `win.spreadsheet_view.workbook` has sheets and cell data is populated.
  - `test_window_manager_open_lectern_loads_content(tmp_path, qtbot)`:
    - Create a test `.pptx` file with slide shapes.
    - Call `win = WindowManager.get_instance().open_lectern(file_path)`.
    - Verify `win.presentation_view.presentation` has slides.
  - `test_window_manager_open_file_auto(tmp_path, qtbot)`:
    - Test routing and content loading for all 3 formats.
  - `test_open_corpus_broken_symlink_guidance(tmp_path, qtbot, monkeypatch)`:
    - Create a broken symlink pointing to `.cache/atboffice_corpora/foo.docx`.
    - Verify `open_file` displays guidance to run `python scripts/fetch_corpora.py`.

## Task 2: BaseOfficeWindow Corpus Symlink Guidance
- File: `src/atboffice/ui/shell/base_window.py`
- In `open_file(file_path)`:
  - Check if `Path(file_path)` is a broken symlink (`is_symlink() and not exists()`).
  - Read link target via `os.readlink(file_path)`.
  - If `"atboffice_corpora"` in link target or path:
    - Display `QMessageBox.warning` instructing user to run `python scripts/fetch_corpora.py`.
    - Return `False`.

## Task 3: Window Classes Init Document Loading
- Files:
  - `src/atboffice/ui/shell/quire_window.py`
  - `src/atboffice/ui/shell/ledger_window.py`
  - `src/atboffice/ui/shell/lectern_window.py`
- When `file_path is not None`:
  - If `Path(file_path).exists() or Path(file_path).is_symlink()`:
    - Call `self.open_file(file_path)`.
  - Else:
    - Set `self.current_file_path = Path(file_path).resolve()` and `self.update_window_title()`.

## Task 4: WindowManager Open File Integration
- File: `src/atboffice/core/window_manager.py`
- In `open_quire`, `open_ledger`, `open_lectern`:
  - Pass `file_path=path` to window constructor.
  - If `path is not None`:
    - Ensure `win.open_file(resolved)` has been invoked if not already loaded.
    - Register to `recent_files`.

## Task 5: Verification & Regressions Check
- Run new tests in `tests/gui/test_window_manager_open_file.py`.
- Run full test suite: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`.
- Ensure clean code formatting and linting: `ruff check src/ tests/`.

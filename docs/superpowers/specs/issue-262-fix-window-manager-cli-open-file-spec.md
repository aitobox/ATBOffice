# Design Specification: Issue #262 — Fix WindowManager and CLI Document Open Flow

## 1. Overview & Problem Analysis
When opening files via:
- Command-line interface (`python -m atboffice <file>`, `python -m atboffice ledger <file>`, etc.),
- Start Center ("Open Local File" button, recent document items, template instances), or
- `WindowManager.open_file_auto(path)` / `open_quire(path)` / `open_ledger(path)` / `open_lectern(path)`

The document windows (`QuireWindow`, `LedgerWindow`, `LecternWindow`) currently set `current_file_path` and update the window title, but never execute `win.open_file(path)`. As a result:
- The window displays the file name in the title bar, but the canvas/grid/slide central view remains completely blank (default empty template).
- The document content is never parsed or bound to the document model.
- Additionally, when opening test corpus documents (`tests/docs/full_corpus/...`) without having run `python scripts/fetch_corpora.py`, broken symlinks fail with a generic "File not found" dialog without guidance on how to fetch corpora.

## 2. Architecture & Design Decisions

### 2.1 WindowManager Integration
In `src/atboffice/core/window_manager.py`:
- In `open_quire(path)`: Instantiate `win = QuireWindow(file_path=path)`. If `path` is provided and `win.current_file_path != resolved`: call `win.open_file(resolved)`.
- In `open_ledger(path)`: Instantiate `win = LedgerWindow(file_path=path)`. If `path` is provided and `win.current_file_path != resolved`: call `win.open_file(resolved)`.
- In `open_lectern(path)`: Instantiate `win = LecternWindow(file_path=path)`. If `path` is provided and `win.current_file_path != resolved`: call `win.open_file(resolved)`.
- In `open_file_auto(path)`: Route to the appropriate module window and guarantee content loading.

### 2.2 Window Initialization Hook
In `QuireWindow.__init__`, `LedgerWindow.__init__`, and `LecternWindow.__init__`:
When `file_path is not None`:
- Check `p = Path(file_path)`:
  - If `p.exists() or p.is_symlink()`: invoke `self.open_file(p)` to parse and load the file.
  - If `not p.exists()` and not a symlink (e.g. newly created blank document staged for saving): set `self.current_file_path = p.resolve()` and `self.update_window_title()`.

### 2.3 Broken Corpus Symlink Guidance
In `BaseOfficeWindow.open_file(file_path)`:
Before checking `path.exists()`:
- Inspect `raw_path = Path(file_path)`:
  - If `raw_path.is_symlink() and not raw_path.exists()`:
    - Inspect link target using `os.readlink(file_path)`.
    - If `"atboffice_corpora"` is in the link target or path:
      - Display a helpful `QMessageBox.warning` with i18n text guiding the user to run:
        `python scripts/fetch_corpora.py`
      - Return `False`.
    - Otherwise, display a standard `QMessageBox.critical` stating the file does not exist.

### 2.4 End-to-End Verification
Create end-to-end unit and integration tests verifying:
1. `WindowManager.open_quire(docx_path)` loads paragraphs into `WriterView`.
2. `WindowManager.open_ledger(xlsx_path)` loads cell values into `SpreadsheetView`.
3. `WindowManager.open_lectern(pptx_path)` loads slides into `PresentationView`.
4. `WindowManager.open_file_auto(path)` correctly routes and loads content.
5. Opening a broken test corpus symlink displays the informative prompt guiding to `scripts/fetch_corpora.py`.
6. Zero regressions across the full existing test suite.

## 3. i18n & Localization
All UI prompt text must use `safe_tr(...)` with Chinese and English translations in `safe_tr` dictionary or gettext catalogue.

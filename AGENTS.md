# ATBOffice — Agent Guide

ATBOffice is an office suite in Python 3.12+ and PySide6 (Qt 6) with the look and
behaviour of Office 2003. It has three editors:

| App | Kind | Window class | Model package |
|-----|------|--------------|---------------|
| Quire | Word processor | `ui/shell/quire_window.py` | `modules/writer` |
| Ledger | Spreadsheet | `ui/shell/ledger_window.py` | `modules/spreadsheet` |
| Lectern | Presentations | `ui/shell/lectern_window.py` | `modules/presentation` |

The Start Center (`ui/shell/start_center.py`) opens them. `core/window_manager.py` owns
every open window.

## Set up, run, test

```bash
python -m pip install -e ".[dev]"

python -m atboffice           # Start Center
atboffice-quire               # or atboffice-ledger, atboffice-lectern

QT_QPA_PLATFORM=offscreen pytest -n auto      # whole suite, in parallel
QT_QPA_PLATFORM=offscreen pytest tests/core/test_i18n.py
```

CI (`.github/workflows/ci.yml`) runs, in order, and each must pass:

```bash
ruff check .
ruff format --check .
mypy src/atboffice/core
pytest -n auto
```

## Layout

```
src/atboffice/
├── core/          app, i18n, settings, action registry, undo, recovery, updater, window manager
├── modules/       writer, spreadsheet, presentation, common: models, views, file I/O
├── drawing/       shapes and drawing objects shared by the editors
├── ui/            shell windows, menus, toolbars, dialogs, panes, styles (Luna 2003), icons
├── vfs/ platform/ utils/ deep/
└── resources/     locale catalogs, bundled fonts, spelling dictionaries
tests/             pytest suite; tests/conftest.py holds the shared fixtures
docs/              guides, task plans, design notes
scripts/           build, corpus audit and screenshot tools
```

## File formats

Use the mature libraries, not hand-written parsers:

- OOXML (docx, xlsx, pptx) is read and written with **lxml**, editing the package XML in
  place so parts we do not model survive a round trip.
- Encrypted Office files go through **msoffcrypto-tool**.
- Legacy `.xls` is read with **xlrd**.

Saving must never drop content the user did not touch. Add a round-trip test for any
format change.

## Rules for changes

1. **Text is translated.** Every visible string goes through `safe_tr()` with the
   Chinese source text, and every window or dialog implements `retranslate_ui()`.
   The English for a Chinese source string lives in
   `resources/locale/source/zh-CN_to_en.json`; other languages are keyed by that
   English text in `resources/locale/<locale>.json`. Chinese (`zh-CN`) is the default.
2. **Commands go through the action registry.** Register a command with an
   `ActionSpec` and bind it with `action_registry.set_handler()`. Each editor hides
   the commands it has no handler for, so a menu item without a handler does not
   appear. A handler that raises shows the person a warning.
3. **Edits are undoable.** Document changes go through the window's undo service
   (`core/undo.py`), one bounded history per document.
4. **Use the theme.** Colours come from `ThemeTokens` and the Luna palette in
   `ui/styles/luna_2003.py`; fonts from `ui_font()`. Do not hard-code colours or
   font families in widgets.
5. **No test-only code paths.** Product code never checks `PYTEST_CURRENT_TEST`.
   Tests stub dialogs and file pickers in `tests/conftest.py` or with `monkeypatch`.
6. **Errors are visible or logged.** Do not swallow an exception silently; log it with
   `logger.exception` or tell the person.
7. **Think about the edge cases first:** existing targets, permissions, full disks,
   cancelled operations, long work that would freeze the UI (use a worker thread).
8. Add tests with every change, and keep the suite green.

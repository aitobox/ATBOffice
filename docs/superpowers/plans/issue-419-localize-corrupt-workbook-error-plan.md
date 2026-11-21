# Plan — Issue #419

1. Add `tests/gui/test_issue419_corrupt_workbook_error.py`; confirm 3 of 4 fail on main.
2. Add `_show_unreadable_file_error` in `src/atboffice/ui/shell/base_window.py`; route both
   failure branches through it; log via `logger.exception` / `logger.error`.
3. Add `Open Failed` and the new message key to every `resources/locale/*.json`; remove the
   two old `{path}` keys.
4. Run `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/ -q`.

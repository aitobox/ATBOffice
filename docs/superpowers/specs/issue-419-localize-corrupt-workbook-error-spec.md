# Issue #419 — Localize the corrupt workbook open error

## Problem
`BaseOfficeWindow.open_file` showed `无法打开文件“{path}”：文件已损坏或格式不兼容。\n{exc}`:
the full local path plus the raw (English) parser exception, even in a Chinese UI.
The Chinese key also bypasses the catalog in the English locale (`translate()` returns
the key verbatim for `en`), so English users saw Chinese.

## Design
- One helper, `_show_unreadable_file_error(path)`, used by both failure branches
  (`do_open` returning `False` and `do_open` raising).
- Dialog names the file by `path.name` only; no exception text.
- English source keys (`Open Failed`, `Cannot open "{name}": the file is corrupt or unreadable.`),
  matching the catalog convention, translated in all 9 locale files.
- `logger.exception` keeps the parser diagnostic (with full path) in the logs.
- Rollback: Ledger already parses into a candidate workbook, so a rejected file leaves the
  open workbook untouched; covered by a regression test.
- Removed the two now-unused Chinese keys from the locale files.

## Tasks
- [x] Regression tests (zh-CN text, English text, logging, workbook preserved, `do_open`→False)
- [x] Shared localized error helper in `base_window.py`
- [x] Translations in all locales; drop orphaned keys
- [x] Full test suite

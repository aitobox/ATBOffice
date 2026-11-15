# Plan: Issue #375

1. Write `tests/test_ledger_comments.py` (reader strip, palette-independent color, black text,
   single author layout via recording QPainter, red triangle, right/bottom flip, no tooltip). Verify that it fails.
2. `io/xlsx_reader.py`: add `_strip_author_prefix`, apply in `_parse_worksheet_comments`.
3. `views/grid_viewport.py`: `_COMMENT_NOTE_BG`, `_comment_callout_rect`, brush reset, flipped
   leader base, drop comment `QToolTip.showText`.
4. Run `pytest tests/test_ledger_comments.py` then the full suite.

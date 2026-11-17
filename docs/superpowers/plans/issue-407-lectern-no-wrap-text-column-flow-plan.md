# Plan: Issue #407

1. Add tests in `tests/test_lectern_text_defaults.py`:
   - `test_nowrap_text_overflows_box`: render tdf104722 subtitle into an image
     larger than the box; assert ink exists right of the text rect.
   - `test_columns_balance_tdf140852`: helper computes per-column text; assert
     column 2 starts with "comes to".
   - `test_columns_balance_rtlcol_third_column`: column 3 contains "Insert".
   - `test_rtl_col_reverses_column_order`: ink of first column appears on the right.
   Verify: they fail before the fix.
2. In `text_editor.py`, extract `_balanced_column_height(doc, col_w, avail_h, cols)`
   and use it in `render_static_text`; skip clip for no-wrap.
   Verify: new tests pass.
3. `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest
   tests/test_lectern_text_defaults.py tests/gui/test_phase9_pptx_autofit.py`
   then wider presentation suites.

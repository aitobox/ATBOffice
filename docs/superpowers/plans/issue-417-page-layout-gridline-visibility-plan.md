# Plan: Issue #417

1. Add tests in `tests/gui/test_phase7_xlsx_render.py`. Confirm that they fail on `main` (missing `default_fill_at` and gridlines visible).
2. Change `models/sheet_model.py` to add `row_fills`, `col_fills` and `default_fill_at`.
3. Change `io/xlsx_reader.py` to populate the fills from the `<col style>` and `<row s customFormat>` deltas.
4. Change `views/grid_viewport.py` to collect and fill empty cells that inherit a default fill.
5. Verify with `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_xlsx_render.py` (11 passed), then run the full suite and recapture the fixture.

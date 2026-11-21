# Plan: Issue #416 — Align imported worksheet row and column geometry

1. Add tests to `tests/modules/spreadsheet/test_xlsx_reader.py` (ht rounding, defaults vs
   custom overrides, writer round-trip) and `tests/gui/test_phase7_xlsx_render.py` (fixture
   boundaries in the grid). Run -> expect the ht rounding / round-trip tests to fail.
2. `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`: use `pt_to_px` for row `ht`.
3. `src/atboffice/modules/spreadsheet/io/xlsx_writer.py`: write `ht` as `px * 0.75`.
4. Verify: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest
   tests/modules/spreadsheet tests/gui/test_phase7_xlsx_render.py -q`.

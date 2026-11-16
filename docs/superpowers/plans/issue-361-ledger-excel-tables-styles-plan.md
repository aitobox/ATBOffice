# Plan: Issue #361 — Excel tables & table styles

TDD order; test file `tests/test_ledger_tables.py`.

1. **Model** — add dataclasses to `models/sheet_model.py`; test `table_at` bounds.
   `pytest tests/test_ledger_tables.py -k model`
2. **Style engine** — `models/table_style.py`; tests: Medium9 header = accent1, band1 =
   tint(accent1, 0.6), Light8 header = black fill + white bold font, header/total precedence,
   custom style with `patternType=none` ignored. `pytest -k style`
3. **Reader** — `_parse_styles` stores `workbook.extra["table_styles"]` and dxf borders;
   `_parse_worksheet_tables` resolves `tablePart` rels. Tests on fixtures XMLMap,
   totalsRowShown, tablerefsnamed, totalsRowFunction. `pytest -k read`
4. **Renderer** — `_collect_pane_items` includes table cells; merge table style into CF result;
   borders; filter buttons. Offscreen QImage render tests sample pixels (C6 header fill,
   rows 7/8 bands, A1/B1 black header, filter arrow pixels). `pytest -k render`
5. **Round-trip** — `write_xlsx(read_xlsx(f))` with and without a dirty edit keeps table part
   count and `tableStyleInfo`. `pytest -k roundtrip`
6. Full suite: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/ -q`

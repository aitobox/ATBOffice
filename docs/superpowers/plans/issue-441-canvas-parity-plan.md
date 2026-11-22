# Plan: Issue #441

1. Baseline: `scripts/run_office_diff.py --all --capture` on main; rank by app and category.
2. Ledger: `grid_viewport.py` (headers, colours, selection), `view.py` (layer re-sync),
   `excel_units.py` (Calibri mdw). Re-measure Excel.
3. Lectern: `workspace.py` (notes pane), `slide_canvas.py` (shadow). Re-measure PowerPoint.
4. SmartArt: `pptx_reader.py` (`_diagram_color_style`, theme slots), `smartart/palettes.py` (theme spec).
5. Tests: `tests/gui/test_phase11_canvas_parity.py`; update tests hard-coding the 46x22 headers.
6. Full `--all --capture --strict` diff, full pytest, ruff.

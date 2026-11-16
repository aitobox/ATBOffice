# Plan: Issue #379 — Quire charts, SmartArt and caption lines

Test command: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_quire_strict.py -q`

## Chunk 1 — Strict line spacing (TDD)
- Test: `libreoffice__strict.docx` default paragraph spacing line ≈ 12.95*20/240; page 1 holds
  header, `Hello world!`, the chart line and the SmartArt caption in that vertical order.
- Fix `docx_reader.py` `spacing` parsing: unit value + `lineRule="auto"` → pt / 12.

## Chunk 2 — Charts
- `models/drawing.py`: `ChartItem(PictureItem)` with `chart`; export from `models/__init__.py`.
- `io/docx_graphics.py`: `read_chart(xml_bytes)` (normalize Strict, parse, auto title).
- `docx_reader._parse_drawing_shape`: `chart` content → `ChartItem`.
- Test: chart item has 3 values; render region contains three bars (columns of the series color).

## Chunk 3 — SmartArt drawing
- `docx_graphics.py`: `smartart_from_drawing(root, w, h, theme)` → group `ShapeItem`;
  `dml_text_story(txBody)` → `Story` of writer paragraphs.
- Reader resolves `dataModelExt/@relId`, falls back to a `diagramDrawing` rel.
- Tests: strict diagram has a filled ellipse painted in accent1; tdf54095 paints three outlined
  boxes and never the placeholder.

## Chunk 4 — SmartArt from data model
- `smartart_from_data(dm_root, layout_id, w, h, theme)`; unit test with a synthetic data part.

## Chunk 5 — Painting
- `canvas_view._paint_picture`: `ChartItem` → `ChartPainter.paint_chart` (scaled for screen).

## Chunk 6 — Verify
- Non-overlap / order test for AC1, full suite, lint (ruff) on touched files.

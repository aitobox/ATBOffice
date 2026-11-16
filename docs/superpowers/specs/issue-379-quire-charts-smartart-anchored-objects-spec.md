# Spec: Issue #379 — Quire shows charts, SmartArt and their caption lines

## Problem
`DocxReader._parse_drawing` turns `c:chart` and `dgm:relIds` graphic frames into a bare
`PictureItem` with no image, so the canvas paints a gray "Diagram 1" placeholder (or nothing
visible). In `libreoffice__strict.docx` everything after `Hello world!` is also pushed onto later
pages: Strict OOXML writes `w:spacing w:line="12.95pt" w:lineRule="auto"`, and the reader took the
point value as a line multiplier (12.95 lines), so every line was ~233pt tall. The header and body
looked displaced for the same reason.

## Design (autonomous decisions, >= 90% confidence)
1. **Strict line spacing** — for `lineRule="auto"` a unit value (`12.95pt`) is a twips measure in
   240ths of a line: multiplier = pt * 20 / 240. Exact/atLeast keep the point value. This fixes the
   header height and the vertical order of the body (header distance was already honored).
2. **Chart model** — `ChartItem(PictureItem)` (`t="chart"`) carries a parsed
   `presentation.chart.model.ChartData`. Subclassing keeps layout, wrapping, selection and the
   verbatim `raw_xml` round-trip unchanged.
3. **Chart reading** — `c:chart r:id` → chart part (via current relationships) → Strict namespaces
   normalized → shared `parse_chart_xml`. A `c:title` without text on a single-series chart uses the
   series name (Office auto title). Unreadable chart parts keep the old `PictureItem` fallback.
4. **SmartArt reading** — follow the data part's `dsp:dataModelExt/@relId` to the stored drawing
   (`diagrams/drawing*.xml`), falling back to any `diagramDrawing` relationship. Each `dsp:sp`
   becomes a child `ShapeItem` of a group `ShapeItem` (geometry, fill, outline via the shared
   `drawing.shape_style` helpers, rotation, DrawingML text from `dsp:txBody` as writer paragraphs,
   text rectangle from `dsp:txXfrm`). Without a stored drawing, lay the data model out like the
   original (`smartArtFromData`): process row, cycle ring, hierarchy rows, or a list column.
5. **Painting** — `ChartItem` painted with the shared `ChartPainter` (screen + vector/print paths go
   through `_paint_picture`). SmartArt reuses the #365 shape painter, so no placeholder.
6. New code lives in `io/docx_graphics.py` to keep `docx_reader.py` from growing further.

## Out of scope
Theme font resolution (#372), chart editing, writing modified charts/diagrams back (raw XML
round-trip is unchanged), SmartArt relayout/editing in Quire.

## Task list
- [ ] Task 1: Strict `w:line` unit values with `lineRule="auto"` become line multipliers + test
- [ ] Task 2: `ChartItem` model and chart reading from the chart relationship (Strict + transitional)
- [ ] Task 3: SmartArt group from the stored diagram drawing, DrawingML text as paragraphs
- [ ] Task 4: SmartArt fallback layout from the data model when no drawing is stored
- [ ] Task 5: Paint charts with the shared ChartPainter (screen + vector)
- [ ] Task 6: Fixture tests `tests/test_quire_strict.py` for the three acceptance criteria + full suite
- [ ] Task 7: grill-me audit

# Plan: Issue #370 — Lectern table styles

1. Write failing tests in `tests/test_lectern_table_styles.py` for the two fixtures
   (fills, text colors, bold), unknown-id fallback, merges, round trip.
   → verify: `pytest tests/test_lectern_table_styles.py` fails.
2. Add `src/atboffice/modules/presentation/io/pptx_table_styles.py` (catalog + resolve + apply).
3. Wire into `pptx_reader.py` (`read()` catalog load, `_parse_graphic_frame` table branch;
   allow `lnL/lnR/lnT/lnB` in `_parse_line`).
4. Update `views/shape_item.py::_paint_table` for spans and borders.
5. Update `io/writer_shapes.py::table_to_xml` and `pptx_writer.py` tableStyles copy.
   → verify: new tests pass; full suite has no new failures.

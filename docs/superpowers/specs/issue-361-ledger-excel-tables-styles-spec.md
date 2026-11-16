# Spec: Issue #361 — Ledger reads Excel tables, applies table styles, draws filter buttons

## Problem
`xl/tables/table*.xml` parts are never read. Header bands, banded rows, totals rows
and table filter buttons are missing, so tables render as plain grids.

## Design (ported from `ledger/js/xlsx-read.js:readTable`, `ledger/js/styles.js`, `ledger/js/grid.js:syncWidgets`)

### Model (`models/sheet_model.py`)
- `TableStyleInfo(name, show_first_column, show_last_column, show_row_stripes, show_column_stripes)`
- `TableColumn(id, name, totals_row_function, totals_row_label)`
- `Table(id, name, display_name, ref, r1, c1, r2, c2, header_row_count, totals_row_count,
  style_info, columns, has_auto_filter, part, spec)`; `has_header` / `has_totals` properties.
- `SheetDataModel.tables: list[Table]` and `table_at(r, c)`.

### Style engine (`models/table_style.py`, new)
- `TableStylePart(fill, font_color, bold, borders)` and `TableStyleSpec` (whole, header,
  total, band1/band2, col_band1/col_band2, first_col, last_col, inner_h, inner_v).
- `builtin_table_style(name, theme_colors)`: Light/Medium/Dark 1–28 families exactly as the
  original (accent = `(n-1) % 7`, 0 = dk1 gray family, tints 0.8/0.6/0.4).
- `custom_table_style(name, custom_styles, dxfs)`: dxf-based `<tableStyle>` from styles.xml;
  `patternType="none"` fills are ignored.
- `resolve_table_style(...)`: custom first, then built-in; unknown name → `None`.
- `table_style_at(sheet, r, c) -> TableCellStyle | None`: whole-table outline + inner lines,
  row/column stripes (data rows only), first/last column, header, totals — same precedence
  as the original `TS.at`.

### Reader (`io/xlsx_reader.py`)
- Parse `<tableStyles>` and dxf borders / pattern type from styles.xml.
- For each `<tablePart r:id>` in a worksheet resolve the rel, parse the table part
  (`ref`, `headerRowCount` default 1, `totalsRowCount`, `tableStyleInfo`, `tableColumns`,
  `autoFilter`), resolve the style spec with the workbook theme, append to `sheet.tables`.
- Malformed / missing parts or refs are skipped silently (never abort the workbook load).

### Renderer (`views/grid_viewport.py`)
- Cells inside a table are painted even when no `CellData` exists.
- Table style merges under conditional formatting and direct cell formatting:
  fill only when the cell has no own fill (cell-level fill overrides the band);
  font colour only when the cell has none; bold OR-ed; borders fill missing sides.
- Filter buttons (▾, same bevel button as the sheet AutoFilter) on every header cell of a
  table with `<autoFilter>` and a header row.

### Writer
- Table parts and sheet rels are already carried from the source package; verified by tests
  (clean and dirty save keep `tableStyleInfo` and the table part count).

## Out of scope
Table editing UI, structured references, totals-row formula evaluation, writing new tables.

## Task checklist
- [x] Task 1: Table / TableStyleInfo / TableColumn model + `SheetDataModel.tables`, `table_at`
- [x] Task 2: Style engine (built-in + custom dxf styles, `table_style_at`) with unit tests
- [x] Task 3: Reader: tableStyles, dxf borders, table parts per sheet
- [x] Task 4: Renderer: table fills/fonts/borders + table filter buttons
- [x] Task 5: Round-trip tests (clean + dirty) keep table parts and tableStyleInfo
- [x] Task 6: Acceptance tests for the 4 fixtures; full test suite passes
- [x] Task 7: grill-me audit

## Audit notes (grill-me)
- Pre-existing bug fixed: the AutoFilter button loop leaked the arrow brush, so every button
  after the first was painted solid black. Brush is now reset per button.
- Cells whose font colour equals the workbook default font (cellXfs[0]) take the table font
  colour, as in Excel; otherwise header text rendered black on black.
- Known limitations (outside this subtask): table filter buttons are drawn but clicking them
  does not open the filter dropdown; a table font colour overrides a number-format colour
  such as `[Red]`; row/column insertion does not shift tables; a dirty save regenerates
  `styles.xml`, so custom `<tableStyles>` are not written back (table parts are).

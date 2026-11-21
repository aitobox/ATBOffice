# Issue #417: Match gridline visibility in worksheet page layout view

## Root cause
`poi__45540_form_Header.xlsx` (stored `view="pageLayout"`, gridlines not disabled) gives every
column a default style (`<col ... style="3">`, including `min=16 max=16384`). Style 3 has a solid
white fill (`fgColor indexed="9"`). In Excel and in .vibeoffice (`ledger/js/render.js`, items
collection plus `styleOf` row → column fallback), empty cells inherit that fill, which covers the
gridlines. ATBOffice applied column/row default styles only to cells present in `<sheetData>`, so
empty cells painted bare gridlines.

The page layout view itself is not the cause. The view state already round-trips. The paint rule
for empty cells was missing.

## Design
- `SheetDataModel.row_fills: dict[int, str]` and `col_fills: list[(c1, c2, color)]` store the solid
  fills of `<row s customFormat="1">` and `<col style>`. `default_fill_at(r, c)` resolves row
  first, then the last matching column range, which matches Excel and the reference precedence.
- `xlsx_reader` records these fills when it parses column ranges and rows, using the resolved
  `FormatDelta.bg_color`.
- `GridViewport._collect_pane_items` keeps empty cells that inherit a fill, and
  `_paint_cell_item_fill` falls back to `default_fill_at` for those cells, including an empty
  merge anchor.

## Edge cases
- Sheets without default fills behave as before, and their gridlines stay.
- `showGridLines="0"` is unchanged.
- Stored cells keep their own resolved fill, which already included the column or row style.
- Out of scope: shifting `row_fills`/`col_fills` on insert/delete. Column widths and hidden flags
  do not shift either. Writing `<col style>` on export is also out of scope.

## Task list
- [x] Task 1: Model row/column default fills with `default_fill_at`
- [x] Task 2: Record fills in the XLSX reader
- [x] Task 3: Paint inherited fills for empty cells in the grid
- [x] Task 4: Regression tests for the fixture (pageLayout) and a control sheet with gridlines kept
- [x] Task 5: Full suite and visual recapture

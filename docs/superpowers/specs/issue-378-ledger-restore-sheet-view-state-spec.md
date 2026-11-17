# Spec: Restore saved sheet view state (Issue #378, TASK-DOC-L04)

## Problem
`_parse_worksheet` reads only `zoomScale` and the frozen pane from `<sheetView>`.
Active cell, selection, gridline visibility, view mode, scroll origin and stored
page breaks are dropped, and the writer emits a bare `<sheetView>`.

## Reference
`.vibeoffice/public/ledger/js/xlsx-read.js:591-620` — `showGridLines`, `zoomScale`,
`view` (`pageBreakPreview` uses `zoomScaleSheetLayoutView` when present),
`topLeftCell`, and the `<selection>` that matches the pane's `activePane`
(falling back to the last selection).

## Design
- **Model** (`sheet_model.py`): new `SheetViewState` dataclass held by
  `SheetDataModel.view_state`: `active_cell`, `sqref`, `show_grid_lines`,
  `zoom_scale`, `view`, `top_left_cell`, `row_breaks`, `col_breaks`.
  Pure-model helpers: `selection_ranges()` parses `sqref` (space-separated,
  multi-range), `active_cell_rc()`.
- **Reader**: fill `view_state` from `<sheetView>`, `<selection>`, `<rowBreaks>`,
  `<colBreaks>`. `extra["zoom"]` is still set (existing consumer).
- **Selection**: `SpreadsheetView` seeds each sheet's `SelectionModel` from
  `view_state` when first created, and writes later selection changes back into
  `view_state` so save keeps the current selection.
- **Viewport**: skip gridline drawing when `show_grid_lines` is false; on the first
  display of each sheet apply `view` (`pageBreakPreview` -> `page_break`, no
  welcome dialog) and scroll to `topLeftCell`. Page-break preview uses stored
  `rowBreaks`/`colBreaks` as page boundaries, with the fixed page size as fallback.
- **Writer**: emit `showGridLines="0"`, `view`, `zoomScale`, `topLeftCell` and a
  `<selection>` element; emit `<rowBreaks>`/`<colBreaks>` in schema order.

## Edge cases
- Malformed/out-of-range `activeCell`/`sqref`: ignored, defaults to A1.
- Active cell outside `sqref`: kept as given (Excel allows it only inside; we do not crash).
- `zoomScale` non-numeric or 0: ignored; clamped by `set_zoom` (10%-400%).
- Frozen panes with several `<selection pane=...>`: pick the one matching `activePane`.
- `topLeftCell` inside the frozen area: no scroll.
- Sheet switching must not re-apply view mode / scroll after the first display.

## Out of scope
Writing `<pane>` freeze state (writer never wrote it); `pageLayout` rendering
(the value is kept and round-tripped, displayed as normal view).

## Task list
- [x] Task 1: `SheetViewState` model + sqref/active-cell helpers
- [x] Task 2: Reader parses sheetView/selection/breaks
- [x] Task 3: Writer round-trips view attributes and breaks
- [x] Task 4: Selection seeded from and synced back to view state
- [x] Task 5: Viewport hides gridlines, applies view mode and topLeftCell, uses stored breaks
- [x] Task 6: Tests (`tests/test_ledger_sheet_view.py`) + full suite pass
- [x] Task 7: grill-me audit

## Audit notes
- Files opened from a source package keep their original `<sheetViews>` via part
  carry (only `<sheetData>`/`<dimension>` are patched), so the round trip is
  byte-faithful; selection changes made after opening are persisted only by the
  full serializer path (new workbooks).
- Template `extra["show_grid"]`/`extra["initial_selection"]` remain unconsumed
  (pre-existing, out of scope).

# Spec: Issue #439 — Ledger focus theft, null-cell formatting, selection wiring

## Design
1. **Object layer** — `SpreadsheetObjectLayer` uses `NoFocus` and takes focus explicitly only when a
   floating object is clicked. Clicking empty space hands focus back to the owning grid. Key handling
   uses `QKeySequence.StandardKey` and acts only while an object is selected (Delete, Copy, Paste,
   Escape). Every other key is forwarded to the grid, so typing, navigation and cell copy/paste work.
2. **Null cells** — `SheetDataModel.ensure_cell(r, c)` returns or creates a `CellData`. The 13 Ledger
   and 5 MainWindow formatting/format-painter sites use it, and active-cell reads fall back to `CellData()`.
   MainWindow's range lookup (`bounding_box`) and viewport refresh (`spreadsheet_view.viewport`) used
   APIs that do not exist; they now use `primary_range` and `grid.viewport()`.
3. **Selection wiring** — `SpreadsheetView.selection_changed` / `active_cell_changed` re-emit the
   active sheet's `SelectionModel` signals. The forwarding is moved (never duplicated) on sheet switch
   and workbook load. Ledger and MainWindow connect to the view signals.
4. **Grid hardening** — `GridViewport.mouseMoveEvent` ignores events without a model or selection and
   cancels drags that have no recorded origin. A sheet switch clears hover/tooltip state and the
   object-layer selection.

## Task list
- [x] Task 1: Object layer focus policy + key forwarding + QKeySequence fix
- [x] Task 2: ensure_cell helper applied across Ledger/MainWindow formatting
- [x] Task 3: View-level selection signals with safe re-wiring
- [x] Task 4: GridViewport mouseMoveEvent / sheet-switch hardening
- [x] Task 5: Regression tests + full suite + review

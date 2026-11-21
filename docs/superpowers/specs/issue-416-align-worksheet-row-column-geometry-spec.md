# Spec: Issue #416 — Align imported worksheet row and column geometry

## Findings
- At current `main`, `libreoffice__cell-value.xlsx` already parses to the reference geometry:
  MDW 7 (Arial 10), columns `width="11.67"` -> 82 px, rows `ht="12.8"` -> 17 px, and the
  grid renders those sizes at 100% zoom (measured with `device_cell_rect`). The audit capture
  (at `3097f75`) predates the sheet-zoom fix in #430.
- One real conversion defect remains: row `ht` is converted with `int(pt * 1.33)`, which
  truncates and under-sizes rows against the reference `M.ptToPx = round(pt * 96 / 72)`
  (e.g. `ht="15"` -> 19 px instead of 20 px; the error grows with height).
- The writer encodes the inverse as `(px + 0.1) / 1.33`; with a corrected reader it must
  become the exact inverse `px * 0.75` so tall rows still round-trip.

## Design
- Reader: `ht_px = round(pt * 96 / 72)` via the existing `pt_to_px` helper.
- Writer: `ht = px * 0.75` (exact; every px maps to a multiple of 0.25 pt).
- No change to column-width math (already the reference formula).

## Task list
- [ ] Task 1: Regression tests — fixture row/col boundaries within 2 px (model + grid)
- [ ] Task 2: Regression tests — `ht` conversion rounding; custom row/col sizes override defaults
- [ ] Task 3: Fix reader `ht` conversion to `round(pt*96/72)`
- [ ] Task 4: Make writer `ht` the exact inverse; round-trip test for tall rows
- [ ] Task 5: Run spreadsheet suites, grill-me audit

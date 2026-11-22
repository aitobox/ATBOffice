# Spec: Issue #441 — Canvas parity (Ledger headers, Lectern workspace, SmartArt theme colours)

## Measurement first
A fresh `run_office_diff.py --all --capture` on `main` scored **74.78%** foreground similarity
(Word 91.1%, Excel 50.1%, PowerPoint 82.8%; 25 CRITICAL). Word already had no critical drift, and its
33px page-top offset is tuned to the baseline captures, so Quire geometry was left unchanged. The
systematic gaps were in Ledger and the Lectern workspace.

## Design
- **Ledger grid (ledger/js/render.js)**: the row header width follows `RD.frame`, max(25, last visible
  row number + 10px), and grows with more digits. The column header height is max(17, default row
  height). Headers use the white→#E4ECF7 gradient (selected #FFE7A2→#F8C55E) with centred Arial 10pt
  labels. Gridlines are #C0C0C0 and the active-cell border is black. Single-cell selections are not
  shaded, and the active cell stays white inside a shaded range. Header changes re-sync the
  floating-object layer.
- **Excel column widths**: Calibri 11 measures 8px per digit in the reference renderer
  (`L.measureDigit`), so custom widths use mdw=8.
- **Lectern workspace (lectern/index.html)**: the notes pane defaults to 92px with a 5px splitter,
  has no caption or frame, a 12px Arial body and the localized "Click to add notes" placeholder.
  The slide drop shadow is a hard 3px #59657C.
- **SmartArt import (lectern/js/smartart-io.js, diagram.js)**: Office `csTypeId`/`qsTypeId` map to
  `accentN`/`colorful` and the intense/moderate/subtle styles. Diagrams are coloured from the file's
  theme (accent/dk/lt slots) instead of the built-in "ocean" palette.

## Task list
- [x] Task 1: Baseline measurement and gap analysis
- [x] Task 2: Ledger header geometry/colours, selection shading, Calibri digit width
- [x] Task 3: Lectern notes pane, splitter and slide shadow
- [x] Task 4: SmartArt theme colours and quick styles for imported diagrams
- [x] Task 5: Regression tests, full diff re-run (>= 90%, 0 CRITICAL) and full suite

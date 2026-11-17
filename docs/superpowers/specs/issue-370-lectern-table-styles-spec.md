# Spec: Issue #370 — Apply PowerPoint table styles from tableStyles.xml

## Problem
`_parse_graphic_frame` keeps only the grid, row heights and cell text. `tableStyleId`,
`tblPr` flags, cell `tcPr` fills/borders and merge attributes are dropped, so styled
tables render as black text on white with a fixed gray grid.

## Design (ported from `lectern/js/pptx-read.js:832-837, 1393-1530`)
1. **Style catalog** — `PptxReader.read()` loads `tableStyles.xml` (presentation rel of
   type `tableStyles`, fallback `ppt/tableStyles.xml`) into `{STYLE_ID: <a:tblStyle>}` plus
   the `def` id. A malformed part is recorded as a `LoadWarning`, never a crash.
2. **Style resolution** (`io/pptx_table_styles.py`, new submodule):
   - id in catalog → parse parts `wholeTbl, band1H, band2H, band1V, band2V, firstCol,
     lastCol, firstRow, lastRow` into `{fill, bd{left,right,top,bottom,insideH,insideV}, tx{b,i,color}}`.
   - known built-in id (Table Grid, No Style/No Grid, Medium Style 2 accents) → synthesized parts.
   - unknown id → the catalog's `def` style (catalog element or built-in); still nothing → unstyled.
   - Results cached per (id, theme).
3. **Application** — parts applied in increasing precedence: wholeTbl, band V, band H,
   lastCol, firstCol, lastRow, firstRow (band ranges exclude first/last row/col when flagged).
   Cell `tcPr` fill/borders (own) always win. Text color applies to runs without color;
   bold/italic set when the style turns them on. Table-style text color takes precedence over
   master `otherStyle` defaults, which are applied afterwards.
4. **Cell model** (`tbl["rows"][i]["cells"][j]`): `fill` `{"t":"solid","c","a"}` or `{"t":"none"}`,
   `bd` `{l,r,t,b: {"c","w","dash"}}`, `gs`/`rs` spans, `hm`/`vm` continuation flags,
   `own` `{fill: bool, bd: [sides]}` for lossless writing. Table keeps `style_id` and flags.
5. **Rendering** — merged origin cells span `gs` columns × `rs` rows; `hm`/`vm` cells are
   skipped, so fills are painted once. Borders drawn per side; unstyled tables without any
   border keep the legacy light-gray grid.
6. **Round trip** — writer emits `tblPr` flags + `tableStyleId`, own `tcPr` fill/borders,
   `gridSpan/rowSpan/hMerge/vMerge`, and copies the source `ppt/tableStyles.xml` instead of
   the empty default list.

## Edge cases
- Missing `tableStyles.xml`, unknown style id, empty `tblPr`, ragged rows (fewer cells than
  grid columns), `lnRef`/`fillRef` theme references, `noFill` in tcPr (own "none" fill),
  style part with empty `tcTxStyle`.
- Known limitation: an explicit `b="0"` in a run cannot be told apart from an unset bold, so a
  style that turns bold on also bolds such runs (TextRun has no tri-state bold).

## Task list
- [x] Task 1: Table-style submodule (catalog parse, built-ins, part resolution, application)
- [x] Task 2: Reader integration (catalog load, tblPr flags, tcPr fill/borders, merges)
- [x] Task 3: Renderer: fills, per-side borders, merged-cell spans
- [x] Task 4: Writer round trip (tblPr, tcPr, merges, tableStyles.xml)
- [x] Task 5: Tests `tests/test_lectern_table_styles.py` + full suite
- [x] Task 6: grill-me audit

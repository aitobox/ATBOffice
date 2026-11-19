# Design Spec: Issue #414 — Correct Inflated Nested Table Heights on Word Import

- **Issue**: [#414](https://github.com/aitobox/ATBOffice/issues/414) (`[Quire] Correct inflated nested table heights on Word import`)
- **Parent Epic**: #406 (Step 8 of 13)
- **Branch**: `agent/issue-414-correct-inflated-nested-table-heights`

## 1. Problem Statement & Root Cause Analysis

Opening `tests/docs/word/docx/libreoffice__tdf131260.docx` produces an outer table height of `335.72 pt` (`447 px` at 96 DPI) in ATBOffice versus `192.00 pt` (`256 px` at 96 DPI) in `.vibeoffice` — an inflation of `191 px`, with both the middle and innermost nested tables inheriting vertical drift and mispositioned text.

Root cause tracing across `word/document.xml`, `word/styles.xml`, `docx_reader.py`, `styles.py`, `portions.py`, and `table_layout.py` reveals four compounding defects:

1. **Explicit zero/auto `<w:spacing>` overrides are lost during style merging (`properties.py`, `docx_reader.py`, `styles.py`)**:
   - `docDefaults` sets `w:after="200"` (`10 pt`) and `w:line="276"` (`1.15x`).
   - Both the `TableGrid` table style and the direct `<w:pPr>` on the innermost `"Table"` paragraph explicitly declare `<w:spacing w:after="0" w:line="240" w:lineRule="auto"/>`.
   - `SpacingProperties` had no explicit-field tracking, so `merge_p_props()` skipped any override whose numeric value happened to match the dataclass default (`0.0`, `1.0`, `"auto"`). Every cell paragraph therefore inherited `after=10.0 pt` and `line=1.15x`.

2. **Table style `<w:pPr>`, `<w:rPr>`, and `<w:tblCellMar>` are not cascaded into cell paragraphs (`docx_reader.py`, `table_layout.py`, `styles.py`, `portions.py`)**:
   - `resolve_table_style_props()` only resolved `borders` and `ind`, ignoring table style `p_pr`, `r_pr`, and `tblCellMar`.
   - `layout_table()` never passed table style context to `layout_paragraph()`, and `resolve_p_props()` / `resolve_r_props()` ignored their `context` argument.
   - As a result, the 12 empty paragraphs inside the outer and middle `TableGrid` tables never received `TableGrid`'s `after=0, line=1.0`, inflating the outer table by ~145 pt (~193 px).

3. **`<w:trHeight w:val="..."/>` with omitted `w:hRule` defaulted to `"auto"` instead of `"atLeast"` (`docx_reader.py`)**:
   - Per ECMA-376 §17.4.80 and `.vibeoffice` (`docx-read.js:1042`), omitting `w:hRule` on `w:trHeight` means `"atLeast"`.
   - The innermost table in `tdf131260.docx` has `<w:trHeight w:val="570"/>` (`28.5 pt`) and `vAlign="bottom"`. Because `h_rule` defaulted to `"auto"`, `layout_table()` ignored `tr_pr.h`, shrinking the row to `25.44 pt` and placing `"Table"` at the top (`content_offset_y=0.0`) instead of the bottom.

4. **Empty paragraph mark font metrics ignored resolved document/table defaults (`portions.py`)**:
   - `layout_paragraph()` read `p.mark` / raw `p.r_pr` (defaulting to `Times New Roman 12pt`) instead of resolving via `resolve_r_props(d, p, None, context=table_context)` (matching `.vibeoffice` `render.js:218`).

## 2. Approaches Considered

- **Approach A (Recommended)**: Fix the root causes directly across the cascade pipeline:
  1. Add `*_explicit` flags (`repr=False, compare=False`) on `SpacingProperties` and `TableProperties.cell_mar_explicit`, populate them in `DocxReader._parse_p_pr()` and `_parse_table()` / `_parse_styles()`, and honor them in `merge_p_props()`.
  2. Parse table style `tblCellMar` in `DocxReader._parse_styles()`, resolve `p_pr`, `r_pr`, and `cell_mar` in `resolve_table_style_props()`, and pass per-table context (`{"tbl_p_pr": ..., "tbl_r_pr": ...}`) into `layout_paragraph()` / `decompose_paragraph_to_portions()` / `resolve_p_props()` / `resolve_r_props()` following Word/LibreOffice/`.vibeoffice` precedence (`doc.defaults < table style < non-default paragraph style < direct`, with table style overriding the default paragraph style's own properties).
  3. Default `w:trHeight`'s omitted `w:hRule` to `"atLeast"` when `w:val` is present.
  4. Resolve empty paragraph mark metrics via `resolve_r_props(d, p, None, context=table_context)`.
  - *Trade-off*: Clean, principled, matches `.vibeoffice` and ECMA-376, fixes both `tdf131260.docx` and all other Word tables relying on table-style spacing or `trHeight`.
- **Approach B (Rejected)**: Special-case zeroing `space_after` inside `layout_table()`.
  - *Why rejected*: Breaks tables whose styles or paragraphs legitimately specify non-zero `space_after`, fails to fix `line=1.0` overrides, and leaves `trHeight` broken.

## 3. Scope & Non-Goals

- **In scope**: Nested table height accuracy, table style `p_pr`/`r_pr`/`cell_mar` cascading, explicit `0`/`1.0`/`auto` spacing overrides, `trHeight` omitted `hRule` defaulting to `"atLeast"`, empty paragraph mark resolution, unit & visual regression verification on `libreoffice__tdf131260.docx`.
- **Non-goals**: Horizontal Word 2003 table overhang (`compat < 15` negative left margin), conditional `tblStylePr` banding, or unrelated Epic #406 subtasks (#413, #415–#419).

## 4. Implementation Task Checklist

- [x] Task 1: Add explicit spacing override tracking (`SpacingProperties`, `DocxReader._parse_p_pr`, `merge_p_props`) and fix `trHeight` default `hRule="atLeast"`
- [x] Task 2: Cascade table style `p_pr`, `r_pr`, and `cell_mar` (`DocxReader._parse_styles`, `TableProperties`, `resolve_table_style_props`, `resolve_p_props`, `resolve_r_props`, `portions.py`, `table_layout.py`)
- [x] Task 3: Add unit and regression tests verifying nested table heights, single-application of row heights and cell padding, explicit spacing overrides, and `libreoffice__tdf131260.docx` geometry
- [x] Task 4: Run full writer & GUI regression suites and visually verify rendered `libreoffice__tdf131260.docx` canvas against `.vibeoffice` baseline (outer table top/bottom within 5 px, nested table and `"Table"` text preserved without overlap)
- [x] Task 5: Perform `grill-me` stress-test audit and hand off to `atb-github-code-reviewer`

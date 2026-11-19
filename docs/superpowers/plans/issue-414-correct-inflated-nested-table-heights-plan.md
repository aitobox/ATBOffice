# Issue #414: Correct Inflated Nested Table Heights on Word Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate nested table height inflation in Quire Word import so `libreoffice__tdf131260.docx` matches `.vibeoffice` outer table top/bottom borders within 5 px, preserves nested table text without overlap, and applies row heights and cell padding once per nesting level.

**Architecture:** Track explicit `<w:spacing>` and `<w:tblCellMar>` overrides on model dataclasses (`repr=False, compare=False`), cascade table style `p_pr`, `r_pr`, and `cell_mar` in `resolve_table_style_props()` and `resolve_p_props()`/`resolve_r_props()` following Word/LibreOffice/`.vibeoffice` precedence without leaking outer table styles into nested child tables, fix `w:trHeight` default `hRule="atLeast"`, and resolve empty paragraph mark metrics from `resolve_r_props()`.

**Tech Stack:** Python 3.12+, PySide6 (Qt6), pytest (`conda run -n ATBOffice`).

**Spec:** `docs/superpowers/specs/issue-414-correct-inflated-nested-table-heights-spec.md`

## Global Constraints

- Follow Word / LibreOffice / `.vibeoffice` style precedence: `doc.defaults < table style < non-default paragraph style < direct`, with table style overriding the default paragraph style's own `p_pr` settings.
- Keep `SpacingProperties` and `TableProperties` backwards-compatible for programmatic callers (`*_explicit` fields use `default=False, repr=False, compare=False`).
- Nested child tables must resolve their own table style independently and never double-apply outer cell margins or row heights.
- All new and existing regression tests must pass under `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest`.

## Review Focus

1. Partial `<w:spacing w:after="0"/>` (omitting `before` and `line`): must zero `after` while preserving inherited `before` and `line` from `docDefaults` / parent style.
2. `<w:trHeight/>` with no `w:val` vs `<w:trHeight w:val="570"/>` (no `w:hRule`) vs `<w:trHeight w:val="570" w:hRule="auto"/>`: omitted `hRule` with `val` must become `"atLeast"`, explicit `"auto"` must stay `"auto"`, missing `val` must keep `h=None`.
3. Non-default paragraph style (e.g. `Heading1` with `after=3`) inside a `TableGrid` (`after=0`) table: non-default paragraph style's own spacing must win over the table style.
4. Nested table with `TableNormal` (no `p_pr`) inside outer table with `TableGrid` (`after=0`): outer table style must not bleed into inner table cells, and outer cell padding (`mar_t`/`mar_b`) must be applied once to the outer cell while inner cell padding is applied once to the inner cell.
5. Empty paragraph inside a document with `docDefaults` (`Calibri 11pt`): paragraph mark line height must reflect resolved `r_pr` (`Calibri 11pt`) rather than hardcoded `Times New Roman 12pt`, while plain `Document()` defaults remain `Times New Roman 12pt`.

---

### Task 1: Explicit spacing overrides & `trHeight` omitted `hRule="atLeast"`

**Files:**
- Modify: `src/atboffice/modules/writer/models/properties.py` (`SpacingProperties`, `TableProperties`)
- Modify: `src/atboffice/modules/writer/io/docx_reader.py` (`_parse_p_pr`, `_parse_table`)
- Modify: `src/atboffice/modules/writer/models/styles.py` (`merge_p_props`)
- Test: `tests/test_quire_tables.py`

**Interfaces:**
- Produces:
  - `SpacingProperties` fields: `before_explicit`, `after_explicit`, `line_explicit`, `line_rule_explicit`, `before_auto_explicit`, `after_auto_explicit` (all `bool = field(default=False, repr=False, compare=False)`).
  - `TableProperties.cell_mar_explicit: bool = field(default=False, repr=False, compare=False)`.
  - `DocxReader._parse_p_pr` sets the exact `*_explicit` flags matching present XML attributes on `<w:spacing>`.
  - `DocxReader._parse_table` sets `tr_pr.h_rule = _get_attr(h_elem, "hRule") or "atLeast"` when `w:val` is present, and sets `tbl_pr.cell_mar_explicit = True` when `<w:tblCellMar>` is present.
  - `merge_p_props(base, over)` overrides `sp.before`, `sp.after`, `sp.line`, `sp.line_rule`, `sp.before_auto`, `sp.after_auto` whenever non-default OR `*_explicit` is True.

- [x] **Step 1: Write failing tests in `tests/test_quire_tables.py`**
  - `test_explicit_zero_spacing_overrides_doc_defaults`: DOCX/model with `docDefaults` `before=12, after=10, line=1.15` and direct `<w:spacing w:after="0" w:line="240" w:lineRule="auto"/>` resolves `before=12, after=0, line=1.0, line_rule="auto"`.
  - `test_tr_height_omitted_hrule_defaults_to_at_least`: `libreoffice__tdf131260.docx` innermost row parses `tr_pr.h == 28.5` and `tr_pr.h_rule == "atLeast"`, and explicit `hRule="auto"` stays `"auto"`.
- [x] **Step 2: Run targeted pytest to confirm new tests fail**
  - Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_quire_tables.py -k "explicit_zero_spacing or tr_height_omitted" -v`
- [x] **Step 3: Implement explicit flags on `SpacingProperties` / `TableProperties`, update `_parse_p_pr` / `_parse_table` in `docx_reader.py`, and update `merge_p_props` in `styles.py`**
- [x] **Step 4: Re-run targeted pytest to confirm Task 1 tests pass**

---

### Task 2: Table style `p_pr` / `r_pr` / `cell_mar` cascade and empty paragraph mark resolution

**Files:**
- Modify: `src/atboffice/modules/writer/io/docx_reader.py` (`_parse_styles` for `tblCellMar`)
- Modify: `src/atboffice/modules/writer/models/styles.py` (`resolve_p_props`, `resolve_r_props`, helper `_default_style_id`, `_is_default_para_style`)
- Modify: `src/atboffice/modules/writer/layout/portions.py` (`decompose_paragraph_to_portions`, `layout_paragraph`)
- Modify: `src/atboffice/modules/writer/layout/table_layout.py` (`resolve_table_style_props`, `layout_table`)
- Test: `tests/test_quire_tables.py`

**Interfaces:**
- Consumes: Task 1's `SpacingProperties.*_explicit`, `TableProperties.cell_mar_explicit`, `merge_p_props`.
- Produces:
  - `resolve_table_style_props(doc: Document, table: Table) -> dict[str, Any]` returning `{"borders", "ind", "cell_mar", "p_pr", "r_pr"}`.
  - `resolve_p_props(doc, para, context=None)` honoring `context["tbl_p_pr"]` with Word precedence.
  - `resolve_r_props(doc, para, item=None, context=None)` honoring `context["tbl_r_pr"]` with Word precedence.
  - `decompose_paragraph_to_portions(p, doc=None, table_context=None)` and `layout_paragraph(..., table_context=None)` forwarding `table_context` to `resolve_p_props`, `resolve_r_props`, and empty paragraph `mark_r_pr`.
  - `layout_table` passing `table_context={"tbl_p_pr": style_props["p_pr"], "tbl_r_pr": style_props["r_pr"]}` only to direct `Paragraph` blocks of the current table, using `style_props["cell_mar"]` for default margins, and isolating nested tables cleanly.

- [x] **Step 1: Write failing tests in `tests/test_quire_tables.py`**
  - `test_table_style_p_pr_overrides_doc_defaults_and_default_normal`: `TableGrid` `p_pr` (`after=0, line=1.0`) overrides `docDefaults` (`after=10, line=1.15`) for `Normal` paragraphs inside the table, while non-default `Heading1` (`after=3`) keeps `after=3`.
  - `test_nested_table_row_heights_and_padding_applied_once`: Outer table (`mar_t=6, mar_b=8`, `TableGrid`) containing a nested table (`mar_t=4, mar_b=5`, `trHeight=30 atLeast`, `TableNormal`) yields exact additive height `outer_mar_t + inner_height + outer_mar_b` where `inner_height == max(30, inner_mar_t + p_h + inner_mar_b)`, and outer `TableGrid` `p_pr` does not leak into inner `TableNormal` cells.
  - `test_fixture_tdf131260_nested_table_heights_match_reference`: Outer table height on `libreoffice__tdf131260.docx` is within `5 px` (`3.75 pt`) of `.vibeoffice`'s `192.0 pt` (`256 px`), middle table height matches `110.25 pt`, innermost row height equals `28.5 pt` with bottom-aligned `"Table"` (`content_offset_y > 0`), and no vertical overlap occurs between sibling blocks.
- [x] **Step 2: Run targeted pytest to confirm new tests fail**
- [x] **Step 3: Implement Task 2 across `docx_reader.py`, `styles.py`, `portions.py`, `table_layout.py`**
- [x] **Step 4: Re-run `tests/test_quire_tables.py` to confirm all tests pass**

---

### Task 3: Full Regression Verification & Visual Canvas Check

**Files:**
- Verify: `tests/test_quire_tables.py`, `tests/unit/writer/`, `tests/gui/test_phase9_docx_rendering.py`, `tests/modules/writer/`

- [x] **Step 1: Run required issue verification tests & broader writer suite**
  - `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/writer/test_layout_regression.py tests/gui/test_phase9_docx_rendering.py tests/test_quire_tables.py tests/unit/writer/test_table_margins_and_borders.py tests/unit/writer/test_tables.py tests/unit/writer/test_dmodel.py tests/modules/writer/test_docx_reader_advanced.py -v`
- [x] **Step 2: Render `libreoffice__tdf131260.docx` on `WriterCanvasView` offscreen, measure rendered outer/middle/inner table border pixel coordinates, and visually inspect the rendered screenshot**
  - Verify outer table top and bottom borders are within 5 px of `.vibeoffice` baseline (`y=96..352`, height `256 px` at 100% zoom after page-origin alignment), and `"Table"` is visible at the bottom of the innermost box with zero overlap.
- [x] **Step 3: Commit clean, well-scoped commit(s) referencing `#414`**

---

### Task 4: `grill-me` Audit & Handoff to `atb-github-code-reviewer`

- [x] **Step 1: Run `grill-me` stress-test audit against every checklist item, edge case, and scope boundary**
- [x] **Step 2: Update `.github-agent-state.yml` to `reviewing` and invoke `atb-github-code-reviewer`**

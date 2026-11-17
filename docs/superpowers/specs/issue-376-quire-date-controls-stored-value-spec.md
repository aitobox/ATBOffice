# Spec: Issue #376 — Quire date fields show stored value, not today's date

## Root cause (verified)
The fixture `libreoffice__tdf146973_signatureBlock.docx` contains no `w:date` SDT. It contains two
**complex fields**: `DATE \@ "dd MMMM yyyy"` and `TIME \@ "dd MMMM yyyy' р.'"`, with cached results
`12 April 2026` and `12 квітня 2026 р.`. Only the `fldChar` runs carry `w:color 2B579A` + gray shading;
the cached result runs carry no color.

`paginate_document()` calls `update_fields()` on every pass. `update_fields()` re-evaluates **every**
field (DATE/TIME → `datetime.now()`) and replaces the cached result with a single `TextItem` that
uses the **field-begin run's** `r_pr` → today's date, in blue. `_evaluate_hf_paragraph()` does the same
for header/footer paragraphs.

## Original behaviour (`.vibeoffice/public/quire/js`)
- `render.js:445` / `layout.js:1258 refreshDynamic`: after layout only PAGE, NUMPAGES, SECTIONPAGES,
  SECTION (and STYLEREF in headers/footers) are refreshed. All other fields keep their stored result
  until the user runs Update Field(s) (`fields.js:389 F.updateField`).
- Dynamic results render with the first result run's properties (`f.firstRes || it`).

## Design
1. `field.py`: add `LAYOUT_FIELD_TYPES = {PAGE, NUMPAGES, SECTIONPAGES, SECTION, PAGEREF}` and
   `HF_LAYOUT_FIELD_TYPES = LAYOUT_FIELD_TYPES | {STYLEREF}`. PAGEREF is kept (deviation from the
   original) because existing TOC page numbers depend on it and it is layout-derived.
2. `update_fields(doc, pagination_result=None, types=None)`: when `types` is given, fields whose type
   is not in it are left untouched. `types=None` (explicit Update Fields, mail merge) updates all.
3. Pagination passes call `update_fields(..., types=LAYOUT_FIELD_TYPES)`;
   `_evaluate_hf_paragraph` skips fields outside `HF_LAYOUT_FIELD_TYPES`.
4. Replacement result run uses the first existing result run's `r_pr` (MERGEFORMAT behaviour),
   falling back to the begin run's `r_pr` when the field has no result.

## Out of scope / notes
- No new `DateField` model: the issue's suggested model is unnecessary — stored values already live in
  the run list and round-trip unchanged once they are no longer overwritten.
- SDT date controls (`w:date`): content is already read from `sdtContent` verbatim (stored text or
  the placeholder run when `showingPlcHdr`); covered by regression tests, no code change.

## Task list
- [x] Task 1: Regression tests (fixture text/colour, round trip, header/footer, SDT date/placeholder)
- [x] Task 2: Restrict automatic field refresh to layout-dependent field types
- [x] Task 3: Keep result-run formatting when a field result is replaced
- [x] Task 4: Update the outdated convergence test; full test suite pass
- [x] Task 5: grill-me audit

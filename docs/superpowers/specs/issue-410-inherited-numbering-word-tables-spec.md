# Issue #410: Restore inherited numbering across Word tables

## Problem

In `libreoffice__tdf132802.docx`, paragraphs numbered through the `CustomStyle` paragraph
style lose numbers 1-3 and 8 in the document body. Paragraphs inside the table still show 4-7.

## Root cause

Import is correct: `compute_lists` labels the paragraphs 1-8 in reading order and leaves the
`numId=0` paragraph blank. The labels are lost during pagination.
`_split_paragraph_by_hard_breaks` rebuilds every body paragraph as a new `Paragraph` without
`label`, so `decompose_paragraph_to_portions` emits no marker. Table cells lay out the original
paragraph, which is why only they show numbers.

## Design

1. Carry `label` onto the first hard-break segment only. A continuation after a page or column
   break is the same list item and must not repeat the number.
2. Recompute list labels at the start of `paginate_document`. Body rendering now depends on
   `Paragraph.label`, which was previously computed only on import, so edits would otherwise
   show stale or missing numbers.
3. Make list markers zero-length in model coordinates. Markers are not document text, but they
   advanced `char_offset`, which would shift caret, selection, and hit-testing by the marker
   length on every numbered line.
4. Map a click on a marker to the portion's model offset instead of an offset inside the glyph.

## Edge cases

| Case | Expected behavior |
|---|---|
| Explicit `numId=0` over a numbered style | Unnumbered and not counted |
| Numbering continues across a table | Single counter in reading order |
| Paragraph with a hard page break | Number on the first segment only |
| Numbered paragraph removed or added | Later numbers update on the next pagination |
| Caret at offset 0 of a numbered line | Sits after the marker, at the text start |
| Click on the marker | Resolves to offset 0 |

## Task checklist

- [x] Task 1: Add failing regression tests
- [x] Task 2: Preserve labels through hard-break segmentation
- [x] Task 3: Refresh list labels on pagination
- [x] Task 4: Keep markers out of model character offsets
- [x] Task 5: Run affected suites and recapture the fixture

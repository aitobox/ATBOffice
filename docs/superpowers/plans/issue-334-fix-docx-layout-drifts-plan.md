# Implementation Plan: Issue #334 — Resolve 6 DOCX Layout Drifts

## Overview
Implement fixes for all 6 Word layout drift issues identified in Phase 9 across DOCX parsing, paragraph frames (`framePr`), table layout refinements, multi-column height balancing, trailing whitespace margin handling, comment balloons, and complex bullet numbering.

---

## Tasks

### Task 1: Reader Parsing Extensions (`docx_reader.py`)
- Clean `framePr` XML attributes of namespace prefixes and parse twip dimensions into pt.
- Parse `word/comments.xml` into `doc.comments: dict[str, Story]` with comment metadata (`id`, `author`, `initials`, `date`).
- Parse `w:commentRangeStart` and `w:commentRangeEnd` as `CommentRangeStart` and `CommentRangeEnd` items in paragraph runs.
- **Verification**: Unit tests verifying `frame_pr` and `doc.comments` extraction from `openxml-sdk__Comment066.docx` and `libreoffice__tdf105035_framePrB.docx`.

### Task 2: Trailing Space Overflow Clipping (`portions.py`)
- Modify `portions.py` portion packing loop: trailing blank portions (`PortionType.BLANK`) that exceed available column width `avail_w` on a non-empty line are retained on that line (clipped over margin) without forcing a premature wrap.
- **Verification**: Test with `libreoffice__tdf43100_tdf120715_cursorOnSpacesOverMargin.docx`.

### Task 3: Bullet Numbering & Hanging Indents (`portions.py` & `pagination.py`)
- When `p.p_pr.num` is present, resolve the level definition from `doc.numbering['nums']` and `doc.numbering['abs']`.
- Prepend bullet/number marker portion to the first line of the paragraph with proper font family (e.g. Wingdings) and glyph.
- Resolve indent properties (`ind.left` and `ind.first_line` / hanging indent) from the level definition when not overridden on paragraph.
- **Verification**: Test with `openxml-sdk__bullet-complex.docx`.

### Task 4: Paragraph Frame Floating Layout (`wrap.py` & `pagination.py`)
- In `wrap.py` and `pagination.py`, recognize paragraphs with `p.p_pr.frame_pr`.
- Resolve absolute page coordinates based on `hAnchor` / `vAnchor` / `xAlign` / `yAlign` / `w` / `h`.
- Register the frame into `page.float_boxes` with appropriate wrap mode (`notBeside`, `around`, `none`).
- Render paragraph lines inside the floating frame.
- **Verification**: Test with `libreoffice__tdf105035_framePrB.docx` and `libreoffice__tdf113182.docx`.

### Task 5: Multi-Column Section Balancing (`pagination.py`)
- In `pagination.py`, when a multi-column section finishes at a continuous break or section boundary, balance column heights by distributing line fragments across columns proportionally rather than exhausting column 0.
- **Verification**: Test with `libreoffice__tdf121670_columnsInSectionsOnly.docx`.

### Task 6: Comment Balloon & Range Rendering (`canvas_view.py`)
- In `canvas_view.py`, render comment markers on page text and draw right-margin comment callout bubbles with connector lines, initials, and text.
- **Verification**: Test with `openxml-sdk__Comment066.docx`.

### Task 7: End-to-End Regression Verification (`test_phase9_docx_rendering.py`)
- Create `tests/gui/test_phase9_docx_rendering.py` with test cases for all 6 documents.
- Run `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_phase9_docx_rendering.py -v`.
- Confirm visual similarity >= 88.0% for all 6 documents and zero regressions.

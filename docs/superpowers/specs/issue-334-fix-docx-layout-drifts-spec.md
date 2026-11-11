# Design Specification: Issue #334 — Resolve 6 DOCX Layout Drifts

## 1. Overview & Problem Statement
In `docs/clone/OFFICE_DOCS_DIFF.md`, 6 core Word (.docx) test files exhibit visual divergence categorized as `LAYOUT_DRIFT` (visual similarity 77.0% ~ 85.0%):
1. `libreoffice__tdf105035_framePrB.docx` (79.0%): Paragraph frame positioning `w:framePr` (`w:dropCap`, vertical/horizontal anchors, text wrap) is ignored in layout.
2. `libreoffice__tdf113182.docx` (77.9%): Unhandled `w:framePr` and table cell margins (`w:tcMar`) / border overlap collapse / `w:gridSpan`.
3. `libreoffice__tdf121670_columnsInSectionsOnly.docx` (85.0%): Multi-column (`w:cols`) section break does not balance column heights at section boundaries.
4. `libreoffice__tdf43100_tdf120715_cursorOnSpacesOverMargin.docx` (84.9%): Trailing whitespaces over margin are wrapped rather than hung/clipped per Word 2003 rules.
5. `openxml-sdk__Comment066.docx` (77.0%): Missing `comments.xml` parsing, comment range markers (`w:commentRangeStart/End`), and right margin callout balloons.
6. `openxml-sdk__bullet-complex.docx` (81.8%): Multi-level bullet numbering (`w:numPr`), symbol fonts (Wingdings), tab stops, and hanging indents are unhandled in paragraph layout.

Target: Achieve >= 88.0% visual similarity for each document (average >= 91.0%), zero crashes, and zero regressions across existing tests.

---

## 2. Architecture & Modules Affected

### 2.1 DOCX Reader (`src/atboffice/modules/writer/io/docx_reader.py`)
- **Normalize `framePr`**: Clean XML namespace prefixes (`{http:...}tag` -> `tag`), convert twip values to points for `w`, `h`, `x`, `y`, `hSpace`, `vSpace`.
- **Parse `comments.xml`**:
  Extract comments into `doc.comments: dict[str, Story]` with `id`, `author`, `initials`, `date`, and blocks.
  Parse `<w:commentRangeStart>` and `<w:commentRangeEnd>` in paragraphs into `CommentRangeStart(id)` and `CommentRangeEnd(id)` in `p.runs`.

### 2.2 Text Wrapping & Frame Positioning (`src/atboffice/modules/writer/layout/wrap.py`)
- Support paragraph frames (`frame_pr`) as `FloatBox` instances with:
  - Coordinate resolution from `hAnchor` ("page", "margin", "column", "text") and `vAnchor` ("page", "margin", "text").
  - Alignment handling (`xAlign`: "left", "center", "right"; `yAlign`: "top", "center", "bottom").
  - Wrapping modes (`notBeside`, `around`, `tight`, `none`).
  - Text exclusion integration in `calculate_line_segments()`.

### 2.3 Table Layout Engine (`src/atboffice/modules/writer/layout/table_layout.py`)
- Ensure per-cell `tc_mar` overrides table `cell_mar`.
- Implement table border collapsing across adjacent cell boundaries.
- Ensure `gridSpan` accurately spans multi-column grid widths.

### 2.4 Pagination & Multi-Column Balancing (`src/atboffice/modules/writer/layout/pagination.py`)
- Add column height balancing for multi-column sections ending with a section break or document end:
  Divide total fragment height by column count and fill columns proportionally.
- Integrate floating paragraph frames during pagination into `page.float_boxes`.

### 2.5 Portions & Bullet Numbering (`src/atboffice/modules/writer/layout/portions.py`)
- **Bullet Numbering**:
  When `p.p_pr.num` is present, resolve level from `doc.numbering['nums']` and `doc.numbering['abs']`.
  Synthesize bullet portion (with font family, e.g., Wingdings for symbol bullets) and tab portion.
  Apply hanging indents from the numbering level (`ind.left`, `ind.first_line`).
- **Trailing Whitespace Overflow**:
  Trailing blanks that exceed `avail_w` on an already non-empty line are attached to the end of the line (hanging over margin) rather than wrapping onto a new line.

### 2.6 Canvas View & Comment Balloons (`src/atboffice/modules/writer/views/canvas_view.py`)
- Render floating text boxes/frames in `_paint_float_box()`.
- Render comment range background highlights and right-margin comment balloons with connector lines and author/initial metadata.

---

## 3. Edge Cases & Pre-Implementation Reflection
1. **Namespaced Attributes**: `child.attrib` in ElementTree may contain `{http://schemas.openxmlformats.org/wordprocessingml/2006/main}`. Always clean with `.split("}")[-1]`.
2. **Missing Comments Part**: Documents without comments must gracefully initialize `doc.comments = {}` without throwing exceptions.
3. **Empty or Missing Numbering Levels**: If a `numId` or `lvl` is missing in `doc.numbering`, fallback gracefully to a standard bullet or default indent without crash.
4. **Zero-Height Frames / Negative Coordinates**: Validate coordinate bounds so frames outside the page boundary are clipped safely.
5. **Multi-Column Underflow**: If multi-column section has fewer lines than columns, balance by placing 1 line per column up to the line count.

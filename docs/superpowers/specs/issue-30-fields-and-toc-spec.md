# Design Specification: Quire Dynamic Fields Evaluation & TOC System

## 1. Overview & Objectives
This specification designs the dynamic fields evaluation and automated Table of Contents (TOC) system for the ATBOffice Quire (Word 2003 port) module.
It addresses [Issue #30](https://github.com/aitobox/ATBOffice/issues/30) and fulfills all requirements:
1. Dynamic field parsing and evaluation (`PAGE`, `NUMPAGES`, `SECTIONPAGES`, `SECTION`, `DATE`, `TIME`, `TITLE`, `AUTHOR`, `FILENAME`, `PAGEREF`, `STYLEREF`, etc.) with formatting switches (`\*`, `\#`, `\@`).
2. Bookmark management (`_Toc...` bookmarks, lookup, and bookmark text / position tracking).
3. Automated Table of Contents (`TOC`) generation from headings (Heading 1~Heading 6, outline levels 1~9), leader dot tab stops, and hyperlink navigation anchors.
4. Two-pass dynamic field backfill and repagination in the pagination engine to handle page-count expansion / shift (e.g. page count moving from 9 to 10).
5. Canvas rendering of leader dots for right-aligned tab stops and interactive click-to-jump navigation for TOC hyperlinks.

## 2. Architecture & Data Structures

### 2.1 Field Tokenizer & AST Model (`src/atboffice/modules/writer/models/field.py`)
- `FieldInstruction`:
  - `field_type: str`: e.g. `"PAGE"`, `"TOC"`, `"DATE"`, `"PAGEREF"`
  - `args: list[str]`: Positional arguments (e.g. bookmark name for PAGEREF)
  - `switches: dict[str, str | bool]`: e.g. `{"\\o": "1-3", "\\h": True, "\\@": "yyyy-MM-dd"}`
  - `fmt: list[str]`: General formatting switches (e.g. `["Upper"]`, `["Roman"]`, `["MERGEFORMAT"]`)
- Helper functions:
  - `tokenize_field_instruction(instr: str) -> list[str]`
  - `parse_field_instruction(instr: str) -> FieldInstruction`
  - `format_field_date(dt: datetime, picture: str) -> str`
  - `apply_field_formatting(value: str | int | float, fmt_switches: list[str]) -> str`
  - `evaluate_field(instr: str, doc: Document, context: FieldContext) -> str`
  - `insert_field(p: Paragraph, offset: int, field_type: str, instr: str, cached_text: str = "") -> None`
  - `update_fields(doc: Document, pagination_result: PaginationResult | None = None) -> bool`

### 2.2 Table of Contents Engine (`src/atboffice/modules/writer/layout/toc.py`)
- `TOCEntry`:
  - `paragraph: Paragraph`: Source heading paragraph
  - `level: int`: Heading / outline level (1 to 9)
  - `text: str`: Plain text of the heading
  - `bookmark_name: str`: Unique anchor bookmark (e.g. `_Toc100000001`)
  - `page_number: int`: Page number on which the heading starts
- `build_toc(doc: Document, instr: str = 'TOC \\o "1-3" \\h \\z \\u', pagination_result: PaginationResult | None = None) -> list[Paragraph]`
  - Extracts headings matching `\o` level range and `\u` outline level.
  - Ensures bookmark wrapping each heading paragraph.
  - Generates TOC paragraph styled with `TOC1`..`TOC9`.
  - Sets right-aligned tab stop with `leader="dot"` at `page_width - ml - mr`.
  - Adds text run with link anchor (if `\h`), Tab item, and `PAGEREF` dynamic field.
- `insert_or_update_toc(doc: Document, instr: str = 'TOC \\o "1-3" \\h \\z \\u', at_idx: int | None = None) -> list[Paragraph]`

### 2.3 Two-Pass Repagination (`src/atboffice/modules/writer/layout/pagination.py`)
- Pass 1: Paginate document layout with existing / initial field values.
- Field Update Pass: Backfill all `PAGE`, `NUMPAGES`, `SECTIONPAGES`, `PAGEREF` fields using actual page numbers and total page counts.
- Pass 2 Check: If any field replacement modified text length or if total page count changed, trigger an incremental second pagination pass to ensure line breaking and page counts stabilize with zero layout drift.

### 2.4 Canvas Interaction & Leader Dots (`src/atboffice/modules/writer/views/canvas_view.py`)
- Render leader dots for tab portions with `leader == "dot"`: draw recurring dot baseline glyphs or dotted pen across the tab span.
- Hyperlink navigation: on click (or Ctrl+click) over a run with `r_pr.link["anchor"]`, scroll canvas view to the target bookmark / paragraph and position caret.

## 3. Verification Plan
- `tests/unit/writer/test_fields.py`:
  - Test field instruction tokenizer (quotes, switches, escaped chars).
  - Test date formatting with pictures (`yyyy-MM-dd`, `MMMM d, yyyy`, `HH:mm:ss`).
  - Test general formatting switches (`\* Upper`, `\* Lower`, `\* Roman`, `\* Arabic`, `\* FirstCap`, `\* Caps`).
  - Test dynamic fields evaluation (`PAGE`, `NUMPAGES`, `SECTIONPAGES`, `SECTION`, `DATE`, `TIME`, `AUTHOR`, `TITLE`, `FILENAME`).
  - Test bookmark insertion, extraction, and `PAGEREF` resolution.
  - Test TOC generation from Heading 1~3, leader dots tab stops, and hyperlink anchors.
  - Test two-pass pagination when field text changes total page count.
- Full test suite: `pytest tests/unit/writer/ tests/gui/test_writer_canvas.py -v`.

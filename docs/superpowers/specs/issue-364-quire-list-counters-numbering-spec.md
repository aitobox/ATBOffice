# Specification: Issue #364 - Quire List Counters, Multi-Level Numbering, and Picture Bullets

## 1. Problem Statement & Scope

Numbered lists in Quire (Word processor module) suffer from severe rendering fidelity defects:
1. Every list item shows `1.` instead of advancing counters across paragraphs in document order.
2. Multi-level numbering patterns display raw placeholders such as `%1.1.` instead of expanding parent and child counters (e.g. `I.1.`, `I.2.`, `I.3.`).
3. Numbering inherited from a paragraph style cannot be toggled off when an override specifies `numId="0"`, causing non-numbered paragraphs to be incorrectly numbered.
4. Picture bullets (`numPicBullet` / `lvlPicBulletId`) are not loaded or rendered, appearing as empty boxes or missing entirely.
5. Symbol and Wingdings bullet characters in the private-use Unicode range (e.g., `0xF000`–`0xF0FF`) are not mapped to standard Unicode glyphs, displaying as unknown or blank boxes unless the specific font is installed.
6. Numbering level indents (`w:ind` with hanging indents) are not propagated from level definitions to paragraph layout.

## 2. Reference Implementation (.vibeoffice/)

In `.vibeoffice/`:
- `dmodel.js:562-616` (`D.computeLists`): Iterates through blocks and nested table cells in reading order; tracks 9-level counter arrays per `abstractNumId`; handles `startOverride`, `lvlRestart`, and `isLgl`; substitutes `%1`–`%9` tokens with formatted numbers; maps bullet glyphs with `mapSymbolChar`.
- `docx-read.js:553-580`: Parses `numPicBullet` from `numbering.xml` and resolves image targets from `numbering.xml.rels`; captures `lvlPicBulletId`.
- `common/core.js:741`: `L.mapSymbolChar` maps Wingdings 1/2/3 and Symbol characters to Unicode glyphs.
- `render.js:316-322`: Renders picture bullets as images inline at bullet positions.

## 3. Architecture & Module Design

### 3.1 Symbol & Bullet Glyph Mapping (`src/atboffice/modules/writer/layout/portions.py`)
Add `map_symbol_char(ch: str, font: str = "") -> str`:
- Translates Wingdings (1, 2, 3), Webdings, and Symbol character codes (both 0x20–0xFF and private-use 0xF000–0xF0FF) to standard Unicode symbols (●, ■, ◆, ✓, ➢, ▪, •, etc.).
- Handles legacy bullet characters `\uf0b7`, `\uf0a7`, `\uf06c`, `\uf06e`, `\uf075`, `\uf0fc`, `\uf0d8`, etc.

### 3.2 List Numbering Computation (`src/atboffice/modules/writer/models/document.py` or `layout/portions.py`)
Implement `compute_lists(doc: Document, stories: list[Story] | None = None) -> dict[int, dict[str, Any]]`:
- Traverses all paragraphs in document reading order, including top-level paragraphs and paragraphs nested inside table cells.
- Evaluates cascading paragraph properties via `resolve_p_props(doc, p)` to inherit style-level `numPr`.
- Enforces strict serial filtering: if `p_pr.num` is None, missing `id`, or `num.id == "0"` or `num.id == 0`, skips the paragraph (unlabeled).
- Skips empty paragraphs carrying only a section break (`p.sect and plen(p) == 0`).
- Manages counter arrays of size 9 per `abstractNumId`.
- Checks for `startOverride` in concrete `num.ov`: resets that level and deeper levels.
- For each numbered paragraph at level `lvl` (clamped 0..8):
  - Initializes uninitialized parent counters (0..lvl-1) to their level `start`.
  - Increments `counter[lvl]` (or initializes to `start`).
  - Resets child counters (lvl+1..8) if `restart is None or restart > lvl`.
  - Expands `lvlText` pattern: replaces all `%(\d)` tokens with `format_number(c[k], fmt)`. If `isLgl` is set and `k < lvl`, forces decimal format. Drops tokens where `k > lvl`.
  - Cleans any leftover `%` tokens to ensure no literal `%` remains in label text.
  - Resolves picture bullets if `lvlPicBulletId` is present.
  - Updates `p.label` with the calculated label string.
  - Stores label metadata dictionary: `{text, lv, num_id, lvl, value, picture}`.

### 3.3 Enhanced DOCX Reader (`src/atboffice/modules/writer/io/docx_reader.py`)
- Parse `w:numPicBullet` elements in `_parse_numbering`:
  - Locate `w:pict` -> `v:shape` -> `v:imagedata` or `a:blip` with relationship ID (`r:id` or `r:embed`).
  - Resolve image part target from `word/_rels/numbering.xml.rels`.
  - Store in `doc.numbering["pic_bullets"][num_pic_bullet_id] = {"image_part": target_part, "shape_style": style}`.
- Parse `w:lvlPicBulletId` in `<w:lvl>` and attach picture bullet info to the level dict.
- Constructor overload: `DocxReader(source_pkg: SourcePackage | str | Path | None = None)` and `read(source: str | Path | None = None)`.
- At the end of `read()`, invoke `compute_lists(self.doc)` to populate `label` on all paragraphs.

### 3.4 Document & Paragraph Model Enhancements (`src/atboffice/modules/writer/models/document.py`)
- Add `label: str = ""` field to `Paragraph`.
- Add `@property def blocks(self) -> list[Any]` on `Document`:
  - Recursively flattens `self.main.blocks`, yielding each paragraph and visiting nested table cells in reading order.
  - Supports `[b.label for b in doc.blocks if hasattr(b, 'label') and b.label]`.
- Add `@property def all_paras(self) -> list[Paragraph]` helper.

### 3.5 Portion Synthesis & Hanging Indent (`src/atboffice/modules/writer/layout/portions.py`)
- Update `decompose_paragraph_to_portions`:
  - Retrieve the computed label info for paragraph `p`.
  - If a picture bullet is present and its image exists:
    - Synthesize a `Portion(type=PortionType.GRAPHIC, width=w, ascent=h, data=PictureItem(...))`.
  - Else if `p.label` is non-empty:
    - Measure text width with mapped glyph and font properties.
    - Synthesize `Portion(type=PortionType.TEXT, text=p.label, ...)`.
  - Append suffix portion (`tab` or `space`).
  - If paragraph has no explicit indent (`p.p_pr.ind.left == 0 and p.p_pr.ind.first_line == 0`), apply the numbering level's indent (`ind.l`, `ind.fl`) to the layout line indent.

## 4. Acceptance Criteria & Test Strategy

1. `libreoffice__tdf132802.docx`:
   - Document blocks return labels `['1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.']`.
   - The paragraph with `Not numbered paragraph1` has `numId="0"` and remains unlabeled.
2. `libreoffice__tdf125881.docx`:
   - Subheadings produce labels `['I.', 'I.1.', 'I.2.', 'I.3.']` (Roman numeral parent + Arabic children).
3. `openxml-sdk__bullet-complex.docx`:
   - Numbered/bullet items expand correctly.
   - Picture bullets are parsed with valid media references.
   - Zero label strings in the document contain the literal character `%`.
4. Verification Across All 24 Word Fixtures:
   - No paragraph label contains `%`.
   - Existing test suite (`pytest tests/`) passes with zero regressions.

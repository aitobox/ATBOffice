# Quire List Counters, Multi-Level Numbering, and Picture Bullets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement robust document-order list counter state machines, multi-level `%N` numbering pattern expansion, style-level numbering inheritance with `numId="0"` deactivation, picture bullet loading/rendering, and Wingdings/Symbol glyph mapping in Quire.

**Architecture:** Maintain a per-list hierarchical counter array across all paragraphs and nested table cells in reading order (`compute_lists`). Enhance DOCX reading to parse `numPicBullet` and image relationships, enrich `Paragraph` and `Document` with `label` and `blocks` properties, and synthesize layout portions (`PortionType.TEXT` and `PortionType.GRAPHIC`) with accurate metrics and hanging indents.

**Tech Stack:** Python 3.12+, PySide6, xml.etree.ElementTree, pytest

**Spec:** `docs/superpowers/specs/issue-364-quire-list-counters-numbering-spec.md`

## Global Constraints
- Strictly maintain backwards compatibility with existing Quire document rendering models.
- Python 3.12+ type hints on all public interfaces.
- Zero regressions on existing test suites (`pytest tests/`).
- Wrap any user-facing UI text in `safe_tr()`.
- No label string in any Word fixture may contain a literal `%` character.

---

### Task 1: Symbol & Wingdings Glyph Mapping (`map_symbol_char`)

**Files:**
- Modify: `src/atboffice/modules/writer/layout/portions.py`
- Test: `tests/test_quire_numbering.py`

**Interfaces:**
- Produces: `map_symbol_char(ch: str, font: str = "") -> str`

- [ ] **Step 1: Write the failing test**
Create test case in `tests/test_quire_numbering.py` testing Wingdings 1/2/3 and Symbol private-use Unicode mappings (e.g., `\uf0b7` -> `•`, `\uf06c` -> `●`, `\uf0fc` -> `✓`, `\uf0a7` -> `▪`).

- [ ] **Step 2: Run test to verify it fails**
Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_quire_numbering.py -k test_map_symbol_char -v`
Expected: FAIL (ImportError or AttributeError: `map_symbol_char` not found).

- [ ] **Step 3: Write minimal implementation**
Implement `map_symbol_char(ch: str, font: str = "") -> str` in `portions.py` matching the reference implementation in `.vibeoffice/public/common/core.js:741`.

- [ ] **Step 4: Run test to verify it passes**
Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_quire_numbering.py -k test_map_symbol_char -v`
Expected: PASS.

- [ ] **Step 5: Commit**
`git add src/atboffice/modules/writer/layout/portions.py tests/test_quire_numbering.py && git commit -m "feat(quire): add symbol and wingdings glyph mapping"`

---

### Task 2: Paragraph & Document Model Enhancements

**Files:**
- Modify: `src/atboffice/modules/writer/models/document.py`
- Test: `tests/test_quire_numbering.py`

**Interfaces:**
- Produces:
  - `Paragraph.label: str = ""`
  - `Document.blocks` property returning all blocks and nested table cell paragraphs in reading order.
  - `Document.all_paras(opts: Any = None) -> list[Paragraph]`

- [ ] **Step 1: Write the failing test**
Add test in `tests/test_quire_numbering.py` verifying `p.label` attribute on `Paragraph` and `doc.blocks` traversing nested table paragraphs.

- [ ] **Step 2: Run test to verify it fails**
Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_quire_numbering.py -k test_document_blocks_traversal -v`
Expected: FAIL (`AttributeError: 'Document' object has no attribute 'blocks'`).

- [ ] **Step 3: Write minimal implementation**
Add `label: str = ""` field to `Paragraph` in `document.py`. Add `@property def blocks(self) -> list[Any]` and `all_paras` method on `Document` to traverse blocks and table cells depth-first.

- [ ] **Step 4: Run test to verify it passes**
Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_quire_numbering.py -k test_document_blocks_traversal -v`
Expected: PASS.

- [ ] **Step 5: Commit**
`git add src/atboffice/modules/writer/models/document.py tests/test_quire_numbering.py && git commit -m "feat(quire): add label to Paragraph and blocks property to Document"`

---

### Task 3: DOCX Numbering & Picture Bullet Parsing

**Files:**
- Modify: `src/atboffice/modules/writer/io/docx_reader.py`
- Test: `tests/test_quire_numbering.py`

**Interfaces:**
- Produces:
  - `DocxReader(source_pkg: SourcePackage | str | Path | None = None)`
  - `DocxReader.read(source: str | Path | None = None) -> Document`
  - `doc.numbering["pic_bullets"]`: dictionary mapping `numPicBulletId` to image part paths and styles.
  - `lvl["pic_bullet_id"]`: level attribute linking to picture bullet.

- [ ] **Step 1: Write the failing test**
Add test in `tests/test_quire_numbering.py` reading `openxml-sdk__bullet-complex.docx` and verifying picture bullets and `DocxReader().read(path)` signature.

- [ ] **Step 2: Run test to verify it fails**
Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_quire_numbering.py -k test_parse_num_pic_bullet -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**
In `docx_reader.py`:
- Update `DocxReader.__init__` and `read` to support optional source paths or packages.
- In `_parse_numbering`: parse `w:numPicBullet`, extract `v:imagedata` or `a:blip` relationships from `numbering.xml.rels`, and record them in `self.doc.numbering["pic_bullets"]`.
- In `lvl` parsing: extract `w:lvlPicBulletId` and attach to level definition dictionary.

- [ ] **Step 4: Run test to verify it passes**
Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_quire_numbering.py -k test_parse_num_pic_bullet -v`
Expected: PASS.

- [ ] **Step 5: Commit**
`git add src/atboffice/modules/writer/io/docx_reader.py tests/test_quire_numbering.py && git commit -m "feat(quire): parse numPicBullet and lvlPicBulletId in docx_reader"`

---

### Task 4: List Counter Calculation & Multi-Level Expansion (`compute_lists`)

**Files:**
- Modify: `src/atboffice/modules/writer/models/document.py` (or `layout/portions.py`)
- Modify: `src/atboffice/modules/writer/io/docx_reader.py`
- Test: `tests/test_quire_numbering.py`

**Interfaces:**
- Consumes: `format_number(n, fmt)` from `pagination.py`, `resolve_p_props` from `styles.py`
- Produces: `compute_lists(doc: Document, stories: list[Story] | None = None) -> dict[int, dict[str, Any]]`

- [ ] **Step 1: Write the failing test**
Add test cases in `tests/test_quire_numbering.py`:
- `test_tdf132802_list_counters`: verifies labels '1.' through '8.' and unlabeled 'Not numbered paragraph'.
- `test_tdf125881_multilevel_patterns`: verifies 'I.', 'I.1.', 'I.2.', 'I.3.'.

- [ ] **Step 2: Run test to verify it fails**
Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_quire_numbering.py -k "test_tdf132802 or test_tdf125881" -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**
Implement `compute_lists(doc, stories=None)`:
- Manage 9-level counters per `absId`.
- Handle `startOverride` in `num.ov`.
- Handle `numId="0"` paragraph-level suppression of style numbering.
- Handle `lvlRestart`.
- Handle `isLgl` decimal conversion for parent tokens.
- Expand `%(\d)` multi-level patterns using `format_number`.
- Clean residual `%` characters.
- Set `p.label = text` on each visited paragraph.
- In `docx_reader.py`: call `compute_lists(self.doc)` at the end of `read()`.

- [ ] **Step 4: Run test to verify it passes**
Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_quire_numbering.py -k "test_tdf132802 or test_tdf125881" -v`
Expected: PASS.

- [ ] **Step 5: Commit**
`git add src/atboffice/modules/writer/layout/portions.py src/atboffice/modules/writer/io/docx_reader.py tests/test_quire_numbering.py && git commit -m "feat(quire): compute real list counters and multi-level patterns"`

---

### Task 5: Layout Portion Synthesis & Hanging Indents

**Files:**
- Modify: `src/atboffice/modules/writer/layout/portions.py`
- Test: `tests/test_quire_numbering.py`

**Interfaces:**
- Consumes: `compute_lists`, `map_symbol_char`, `PictureItem`
- Produces: Updated `decompose_paragraph_to_portions` handling picture bullets and numbering level indents.

- [ ] **Step 1: Write the failing test**
Add test verifying that `decompose_paragraph_to_portions` for a picture-bullet paragraph emits a `PortionType.GRAPHIC` portion, and that hanging indents from numbering are applied when no direct paragraph indent exists.

- [ ] **Step 2: Run test to verify it fails**
Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_quire_numbering.py -k test_portion_picture_bullet_and_hanging_indent -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**
In `portions.py`:
- Use computed `p.label` or `compute_lists` result.
- For picture bullets, synthesize `Portion(type=PortionType.GRAPHIC, width=w, ascent=h, data=PictureItem(...))`.
- For text/bullet numbering, use `map_symbol_char` and apply font properties from `lvl.r_pr`.
- Apply numbering level `ind` (`l` and `fl`) when `p.p_pr.ind.left == 0 and p.p_pr.ind.first_line == 0`.

- [ ] **Step 4: Run test to verify it passes**
Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_quire_numbering.py -k test_portion_picture_bullet_and_hanging_indent -v`
Expected: PASS.

- [ ] **Step 5: Commit**
`git add src/atboffice/modules/writer/layout/portions.py tests/test_quire_numbering.py && git commit -m "feat(quire): synthesize picture bullets and apply numbering indents in portions"`

---

### Task 6: Full Fixture Verification & Regression Testing

**Files:**
- Modify: `tests/test_quire_numbering.py`

- [ ] **Step 1: Write fixture-wide assertion test**
Add `test_all_word_fixtures_no_percent_in_labels` iterating through all 24 Word docx fixtures and asserting that no paragraph's `label` contains `%`.

- [ ] **Step 2: Run numbering test suite**
Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_quire_numbering.py -v`
Expected: PASS (all tests pass).

- [ ] **Step 3: Run full repository test suite**
Run: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`
Expected: All tests pass (with only the pre-existing known failure in `test_tab_panel_focus_navigation` if any).

- [ ] **Step 4: Commit**
`git add tests/test_quire_numbering.py && git commit -m "test(quire): add comprehensive test suite for list numbering and bullets"`

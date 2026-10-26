# Implementation Plan: Quire Line Portions Layout Engine & East Asian Grid Snapping

## Overview
Implement `src/atboffice/modules/writer/layout/portions.py` to provide Apache OpenOffice Writer style line portions layout, font metrics, line height calculation, East Asian line grid snapping, Word spacing collapse, and 20% micro-compression for justified alignment.

---

## Tasks

### Task 1: Module Scaffolding and Data Structures
- Create `src/atboffice/modules/writer/layout/__init__.py`.
- Define `PortionType`, `Portion`, `LayoutLine`, and `ParagraphLayout` in `src/atboffice/modules/writer/layout/portions.py`.
- Define font line factors (`FONT_LINE_FACTORS`), font ascent/descent ratios, and deterministic font measurement routines.
- Export key symbols in `__init__.py`.

### Task 2: East Asian Line Grid Snapping and Paragraph Spacing Collapse
- Implement `compute_grid_line_height(pitch, mult, font_size, font_family)` with exact Word rounding rules.
- Implement `collapse_paragraph_spacing(sp_after_prev, sp_before_curr, is_page_top)`.
- Implement `vertical_align_in_grid(line_height, natural_line, ascent)`.

### Task 3: Portion Decomposition & Tokenization
- Implement `decompose_paragraph_to_portions(paragraph, style_resolver)`:
  - TextItem -> splits into TextPortion, BlankPortion, CJK portions.
  - TabItem -> TabPortion with target position.
  - BreakItem -> BreakPortion.
  - Inline Graphic / Object -> GraphicPortion with ascent=height, descent=0.
  - End of paragraph mark -> MarkPortion (for empty height).

### Task 4: Line Breaking and Justification with 20% Micro-Compression
- Implement `layout_paragraph(paragraph, container_width, section_props, style_resolver)`:
  - First-line indent vs hanging indent.
  - Break on whitespace, word boundaries, or CJK characters.
  - East Asian kinsoku shori (forbidden leading/trailing characters).
  - Justified alignment (`jc == "both"` / `"distribute"`):
    - 20% inter-word spacing micro-compression before breaking.
    - Slack distribution across space portions.
  - Line height calculation:
    - Empty paragraph -> `markR` font height (`EmptyHeight`).
    - Non-empty line -> `max(ascent) + max(descent)` of counting portions.
    - Blanks and tabs count for nothing in line height (OpenOffice `#i3952`).
    - Only pictures -> `max(picture_height, markR_line_height)`.
    - Exact, atLeast, auto line rules.
    - Line grid snapping if enabled.

### Task 5: Unit Test Suite
- Create `tests/unit/writer/test_portions.py` testing:
  - Basic text and blank portions creation.
  - Blank and tab non-expansion rule (#i3952).
  - Empty paragraph height.
  - Spacing collapse (`max(after, before)`) and page top flattening.
  - East Asian grid line height calculations (matching issue #11 15.6pt / 18pt test cases).
  - Justification 20% micro-compression.
  - Tab stop alignment.
  - Inline graphic baseline and sizing.

### Task 6: Verification & Test Suite Execution
- Run `pytest tests/unit/writer/test_portions.py -v`.
- Run full repository test suite `pytest tests/`.
- Verify lint and code quality.

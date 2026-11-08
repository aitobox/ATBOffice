# Implementation Plan: Issue #311 - In-cell Rich Text Runs Layout, Multi-style Mixing and Sub/superscript

- **Issue**: #311
- **Branch**: `agent/issue-311-ledger-incell-rich-text`
- **Spec**: `docs/superpowers/specs/issue-311-ledger-incell-rich-text-spec.md`
- **Target Verification**: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/spreadsheet/test_cell_rich_text_render.py -v`

---

## Task 1: RichTextRun Model & CellData Integration
**Files to Modify**: `src/atboffice/modules/spreadsheet/models/sheet_model.py`
- Define `RichTextRun` dataclass with `text`, `font_family`, `font_size`, `bold`, `italic`, `underline`, `underline_style`, `strike`, `fg_color`, `vert_align`, and `clone()`.
- Add `rich_runs: list[RichTextRun] | None = None` to `CellData`.
- Update `CellData.clone()` to clone `rich_runs`.

## Task 2: OOXML Shared Strings & Inline Strings Parsing
**Files to Modify**: `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`
- Enhance `_parse_shared_strings` to retain rich text run formatting `<rPr>` (`rFont`, `sz`, `b`, `i`, `u`, `strike`, `color`, `vertAlign`) along with `<t>` text.
- Return structured representation for rich strings.
- In `_parse_worksheet`, populate `cell.rich_runs` when reading string cells (`<c t="s">` or `<c t="inlineStr">`).

## Task 3: OOXML Shared Strings Serialization
**Files to Modify**: `src/atboffice/modules/spreadsheet/io/xlsx_writer.py`
- Support `runs: list[RichTextRun] | None` in `SharedStringsManager.add()`.
- Format `<r>` with `<rPr>` elements (`<rFont>`, `<sz>`, `<b/>`, `<i/>`, `<u/>`, `<strike/>`, `<color>`, `<vertAlign>`) and `<t>` in `xl/sharedStrings.xml`.
- Pass `cell.rich_runs` when adding cell values to SST.

## Task 4: Viewport Layout and Sequential Run Rendering
**Files to Modify**: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- In `auto_fit_column`: calculate cell width using rich runs metrics if `cell.rich_runs` is set.
- In `_paint_cells`:
  - When `cell.rich_runs` is present and non-empty:
    - Split runs into lines by `\n` and optionally word wrap if `cell.wrap_text`.
    - Compute line widths and baseline positions.
    - Measure each run with `QFontMetricsF`.
    - For subscript (`vert_align == "subscript"`): scale font size ~70% and offset baseline downwards (`+base_fm.descent() * 0.8`).
    - For superscript (`vert_align == "superscript"`): scale font size ~70% and offset baseline upwards (`-base_fm.ascent() * 0.35`).
    - Render runs sequentially with `painter.drawText(QPointF(x, y), run.text)`.
    - Advance horizontal position accurately.
    - Apply cell clip boundaries.

## Task 5: Inplace Edit Preservation
**Files to Modify**: `src/atboffice/modules/spreadsheet/views/editor_controller.py`
- In `EditorController.commit()`, if `parsed_val == cell.value` or `text == str(cell.value)` or `text == "".join(r.text for r in cell.rich_runs)`:
  - Preserve `cell.rich_runs` instead of discarding it.

## Task 6: Unit Test Suite & Regression Verification
**Files to Create/Run**:
- Create `tests/unit/spreadsheet/test_cell_rich_text_render.py` testing:
  1. `RichTextRun` model properties and cloning.
  2. Sequential horizontal advancement rendering with `QFontMetricsF`.
  3. Subscript and superscript scaling and baseline offset calculation.
  4. Multi-color, multi-font, bold/italic mixed runs.
  5. OOXML reader parsing rich runs from shared strings and inline strings.
  6. OOXML writer roundtrip writing and re-reading rich runs without data loss.
  7. Inplace editing preservation.
  8. Column auto-fit with rich text runs.
- Run tests:
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/spreadsheet/test_cell_rich_text_render.py -v`
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/spreadsheet/ -ra`

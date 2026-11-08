# Specification: Issue #311 - In-cell Rich Text Runs Layout, Multi-style Mixing and Sub/superscript

- **Issue**: #311
- **Title**: [phase8] feat(ledger): In-cell rich text runs layout, multi-style mixing and sub/superscript
- **Parent Epic**: #308 (Phase 8: Document Rendering Parity, In-Cell Rich Text, Master Placeholders & Task Panes Alignment)
- **Status**: Draft / In Review

---

## 1. Problem Statement & Background

In `src/atboffice/modules/spreadsheet/views/grid_viewport.py`, cell rendering previously retrieved formatted text via `model.get_formatted_text(r, c)` and drew the text inside the cell using a single uniform `QFont` and color via `painter.drawText(text_rect, align_flag, text)`.

In OOXML (`.xlsx`), shared strings (`xl/sharedStrings.xml`) and inline strings (`<c t="inlineStr"><is>...`) can contain rich text runs `<r>` with distinct run formatting `<rPr>` (including `<b/>`, `<i/>`, `<u/>`, `<strike/>`, `<color/>`, `<sz/>`, `<rFont/>`, and `<vertAlign val="subscript|superscript"/>`).
Currently:
1. `xlsx_reader.py` flattens rich text runs into a single concatenated string, dropping all styling information (`sst.append("".join(parts))`).
2. `CellData` in `sheet_model.py` lacks a field to hold structured rich text runs.
3. `grid_viewport.py` paints the entire cell with a single uniform font and color. For scientific notations, chemical formulas (e.g., $H_2O$, $CO_2$, $E = mc^2$), or multi-color/multi-font runs, visual fidelity is lost.
4. `xlsx_writer.py` only writes plain text `<si><t>...</t></si>`, losing rich text on save.
5. Inplace editing in `editor_controller.py` clears or ignores rich text runs upon commit.

---

## 2. Architecture & Design Details

### 2.1 Data Model: `RichTextRun` and `CellData`

In `src/atboffice/modules/spreadsheet/models/sheet_model.py`:
Define `RichTextRun`:
```python
@dataclass
class RichTextRun:
    text: str
    font_family: str | None = None
    font_size: float | None = None  # in pt
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    underline_style: str | None = None  # "single", "double", etc.
    strike: bool | None = None
    fg_color: str | None = None  # hex color string e.g. "#FF0000"
    vert_align: str | None = None  # "subscript", "superscript", "baseline", or None

    def clone(self) -> RichTextRun:
        import copy
        return copy.copy(self)
```

Add `rich_runs: list[RichTextRun] | None = None` to `CellData`:
- `CellData.clone()` deep-copies `rich_runs`.
- If `rich_runs` is set, `cell.value` represents the plain concatenated text of the runs.

### 2.2 OOXML Reader (`xlsx_reader.py`)

1. In `_parse_shared_strings`:
   - Parse each `<si>` element. If it contains child `<r>` elements:
     - For each `<r>`, extract `<rPr>`:
       - Font family: `rFont` / `name`
       - Size: `sz`
       - Bold: `b`
       - Italic: `i`
       - Underline: `u`
       - Strikethrough: `strike`
       - Color: `color` (resolve rgb hex or indexed)
       - Vertical alignment: `vertAlign` ("subscript", "superscript", "baseline")
     - Extract text from `<t>` (handling `xml:space="preserve"` and unescaping).
     - Store structured entry in `sst`: either `str` for plain text, or an object/dict `{ "text": plain_text, "runs": [RichTextRun, ...] }`.
2. In `_parse_worksheet`:
   - When reading `<c t="s">`, if `sst[idx]` contains rich text runs, assign `cell.value = item["text"]` and `cell.rich_runs = item["runs"]`.
   - When reading `<c t="inlineStr">`, if `<is>` contains `<r>` elements, parse runs into `RichTextRun` and assign to `cell.rich_runs`.

### 2.3 OOXML Writer (`xlsx_writer.py`)

1. In `SharedStringsManager`:
   - Update `add(self, s: str, runs: list[RichTextRun] | None = None) -> int`.
   - If `runs` is present, store run metadata.
   - When generating `xl/sharedStrings.xml`, write `<si><r><rPr>...</rPr><t>...</t></r>...</si>`.
2. In `_serialize_worksheet`:
   - Pass `cell.rich_runs` to `sst_manager.add(str(cell.value), cell.rich_runs)`.

### 2.4 Viewport Rendering & Layout Engine (`grid_viewport.py`)

1. **Auto-fit and Width Measurement**:
   - When `cell.rich_runs` exists, compute effective width by summing `QFontMetricsF(run_font).horizontalAdvance(run.text)`.
2. **Text Lines Layout**:
   - Split runs by newline characters (`\n`).
   - If `cell.wrap_text` is True:
     - Wrap words at `available_width = span_w - 6`.
3. **Sequential Run Rendering**:
   - For each line:
     - Compute line width = sum of run advances.
     - Compute `line_x` based on `eff_h` (left, center, right).
     - Compute base baseline `line_y` based on `eff_v` (top, center, bottom).
     - For each run in line:
       - Determine font:
         - Base size: `run.font_size or cell.font_size`
         - If `run.vert_align == "subscript"`:
           - Scale font to `font_size * 0.7`.
           - Baseline offset: `+base_fm.descent() * 0.8` (downward shift).
         - If `run.vert_align == "superscript"`:
           - Scale font to `font_size * 0.7`.
           - Baseline offset: `-base_fm.ascent() * 0.35` (upward shift).
         - Apply bold, italic, underline, strikeout.
       - Set pen to `run.fg_color` or cell's color.
       - Paint with `painter.drawText(QPointF(current_x, line_y + offset), run.text)`.
       - Advance `current_x += fm.horizontalAdvance(run.text)`.
4. **Clipping & Boundaries**:
   - Painter clipping rectangle `QRect(col_x, row_y, span_w - 1, row_h - 1)` ensures clean boundaries without bleeding into neighboring cells.

### 2.5 Inplace Editing Preservation (`editor_controller.py`)

- In `EditorController.commit()`:
  - If `text == "".join(r.text for r in cell.rich_runs)` or `text == str(cell.value)`:
    - Retain `cell.rich_runs` so casual edits or confirmations do not discard rich formatting.

---

## 3. Verification & Acceptance Criteria

- [x] Full unit test suite `tests/unit/spreadsheet/test_cell_rich_text_render.py` covering:
  - `RichTextRun` creation, cloning, properties.
  - Multi-style cell parsing and rendering (chemical formula $H_2O$, superscript $E=mc^2$).
  - Subscript/superscript scaling and baseline offsets.
  - Mixed colors, fonts, bold/italic runs.
  - Roundtrip XLSX write & read preserving runs and formatting.
  - Inplace edit commit preserving rich runs.
  - Column auto-fit with rich text runs.
- [x] Zero regressions on all existing spreadsheet tests:
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/spreadsheet/ -v`

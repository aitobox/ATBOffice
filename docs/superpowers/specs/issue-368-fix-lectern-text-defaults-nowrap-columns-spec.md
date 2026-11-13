# Specification: Issue #368 - fix(lectern): default text style, no-wrap, and column layout for text bodies

## 1. Problem Statement
PowerPoint text boxes currently default to an excessively large font size (falling back to outline level 0's 32 pt bullet text) and completely ignore `<a:bodyPr wrap="none">`, multi-column (`numCol`), column spacing (`spcCol`), and right-to-left column direction (`rtlCol`).
Furthermore:
1. `<p:defaultTextStyle>` in `ppt/presentation.xml` is never parsed, causing text in non-placeholder shapes to lack baseline outline sizing (which defaults to 18 pt in DrawingML/PowerPoint).
2. The master's `otherStyle` is parsed in `_load_master` but never applied to non-placeholder shapes or table cells.
3. Multi-column settings (`numCol`, `spcCol`, `rtlCol`) are omitted from `TextBody` models and rendering, flattening multi-column text into a single column where text overflows past the bottom of the shape and becomes invisible.
4. Non-wrapping text (`wrap="none"`) still breaks at word boundaries instead of remaining on a single line and clipping overflow.

## 2. Requirements & Acceptance Criteria
1. **Presentation Default Text Style**:
   - Parse `<p:defaultTextStyle>` from `ppt/presentation.xml` (levels 1..9 via `_parse_style_levels`).
   - Store it on `PptxReader.default_text_style` and `pres.props["default_text_style"]`.
2. **Text Inheritance Precedence (lowest to highest)**:
   - Presentation `defaultTextStyle` (defaults to 18 pt for `otherStyle` text).
   - Master text styles (`otherStyle`, `bodyStyle`, `titleStyle`).
   - Placeholder on master, then placeholder on layout.
   - Shape's own `<p:txBody><a:lstStyle>`.
   - Paragraph-level `<a:pPr>`.
   - Run-level `<a:rPr>`.
3. **Table Cell Text Default Size**:
   - Table cells inherit text properties from `master.other_style` (and `defaultTextStyle`), falling back to 18 pt when run size is unspecified.
4. **No-Wrap Support (`wrap="none"`)**:
   - When `<a:bodyPr wrap="none">`, `text_body.wrap = False`.
   - In `ShapeTextEditorItem.render_static_text`: configure `QTextOption.WrapMode.NoWrap`.
   - Clip overflow to the shape bounds with `painter.setClipRect(text_rect)`.
5. **Multi-Column Layout (`numCol`, `spcCol`, `rtlCol`)**:
   - Parse `numCol`, `spcCol`, `rtlCol` in `_parse_text_body`.
   - Propagate placeholder column definitions from layout and master in `_apply_placeholder_text_inheritance`.
   - Model `cols: int`, `col_gap: float`, `rtl_col: bool` on `TextBody`.
   - In `render_static_text`: paginate `QTextDocument` via `doc.setPageSize(QSizeF(col_w, col_h))` and paint each column across the bounding rectangle, reversing horizontal order when `rtl_col=True`.
6. **Acceptance Criteria Verification**:
   - `openxml-sdk__cmpdThickThin...pptx`: Text lays out on one line at 18 pt.
   - `libreoffice__tdf104722.pptx`: "Subtitle for this part" lays out on one line and stays inside the slide.
   - `libreoffice__tdf140852.pptx`: Lays out two columns.
   - `openxml-sdk__main_bodyPr_rtlCol.pptx`: Lays out three columns and all text is visible.
   - Table cell text uses table style `otherStyle` when no run-level size is specified.

## 3. Architecture & Data Structures

### 3.1 Model Changes (`src/atboffice/modules/presentation/models/text.py`)
Add fields to `TextBody`:
```python
cols: int = 1
col_gap: float = 0.0
rtl_col: bool = False
```
Properties and aliases:
```python
@property
def columns(self) -> int:
    return self.cols

@columns.setter
def columns(self, value: int) -> None:
    self.cols = value
```
Update `to_dict` and `from_dict` to serialize and deserialize `cols`, `colGap`, and `rtlCol`.

### 3.2 Reader (`src/atboffice/modules/presentation/io/pptx_reader.py`)
- Parse `<p:defaultTextStyle>` in `PptxReader.read()` from `pres_xml`.
- In `_parse_text_body()`:
  - Parse `numCol`, `spcCol`, `rtlCol` from `bodyPr`.
- In `_apply_placeholder_text_inheritance()`:
  - Inherit `cols`, `col_gap`, `rtl_col`, and `wrap` from layout placeholder (`lp`) or master placeholder (`mp`).
- In `_parse_sp_element()`:
  - For non-placeholder shapes, apply style hierarchy starting from `self.default_text_style` -> `master_info.other_style` -> `shape.lstStyle` -> `pPr` -> `rPr`.
- In `_parse_graphic_frame()`:
  - Pass `layout_info` into `_parse_graphic_frame`.
  - For table cells, apply `other_style` (and `defaultTextStyle`) so runs with unspecified `size` default to 18 pt.

### 3.3 Static Text Painting (`src/atboffice/modules/presentation/views/text_editor.py`)
- If `not text_body.wrap`:
  - Set `doc.defaultTextOption().setWrapMode(QTextOption.WrapMode.NoWrap)`.
- If `text_body.cols > 1`:
  - Compute `col_w = max(10.0, (avail_w - (num_cols - 1) * col_gap) / num_cols)`.
  - Compute `col_h = avail_h`.
  - Call `doc.setPageSize(QSizeF(col_w, col_h))`.
  - Iterate `c` from 0 to `min(num_cols, doc.pageCount()) - 1`.
  - Calculate `col_x = (num_cols - 1 - c) * (col_w + col_gap)` if `rtl_col` else `c * (col_w + col_gap)`.
  - Clip to column rect and translate painter to paint page `c`.

### 3.4 Writer (`src/atboffice/modules/presentation/io/writer_text.py`)
- In `body_properties_to_xml`:
  - Emit `numCol` and `spcCol` if `cols > 1`.
  - Emit `rtlCol="1"` if `rtl_col` else `rtlCol="0"`.

## 4. Edge Cases Analyzed
1. `numCol` is missing or `"1"`: Do not overwrite layout placeholder's `cols > 1` (matches `.vibeoffice` `if (at(bp, 'numCol') && +at(bp, 'numCol') > 1)`).
2. `col_gap` default: When `spcCol` is omitted, default is `0.0 pt`.
3. Extreme column counts (e.g. `cols > 16` or `avail_w` too small): Guard `col_w` with `max(10.0, ...)`.
4. Page count less than `num_cols`: Only render available pages without error.
5. Mixed runs in table cells: Runs with explicit `sz` retain their size; only runs without `size` inherit `18 pt`.
6. Negative or missing margins/indents: Safely default to 0.0 without crash.

# Implementation Plan: Issue #368 - fix(lectern): default text style, no-wrap, and column layout for text bodies

## Task Breakdown

### Task 1: Extend `TextBody` Model (`src/atboffice/modules/presentation/models/text.py`)
- Add fields `cols: int = 1`, `col_gap: float = 0.0`, `rtl_col: bool = False`.
- Add `columns` property with getter and setter pointing to `cols`.
- Update `to_dict()` and `from_dict()` to serialize `cols`, `colGap`, and `rtlCol`.
- Test: Verify instantiation and dict round-tripping of `TextBody(cols=3, col_gap=28.35, rtl_col=True)`.

### Task 2: Presentation Default Text Style & Reader Inheritance (`src/atboffice/modules/presentation/io/pptx_reader.py`)
- In `PptxReader.read()`:
  - Parse `<p:defaultTextStyle>` from `pres_xml` using `self._parse_style_levels`.
  - Store on `self.default_text_style` and `pres.props["default_text_style"]`.
- In `_parse_text_body()`:
  - Parse `numCol`, `spcCol`, `rtlCol` from `bodyPr`.
- In `_apply_placeholder_text_inheritance()`:
  - If `text_body.cols <= 1`: inherit `cols`, `col_gap`, and `rtl_col` from layout placeholder (`lp`) or master placeholder (`mp`).
  - If `text_body.wrap`: inherit `wrap` from `lp` or `mp`.
- In `_parse_sp_element()`:
  - For non-placeholder shapes, apply style inheritance from `default_text_style` -> `master.other_style` -> `lstStyle` -> `pPr` -> `rPr`.
  - Specifically ensure run font size defaults to 18.0 pt when unspecified.
- In `_parse_shape()` and `_parse_graphic_frame()`:
  - Pass `layout_info` to `_parse_graphic_frame`.
  - For table cells, inherit default size (18.0 pt) from `master.other_style` / `default_text_style`.

### Task 3: Static Painting Support for No-Wrap and Multi-Column Layout (`src/atboffice/modules/presentation/views/text_editor.py`)
- In `ShapeTextEditorItem.render_static_text()`:
  - If `not text_body.wrap`: configure `doc.defaultTextOption().setWrapMode(QTextOption.WrapMode.NoWrap)`.
  - Always clip painter to `text_rect`.
  - If `text_body.cols > 1`:
    - Calculate column width `col_w = max(10.0, (avail_w - (num_cols - 1) * col_gap) / num_cols)`.
    - Set document page size `doc.setPageSize(QSizeF(col_w, avail_h))`.
    - Paint each page into its column rectangle, flipping horizontal coordinates if `text_body.rtl_col` is `True`.
  - When `run.size is None`, ensure fallback font size is 18 pt (instead of hardcoded 32 pt for non-body shapes).

### Task 4: Text Body XML Serialization (`src/atboffice/modules/presentation/io/writer_text.py`)
- In `body_properties_to_xml`:
  - When `cols > 1`: emit `numCol="{cols}"` and `spcCol="{pt_to_emu(col_gap)}"`.
  - Emit `rtlCol="1"` when `rtl_col` is True, else `rtlCol="0"`.

### Task 5: Unit Tests (`tests/test_lectern_text_defaults.py`)
- Test 1 (`test_default_text_style_18pt`): Verify `openxml-sdk__cmpdThickThin...pptx` resolves text run size to 18 pt.
- Test 2 (`test_nowrap_single_line`): Verify `libreoffice__tdf104722.pptx` subtitle has `wrap=False` and renders onto 1 line without wrapping.
- Test 3 (`test_multicolumn_layout`): Verify `libreoffice__tdf140852.pptx` body shape inherits `cols=2` from layout, and `openxml-sdk__main_bodyPr_rtlCol.pptx` parses `cols=3`.
- Test 4 (`test_table_cell_other_style`): Verify table cells without run-level size inherit 18 pt from `otherStyle`.

### Task 6: Verification & Quality Checks
- Run `pytest tests/test_lectern_text_defaults.py -v`.
- Run full presentation test suite.
- Run `ruff check .` ensuring max-line-length <= 100 and clean lint.
- Run `scripts/run_office_diff.py --file libreoffice__tdf104722.pptx --score-only`.

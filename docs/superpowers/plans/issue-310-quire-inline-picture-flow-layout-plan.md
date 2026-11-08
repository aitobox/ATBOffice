# Implementation Plan: Issue #310 — [phase8] feat(quire): Inline picture flow layout and line height/baseline measurement

## Proposed Changes

### 1. `src/atboffice/modules/writer/layout/portions.py`
- Import `PictureItem` and `WrapMode` from `atboffice.modules.writer.models.drawing`.
- In `decompose_paragraph_to_portions()`:
  - Explicitly match `isinstance(item, PictureItem)` or `getattr(item, "t", "") in ("picture", "img")`.
  - Check `is_floating = float_pr is not None and getattr(float_pr, "wrap", None) not in (WrapMode.INLINE, "inline", None)`.
  - If floating: output zero-width anchor portion with `counts_for_height=False`.
  - If inline: output `PortionType.GRAPHIC` with `width=item.width`, `ascent=item.height`, `descent=0.0`, `counts_for_height=True`.
- In `layout_paragraph()` / `finalize_line()`:
  - Verify baseline alignment: `ascent = max(pt.ascent for pt in counting)`.
  - For lines with pictures, ensure `line.height` reflects `max(font_line_height, pic_height)` and picture bottom aligns to text baseline.
  - For lines with only pictures, ensure picture rests at the foot of the line if strut height exceeds picture height.

### 2. `src/atboffice/modules/writer/views/canvas_view.py`
- Add `self._pixmap_cache: dict[str, QPixmap] = {}` to `CanvasView.__init__` and clear it on `set_document()`.
- Add `_resolve_pixmap(self, pic: PictureItem) -> QPixmap | None`:
  - Check `_pixmap_cache`.
  - Check `pic.raw_data` for `"pixmap"`, `"image"`, or `"bytes"`.
  - Check `self.doc._source_pkg` or `self.doc.keep.get("source_pkg")` via `pkg.read_part(pic.image_part)`.
  - Check disk path if `os.path.isfile(pic.image_part)`.
  - Cache valid pixmaps.
- Add `_paint_picture(self, painter: QPainter, pic: PictureItem, dest_rect: QRectF, zoom: float = 1.0, is_vector: bool = False) -> None`:
  - Query device pixel ratio `dpr = float(self.devicePixelRatioF()) if hasattr(self, "devicePixelRatioF") else 1.0`.
  - Enable `QPainter.RenderHint.SmoothPixmapTransform`.
  - Compute `src_rect` taking `pic.crop` into account.
  - Handle rotation `pic.rotation`.
  - Call `painter.drawPixmap(dest_rect, pixmap, src_rect)`.
  - If pixmap is null or unavailable: render graceful dashed placeholder with label.
- Update `_paint_page_content()`, `_paint_header_footer()`, and `render_page_to_painter()`:
  - In each section where `po.type == PortionType.GRAPHIC`, handle `isinstance(po.data, PictureItem)` by invoking `_paint_picture()`.

### 3. `tests/unit/writer/test_inline_picture_layout_and_paint.py`
- Test cases:
  1. `test_decompose_inline_picture_to_portion`: Verify `PortionType.GRAPHIC`, dimensions, `counts_for_height=True`.
  2. `test_decompose_floating_picture_to_anchor`: Verify zero-width anchor with `counts_for_height=False`.
  3. `test_line_height_elevated_by_picture`: Verify `line.height >= pic_height` and baseline accommodates picture.
  4. `test_picture_and_text_baseline_alignment`: Verify picture bottom rests on text baseline.
  5. `test_inline_picture_line_wrapping`: Verify multiple pictures advance horizontally and wrap when exceeding column width.
  6. `test_canvas_paint_inline_picture_with_pixmap`: Verify `_paint_picture` draws pixmap with DPR and SmoothPixmapTransform.
  7. `test_canvas_paint_picture_with_crop_and_rotation`: Verify crop `src_rect` calculation and rotation transform.
  8. `test_canvas_paint_missing_picture_fallback`: Verify graceful placeholder rendering without raising exceptions.

## Verification Commands
```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/writer/test_inline_picture_layout_and_paint.py -v
QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/writer/ -v
```

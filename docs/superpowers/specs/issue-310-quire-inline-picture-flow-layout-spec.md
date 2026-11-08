# Specification: Issue #310 — [phase8] feat(quire): Inline picture flow layout and line height/baseline measurement

## 1. Overview & Problem Statement

In the Quire word processor module, `docx_reader.py` extracts inline `<w:drawing>` and `<w:pict>` elements into `PictureItem` models. However:
1. `src/atboffice/modules/writer/layout/portions.py` does not explicitly recognize `PictureItem` in `decompose_paragraph_to_portions()`. While a generic fallback existed, floating drawings vs inline pictures were not disambiguated by `wrap` mode, and `PictureItem` attributes were not fully integrated with typographic line metrics.
2. Inline pictures were completely omitted from rendering in `src/atboffice/modules/writer/views/canvas_view.py` (`_paint_page_content`, `_paint_header_footer`, and `render_page_to_painter`), which only checked for `OfficeMathItem` under `PortionType.GRAPHIC`. Consequently, documents with inline figures and illustrations showed empty blank spaces.
3. High-DPI (Retina) display pixel ratios (DPR) were not taken into account when rendering raster pixmaps, leading to potential blurriness or incorrect scaling.

## 2. Technical Architecture & Design

### 2.1 Paragraph Decomposition (`portions.py`)
- Import `PictureItem` and `WrapMode` from `atboffice.modules.writer.models.drawing`.
- In `decompose_paragraph_to_portions()`:
  - Add explicit branch for `isinstance(item, PictureItem)` (and `getattr(item, "t", "") in ("picture", "img")`).
  - Check whether the object is floating: `is_floating = float_pr is not None and getattr(float_pr, "wrap", None) not in (WrapMode.INLINE, "inline", None)`.
  - If floating: create a zero-width, non-height-raising anchor portion (`type=PortionType.GRAPHIC`, `width=0.0`, `ascent=0.0`, `descent=0.0`, `counts_for_height=False`, `data=item`).
  - If inline:
    - Width: `w = float(getattr(item, "width", 0.0) or getattr(item, "w", 0.0) or 72.0)`.
    - Height: `h = float(getattr(item, "height", 0.0) or getattr(item, "h", 0.0) or 72.0)`.
    - Create `Portion(type=PortionType.GRAPHIC, width=w, ascent=h, descent=0.0, counts_for_height=True, data=item)`.
    - Advance `char_offset += 1`.

### 2.2 Line Height & Baseline Alignment (`portions.py`)
- According to Microsoft Word typographic rules:
  - An inline picture rests on the line's text baseline (bottom of picture aligns with text baseline).
  - Its ascent is its physical height (`ascent = h`), while its descent is 0 (`descent = 0.0`).
  - In a line containing both text and pictures:
    - `line.ascent = max(max_text_ascent, max_pic_height)`
    - `line.descent = max_text_descent`
    - `line.baseline = line.ascent`
    - `line.height = (line.ascent + line.descent) * line_mult` (or exact/atLeast constraints).
    - As a result, `line.height >= max(font_line_height, max_pic_height)`.
  - In a line containing only pictures:
    - `line.ascent = max_pic_height`
    - `line.descent = 0.0`
    - Line height is at least `max(pic_height * line_mult, mark_natural_height)`.
    - If `height > ascent` (strut applies), the picture sits at the foot of the line (`line.baseline = height`).

### 2.3 Canvas & Vector Rendering (`canvas_view.py`)
- Implement a centralized rendering method:
  `_paint_picture(painter: QPainter, pic: PictureItem, dest_rect: QRectF, zoom: float = 1.0, is_vector: bool = False) -> None`
- Image resolution pipeline:
  1. Check in-memory pixmap cache `self._pixmap_cache` on `CanvasView`.
  2. If not cached, inspect:
     - `pic.raw_data` for `"pixmap"`, `"image"`, or `"bytes"`.
     - `self.doc._source_pkg` or `self.doc.keep["source_pkg"]` via `pkg.read_part(pic.image_part)`.
     - Local file system if `pic.image_part` is a valid file path.
     - `self.doc.keep.get("media", {}).get(pic.image_part)`.
  3. If loaded into `QPixmap`:
     - Calculate destination rectangle `QRectF(x_px, baseline_px - pic_h_px, pic_w_px, pic_h_px)`.
     - Apply device pixel ratio (DPR) awareness:
       - Query DPR from widget (`self.devicePixelRatioF()`) or painter device.
       - Enable `QPainter.RenderHint.SmoothPixmapTransform`.
     - Handle cropping (`pic.crop.left`, `pic.crop.top`, `pic.crop.right`, `pic.crop.bottom`) to compute `src_rect` in image pixels.
     - Handle rotation (`pic.rotation`) with `painter.translate(center)` and `painter.rotate()`.
     - Draw via `painter.drawPixmap(dest_rect, pixmap, src_rect)`.
  4. If image data is unavailable or decoding fails:
     - Gracefully draw a subtle placeholder rectangle with dashed border and alt text, guaranteeing zero crashes.
- Wire `_paint_picture` into:
  - `_paint_page_content` (column fragments and table cells).
  - `_paint_header_footer` (headers and footers).
  - `render_page_to_painter` (vector / PDF / printing pipeline).

## 3. Verification Plan
- Unit test suite: `tests/unit/writer/test_inline_picture_layout_and_paint.py`
  - Inline picture portion decomposition (ascent, descent, width, counts_for_height).
  - Line height and baseline calculation with mixed text and inline picture.
  - Multi-picture line wrapping and line advance.
  - QPixmap image rendering with DPR awareness, cropping, and rotation.
  - Fallback placeholder rendering when image part is missing.
- Full project test suite regression check:
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/writer/test_inline_picture_layout_and_paint.py -v`

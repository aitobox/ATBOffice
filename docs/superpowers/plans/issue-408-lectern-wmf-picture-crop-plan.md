# Plan: Issue #408

1. Tests in `tests/gui/test_phase7_pptx_render.py`:
   - fixture slide renders the bitmap inside the picture frame (not the #F5F5F5 placeholder),
     the frame bottom shows the crop (content from the top 62.6% only), area outside frame is untouched;
   - a synthetic bitmap-bearing WMF (`META_STRETCHDIB`) picture renders its bitmap color;
   - a PNG picture with a bottom srcRect crop shows only the uncropped half.
   Run → expect the metafile tests to fail.
2. `shape_item.py`: `_decode_picture_bytes(data) -> QImage | None` with metafile fallback; use it
   in `_paint_media_or_image`.
3. Run the module test file, then the full suite.

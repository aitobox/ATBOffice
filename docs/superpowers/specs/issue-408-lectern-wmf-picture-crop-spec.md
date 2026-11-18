# Spec: Issue #408 — Render embedded WMF pictures with source cropping

## Problem
`libreoffice__tdf149206.pptx` slide 1 holds one picture, `ppt/media/image1.wmf`, with
`<a:srcRect b="37396"/>`. The canvas shows the gray dashed fallback rectangle instead of the
bitmap. The part is named `.wmf` but its bytes are an EMF (`EMR_HEADER`, ` EMF` signature) whose
content is an `EMR_STRETCHDIBITS` bitmap.

## Root cause
`PictureShapeItem._paint_media_or_image` (shape_item.py) decodes picture bytes only with
`QImage.fromData`. Qt has no WMF/EMF reader, so decoding fails and the placeholder is drawn.
The metafile player in `atboffice.vfs.metafile` already renders this file correctly, and the
srcRect crop is already parsed (`pptx_reader._parse_src_rect`) and applied
(`_image_target_rect`).

## Design
- Add a small decode helper in `shape_item.py`: try `QImage.fromData`; if that fails and the bytes
  sniff as EMF or WMF (content, not extension — this fixture proves the extension can lie),
  rasterize with `render_metafile_to_image`.
- Raster size cap: 2048 px on the long side, so a zoomed canvas stays sharp while memory stays bounded.
- The result is cached by the existing `_cached_media_key`, so the metafile plays once per item.
- Unrecognized or corrupt bytes still fall back to the placeholder (no exceptions in paint).
- The original (`.vibeoffice/public/lectern/js/pptx-read.js`) also converts WMF/EMF to PNG
  via its metafile player; this matches its behavior.

## Edge cases
- Corrupt metafile → player returns None → placeholder; paint never raises.
- Placeable WMF and bitmap-bearing WMF (`META_STRETCHDIB`) → handled by the same player.
- Ordinary PNG with crop → unchanged path; regression test added.
- No UI strings are added, so no i18n changes.

## Task list
- [x] Task 1: Root-cause trace (decode path, crop path, fixture bytes)
- [x] Task 2: Regression tests (EMF fixture with bottom crop, bitmap-bearing WMF, PNG with crop)
- [x] Task 3: Metafile fallback in picture decoding
- [x] Task 4: Module test suite and full suite pass
- [x] Task 5: Grill audit

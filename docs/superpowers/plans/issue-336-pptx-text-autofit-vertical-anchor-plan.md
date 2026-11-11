# Implementation Plan: Issue #336 - Implement PPTX text auto-fitting normAutofit and vertical anchor alignment

## Task 1: Update TextBody Data Model
- Target: `src/atboffice/modules/presentation/models/text.py`
- Steps:
  1. Add `has_explicit_font_scale: bool = False` to `TextBody`.
  2. Add `anchor_ctr: bool = False` to `TextBody`.
  3. Verify default values maintain full backwards compatibility.

## Task 2: Enhance PPTX Reader for normAutofit, Anchor, and Placeholder Cascade
- Target: `src/atboffice/modules/presentation/io/pptx_reader.py`
- Steps:
  1. In `_parse_text_body()`:
     - When parsing `normAutofit`, check `fontScale` attribute. If present, compute `font_scale = max(0.01, min(1.0, float(fontScale) / 100000.0))` and set `has_explicit_font_scale = True`.
     - Check `lnSpcReduction` attribute. If present, compute `ln_spc_reduction = max(0.0, min(1.0, float(lnSpcReduction) / 100000.0))`.
     - Map anchor `"just"` and `"dist"` to `"ctr"`.
     - Read `anchorCtr` boolean (`anchorCtr == "1"`).
  2. In `_apply_placeholder_text_inheritance()`:
     - Cascade `anchor`, `anchor_ctr`, `autofit`, `font_scale`, `ln_spc_reduction`, and `has_explicit_font_scale` when shape text body lacks an explicit setting.

## Task 3: Support Image Bytes Fallback in Shape Graphics Item
- Target: `src/atboffice/modules/presentation/views/shape_item.py`
- Steps:
  1. In `_paint_media_or_image()`:
     - If `self.model.media_item.poster_bytes` is None and `self.model.media` is present:
     - Retrieve image bytes from `self.scene().presentation.props.get("_media_map", {}).get(self.model.media)`.
     - If found, load `QPixmap` from raw bytes and draw scaled to target rectangle with smooth transformation.
     - Prevent falling through to gray placeholder box when valid image data exists.

## Task 4: Align Slide Workspace Background Color
- Target: `src/atboffice/modules/presentation/views/slide_canvas.py`
- Steps:
  1. In `SlideScene.drawBackground()`:
     - Update outer workspace color from `#EBEBEB` to `#B7C6E2` (183, 198, 226) matching `.vibeoffice`'s `--work` CSS variable.

## Task 5: Preserve Explicit Font Scale in Text Editor Static Rendering
- Target: `src/atboffice/modules/presentation/views/text_editor.py`
- Steps:
  1. In `render_static_text()`:
     - Check if `body.autofit == "norm"`.
     - If `body.has_explicit_font_scale` or (`body.font_scale < 0.999` and `body.font_scale > 0.0`):
       Use `effective_font_scale = body.font_scale` and `effective_ln_spc = body.ln_spc_reduction` directly.
     - Otherwise, call `solve_norm_autofit_scale()`.
  2. Verify vertical anchor calculations for top, center (`ctr`), and bottom (`b`) alignment.

## Task 6: Comprehensive Regression Testing & Visual Diff Verification
- Targets:
  - `tests/gui/test_phase9_pptx_autofit.py`
  - `docs/clone/OFFICE_DOCS_DIFF.md`
- Steps:
  1. Write tests in `tests/gui/test_phase9_pptx_autofit.py`:
     - Test `normAutofit` parsing with `fontScale` and `lnSpcReduction`.
     - Test vertical anchor mapping and placeholder inheritance.
     - Test media map fallback image loading in `ShapeGraphicsItem`.
     - Test static text rendering scale preservation.
  2. Run unit tests via pytest: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_phase9_pptx_autofit.py -v`.
  3. Execute visual diff: `PYTHONPATH=src:scripts conda run -n ATBOffice python scripts/run_office_diff.py --file tests/docs/powerpoint/pptx/libreoffice__TextFittingComparisonWithMSO_3.pptx --capture`.
  4. Ensure similarity >= 92.0% (target >= 94%).
  5. Run full test suite: `PYTHONPATH=src conda run -n ATBOffice pytest tests/`.

# Specification: Issue #336 - Implement PPTX text auto-fitting normAutofit and vertical anchor alignment

## 1. Problem Statement & Background
In `docs/clone/OFFICE_DOCS_DIFF.md`, `libreoffice__TextFittingComparisonWithMSO_3.pptx` exhibited significant rendering discrepancies (similarity ~43.7%).
Root cause analysis revealed four distinct issues:
1. **Auto-fit Font Scaling Overwrite**:
   - In PPTX OpenXML, `<a:normAutofit fontScale="92500" lnSpcReduction="20000"/>` stores the pre-calculated font scale (92.5%) and line spacing reduction (20%).
   - In `.vibeoffice/public/lectern/js/render.js`, static rendering honors `(tx.fontScale || 1)` directly when present, rather than blindly recomputing a generic scale.
   - In ATBOffice (`src/atboffice/modules/presentation/views/text_editor.py`), `render_static_text()` detected `autofit == "norm"` and invoked `solve_norm_autofit_scale()`, producing an erroneous scale (0.874) that overwrote the explicitly authored font scale.
2. **Text Anchor & Vertical Alignment**:
   - In OpenXML PresentationML, `<p:spPr>` / `<p:txBody>` contains `<a:bodyPr anchor="ctr" anchorCtr="1">`.
   - In `.vibeoffice/public/lectern/js/pptx-read.js`:
     `anchor: { t: 't', ctr: 'ctr', b: 'b', just: 'ctr', dist: 'ctr' }[at(bp, 'anchor')] || 't'`, and `anchorCtr: at(bp, 'anchorCtr') === '1'`.
   - Shape placeholder inheritance: when a shape inherits from layout or master placeholders, text body properties (`anchor`, `anchor_ctr`, `autofit`, `font_scale`, `ln_spc_reduction`) must cascade down unless explicitly overridden.
   - Text layout vertical positioning: top margin/offset must shift by `(avail_h - doc_h) / 2.0` for `ctr` and `(avail_h - doc_h)` for `b`.
3. **Picture Rendering Fallback**:
   - Slide 1 contains background pictures (Picture 12 and Picture 13). In `shape_item.py`, `_paint_media_or_image` only checked `self.model.media_item.poster_bytes`. Ordinary pictures store their image path in `model.media` and data in `presentation.props["_media_map"]`.
   - Missing data caused `_paint_media_or_image` to paint a solid `#F5F5F5` gray rectangle, obscuring slide elements and severely degrading visual fidelity.
4. **Slide Workspace Background Color Mismatch**:
   - `SlideScene.drawBackground()` in `slide_canvas.py` filled the canvas background with `#EBEBEB` (235, 235, 235).
   - `.vibeoffice` uses CSS variable `--work: #B7C6E2` (183, 198, 226) in `.editor-wrap`. Aligning this color eliminates ~250,000 pixel discrepancies outside the slide rect.

## 2. Requirements & Acceptance Criteria
- [x] In `src/atboffice/modules/presentation/models/text.py`:
  - Extend `TextBody` with `has_explicit_font_scale: bool = False` and `anchor_ctr: bool = False`.
- [x] In `src/atboffice/modules/presentation/io/pptx_reader.py`:
  - In `_parse_text_body()`: parse `normAutofit` attributes `fontScale` and `lnSpcReduction`, setting `has_explicit_font_scale = True` when `fontScale` is explicitly specified.
  - Map anchor attribute values: `"just"` and `"dist"` map to `"ctr"`; parse `anchorCtr` boolean flag.
  - In `_apply_placeholder_text_inheritance()`: cascade `anchor`, `anchor_ctr`, `autofit`, `font_scale`, `ln_spc_reduction`, and `has_explicit_font_scale` from layout/master placeholders to shape text bodies if not set on the shape.
- [x] In `src/atboffice/modules/presentation/views/text_editor.py`:
  - In `render_static_text()`: when `has_explicit_font_scale` is True or `font_scale < 0.999`, preserve and apply the explicit `font_scale` and `ln_spc_reduction` directly rather than invoking `solve_norm_autofit_scale()`.
  - Maintain vertical anchor alignment calculation with proper top/bottom insets and bounding bounds.
- [x] In `src/atboffice/modules/presentation/views/shape_item.py`:
  - In `_paint_media_or_image()`: resolve image bytes from `self.scene().presentation.props.get("_media_map", {}).get(self.model.media)` when `poster_bytes` is None and `self.model.media` is present.
- [x] In `src/atboffice/modules/presentation/views/slide_canvas.py`:
  - Update `SlideScene.drawBackground` to use `#B7C6E2` (183, 198, 226), matching `.vibeoffice`'s `--work` workspace canvas background.
- [x] Elevate `libreoffice__TextFittingComparisonWithMSO_3.pptx` visual similarity to >= 92.0% (target >= 94%).
- [x] Add automated regression tests in `tests/gui/test_phase9_pptx_autofit.py`.
- [x] All existing tests pass without regressions.

## 3. Architecture & Interface Contracts

### 3.1 TextBody Model Extension
```python
@dataclass
class TextBody:
    anchor: str = "t"  # "t" | "ctr" | "b" | "dist" | "just"
    anchor_ctr: bool = False
    autofit: str = "none"  # "none" | "norm" | "sp"
    font_scale: float = 1.0
    ln_spc_reduction: float = 0.0
    has_explicit_font_scale: bool = False
    ...
```

### 3.2 Reading normAutofit and Anchoring
In `src/atboffice/modules/presentation/io/pptx_reader.py`:
```python
norm = _find_child(body_pr, "normAutofit")
if norm is not None:
    body.autofit = "norm"
    fs_val = _attr(norm, "fontScale")
    if fs_val:
        try:
            body.font_scale = max(0.01, min(1.0, float(fs_val) / 100000.0))
            body.has_explicit_font_scale = True
        except ValueError:
            pass
    ln_val = _attr(norm, "lnSpcReduction")
    if ln_val:
        try:
            body.ln_spc_reduction = max(0.0, min(1.0, float(ln_val) / 100000.0))
        except ValueError:
            pass
```

### 3.3 Text Rendering Dynamic vs Explicit Fit
In `src/atboffice/modules/presentation/views/text_editor.py`:
```python
if body.autofit == "norm":
    if body.has_explicit_font_scale or (body.font_scale < 0.999 and body.font_scale > 0.0):
        effective_font_scale = body.font_scale
        effective_ln_spc = body.ln_spc_reduction
    else:
        effective_font_scale, effective_ln_spc = solve_norm_autofit_scale(...)
```

## 4. Verification & Testing Strategy
- Unit & GUI tests in `tests/gui/test_phase9_pptx_autofit.py`:
  - `test_norm_autofit_parsing`: Verify `fontScale` and `lnSpcReduction` attributes on `a:normAutofit`.
  - `test_anchor_alignment_parsing`: Verify `anchor` ("ctr", "b", "t") and `anchorCtr`.
  - `test_placeholder_text_inheritance`: Verify inheritance of `anchor` and autofit settings from master/layout.
  - `test_shape_image_rendering_from_media_map`: Verify picture shapes load data from `_media_map`.
  - `test_render_static_text_explicit_scale`: Verify `render_static_text` uses explicit scale without overwrite.
- Visual parity test:
  Run `PYTHONPATH=src:scripts conda run -n ATBOffice python scripts/run_office_diff.py --file tests/docs/powerpoint/pptx/libreoffice__TextFittingComparisonWithMSO_3.pptx --capture` and confirm >= 92.0% similarity.

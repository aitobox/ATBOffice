# Specification: Fix Lectern Text AutoFit (normAutofit) and Vertical Anchor Alignment

- **Issue**: [#283](https://github.com/aitobox/ATBOffice/issues/283)
- **Epic**: [#281](https://github.com/aitobox/ATBOffice/issues/281) (Step 2 of 4)
- **Status**: Draft -> Accepted
- **Author**: Antigravity Autonomous Agent

---

## 1. Context & Background

In `.agents/skills/atb-office-diff` audits and presentation fidelity testing (e.g., `tests/docs/powerpoint/pptx/libreoffice__TextFittingComparisonWithMSO_3.pptx`), the presentation module (Lectern) exhibits text layout drift and bounding box overflow:
1. **normAutofit Handling**: OOXML DrawingML `<a:normAutofit fontScale="..." lnSpcReduction="..."/>` specifies that text should automatically scale down font sizes and optionally compress line spacing to fit within the text container's available height and width. Currently, `PptxReader` reads attributes if present, but when files omit explicit scale factors or when text overflows the container, there is no precise binary search solver to dynamically compute the fitting scale while preserving relative font size proportions across multi-level / multi-run paragraphs.
2. **Missing Paragraph Spacing Properties in PPTX I/O**: `<a:pPr>` attributes and elements for `lnSpc` (line spacing), `spcBef` (space before), and `spcAft` (space after) are not parsed in `PptxReader._parse_paragraph` and not emitted in `writer_text.py`, causing inter-paragraph spacing to be lost during import and roundtrip.
3. **QTextDocument Rendering Geometry & Margins**: By default, `QTextDocument` in PySide6 applies a default `documentMargin` of 4.0pt, which adds unexpected padding around all text blocks, drifting the text baseline by 4pt vertically and horizontally.
4. **Vertical Anchor Geometry**: Text frames with `anchor="ctr"` (vertical centering) and `anchor="b"` (bottom alignment) require exact offset calculations relative to actual document content height with `documentMargin=0.0`, incorporating paragraph spacing and line spacing reductions.

---

## 2. Requirements & Acceptance Criteria

### 2.1 PPTX Reader & Writer Enhancements
- [x] **Paragraph Spacing Parsing**:
  - Parse `<a:lnSpc>` (`<a:spcPts>` in 1/100 pt, `<a:spcPct>` in 1/1000 %) into `para.props["lnSpc"] = {"pts": float}` or `{"pct": float}`.
  - Parse `<a:spcBef>` (`<a:spcPts>`, `<a:spcPct>`) into `para.props["spcBef"]`.
  - Parse `<a:spcAft>` (`<a:spcPts>`, `<a:spcAft>`) into `para.props["spcAft"]`.
  - Parse `<a:pPr marL="..." indent="...">` in EMU to points into `para.props["marL"]` and `para.props["indent"]`.
- [x] **Paragraph Spacing Serialization**:
  - In `writer_text.py`, serialize `lnSpc`, `spcBef`, and `spcAft` into standard DrawingML XML `<a:lnSpc>`, `<a:spcBef>`, `<a:spcAft>`.
  - Ensure lossless roundtrip serialization and deserialization.

### 2.2 Dynamic normAutofit Solver (`solve_norm_autofit_scale`)
- [x] **Proportional Multi-Run Scaling**:
  - Scale all runs and paragraph margins proportionally using a single unified scale factor: `scaled_sz = original_sz * scale`.
  - Binary search solver between `min_scale` (0.20) and `max_scale` (1.0) with tolerance <= 0.005.
  - If text fits at scale 1.0, return `(1.0, 0.0)`.
  - If text overflows at scale 1.0, compute optimal `font_scale` so document height fits inside `avail_h`.
  - If `font_scale < 0.90`, apply line spacing reduction `ln_spc_reduction = min(0.20, (1.0 - font_scale) * 0.5)`.

### 2.3 QTextDocument Rendering & Vertical Anchor Alignment
- [x] **Zero Document Margin**:
  - Explicitly set `doc.setDocumentMargin(0.0)` in `ShapeTextEditorItem.render_static_text` and `load_from_text_body`.
- [x] **Apply Paragraph Spacing**:
  - Apply `spcBef` as `block_fmt.setTopMargin(spc_bef_pts)` (for paragraphs after the first).
  - Apply `spcAft` as `block_fmt.setBottomMargin(spc_aft_pts)`.
  - Apply `lnSpc` and `ln_spc_reduction` via `block_fmt.setLineHeight(...)`.
- [x] **Vertical Alignment Offset**:
  - `anchor == "t"`: `dy = 0.0`.
  - `anchor == "ctr"`: `dy = max(0.0, (avail_h - doc_h) / 2.0)`.
  - `anchor == "b"`: `dy = max(0.0, avail_h - doc_h)`.

### 2.4 Test Suite & Quality Verification
- [x] Unit tests for paragraph spacing import/export, dynamic solver, and vertical anchor calculations.
- [x] All presentation/lectern tests pass.

---

## 3. Architecture & Edge Case Analysis

### Edge Cases
1. **Empty Paragraphs or Single-Run Text**: Must not divide by zero or crash if `need_height == 0` or `avail_height <= 0`.
2. **Extreme Text Overflow**: When text cannot fit even at `min_scale` (0.20), clamp to `min_scale` and avoid negative dimensions.
3. **Mixed Font Sizes**: Paragraphs with headers (e.g. 40pt) and body text (e.g. 18pt) must shrink in strict proportion, never flattening all text to a single uniform size.
4. **spcBef on First Paragraph**: In Presentation rendering, top margin before the very first paragraph in a top-anchored box is ignored to align with the shape boundary.

---

## 4. Verification Plan

```bash
# Unit & integration tests
PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/presentation/test_norm_autofit_vertical_anchor.py -v
PYTHONPATH=src conda run -n ATBOffice pytest tests/ -k "lectern or presentation" -v
```

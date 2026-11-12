# Design Specification: Issue #358 — Foreground-Weighted Visual Diff Scoring (`TASK-DOC-T01`)

- **Issue**: [#358](https://github.com/aitobox/ATBOffice/issues/358) (`[TASK-DOC-T01] fix(audit): foreground-weighted score — stop rating missing ink as parity`)
- **Branch**: `agent/issue-358-foreground-weighted-score`
- **Date**: 2026-11-12
- **Status**: Approved (Autonomous Decision Rule >= 90% confidence)

---

## 1. Problem Statement

Both `.agents/skills/atb-office-diff/scripts/doc_imgdiff.py` and `scripts/office_diff/comparator.py` currently score rendered document pairs using whole-image Mean Absolute Error (MAE):

```python
similarity = 1.0 - (mae / 255.0)
```

Because white page/slide/sheet backgrounds and outer viewport desks occupy 70–99% of every screenshot, documents with missing charts, missing shapes, missing text, or missing fills (`LOSS` / `WRONG`) still score >= 95% (`PARITY_MATCH`). In the 2026-11-12 evidence set, 37 of 59 `PARITY_MATCH` documents had `LOSS` or `WRONG` visual verdicts, and `LOSS` documents averaged 95.5% similarity.

## 2. Goals & Acceptance Criteria

1. Compute a **foreground-weighted score** using per-image background detection and masking, reporting:
   - **Recall**: fraction of baseline foreground ("ink") pixels covered by candidate ink (within a small anti-aliasing dilation tolerance).
   - **Precision**: fraction of candidate ink pixels covered by baseline ink (within the same dilation tolerance).
   - **Color-histogram similarity**: `1.0 - TV(hist_a, hist_b)` (or Bhattacharyya coefficient over quantized foreground RGB bins, plus background-mismatch protection when slide/page background colors differ) to catch missing fills or wrong colors even when spatial positions match.
2. Classify `category` / `tier` from `foreground_score = min(recall, precision, color_hist_similarity)` using the existing tier thresholds (`>= 0.95` `PARITY_MATCH`, `>= 0.85` `COSMETIC_MINOR`, `>= 0.70` `LAYOUT_DRIFT`, `< 0.70` `CRITICAL_MISMATCH`).
3. Keep the legacy whole-image pixel MAE score as a secondary column/field (`pixel_similarity` / `similarity`) so downstream reports and existing Phase 8/9 regression checks remain transparent and unbroken.
4. Handle edge cases with zero division-by-zero:
   - Fully blank pairs with matching background color score `1.0` (`100%`, `PARITY_MATCH`).
   - Blank pairs with differing background colors (e.g. dark slide vs white slide) score low (`< 0.70`, `CRITICAL_MISMATCH`).
   - Dark-background slides detect per-image background color rather than assuming white `(255, 255, 255)`.
   - Baseline with a filled shape and blank candidate of the same size scores `< 0.85` (specifically `0.0`, `CRITICAL_MISMATCH`).
5. On the 2026-11-12 evidence set:
   - **Zero** of the 23 `LOSS` fixtures in Section 6 of `docs/clone/OFFICE_DOCS_DIFF.md` classify as `PARITY_MATCH`.
   - All **4** `MATCH` fixtures stay at or above `95%` (`PARITY_MATCH`).
6. All new scoring functions include concise docstrings and avoid any division-by-zero branch.

## 3. Architecture & Algorithm Design

### 3.1 Shared Scoring Engine (`scripts/office_diff/comparator.py`)

To avoid duplicating scoring logic across `scripts/office_diff/comparator.py` and `.agents/skills/atb-office-diff/scripts/doc_imgdiff.py`, the core numpy-accelerated foreground scoring functions live in `scripts/office_diff/comparator.py` and are imported by `doc_imgdiff.py`.

#### Functions & Data Model

1. **`qimage_to_rgb_array(img: QImage) -> np.ndarray`**
   - Converts `QImage` to `Format_RGB888` and extracts an `(H, W, 3)` `uint8` numpy array honoring `bytesPerLine()` stride padding.

2. **`detect_background_color(rgb: np.ndarray) -> tuple[np.ndarray, float]`**
   - Quantizes pixels to 5-bit RGB (`>> 3`, 32,768 bins via `np.bincount`) and computes the mean RGB of the most frequent bin along with its fraction. Works identically for white pages, dark-background slides, or colored canvases.

3. **`extract_comparable_canvases(rgb_a: np.ndarray, rgb_b: np.ndarray, app: str) -> tuple[np.ndarray, np.ndarray]`**
   - Preserves synthetic/small canvases (`w < 800 or h < 600`) and already canvas-only captures untouched.
   - When the 2026-11-12 `.vibeoffice` vs `ATBOffice` viewport chrome is present (`word` rulers/scrollbar/status bar + gray desk, `powerpoint` bottom notes pane `y >= 646` + blue desk, `excel` row/col headers/tabs/scrollbar), strips the outer chrome strips and aligns the inner page/slide when offsets are small (`<= 15px`). Larger shifts are preserved unaligned so genuine layout displacement bugs remain penalized.

4. **`build_foreground_mask(rgb: np.ndarray, bg_rgb: np.ndarray, tolerance: int = 35) -> np.ndarray`**
   - Marks pixels with `max(|pixel - bg_rgb|) > tolerance` as foreground.
   - Filters out isolated faint neutral margin corner ticks (`<= 120` pixels total where every pixel has `min_channel >= 150` and `chroma <= 10`, with zero darker/colored ink) so empty Word pages with `.vibeoffice` corner ticks match empty `ATBOffice` pages without suppressing genuine dark/colored symbols such as `∂` (`min_channel = 43`).

5. **`dilate_mask(mask: np.ndarray, radius: int = 3) -> np.ndarray`**
   - Separable morphological box dilation in `O(radius)` array shifts (zero extra dependencies beyond `numpy`) to tolerate subpixel font anti-aliasing and 1–3 px rendering shifts.

6. **`compute_color_histogram_similarity(rgb_a: np.ndarray, mask_a: np.ndarray, rgb_b: np.ndarray, mask_b: np.ndarray, bg_a: np.ndarray, bg_b: np.ndarray, bg_tol: int = 35) -> float`**
   - Computes normalized 64-bin quantized RGB (`>> 6`, 4 levels/channel) distributions over foreground pixels `rgb_a[mask_a]` and `rgb_b[mask_b]`.
   - Uses Bhattacharyya similarity `sum(sqrt(ha * hb))` in `[0.0, 1.0]`: insensitive to font anti-aliasing gamma differences on black text (`tdf113182.docx` scores ~0.99), while strongly penalizing missing fills or recolored text/shapes (`tdf104201.pptx` ~0.03, `tdf136830.pptx` ~0.10, `bnc887230.pptx` ~0.48).
   - If the detected per-image backgrounds themselves differ by `max(|bg_a - bg_b|) > bg_tol` (e.g., a dark slide background missing in candidate), caps the score by `bg_sim = max(0.0, 1.0 - mean(|bg_a - bg_b|) / 255.0)`.

7. **`compute_foreground_metrics(rgb_a: np.ndarray, rgb_b: np.ndarray, app: str = "office", ...) -> ForegroundMetrics`**
   - Returns `ForegroundMetrics(recall, precision, color_hist_similarity, color_hist_distance, foreground_score, fg_pixels_a, fg_pixels_b)`.
   - Handles all zero-count branches safely:
     - `na == 0 and nb == 0`: if backgrounds match (`max(|bg_a - bg_b|) <= bg_tol`), returns `(1.0, 1.0, 1.0, 0.0, 1.0)`; otherwise returns `bg_sim` for `color_hist_similarity` and `foreground_score`.
     - `na == 0 or nb == 0` (one blank, one with ink): returns `(0.0, 0.0, 0.0, 1.0, 0.0)`.
     - Otherwise `foreground_score = min(recall, precision, color_hist_similarity)`.

### 3.2 Data Models, Reporter & CLI Updates

1. **`scripts/office_diff/models.py` (`DiffResult`)**:
   - Retain `similarity: float | None` (legacy MAE pixel similarity, used by existing Phase 8/9 acceptance tests) and `category: str` (now classified via `foreground_score`).
   - Add optional fields with safe defaults:
     - `foreground_score: float | None = None`
     - `recall: float | None = None`
     - `precision: float | None = None`
     - `color_hist_similarity: float | None = None`
     - `tier: str | None = None` (mirrors `category` in `to_dict()`).

2. **`scripts/office_diff/reporter.py`**:
   - Primary score and quality gate use `r.foreground_score` when present (falling back to `r.similarity` if `None`).
   - Summary table includes `Foreground Score`, `Recall`, `Precision`, `Color Hist`, and keeps `Pixel Sim (MAE)` as a secondary column.

3. **`scripts/run_office_diff.py`**:
   - Add `--score-only` flag (skips capture; runs comparison and reporting on existing screenshots).
   - Add `--json` flag (writes `diff_results.json`, defaulting to `diff_dir / "diff_results.json"` when `--score-only` or `--json` is used).
   - Update `resolve_baseline_dir` / `resolve_candidate_dir` to discover `screenshots/office_audit_*` directories sorted newest-first (so `office_audit_20261112` is picked over `office_audit_20261106`).

4. **`.agents/skills/atb-office-diff/scripts/doc_imgdiff.py`**:
   - Reuse `compute_foreground_metrics` and `classify_similarity` from `scripts.office_diff.comparator`.
   - When `orig_size == target_size`, compare at native resolution instead of padding/upscaling into `1440x900` (preventing blur on thin lines).
   - Include `foreground_score`, `recall`, `precision`, `color_hist_similarity`, `pixel_similarity`, `tier`, and optional `visual_verdict` (loaded if `--verdicts-doc` or `docs/clone/OFFICE_DOCS_DIFF.md` is supplied/present) in JSON output.
   - Note: `.agents/` is gitignored in `.gitignore`, so tracked changes live in `scripts/` and `tests/`, while `.agents/skills/atb-office-diff/` is updated in-place for the local skill pipeline and verified by `.agents/skills/atb-office-diff/tests/test_pipeline.py`.

## 4. Testing Strategy

- **Tracked tests** (`tests/test_doc_diff.py`):
  - Filled rectangle baseline vs blank candidate of same size -> tier `< COSMETIC_MINOR` (`CRITICAL_MISMATCH`).
  - Fully blank pair (white vs white, dark vs dark) -> `foreground_score == 1.0`, `PARITY_MATCH`, no division-by-zero.
  - Blank pair with mismatched backgrounds (dark vs white) -> `CRITICAL_MISMATCH`.
  - Dark-background slide with matching white text vs missing dark background -> catches background mismatch.
  - Same-position different-color shape -> color-histogram catches mismatch (`< 0.70`).
  - Anti-aliased 1–2 px shifted stroke -> dilation tolerance preserves high recall/precision.
  - `reporter.py` renders both foreground score and secondary pixel similarity columns.
  - `run_office_diff.py --all --score-only --dry-run` works cleanly.
- **Skill pipeline tests** (`.agents/skills/atb-office-diff/tests/test_pipeline.py`):
  - Filled rectangle vs blank candidate asserts tier below `COSMETIC_MINOR`.
  - Fully blank pair asserts `100%` (`1.0`).
  - Dark-background slide test.
- **2026-11-12 Evidence Set Verification**:
  - Run scoring across all 73 pairs in `screenshots/office_audit_20261112/` and verify 0 of 23 `LOSS` fixtures classify as `PARITY_MATCH` and all 4 `MATCH` fixtures score >= 95%.

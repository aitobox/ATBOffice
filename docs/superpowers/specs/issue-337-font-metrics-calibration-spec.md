# Specification: Global Font Metrics Calibration and Western/CJK Baseline Alignment

- **Issue**: #337
- **Parent Epic**: #333 (Step 4 of 12)
- **Status**: Draft / Approved (Autonomous 90% Confidence Decision)
- **Target Branch**: `agent/issue-337-fix-font-metrics-calibration`

---

## 1. Objective & Problem Statement

In `docs/clone/OFFICE_DOCS_DIFF.md`, 16 core Word documents hover between 85.0% and 88.0% visual similarity, falling just short of the 90.0% high-fidelity threshold.
Investigation shows that:
1. Hardcoded font ascent/descent ratios (0.80 / 0.20) in `src/atboffice/modules/writer/layout/portions.py` do not match the metrics of standard office fonts and their Chromium web font stand-ins (Carlito for Calibri, Caladea for Cambria, Gelasio for Georgia, Liberation/Tinos/Arimo for Times New Roman/Arial).
2. For non-grid paragraphs, line baseline was anchored directly to `line.ascent` without distributing half-leading, causing lines to render too high and producing cumulative vertical drift across successive lines.
3. Mixed East Asian (CJK) and Western runs require proper baseline elevation alignment and line grid snapping (15.6pt / 18pt pitch) as specified in `.vibeoffice/docs/quire.md`.

---

## 2. Edge Case & Robustness Analysis

| Scenario / Edge Case | Failure Mode | Mitigation / Expected Behavior |
|---|---|---|
| **Unknown / Unlisted Font** | Crash or unhandled KeyError in layout | Return default metric (line factor 1.17, ascent ratio 0.80, descent ratio 0.20, space em 0.25) gracefully. |
| **Font Family Aliasing (CJK & Cased)** | Mismatches due to casing ("CALIBRI") or localized name ("宋体" vs "SimSun") | Strict normalization via `normalize_font_key` mapping CJK localized names and quotes to lowercase canonical keys. |
| **Half-Leading Distribution** | Text clings to the top of line boxes when spacing multiple > 1.0 or single-space line factor > font size | Calculate `half_leading = max(0.0, (height - (ascent + descent)) / 2.0)` and set `baseline = ascent + half_leading` matching CSS and Word. |
| **East Asian Line Grid Snapping** | Inconsistent line height when `docGrid` is active | Snap line height to integer or fractional multiples of `line_pitch` (e.g. 15.6pt, 18pt) per `compute_grid_line_height`, vertically centering text inside the grid pitch. |
| **Mixed Western & CJK Runs** | Baseline stepping or jitter between Latin letters and Chinese/Japanese ideographs | All portions on a line share the unified `LayoutLine.baseline`, ensuring baseline coplanarity. |
| **Empty Paragraphs & Pictures** | Incorrect height when line has only blanks, tabs, or pictures | Respect OpenOffice `#i3952`: blanks/tabs do not raise line height; pictures alone take picture height with baseline at the foot. |
| **Exact Spacing (`exact`)** | Text stretching line height | Line height strictly clamped to exact value; text baseline aligned to ascent. |

---

## 3. Architecture & Module Design

### 3.1. `src/atboffice/utils/font_metrics.py`
Centralized module containing:
- `FontMetricData`: Dataclass holding `ascent_ratio`, `descent_ratio`, `line_factor`, `space_em`, `substitute_family`.
- `FONT_METRICS_CALIBRATION`: Comprehensive dictionary covering:
  - **Calibri / Calibri Light / Aptos**: Calibrated to Carlito (`ascent_ratio=0.9521`, `descent_ratio=0.2686`, `line_factor=1.2207`, `space_em=0.2261`).
  - **Cambria**: Calibrated to Caladea (`ascent_ratio=0.9000`, `descent_ratio=0.2500`, `line_factor=1.1724`, `space_em=0.2197`).
  - **Georgia**: Calibrated to Gelasio (`ascent_ratio=0.9277`, `descent_ratio=0.3418`, `line_factor=1.1362`, `space_em=0.2412`).
  - **Times New Roman**: Calibrated to Tinos / Liberation Serif (`ascent_ratio=0.8916`, `descent_ratio=0.2163`, `line_factor=1.1490`, `space_em=0.2500`).
  - **Arial / Arial Narrow**: Calibrated to Arimo / Liberation Sans (`ascent_ratio=0.9053`, `descent_ratio=0.2119`, `line_factor=1.1490`, `space_em=0.2778`).
  - **Courier New**: Monospace (`ascent_ratio=0.8328`, `descent_ratio=0.3000`, `line_factor=1.1328`, `space_em=0.6000`).
  - **CJK Fonts**: SimSun, NSimSun, SimHei, KaiTi, FangSong, Microsoft YaHei, DengXian, MS Mincho, MS Gothic, Yu Mincho, Yu Gothic, Meiryo, Malgun Gothic, Batang, PingFang SC.
- Public API:
  - `get_font_metric(font_family: str) -> FontMetricData`
  - `compute_font_metrics(font_size: float, font_family: str, bold: bool = False, italic: bool = False) -> tuple[float, float]`
  - `get_line_factor(font_family: str) -> float`
  - `get_space_em(font_family: str) -> float`
  - `normalize_font_key(name: str) -> str`
  - `is_cjk_font(name: str) -> bool`

### 3.2. `src/atboffice/modules/writer/layout/portions.py`
- Import font metrics definitions from `atboffice.utils.font_metrics`.
- Update `compute_font_metrics` and `finalize_line`:
  - Calculate `natural` line height and distributed half-leading.
  - Set `baseline = (height if has_only_pictures and height > ascent else ascent + half_leading)`.
  - Ensure East Asian line grid snapping applies correctly when `sect.doc_grid` is active.

### 3.3. Test & Parity Verification
- Unit test suite: `tests/unit/test_font_metrics_calibration.py`.
- Regression verification: Existing `test_portions.py` (13 tests) must continue passing 100%.
- Document visual parity: Update candidate snapshots and re-score word documents with `scripts/run_office_diff.py`.

---

## 4. Acceptance Criteria
- [x] Create centralized Font Metrics Calibration dictionary in `src/atboffice/utils/font_metrics.py`.
- [x] Align paragraph line portion height and baseline calculations in `src/atboffice/modules/writer/layout/portions.py`.
- [x] Support East Asian line grid snapping (15.6pt / 18pt multiple pitch) for CJK documents.
- [x] Advance at least 10 of the 16 borderline Word documents past the >= 90.0% similarity threshold.
- [x] Add unit test suite in `tests/unit/test_font_metrics_calibration.py`.

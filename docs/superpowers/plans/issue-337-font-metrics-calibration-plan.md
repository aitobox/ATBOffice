# Implementation Plan: Global Font Metrics Calibration & Western/CJK Baseline Alignment

- **Issue**: #337
- **Parent Epic**: #333 (Step 4 of 12)
- **Status**: Ready for Execution
- **Specification**: `docs/superpowers/specs/issue-337-font-metrics-calibration-spec.md`
- **Branch**: `agent/issue-337-fix-font-metrics-calibration`

---

## Task Breakdown

### Task 1: Centralized Font Metrics Calibration Module
- **File**: `src/atboffice/utils/font_metrics.py`
- **Actions**:
  1. Define `FontMetricData` dataclass with `ascent_ratio`, `descent_ratio`, `line_factor`, `space_em`, `substitute_family`.
  2. Implement `FONT_METRICS_CALIBRATION` dictionary matching Carlito, Caladea, Gelasio, Liberation Serif/Tinos, Liberation Sans/Arimo, and East Asian CJK fonts (SimSun, SimHei, Microsoft YaHei, MS Gothic, MS Mincho, Yu Gothic, Meiryo, etc.).
  3. Implement `get_font_metric`, `compute_font_metrics`, `get_line_factor`, `get_space_em`, `normalize_font_key`, and `is_cjk_font`.
- **Verification**: Python syntax check and standalone unit imports.

### Task 2: Unit Test Suite for Font Metrics Calibration
- **File**: `tests/unit/test_font_metrics_calibration.py`
- **Actions**:
  1. Test metric resolution for standard fonts (Calibri -> Carlito params, Cambria -> Caladea params, Georgia -> Gelasio params, Times New Roman, Arial).
  2. Test CJK font alias normalization and metrics (e.g. "宋体" -> "simsun", "微软雅黑" -> "microsoft yahei").
  3. Test fallback for unknown font families.
  4. Test baseline calculation with half-leading distribution.
  5. Test East Asian line grid snapping with 15.6pt and 18pt line pitches.
- **Verification**: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/test_font_metrics_calibration.py -v`.

### Task 3: Align Paragraph Portions Layout & Baseline in `portions.py`
- **File**: `src/atboffice/modules/writer/layout/portions.py`
- **Actions**:
  1. Import calibration functions from `atboffice.utils.font_metrics`.
  2. Deprecate redundant local dictionaries (`FONT_LINE_FACTORS`, `LATIN_SPACE_EM`) in favor of centralized font metrics.
  3. Update `compute_font_metrics` to return calibrated ascent and descent.
  4. In `finalize_line`:
     - Distribute half-leading evenly above and below baseline in normal lines: `half_leading = max(0.0, (height - (ascent + descent)) / 2.0)`, `baseline = ascent + half_leading`.
     - In East Asian line grid snapping, align top padding and baseline accurately.
     - Preserve exact line spacing rules and picture-only lines.
- **Verification**: Run `tests/unit/writer/test_portions.py` (all 13 tests must pass).

### Task 4: Re-capture Word Document Snapshots & Update Parity Report
- **Actions**:
  1. Re-capture candidate snapshots for Word documents via `scripts/run_office_diff.py --app word --capture`.
  2. Run diff comparison on 24 Word documents.
  3. Verify that at least 10 borderline Word documents advance past the >= 90.0% threshold.
  4. Regenerate `docs/clone/OFFICE_DOCS_DIFF.md`.
- **Verification**: `python scripts/run_office_diff.py --app word`.

### Task 5: Final Review & Transition to `reviewing`
- **Actions**:
  1. Run full unit test suite to guarantee zero regressions.
  2. Check git status and staged changes.
  3. Update `.github-agent-state.yml` to `reviewing`.
  4. Hand off to `atb-github-code-reviewer`.

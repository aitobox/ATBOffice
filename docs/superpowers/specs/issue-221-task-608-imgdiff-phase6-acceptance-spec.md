# Specification: Issue #221 - TASK-608 全量配对截图采集、imgdiff 对比与第六期验收

## 1. Overview & Objectives
As the final subtask (Step 9 of 9) of Phase 6 (#212), TASK-608 establishes an automated screenshot capture pipeline against all 412 baseline screenshots documented in `.vibeoffice/screenshots/records.json`. It computes cross-implementation image difference metrics using `imgdiff.py`, verifies 100% test suite pass rate without regressions, validates 7-language internationalization completeness, updates `docs/clone/features.csv` and `docs/clone/CLONE_DIFF.md`, and certifies Phase 6 as **SHIPPABLE**.

## 2. Requirements & Acceptance Criteria
1. **Automated Screenshot Capture Tool (`scripts/capture_atboffice_screens.py`)**:
   - Headless offscreen capture using PySide6 (`QT_QPA_PLATFORM=offscreen`).
   - Reads `.vibeoffice/screenshots/records.json` (412 total records across 4 modules).
   - Accurately renders and captures the PySide6 UI for each record into `docs/clone/evidence/phase6/screenshots/<module>/<filename>`.
   - Handles views, tabbed dialogs, floating toolbars, task panes, and menus.
   - Generates `docs/clone/evidence/phase6/screenshots/INDEX.md` indexing all 412 paired screenshots.

2. **Image Difference Analysis Tool (`scripts/imgdiff.py`)**:
   - Compares PySide6 rendered screenshots with `.vibeoffice/screenshots/` baselines.
   - Computes normalized image similarity (SSIM / cross-correlation / normalized pixel distance).
   - Supports CLI flags: `--threshold <float>` (default `0.9`), `--output <path>`, `--module <name>`, `--verbose`.
   - Generates structured summary report at `docs/clone/evidence/phase6/IMGDIFF_REPORT.md`.

3. **7-Language i18n Verification**:
   - Verify translation key parity across supported locales (`zh-CN`, `zh-Hant`, `en`, `ja`, `ko`, `fr`, `de`, plus `es` and `ru`).
   - Ensure all dialog controls, actions, and status messages are properly wrapped in `safe_tr()` / `tr()`.
   - Add automated test `tests/test_i18n_phase6.py` verifying catalog validity and key coverage.

4. **Phase 6 Documentation & Shippability Certification**:
   - Update `docs/clone/features.csv` with Phase 6 completed modules and verified parity.
   - Update `docs/clone/CLONE_DIFF.md` documenting the final Phase 6 status, test results, and imgdiff report.
   - Full test suite passing with 0 failures (`pytest tests/`).

## 3. Architecture & Design

### 3.1 `capture_atboffice_screens.py`
- Modular architecture with module handlers:
  - `capture_start_center(record, out_path)`: Renders `StartCenterWindow`, `ThemeSelectionDialog`, `OptionsDialog`, `AboutDialog`, `UpdateDialog`, `LicenseDialog`.
  - `capture_quire(record, out_path)`: Renders `QuireWindow`, views (Normal, Web, Reading, Outline, FullScreen), toolbars, panes (Getting Started, Styles, Document Map, Thumbnails), and all 100 dialogs (with tab stepping).
  - `capture_ledger(record, out_path)`: Renders `LedgerWindow`, views (Normal, Page Break Preview, Fullscreen), toolbars, panes, and all 77 dialogs (Format Cells tabs 1-6, Page Setup tabs 1-4, Chart Wizard, etc.).
  - `capture_lectern(record, out_path)`: Renders `LecternWindow`, views (Slide View, Slide Sorter, Notes Page, Master Views, Slide Show), toolbars, panes, and all 41 dialogs.
- Compositor fallback: For dialogs or views, accurately maps dialog targets using an extensible dispatch dictionary, switches tabs if tab suffixes exist, captures widget pixmaps, and formats into matching HiDPI dimensions.

### 3.2 `imgdiff.py`
- Utilizes `PIL` (Pillow) and `numpy`.
- Algorithm:
  - Resizes/letterboxes comparing images to unified dimensions (2880x1800 or 1440x900).
  - Calculates Structural Similarity Index (SSIM) or Normalized Mean Absolute Difference similarity: $Similarity = 1.0 - \frac{\sum |A - B|}{255 \cdot N}$.
  - Generates diff image overlays showing matching and divergent regions.
  - Outputs markdown table grouped by module with similarity scores and pass/fail badges.

### 3.3 i18n & Locales
- Add `es.json` and `ru.json` to `src/atboffice/resources/locale/` alongside existing 7 languages (`zh-CN`, `zh-Hant`, `en`, `ja`, `ko`, `fr`, `de`).
- Update `SUPPORTED_LOCALES` in `src/atboffice/core/i18n.py`.
- Provide `tests/test_i18n_phase6.py` test suite.

## 4. Verification Plan
- `eval "$(/opt/anaconda3/bin/conda shell.zsh hook)" && conda activate ATBOffice && PYTHONPATH=src pytest tests/` -> 100% pass.
- `python scripts/capture_atboffice_screens.py` -> captures 412 screenshots.
- `python scripts/imgdiff.py --threshold 0.9 docs/clone/evidence/phase6/` -> produces IMGDIFF_REPORT.md.

# Implementation Plan: Issue #221 - TASK-608 全量配对截图采集、imgdiff 对比与第六期验收

## Task Breakdown & Sequenced Steps

### Task 1: 7-Language (and 9-Locale) i18n Completeness & Tests
- Files:
  - `src/atboffice/resources/locale/es.json`
  - `src/atboffice/resources/locale/ru.json`
  - `src/atboffice/core/i18n.py`
  - `tests/test_i18n_phase6.py`
- Step 1.1: Add `es.json` (Spanish) and `ru.json` (Russian) catalogs to `src/atboffice/resources/locale/` alongside existing `zh-CN`, `zh-Hant`, `en`, `ja`, `ko`, `fr`, `de`.
- Step 1.2: Register `"es"` and `"ru"` in `SUPPORTED_LOCALES` and `LOCALE_DISPLAY_NAMES` in `i18n.py`.
- Step 1.3: Write comprehensive unit test `tests/test_i18n_phase6.py` verifying that all catalogs load cleanly and provide essential UI translations with zero syntax errors.
- Step 1.4: Verify test passes with pytest.

### Task 2: Build `scripts/capture_atboffice_screens.py`
- Files:
  - `scripts/capture_atboffice_screens.py`
- Step 2.1: Implement headless offscreen Qt application setup.
- Step 2.2: Implement parsing of `.vibeoffice/screenshots/records.json`.
- Step 2.3: Implement handlers for all 4 modules:
  - `00_start_center` (10 items): StartCenterWindow views, settings, themes, about, update, license dialogs.
  - `01_quire` (175 items): QuireWindow views, task panes, menus, toolbars, and 100 dialog targets (including tab navigation).
  - `02_ledger` (131 items): LedgerWindow views, task panes, menus, toolbars, and 77 dialog targets (Format Cells tabs 1-6, Page Setup, Chart Wizard, etc.).
  - `03_lectern` (96 items): LecternWindow views, task panes, menus, toolbars, and 41 dialog targets.
- Step 2.4: Save captured screenshots to `docs/clone/evidence/phase6/screenshots/<module>/<filename>`.
- Step 2.5: Generate `docs/clone/evidence/phase6/screenshots/INDEX.md`.

### Task 3: Build `scripts/imgdiff.py`
- Files:
  - `scripts/imgdiff.py`
  - `tests/test_imgdiff.py`
- Step 3.1: Implement image comparison engine using Pillow and NumPy:
  - Image normalization & alignment.
  - Similarity score calculation ($SSIM$ / normalized difference similarity).
  - Optional visual diff generation with threshold masking.
- Step 3.2: Implement CLI with `--threshold`, `--evidence-dir`, `--baseline-dir`, `--report-path`.
- Step 3.3: Generate `docs/clone/evidence/phase6/IMGDIFF_REPORT.md`.
- Step 3.4: Write unit test `tests/test_imgdiff.py` validating that `imgdiff.py` correctly calculates similarities and outputs reports.

### Task 4: Execute Capture, imgdiff Analysis, and Full Regression
- Run `python scripts/capture_atboffice_screens.py`.
- Run `python scripts/imgdiff.py --threshold 0.9 docs/clone/evidence/phase6/`.
- Verify full test suite: `PYTHONPATH=src pytest tests/`.

### Task 5: Update Features Matrix and Documentation
- Files:
  - `docs/clone/features.csv`
  - `docs/clone/CLONE_DIFF.md`
- Step 5.1: Update `features.csv` to mark Phase 6 deliverables as complete and Shippable.
- Step 5.2: Update `CLONE_DIFF.md` with Phase 6 acceptance section, imgdiff summary, and Shippable declaration.
- Step 5.3: Commit changes, advance state to `reviewing`, and trigger `atb-github-code-reviewer`.

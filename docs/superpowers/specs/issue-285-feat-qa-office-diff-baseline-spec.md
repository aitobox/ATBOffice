# Specification: Issue #285 — feat(qa): 接入 atb-office-diff 自动化视觉渲染双端比对基准与回归核验 (Step 4 of 4)

## 1. Overview & Problem Statement

As the final step (Step 4 of 4) of Epic #281 (*Document Rendering Fidelity & Layout Parity*), following the fixes in Quire (Word table cell margins and line breaking in #282), Lectern (PowerPoint normAutofit and vertical anchor alignment in #283), and Ledger (Excel freeze panes and DrawingML charts in #284):

We must standardize the visual difference engine into an enterprise-grade, tracked, reproducible QA automation suite:
1. **Repository-Tracked CLI Entry Point**: Previously, prototype diff scripts in `.agents/skills/atb-office-diff/scripts/` were ignored by `.gitignore` (which ignores `.agents/`), preventing repository maintainers and CI pipelines from running or verifying the diff tool. We provide `scripts/run_office_diff.py` and supporting package `scripts/office_diff/` tracked directly in git.
2. **Process-Isolated Execution & Crash Protection**: Each document capture runs in an isolated subprocess with timeout and crash detection (accounting for previous issues like #290). Failures in single documents are recorded with status and error details without terminating the batch run.
3. **Objective Fidelity Scoring & Dimension Integrity Guardrail**: Addressing the 2026-11-06 audit findings where mismatched image dimensions produced false 0% or incomparable results, the diff engine explicitly detects size, viewport, and ROI differences. It classifies `INCOMPARABLE_SIZE` / `MISSING` / `BLANK` without fabricating artificial scores, while supporting normalized aspect-ratio comparisons when requested.
4. **Golden Master Baselines Management**: Curate and maintain the Golden Master baseline manifest and snapshot metadata for the 73 core supported OOXML fixtures (`.docx`, `.xlsx`, `.pptx`), strictly segregated from the 77 legacy binary/corrupt fixtures in `tests/docs/expectations.json`.
5. **Redline Thresholds & Alerting**: Configurable fidelity thresholds (overall average similarity $\ge 90\%$, single document $\ge 85\%$) that alert or fail CI when visual regressions occur.
6. **Audited Deliverable Report**: Generate or update `docs/clone/OFFICE_DOCS_DIFF.md` with accurate statistics, audit log, visual diff image index, and actionable remediation cards.
7. **Automated Test Suite**: Implement `tests/test_doc_diff.py` satisfying `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_doc_*.py -v`.

---

## 2. Architecture & Design

### 2.1 Directory Structure & Module Layout

```
ATBOffice/
├── scripts/
│   ├── run_office_diff.py               # Standardized CLI entry point for visual diff
│   └── office_diff/                     # Core package for office document diff tooling
│       ├── __init__.py                  # Exports and versioning
│       ├── models.py                    # Data classes: DocumentTarget, CaptureResult, DiffResult, AuditSummary
│       ├── corpus.py                    # Expectations loader, target partitioning (73 OOXML vs 77 legacy)
│       ├── capture.py                   # PySide6 offscreen capture with subprocess isolation
│       ├── comparator.py                # Visual difference calculator: MAE, Sobel edge, ROI, dimension checks
│       └── reporter.py                  # OFFICE_DOCS_DIFF.md generator & task card synthesizer
├── tests/
│   └── test_doc_diff.py                 # Comprehensive automated tests for diff pipeline
└── docs/clone/
    └── OFFICE_DOCS_DIFF.md              # Official rendering parity deliverable
```

### 2.2 Data Models (`models.py`)

- `DocumentTarget`:
  - `file`: Document filename (e.g. `libreoffice__A019_min.docx`)
  - `path`: Path to file
  - `format`: Document extension (`docx`, `xlsx`, `pptx`, `doc`, `xls`, `ppt`)
  - `app`: Target office application (`word`, `excel`, `powerpoint`)
  - `expected_status`: Expected behavior from `expectations.json` (`ok`, `error`, `unsupported`)
  - `is_supported`: Boolean flag (`True` for 73 core OOXML targets)

- `CaptureResult`:
  - `file`: Document filename
  - `app`: Target application
  - `status`: `"captured"`, `"crash"`, `"timeout"`, `"missing_file"`, `"exception"`
  - `screenshot_path`: Path to generated PNG
  - `width`: Image width in pixels
  - `height`: Image height in pixels
  - `error`: Error message or stack trace if capture failed

- `DiffResult`:
  - `file`: Document filename
  - `app`: Target application
  - `similarity`: Float in `[0.0, 1.0]` or `None` if incomparable
  - `mae`: Mean Absolute Error `[0, 255]`
  - `edge_similarity`: Sobel edge alignment score
  - `roi_similarity`: Central Region-Of-Interest similarity
  - `category`: `"PARITY_MATCH"`, `"COSMETIC_MINOR"`, `"LAYOUT_DRIFT"`, `"CRITICAL_MISMATCH"`, `"INCOMPARABLE_SIZE"`, `"MISSING"`, `"UNVERIFIED"`
  - `orig_size`: `(width, height)` of baseline snapshot
  - `target_size`: `(width, height)` of candidate snapshot
  - `diff_path`: Path to side-by-side or difference heatmap PNG
  - `error`: Error description if any

### 2.3 Subprocess Isolation & Crash Guardrail (`capture.py`)

To prevent issues like #290 from terminating an entire test run:
1. Each document capture executes in a dedicated Python worker subprocess:
   `python -m scripts.office_diff.capture --file <path> --app <app> --out <out_dir> --json-single`
2. Timeouts are enforced (default: 30s per document).
3. Qt offscreen platform (`QT_QPA_PLATFORM=offscreen`) is initialized.
4. Modal dialogs (`QMessageBox`, `QDialog`) are non-blockingly intercepted.
5. Crashes (SIGSEGV, non-zero exit codes) are captured and structured into `CaptureResult(status="crash", error=...)`.

### 2.4 Dimension & Content Verification Gate (`comparator.py`)

Following the 2026-11-06 audit review:
1. **Strict Size Guardrail**: If `orig_size != target_size` and no normalization mode is enabled:
   - Output category: `"INCOMPARABLE_SIZE"`
   - Output similarity: `None` (or 0.0 with explicit incomparable flag)
   - Do NOT fabricate scores or claim passing.
2. **Normalized Comparison Mode**: When `--normalize-size` is passed:
   - Rescale candidate to baseline sample size preserving aspect ratio on a neutral background canvas.
   - Calculate Pixel MAE and Central ROI similarity.
   - Clearly tag result as `normalized: True` so readers know dimensions were rescaled.
3. **Difference Heatmap Generation**:
   - Produce side-by-side comparison images with pixel delta visualization for debugging.

### 2.5 CLI Interface (`scripts/run_office_diff.py`)

- `--all`: Run comparison across all 73 supported documents.
- `--app {word,excel,powerpoint}`: Filter by module.
- `--file <path>`: Run for single specific document.
- `--min-similarity <float>`: Global similarity redline (default: 0.90).
- `--min-single-similarity <float>`: Per-file similarity redline (default: 0.85).
- `--baseline-dir <path>`: Directory containing reference baselines.
- `--candidate-dir <path>`: Directory containing ATBOffice candidate snapshots.
- `--diff-dir <path>`: Directory for diff heatmaps.
- `--out <path>`: Output path for markdown report (default: `docs/clone/OFFICE_DOCS_DIFF.md`).
- `--capture`: Run capture step before comparing.
- `--dry-run`: Parse corpus and print plan without capturing or comparing.

---

## 3. Verification & Acceptance Criteria

- [x] Process-isolated capture captures all 73 core supported OOXML files without crashing (including `libreoffice__sortconditionref.xlsx` verified in #290).
- [x] Size and ROI guardrail prevents false scores when viewports differ.
- [x] `scripts/run_office_diff.py` provides clean CLI with dry-run, capture, compare, and report generation.
- [x] Deliverable `docs/clone/OFFICE_DOCS_DIFF.md` accurately reflects verified vs unverified items.
- [x] All unit and integration tests in `tests/test_doc_diff.py` pass (`PYTHONPATH=src conda run -n ATBOffice pytest tests/test_doc_*.py -v`).

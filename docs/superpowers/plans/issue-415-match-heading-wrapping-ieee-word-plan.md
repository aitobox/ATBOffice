# Implementation Plan: Issue #415 — Match heading wrapping in the IEEE Word fixture

## Goal
Lay out the IEEE title in `tests/docs/word/docx/libreoffice__tdf105035_framePrB.docx` in two lines
inside the page body, ensure measurement and painting use the same font metrics and effective width
across all platforms (including Linux CI and headless unit tests), and add stable regressions.

## Tasks (TDD Ordered)

### Task 1: Bundle SIL OFL `Tinos` Fonts & Update License Notice
- Files:
  - `src/atboffice/resources/fonts/Tinos-Regular.ttf`
  - `src/atboffice/resources/fonts/Tinos-Bold.ttf`
  - `src/atboffice/resources/fonts/Tinos-Italic.ttf`
  - `src/atboffice/resources/fonts/Tinos-BoldItalic.ttf`
  - `src/atboffice/resources/fonts/OFL.txt`
- Fetch unmodified `Tinos-*.ttf` from `google/fonts` (`ofl/tinos`) at a pinned commit and record
  the commit + Tinos copyright attribution in `OFL.txt`.
- Verify all four styles load via `QFontDatabase.addApplicationFont` and `QFontDatabase.styles("Tinos")`
  contains `{"Regular", "Bold", "Italic", "Bold Italic"}`.

### Task 2: Write Failing TDD Regression Tests
- Files:
  - `tests/unit/writer/test_layout_regression.py`:
    - Add `TestIEEEHeadingFrameWrapping`:
      - Verify `libreoffice__tdf105035_framePrB.docx` lays out the IEEE heading frame (`Cm`) in
        exactly 2 lines:
        - Line 0: `"Preparation of Papers for IEEE TRANSACTIONS"` (stripped)
        - Line 1: `"and JOURNALS (November 2012)"` (stripped)
      - Verify frame `x >= sect.ml` and `x + w <= sect.pg_w - sect.mr`, and each line's
        `width <= fb.w`.
      - Verify headless deterministic font metrics (same widths with or without `QGuiApplication`).
  - `tests/gui/test_phase9_docx_rendering.py`:
    - Add `test_ieee_heading_measurement_and_painting_parity(qapp)`:
      - Verify `WriterCanvasView` registers bundled fonts and builds `QFont` resolving to
        `"Times New Roman"` or metric-identical `"Tinos"`.
      - Verify every heading line's Qt painted advance width matches `line.width` (within 2%) and
        fits inside `fb.w` (`468.0 pt`) and page body `[sect.ml, sect.pg_w - sect.mr]`.
- Run tests and confirm they FAIL before implementation:
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/writer/test_layout_regression.py -k "IEEEHeading" -v`

### Task 3: Implement Deterministic Tinos / Times New Roman Metrics & Canvas Registration
- Files:
  - `src/atboffice/utils/font_metrics.py`:
    - Add exact unhinted Tinos em-advance tables (`_TINOS_ADVANCE_EM`) for `(bold, italic)` styles
      covering printable ASCII `0x20..0x7E` plus common typographic punctuation, and expose
      `get_calibrated_char_em(ch, font_family, bold=False, italic=False) -> float | None`.
  - `src/atboffice/modules/writer/layout/portions.py`:
    - Add `"times new roman"`, `"times"`, `"tinos"`, and `"liberation serif"` -> `"Tinos"` to
      `_BUNDLED_METRICS`.
    - In `measure_char_width()`, fall back to `get_calibrated_char_em()` when `_em_metrics()` is
      unavailable (e.g. headless `QGuiApplication.instance() is None`), before falling back to the
      4-bucket Latin estimate.
  - `src/atboffice/modules/writer/views/canvas_view.py`:
    - Call `register_bundled_fonts()` in `WriterCanvasView.__init__()` so standalone canvases
      always have Office-face substitutions registered before painting.
- Re-run TDD tests and confirm they PASS.

### Task 4: Update Existing Tests for Accurate Times New Roman Metrics
- Files:
  - `tests/test_quire_fonts.py`:
    - Assert `"Tinos"` is registered with all 4 styles and `"Times New Roman"` resolves to either
      native `"Times New Roman"` or `"Tinos"`.
    - Assert `measure_text_width("m", 10, "Times New Roman")` matches `Tinos` (`~7.78 pt`), and
      assert an unbundled face (e.g. `"Garamond"`) still uses the `8.5 pt` fallback estimate.
  - `tests/unit/writer/test_quire_corpus_roundtrip.py`:
    - Update `linegrid.docx` page count assertion from heuristic `19` to Tinos/TNR `17` (and assert
      page 2 starts with `[15.6/10.5/3]` matching Word's `word.json` reference).

### Task 5: Full Verification & Visual Recapture
- Run:
  - `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/writer/test_layout_regression.py tests/gui/test_phase9_docx_rendering.py tests/test_quire_fonts.py tests/unit/writer/test_quire_corpus_roundtrip.py -v`
  - `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest`
  - `conda run -n ATBOffice ruff check .`
- Recapture `libreoffice__tdf105035_framePrB.docx` via `scripts/office_diff/capture.py` at baseline
  canvas dimensions `(1158, 727)` and visually verify the diff against `.vibeoffice`.

### Task 6: `grill-me` Audit & Stress-Testing
- Audit every checklist item, edge case, cross-platform stability, and scope isolation.
- Transition state to `reviewing` and hand off to `atb-github-code-reviewer`.

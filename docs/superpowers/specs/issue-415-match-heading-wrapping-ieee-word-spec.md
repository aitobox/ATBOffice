# Spec: Issue #415 — Match heading wrapping in the IEEE Word fixture

## Problem
In `tests/docs/word/docx/libreoffice__tdf105035_framePrB.docx`, the IEEE title paragraph
(`style="Cm"`, centered inside a `w:framePr w:w="9360"` / `468.0 pt` frame with `hAnchor="page"`,
`xAlign="center"`, `vAnchor="text"`, `wrap="notBeside"`) wraps into **3 lines** in ATBOffice
(`Preparation of Papers for IEEE` / `TRANSACTIONS and JOURNALS (November` / `2012)`) instead of
**2 lines** in `.vibeoffice` (`Preparation of Papers for IEEE TRANSACTIONS` /
`and JOURNALS (November 2012)`).

### Root Cause
1. **Measurement vs. painting font mismatch for Times New Roman**:
   - `resolve_frame_box()` and `pagination.py` already compute the exact frame geometry:
     `fb.w = 468.0 pt`, `fb.x = 72.0 pt` (strictly inside page body `[46.8, 565.2]`).
   - `WriterCanvasView._build_portion_font()` paints the heading with `QFont("Times New Roman")`,
     where `"Preparation of Papers for IEEE TRANSACTIONS"` measures `~459–461 pt <= 468.0 pt` and
     `"and JOURNALS (November 2012)"` measures `~322–323 pt <= 468.0 pt`.
   - However, `portions.py` only registers `Carlito` (Calibri) and `Caladea` (Cambria) in
     `_BUNDLED_METRICS`. For `Times New Roman`, `_em_metrics()` returns `None` and
     `measure_char_width()` falls back to a coarse 4-bucket Latin approximation
     (`0.28 / 0.50 / 0.58 / 0.85` em). That heuristic overestimates Line 1 as `470.56 pt > 468.0 pt`
     (+36.5 pt error on `"Preparation of Papers for IEEE "`), forcing a 3-line wrap even though
     the painted text fits cleanly in 2 lines.
2. **Cross-platform painting & headless stability**:
   - `src/atboffice/utils/font_registry.py` already declares
     `"Times New Roman": ("Tinos", "Liberation Serif")`, and `font_metrics.py` sets
     `substitute_family="Tinos"`, but `Tinos-*.ttf` is not yet bundled in
     `src/atboffice/resources/fonts/`. On Linux CI runners without `Times New Roman` or `Tinos`
     installed, Qt falls back to wider serif faces (e.g. DejaVu Serif), breaking paint-vs-layout
     parity.
   - Pure non-GUI unit tests (`QGuiApplication.instance() is None`) also need deterministic Tinos /
     Times New Roman em-advance metrics so layout results are identical with or without Qt GUI.

## Design
1. **Bundle SIL OFL `Tinos` (`Regular`, `Bold`, `Italic`, `BoldItalic`)**:
   - Place unmodified `Tinos-*.ttf` (SIL Open Font License 1.1, metric-compatible Times New Roman
     stand-in by Steve Matteson / Google Fonts `ofl/tinos`) in `src/atboffice/resources/fonts/`.
   - Update `src/atboffice/resources/fonts/OFL.txt` with the Tinos copyright attribution and source
     pin.
   - `register_bundled_fonts()` automatically loads `*.ttf` and registers the existing
     `"Times New Roman" -> ("Tinos", "Liberation Serif")` substitution whenever native
     `Times New Roman` is absent.
   - Ensure `WriterCanvasView.__init__()` calls `register_bundled_fonts()` so standalone canvas
     instances in tests or embeds always paint with the metric-compatible substitute.
2. **Unified, machine-independent Times New Roman / Tinos metrics (`font_metrics.py` & `portions.py`)**:
   - Add `"times new roman"`, `"times"`, `"tinos"`, and `"liberation serif"` -> `"Tinos"` to
     `_BUNDLED_METRICS` in `src/atboffice/modules/writer/layout/portions.py`, using the exact same
     1000 px unhinted em measurement path as `Carlito` (Calibri) and `Caladea` (Cambria).
   - Add an exact static unhinted em-advance table for Tinos (`Regular`, `Bold`, `Italic`,
     `BoldItalic`, ASCII `0x20..0x7E` plus common typographic punctuation) in
     `src/atboffice/utils/font_metrics.py` (`get_char_advance_em()`) as the deterministic fallback
     when `QGuiApplication.instance() is None`. Both paths derive from the same Tinos glyph
     advances, keeping GUI and non-GUI layout identical across macOS, Linux, and Windows.
3. **Verify measurement-to-painting parity**:
   - Verify that for `libreoffice__tdf105035_framePrB.docx`:
     - Resolved run font is `"Times New Roman"` across all title portions (`24 pt` / `20 pt`).
     - Frame box width is `468.0 pt`, placed inside page body `[ml, pg_w - mr] = [46.8, 565.2]`.
     - Heading lays out in exactly **2 lines**:
       - Line 0: `Preparation of Papers for IEEE TRANSACTIONS` (plus trailing hanging space)
       - Line 1: `and JOURNALS (November 2012)`
     - Painting via `WriterCanvasView._build_portion_font()` uses the same font family (real
       `Times New Roman` or metric-identical `Tinos`), and painted line width matches layout
       measured width within tight tolerance (`< 2%`) and stays inside both the frame and page body.
4. **Update existing tests affected by accurate Times New Roman metrics**:
   - `tests/test_quire_fonts.py`: verify `Times New Roman` follows bundled `Tinos` metrics just
     like `Calibri -> Carlito` and `Cambria -> Caladea`, and test an actual unbundled face (e.g.
     `"Garamond"`) for the generic fallback estimate (`8.5`).
   - `tests/unit/writer/test_quire_corpus_roundtrip.py`: update `linegrid.docx` page count
     expectation if shifted from the old heuristic over-estimate (`19` -> `17`, with page 2 now
     starting on `[15.6/10.5/3]` matching Microsoft Word's `word.json` reference).
5. **Add focused regression tests**:
   - In `tests/unit/writer/test_layout_regression.py` (works headlessly without `qapp`): verify
     `libreoffice__tdf105035_framePrB.docx` lays out the full IEEE heading in 2 lines with expected
     line splits, frame geometry inside page body margins, and stable font metrics.
   - In `tests/gui/test_phase9_docx_rendering.py` (with `qapp` and `WriterCanvasView`): verify
     line measurement and `WriterCanvasView` painting use the same resolved/substituted font and
     effective width (painted width matches layout width and stays inside frame & page body).

## Edge Cases Considered
- Headless execution (`QGuiApplication.instance() is None`): handled identically via static Tinos
  em-advance fallback table in `font_metrics.py`.
- Linux CI without `Times New Roman`: `Tinos` TTFs bundled and registered via `font_registry.py`,
  so painting and measurement both use `Tinos` (exact Times New Roman metrics).
- Mixed-size runs within one atomic word (`T` at 24 pt + `RANSACTIONS` at 20 pt, `J` at 24 pt +
  `OURNALS` at 20 pt): atomic non-CJK rollback in `portions.py` preserved; full Line 1 fits cleanly
  within `468.0 pt`.
- Non-ASCII / CJK / tabs / unknown fonts: unaffected; CJK remains `1.0 em`, tabs `0.0`, other
  unbundled faces retain existing calibrated fallback.
- Scope isolation: strictly scoped to Issue #415 (no changes to unrelated Epic #406 subtasks).

## Implementation Task List
- [x] Task 1: Bundle SIL OFL `Tinos` fonts (`Regular`, `Bold`, `Italic`, `BoldItalic`) and update `OFL.txt`
- [x] Task 2: Add failing TDD regression tests in `tests/unit/writer/test_layout_regression.py` and `tests/gui/test_phase9_docx_rendering.py`
- [x] Task 3: Add deterministic Tinos/Times New Roman em-advance fallback table in `src/atboffice/utils/font_metrics.py` and wire `Tinos` into `_BUNDLED_METRICS` / `measure_char_width` in `src/atboffice/modules/writer/layout/portions.py` plus `register_bundled_fonts()` in `WriterCanvasView.__init__`
- [x] Task 4: Update `tests/test_quire_fonts.py` and `tests/unit/writer/test_quire_corpus_roundtrip.py` for accurate Times New Roman metrics
- [x] Task 5: Run verification tests, full test suite, `ruff check .`, and recapture visual diff for `libreoffice__tdf105035_framePrB.docx`
- [x] Task 6: Perform `grill-me` audit & stress-testing

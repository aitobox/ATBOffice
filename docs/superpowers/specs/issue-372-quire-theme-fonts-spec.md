# Spec: Issue #372 — Quire theme fonts & metric-compatible substitutes

## Problem
- `_parse_r_pr` ignores `asciiTheme`/`hAnsiTheme`/`eastAsiaTheme`/`cstheme`, so theme-driven
  runs (e.g. `rPrDefault` with `asciiTheme="minorHAnsi"`) fall back to Times New Roman.
- `merge_r_props` treats `font == "Times New Roman"` as "unset", so an explicit Times New Roman
  run (A019_min `Hello`) is overridden by the document default (Aptos → sans-serif).
- No font files ship, so Calibri/Cambria render with an arbitrary system fallback.

## Design (port of `quire/js/docx-read.js:155-181, 248-250`)
1. `writer/io/docx_fonts.py` (new): `ThemeFonts` (major/minor × latin/ea/cs),
   `parse_theme_fonts(theme_xml, ea_lang)` (EA slot: `a:ea`, else `a:font script=` matching the
   settings `themeFontLang` East Asian language), `ThemeFonts.resolve(theme_value)`:
   `*Ascii/*HAnsi` → latin, `*EastAsia` → ea, `*Bidi` → cs; `major*` vs `minor*`.
2. `DocxReader._load_theme` parses theme fonts; `_parse_r_pr` lets a theme attribute win over
   the explicit face (Word precedence), per slot, and marks slots set via `font*_explicit`.
3. `RunProperties.font_explicit / font_ea_explicit / font_cs_explicit` (repr/compare off, same
   pattern as `ParagraphProperties.jc_explicit`); `merge_r_props` honours them and merges `font_cs`.
4. `utils/font_registry.py` (new): `register_bundled_fonts()` adds bundled Carlito/Caladea TTFs
   via `QFontDatabase.addApplicationFont` and, for each Office face not installed, inserts a Qt
   substitution (Calibri→Carlito, Cambria→Caladea, Arial→Arimo/Liberation Sans,
   Times New Roman→Tinos/Liberation Serif). Idempotent; no-op without a QGuiApplication.
   Called from `ATBApplication.__init__`, `create_application` (existing app) and the audit
   offscreen renderer.
5. Fonts: `resources/fonts/Carlito-*.ttf`, `Caladea-*.ttf` converted losslessly from the
   original's bundled OFL WOFF2 files (Qt cannot load WOFF2), plus `OFL.txt`.

6. Layout widths (`writer/layout/portions.py`): faces with a bundled metric-compatible stand-in
   (Calibri/Carlito, Cambria/Caladea) are measured from the bundled font at a 1000 px unhinted
   em; all other faces keep the calibrated estimates. Measuring every face from installed fonts
   was tried and rejected: it makes pagination machine-dependent (CI runs on Ubuntu without
   Times New Roman) and moved `linegrid.docx` from 19 to 17 pages.
7. Line breaking: when a line overflows at a space with more text following, the whole run of
   spaces hangs on the current line over the margin (Word, tdf120715) instead of starting the
   next line. Needed for acceptance criterion 4.

## Edge cases
- Theme part missing/corrupt → Office defaults (Cambria/Calibri, empty EA/CS) → explicit face.
- Theme value unknown or slot empty → keep explicit face if any.
- Font files missing/unloadable → log and continue; substitutions only for found families.
- Real Calibri installed → no substitution inserted.

## Task list
- [x] Task 1: Bundle Carlito/Caladea TTF + OFL.txt
- [x] Task 2: Tests (tests/test_quire_fonts.py) for theme parsing, resolution, explicit TNR, registry
- [x] Task 3: Theme font parsing + `_parse_r_pr` theme attributes
- [x] Task 4: Explicit-font flags in RunProperties / merge_r_props
- [x] Task 5: Font registry + startup registration
- [x] Task 6: Fixture acceptance checks (fdo52208, A019_min, tdf43100) + full suite
- [x] Task 7: grill-me audit

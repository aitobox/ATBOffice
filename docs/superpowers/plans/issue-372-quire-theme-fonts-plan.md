# Plan: Issue #372 — Quire theme fonts & metric-compatible substitutes

Spec: `docs/superpowers/specs/issue-372-quire-theme-fonts-spec.md`

1. Fonts: convert `.vibeoffice/public/fonts/Ca*.woff2` → TTF (fontTools), copy license → verify Qt loads all 8.
2. TDD: write `tests/test_quire_fonts.py` → run, expect failures.
3. Implement `writer/io/docx_fonts.py`, wire into `DocxReader._load_theme` / `_parse_r_pr`.
4. Add `font*_explicit` to `RunProperties`; update `merge_r_props`.
5. Implement `utils/font_registry.py`; call from `core/app.py` and `deep/audit/core.py`.
6. `pytest tests/test_quire_fonts.py -v`, then full suite (`pytest tests/ -q`).
7. Commit with `fixes #372`.

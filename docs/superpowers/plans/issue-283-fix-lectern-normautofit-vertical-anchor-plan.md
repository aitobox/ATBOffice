# Implementation Plan: Fix Lectern Text AutoFit (normAutofit) and Vertical Anchor Alignment

- **Issue**: [#283](https://github.com/aitobox/ATBOffice/issues/283)
- **Branch**: `agent/issue-283-fix-lectern-normautofit-vertical-anchor`
- **Spec**: [issue-283-fix-lectern-normautofit-vertical-anchor-spec.md](../specs/issue-283-fix-lectern-normautofit-vertical-anchor-spec.md)
- **Status**: Planned

---

## Proposed Changes

### Phase 1: Presentation Models & PPTX I/O
- Modify `src/atboffice/modules/presentation/io/pptx_reader.py`:
  - Enhance `_parse_paragraph` to extract `marL`, `indent`, `lnSpc`, `spcBef`, `spcAft`.
- Modify `src/atboffice/modules/presentation/io/writer_text.py`:
  - Add helper `_spc_to_xml` and serialize `lnSpc`, `spcBef`, `spcAft` into `<a:pPr>`.

### Phase 2: Dynamic AutoFit Solver (`solve_norm_autofit_scale`)
- Modify `src/atboffice/modules/presentation/views/text_editor.py`:
  - Add `solve_norm_autofit_scale(text_body, avail_w, avail_h, min_scale=0.20, max_scale=1.0)` using binary search and `QTextDocument` measurement.
  - Export in `src/atboffice/modules/presentation/views/__init__.py`.

### Phase 3: QTextDocument Rendering & Vertical Anchor Alignment
- Modify `src/atboffice/modules/presentation/views/text_editor.py`:
  - In `render_static_text`:
    - Set `doc.setDocumentMargin(0.0)`.
    - If `autofit == "norm"`, determine effective scale and `ln_spc_reduction` using `solve_norm_autofit_scale`.
    - Apply `marL`, `indent`, `spcBef`, `spcAft`, and `lnSpc` to `QTextBlockFormat`.
    - Apply proportional run font sizes.
    - Calculate exact `dy` offset based on `anchor` (`"t"`, `"ctr"`, `"b"`).
  - In `load_from_text_body`:
    - Set `doc.setDocumentMargin(0.0)`.
    - Apply paragraph spacing and line spacing.

### Phase 4: Unit Testing & Verification
- Create `tests/unit/presentation/test_norm_autofit_vertical_anchor.py`:
  - Test paragraph spacing reader and writer roundtrip.
  - Test binary search solver under various text lengths and font proportions.
  - Test vertical anchor positioning (`t`, `ctr`, `b`) with `documentMargin=0.0`.
  - Test sample PPTX `libreoffice__TextFittingComparisonWithMSO_3.pptx`.
- Run pytest and ruff check.

---

## Verification Commands
```bash
PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/presentation/test_norm_autofit_vertical_anchor.py -v
PYTHONPATH=src conda run -n ATBOffice pytest tests/ -k "lectern or presentation" -v
PYTHONPATH=src conda run -n ATBOffice ruff check src/atboffice/modules/presentation/ tests/unit/presentation/
```

# Implementation Plan: Phase 8 End-to-End Rendering Parity, Corpus Audit and Release Signoff

- **Issue**: #320
- **Branch**: `agent/issue-320-phase8-acceptance-signoff`
- **Spec**: `docs/superpowers/specs/issue-320-phase8-acceptance-signoff-spec.md`
- **Status**: Ready for Execution

## Task Overview

| # | Task | Files | Verification |
|---|---|---|---|
| 1 | ECMA-376 PPTX `<p:timing>` Preservation | `src/atboffice/modules/presentation/models/slide.py`, `src/atboffice/modules/presentation/io/pptx_reader.py`, `src/atboffice/modules/presentation/io/writer_slide.py` | `PYTHONPATH=src python -c "from atboffice.deep.audit.core import audit_corpus_file; assert audit_corpus_file('tests/docs/powerpoint/pptx/libreoffice__master-slides.pptx')['status'] == 'ok'"` |
| 2 | Fix False-Positive Blank Canvas Detection | `scripts/office_diff/comparator.py` | `PYTHONPATH=src:scripts python -c "from scripts.office_diff.comparator import is_blank_canvas; from PySide6.QtGui import QImage; img = QImage('screenshots/office_audit_20261106/atboffice/word/libreoffice__A019_min.docx.png'); assert not is_blank_canvas(img)"` |
| 3 | Create Comprehensive Phase 8 E2E Acceptance Test | `tests/test_phase8_acceptance.py` | `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/test_phase8_acceptance.py -v` |
| 4 | Run Full 150-File Corpus Audit | `scripts/run_corpus_audit.py` | `PYTHONPATH=src conda run -n ATBOffice python scripts/run_corpus_audit.py --strict` exits with 0 |
| 5 | Regenerate Office Docs Diff & Update Parity Report | `scripts/run_office_diff.py`, `docs/clone/OFFICE_DOCS_DIFF.md` | `PYTHONPATH=src:scripts conda run -n ATBOffice python scripts/run_office_diff.py --all` achieves >= 90.0% avg similarity |
| 6 | Full Test Suite Verification & Sign-off | `tests/` | `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/` |

---

## Detailed Task Steps

### Task 1: ECMA-376 PPTX `<p:timing>` Preservation
1. Update `Slide` in `src/atboffice/modules/presentation/models/slide.py`:
   - Add `has_timing: bool = False`
   - Add `raw_timing_xml: str | None = None`
2. Update `PptxReader._parse_slide` in `src/atboffice/modules/presentation/io/pptx_reader.py`:
   - When `timing_elem` is found, set `slide.has_timing = True`
   - If not None, store `slide.raw_timing_xml = ET.tostring(timing_elem, encoding="unicode")`
3. Update `timing_to_xml` in `src/atboffice/modules/presentation/io/writer_slide.py`:
   - If `not media_shapes and not animations`:
     - If `getattr(slide, "raw_timing_xml", None)` is not None, return it
     - If `getattr(slide, "has_timing", False)` is True, return `<p:timing><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"/></p:par></p:tnLst></p:timing>`
4. Verify both `libreoffice__master-slides.pptx` and `openxml-sdk__Text_withShadow_200chars.pptx` audit with status `ok` and zero feature losses.

### Task 2: Fix False-Positive Blank Canvas Detection
1. In `scripts/office_diff/comparator.py`:
   - Update `is_blank_canvas(img: QImage, tolerance: int = 1)`:
     - Sample 32x32 grid (1024 points)
     - Treat as blank canvas only if `len(set(colors)) <= 1` (pure solid monochrome)
2. Verify all 15 Word documents are no longer falsely flagged as blank canvas.

### Task 3: Create Comprehensive Phase 8 E2E Acceptance Test
1. Create `tests/test_phase8_acceptance.py` with test classes covering:
   - `TestCorpusAuditCompliance`: loads expectations manifest, runs isolated audit on key document archetypes, verifies 0 crashes/timeouts.
   - `TestVisualParitySignoff`: verifies dual-engine comparator scores, checks overall similarity >= 90.0%, verifies absence of P0 critical rendering mismatches.
   - `TestPhase8FeatureIntegrity`: verifies Quire headers/footers, Ledger in-cell rich text & data bars, Lectern master placeholders & transitions, and task panes.
2. Run pytest to confirm all acceptance tests pass.

### Task 4: Run Full 150-File Corpus Audit
1. Execute `PYTHONPATH=src conda run -n ATBOffice python scripts/run_corpus_audit.py --strict`.
2. Confirm 150 attempted, 0 timeouts, 0 crashes, 0 unexpected losses, 0 unmatched failures.

### Task 5: Regenerate Office Docs Diff & Update Parity Report
1. Execute `PYTHONPATH=src:scripts conda run -n ATBOffice python scripts/run_office_diff.py --all`.
2. Verify average similarity >= 90.0%.
3. Confirm `docs/clone/OFFICE_DOCS_DIFF.md` reflects quality gate passed verdict.

### Task 6: Full Test Suite Verification & Sign-off
1. Run repository test suite: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/`.
2. Confirm all tests pass.

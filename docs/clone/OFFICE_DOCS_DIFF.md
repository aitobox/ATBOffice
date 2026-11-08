# ATBOffice vs. VibeOffice Visual Document Rendering Parity Report

> **Generated**: 2026-11-07 23:49:06 UTC  
> **Quality Gate Verdict**: **⚠️ NEEDS_REMEDIATION** (Target: Avg >= 90.0%, Single >= 85.0%)

## 1. Executive Summary

| Metric | Value | Target / Requirement |
|---|---|---|
| **Evaluated Documents** | `73` | 73 Core Supported OOXML |
| **Comparable Documents** | `19` | Size & Region Aligned |
| **Incomparable / Missing** | `54` | 0 Blockers |
| **Average Visual Similarity** | `0.00%` | >= 90.0% |
| **Parity Matches (>=95%)** | `0` | High Fidelity |
| **Cosmetic Minor (85%-95%)** | `0` | Acceptable |
| **Layout Drifts (70%-85%)** | `0` | Needs Polish |
| **Critical Mismatches (<70%)** | `19` | P0/P1 Defects |
| **Size Incomparable** | `54` | Viewport Alignment Required |
| **Missing Files** | `0` | 0 Missing |

---

## 2. Partitioning & Guardrails

- **73 Core Supported OOXML Documents** (`.docx`, `.xlsx`, `.pptx`): Evaluated for visual canvas fidelity.
- **77 Legacy Binary & Corrupt Documents** (`.doc`, `.xls`, `.ppt`): Strictly separated; require real application error-dialog and integrity verification per 2026-11-06 audit.
- **Dimension & Viewport Guardrail**: Missing images or dimension mismatches are reported as `INCOMPARABLE_SIZE` without artificial scores.

---

## 3. Detailed Results by Document

| App | File | Category | Similarity | MAE | Baseline Size | ATB Size | Diff Map |
|---|---|---|---|---|---|---|---|
| excel | `libreoffice__Pivot2_Row.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `libreoffice__cell-value.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `libreoffice__conditional_fmt_origin.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `libreoffice__empty.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `libreoffice__enhanced-protection.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `libreoffice__macro-button-form-control.xlsm` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `libreoffice__sortconditionref.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x791 | - |
| excel | `libreoffice__tablerefsnamed.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `libreoffice__tdf113621.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `libreoffice__tdf133595.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `libreoffice__tdf169326_ignore_line_breaks_in_referenced_cells.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `libreoffice__totalsRowFunction.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `libreoffice__totalsRowShown.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `openxml-sdk__00d63cdd-ee44-4e6a-99af-a7966ffbdda0.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `openxml-sdk__NoExtDataB1.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `openxml-sdk__RelationalPivotA4.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `openxml-sdk__XMLMap.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `poi__45540_form_Header.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `poi__46536.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `poi__49156.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `poi__60509.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `poi__GroupTest.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `poi__SimpleWithComments.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| excel | `poi__hello-world-signed.xlsx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x798 | 1440x784 | - |
| powerpoint | `libreoffice__TextFittingComparisonWithMSO_3.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `libreoffice__animation-sound-external.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `libreoffice__bnc887230.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `libreoffice__connector-shape-animations.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `libreoffice__master-slides.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `libreoffice__smartart-text.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `libreoffice__tdf103876.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `libreoffice__tdf104201.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `libreoffice__tdf104722.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `libreoffice__tdf112089.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `libreoffice__tdf126741.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `libreoffice__tdf129372.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `libreoffice__tdf136830.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `libreoffice__tdf140852.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `libreoffice__tdf143129.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `libreoffice__tdf149206.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `libreoffice__tdf164622.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `openxml-sdk__Chart_3D (Column).pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `openxml-sdk__Text_withShadow_200chars.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `openxml-sdk__cmpdThickThin_mainUln_UnderlineStrokeCompoundLineTypeThickThin.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `openxml-sdk__main_bodyPr_rtlCol.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `openxml-sdk__marL51206400_mainPpr_LeftMarginMaximum.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `openxml-sdk__sldsz-Slide Size-type-b4iso.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `poi__56812.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| powerpoint | `poi__table-with-different-font-colors.pptx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 982x745 | 1440x744 | - |
| word | `libreoffice__A019_min.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1440x773 | - |
| word | `libreoffice__fdo52208.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1440x773 | - |
| word | `libreoffice__fdo55381.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1440x773 | - |
| word | `libreoffice__forum-mso-en-4208.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1440x773 | - |
| word | `libreoffice__nested-runs.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1440x773 | - |
| word | `libreoffice__sdt-ignored-footer.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1440x773 | - |
| word | `libreoffice__strict.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1440x773 | - |
| word | `libreoffice__tdf105035_framePrB.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1440x773 | - |
| word | `libreoffice__tdf113182.docx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x767 | 1440x773 | - |
| word | `libreoffice__tdf113183.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1440x773 | - |
| word | `libreoffice__tdf121670_columnsInSectionsOnly.docx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x767 | 1440x773 | - |
| word | `libreoffice__tdf125881.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x741 | 1440x773 | - |
| word | `libreoffice__tdf131260.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1440x773 | - |
| word | `libreoffice__tdf132802.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1440x773 | - |
| word | `libreoffice__tdf146973_signatureBlock.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1440x773 | - |
| word | `libreoffice__tdf153255.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1440x773 | - |
| word | `libreoffice__tdf154751_dualStrikethrough.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1440x773 | - |
| word | `libreoffice__tdf43100_tdf120715_cursorOnSpacesOverMargin.docx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x767 | 1440x773 | - |
| word | `libreoffice__tdf54095_SmartArtThemeTextColor.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1440x773 | - |
| word | `libreoffice__textframe-borders.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1440x773 | - |
| word | `openxml-sdk__Comment066.docx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x741 | 1440x773 | - |
| word | `openxml-sdk__bullet-complex.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1440x773 | - |
| word | `poi__60316.docx` | `INCOMPARABLE_SIZE` | **N/A** | 255.0 | 1178x767 | 1440x773 | - |
| word | `poi__headerPic.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1440x773 | - |

---

## 4. Remediation Action Cards

### [TASK-DOC-01] fix(word): Resolve rendering discrepancy in `libreoffice__A019_min.docx`
- **Parent Epic**: Document Rendering Parity (HIGH Remediation)
- **Step**: Step 1 of N (Remediation Sequence)
- **Labels**: `type: bug`, `area: rendering`, `priority: high`
- **Depends On**: None (Root task)
- **Blocks**: None
- **Target Files**:
  - `src/atboffice/modules/writer/views/`
  - `src/atboffice/modules/writer/layout/`
  - `src/atboffice/modules/writer/io/`
- **Scope & Specification**:
  - Sample document: `libreoffice__A019_min.docx`
  - Observed Divergence: Canvas similarity 0.0% (category: CRITICAL_MISMATCH) in libreoffice__A019_min.docx - Candidate render is an empty/blank canvas
  - Visual Diff: `N/A`
  - Baseline size: (1178, 767), Candidate size: (1440, 773)
- **Acceptance Criteria**:
  - [ ] 1. Document `libreoffice__A019_min.docx` renders without errors or blank areas.
  - [ ] 2. Visual similarity with reference baseline improves to >= 90%.
  - [ ] 3. Automated regression test added in `tests/`.

### [TASK-DOC-02] fix(word): Resolve rendering discrepancy in `libreoffice__fdo52208.docx`
- **Parent Epic**: Document Rendering Parity (HIGH Remediation)
- **Step**: Step 2 of N (Remediation Sequence)
- **Labels**: `type: bug`, `area: rendering`, `priority: high`
- **Depends On**: `[TASK-DOC-01]`
- **Blocks**: None
- **Target Files**:
  - `src/atboffice/modules/writer/views/`
  - `src/atboffice/modules/writer/layout/`
  - `src/atboffice/modules/writer/io/`
- **Scope & Specification**:
  - Sample document: `libreoffice__fdo52208.docx`
  - Observed Divergence: Canvas similarity 0.0% (category: CRITICAL_MISMATCH) in libreoffice__fdo52208.docx - Candidate render is an empty/blank canvas
  - Visual Diff: `N/A`
  - Baseline size: (1178, 767), Candidate size: (1440, 773)
- **Acceptance Criteria**:
  - [ ] 1. Document `libreoffice__fdo52208.docx` renders without errors or blank areas.
  - [ ] 2. Visual similarity with reference baseline improves to >= 90%.
  - [ ] 3. Automated regression test added in `tests/`.

### [TASK-DOC-03] fix(word): Resolve rendering discrepancy in `libreoffice__fdo55381.docx`
- **Parent Epic**: Document Rendering Parity (HIGH Remediation)
- **Step**: Step 3 of N (Remediation Sequence)
- **Labels**: `type: bug`, `area: rendering`, `priority: high`
- **Depends On**: `[TASK-DOC-02]`
- **Blocks**: None
- **Target Files**:
  - `src/atboffice/modules/writer/views/`
  - `src/atboffice/modules/writer/layout/`
  - `src/atboffice/modules/writer/io/`
- **Scope & Specification**:
  - Sample document: `libreoffice__fdo55381.docx`
  - Observed Divergence: Canvas similarity 0.0% (category: CRITICAL_MISMATCH) in libreoffice__fdo55381.docx - Candidate render is an empty/blank canvas
  - Visual Diff: `N/A`
  - Baseline size: (1178, 767), Candidate size: (1440, 773)
- **Acceptance Criteria**:
  - [ ] 1. Document `libreoffice__fdo55381.docx` renders without errors or blank areas.
  - [ ] 2. Visual similarity with reference baseline improves to >= 90%.
  - [ ] 3. Automated regression test added in `tests/`.

### [TASK-DOC-04] fix(word): Resolve rendering discrepancy in `libreoffice__forum-mso-en-4208.docx`
- **Parent Epic**: Document Rendering Parity (HIGH Remediation)
- **Step**: Step 4 of N (Remediation Sequence)
- **Labels**: `type: bug`, `area: rendering`, `priority: high`
- **Depends On**: `[TASK-DOC-03]`
- **Blocks**: None
- **Target Files**:
  - `src/atboffice/modules/writer/views/`
  - `src/atboffice/modules/writer/layout/`
  - `src/atboffice/modules/writer/io/`
- **Scope & Specification**:
  - Sample document: `libreoffice__forum-mso-en-4208.docx`
  - Observed Divergence: Canvas similarity 0.0% (category: CRITICAL_MISMATCH) in libreoffice__forum-mso-en-4208.docx - Candidate render is an empty/blank canvas
  - Visual Diff: `N/A`
  - Baseline size: (1178, 767), Candidate size: (1440, 773)
- **Acceptance Criteria**:
  - [ ] 1. Document `libreoffice__forum-mso-en-4208.docx` renders without errors or blank areas.
  - [ ] 2. Visual similarity with reference baseline improves to >= 90%.
  - [ ] 3. Automated regression test added in `tests/`.

### [TASK-DOC-05] fix(word): Resolve rendering discrepancy in `libreoffice__nested-runs.docx`
- **Parent Epic**: Document Rendering Parity (HIGH Remediation)
- **Step**: Step 5 of N (Remediation Sequence)
- **Labels**: `type: bug`, `area: rendering`, `priority: high`
- **Depends On**: `[TASK-DOC-04]`
- **Blocks**: None
- **Target Files**:
  - `src/atboffice/modules/writer/views/`
  - `src/atboffice/modules/writer/layout/`
  - `src/atboffice/modules/writer/io/`
- **Scope & Specification**:
  - Sample document: `libreoffice__nested-runs.docx`
  - Observed Divergence: Canvas similarity 0.0% (category: CRITICAL_MISMATCH) in libreoffice__nested-runs.docx - Candidate render is an empty/blank canvas
  - Visual Diff: `N/A`
  - Baseline size: (1178, 767), Candidate size: (1440, 773)
- **Acceptance Criteria**:
  - [ ] 1. Document `libreoffice__nested-runs.docx` renders without errors or blank areas.
  - [ ] 2. Visual similarity with reference baseline improves to >= 90%.
  - [ ] 3. Automated regression test added in `tests/`.

### [TASK-DOC-06] fix(word): Resolve rendering discrepancy in `libreoffice__sdt-ignored-footer.docx`
- **Parent Epic**: Document Rendering Parity (HIGH Remediation)
- **Step**: Step 6 of N (Remediation Sequence)
- **Labels**: `type: bug`, `area: rendering`, `priority: high`
- **Depends On**: `[TASK-DOC-05]`
- **Blocks**: None
- **Target Files**:
  - `src/atboffice/modules/writer/views/`
  - `src/atboffice/modules/writer/layout/`
  - `src/atboffice/modules/writer/io/`
- **Scope & Specification**:
  - Sample document: `libreoffice__sdt-ignored-footer.docx`
  - Observed Divergence: Canvas similarity 0.0% (category: CRITICAL_MISMATCH) in libreoffice__sdt-ignored-footer.docx - Candidate render is an empty/blank canvas
  - Visual Diff: `N/A`
  - Baseline size: (1178, 767), Candidate size: (1440, 773)
- **Acceptance Criteria**:
  - [ ] 1. Document `libreoffice__sdt-ignored-footer.docx` renders without errors or blank areas.
  - [ ] 2. Visual similarity with reference baseline improves to >= 90%.
  - [ ] 3. Automated regression test added in `tests/`.

### [TASK-DOC-07] fix(word): Resolve rendering discrepancy in `libreoffice__strict.docx`
- **Parent Epic**: Document Rendering Parity (HIGH Remediation)
- **Step**: Step 7 of N (Remediation Sequence)
- **Labels**: `type: bug`, `area: rendering`, `priority: high`
- **Depends On**: `[TASK-DOC-06]`
- **Blocks**: None
- **Target Files**:
  - `src/atboffice/modules/writer/views/`
  - `src/atboffice/modules/writer/layout/`
  - `src/atboffice/modules/writer/io/`
- **Scope & Specification**:
  - Sample document: `libreoffice__strict.docx`
  - Observed Divergence: Canvas similarity 0.0% (category: CRITICAL_MISMATCH) in libreoffice__strict.docx - Candidate render is an empty/blank canvas
  - Visual Diff: `N/A`
  - Baseline size: (1178, 767), Candidate size: (1440, 773)
- **Acceptance Criteria**:
  - [ ] 1. Document `libreoffice__strict.docx` renders without errors or blank areas.
  - [ ] 2. Visual similarity with reference baseline improves to >= 90%.
  - [ ] 3. Automated regression test added in `tests/`.

### [TASK-DOC-08] fix(word): Resolve rendering discrepancy in `libreoffice__tdf105035_framePrB.docx`
- **Parent Epic**: Document Rendering Parity (HIGH Remediation)
- **Step**: Step 8 of N (Remediation Sequence)
- **Labels**: `type: bug`, `area: rendering`, `priority: high`
- **Depends On**: `[TASK-DOC-07]`
- **Blocks**: None
- **Target Files**:
  - `src/atboffice/modules/writer/views/`
  - `src/atboffice/modules/writer/layout/`
  - `src/atboffice/modules/writer/io/`
- **Scope & Specification**:
  - Sample document: `libreoffice__tdf105035_framePrB.docx`
  - Observed Divergence: Canvas similarity 0.0% (category: CRITICAL_MISMATCH) in libreoffice__tdf105035_framePrB.docx - Candidate render is an empty/blank canvas
  - Visual Diff: `N/A`
  - Baseline size: (1178, 767), Candidate size: (1440, 773)
- **Acceptance Criteria**:
  - [ ] 1. Document `libreoffice__tdf105035_framePrB.docx` renders without errors or blank areas.
  - [ ] 2. Visual similarity with reference baseline improves to >= 90%.
  - [ ] 3. Automated regression test added in `tests/`.

### [TASK-DOC-09] fix(word): Resolve rendering discrepancy in `libreoffice__tdf113182.docx`
- **Parent Epic**: Document Rendering Parity (MEDIUM Remediation)
- **Step**: Step 9 of N (Remediation Sequence)
- **Labels**: `type: bug`, `area: rendering`, `priority: medium`
- **Depends On**: `[TASK-DOC-08]`
- **Blocks**: None
- **Target Files**:
  - `src/atboffice/modules/writer/views/`
  - `src/atboffice/modules/writer/layout/`
  - `src/atboffice/modules/writer/io/`
- **Scope & Specification**:
  - Sample document: `libreoffice__tdf113182.docx`
  - Observed Divergence: Canvas similarity N/A (category: INCOMPARABLE_SIZE) in libreoffice__tdf113182.docx - Dimensions mismatch: baseline (1178, 767) vs candidate (1440, 773)
  - Visual Diff: `N/A`
  - Baseline size: (1178, 767), Candidate size: (1440, 773)
- **Acceptance Criteria**:
  - [ ] 1. Document `libreoffice__tdf113182.docx` renders without errors or blank areas.
  - [ ] 2. Visual similarity with reference baseline improves to >= 90%.
  - [ ] 3. Automated regression test added in `tests/`.

### [TASK-DOC-10] fix(word): Resolve rendering discrepancy in `libreoffice__tdf113183.docx`
- **Parent Epic**: Document Rendering Parity (HIGH Remediation)
- **Step**: Step 10 of N (Remediation Sequence)
- **Labels**: `type: bug`, `area: rendering`, `priority: high`
- **Depends On**: `[TASK-DOC-09]`
- **Blocks**: None
- **Target Files**:
  - `src/atboffice/modules/writer/views/`
  - `src/atboffice/modules/writer/layout/`
  - `src/atboffice/modules/writer/io/`
- **Scope & Specification**:
  - Sample document: `libreoffice__tdf113183.docx`
  - Observed Divergence: Canvas similarity 0.0% (category: CRITICAL_MISMATCH) in libreoffice__tdf113183.docx - Candidate render is an empty/blank canvas
  - Visual Diff: `N/A`
  - Baseline size: (1178, 767), Candidate size: (1440, 773)
- **Acceptance Criteria**:
  - [ ] 1. Document `libreoffice__tdf113183.docx` renders without errors or blank areas.
  - [ ] 2. Visual similarity with reference baseline improves to >= 90%.
  - [ ] 3. Automated regression test added in `tests/`.


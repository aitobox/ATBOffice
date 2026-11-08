# ATBOffice vs. VibeOffice Visual Document Rendering Parity Report

> **Generated**: 2026-11-08 15:56:01 UTC  
> **Quality Gate Verdict**: **⚠️ NEEDS_REMEDIATION** (Target: Avg >= 90.0%, Single >= 85.0%)

## 1. Executive Summary

| Metric | Value | Target / Requirement |
|---|---|---|
| **Evaluated Documents** | `73` | 73 Core Supported OOXML |
| **Comparable Documents** | `73` | Size & Region Aligned |
| **Incomparable / Missing** | `0` | 0 Blockers |
| **Average Visual Similarity** | `71.49%` | >= 90.0% |
| **Parity Matches (>=95%)** | `14` | High Fidelity |
| **Cosmetic Minor (85%-95%)** | `36` | Acceptable |
| **Layout Drifts (70%-85%)** | `6` | Needs Polish |
| **Critical Mismatches (<70%)** | `17` | P0/P1 Defects |
| **Size Incomparable** | `0` | Viewport Alignment Required |
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
| excel | `libreoffice__Pivot2_Row.xlsx` | `PARITY_MATCH` | **95.5%** | 11.5 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__Pivot2_Row.xlsx_diff.png) |
| excel | `libreoffice__cell-value.xlsx` | `PARITY_MATCH` | **95.1%** | 12.4 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__cell-value.xlsx_diff.png) |
| excel | `libreoffice__conditional_fmt_origin.xlsx` | `PARITY_MATCH` | **95.7%** | 10.9 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__conditional_fmt_origin.xlsx_diff.png) |
| excel | `libreoffice__empty.xlsx` | `PARITY_MATCH` | **95.7%** | 10.9 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__empty.xlsx_diff.png) |
| excel | `libreoffice__enhanced-protection.xlsx` | `PARITY_MATCH` | **95.4%** | 11.8 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__enhanced-protection.xlsx_diff.png) |
| excel | `libreoffice__macro-button-form-control.xlsm` | `PARITY_MATCH` | **95.9%** | 10.3 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__macro-button-form-control.xlsm_diff.png) |
| excel | `libreoffice__sortconditionref.xlsx` | `PARITY_MATCH` | **95.7%** | 10.9 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__sortconditionref.xlsx_diff.png) |
| excel | `libreoffice__tablerefsnamed.xlsx` | `COSMETIC_MINOR` | **95.0%** | 12.9 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__tablerefsnamed.xlsx_diff.png) |
| excel | `libreoffice__tdf113621.xlsx` | `PARITY_MATCH` | **95.9%** | 10.4 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__tdf113621.xlsx_diff.png) |
| excel | `libreoffice__tdf133595.xlsx` | `COSMETIC_MINOR` | **94.9%** | 13.1 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__tdf133595.xlsx_diff.png) |
| excel | `libreoffice__tdf169326_ignore_line_breaks_in_referenced_cells.xlsx` | `PARITY_MATCH` | **96.0%** | 10.2 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__tdf169326_ignore_line_breaks_in_referenced_cells.xlsx_diff.png) |
| excel | `libreoffice__totalsRowFunction.xlsx` | `COSMETIC_MINOR` | **91.4%** | 22.0 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__totalsRowFunction.xlsx_diff.png) |
| excel | `libreoffice__totalsRowShown.xlsx` | `COSMETIC_MINOR` | **94.9%** | 12.9 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__totalsRowShown.xlsx_diff.png) |
| excel | `openxml-sdk__00d63cdd-ee44-4e6a-99af-a7966ffbdda0.xlsx` | `PARITY_MATCH` | **95.8%** | 10.8 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/openxml-sdk__00d63cdd-ee44-4e6a-99af-a7966ffbdda0.xlsx_diff.png) |
| excel | `openxml-sdk__NoExtDataB1.xlsx` | `CRITICAL_MISMATCH` | **68.9%** | 79.3 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/openxml-sdk__NoExtDataB1.xlsx_diff.png) |
| excel | `openxml-sdk__RelationalPivotA4.xlsx` | `COSMETIC_MINOR` | **92.0%** | 20.4 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/openxml-sdk__RelationalPivotA4.xlsx_diff.png) |
| excel | `openxml-sdk__XMLMap.xlsx` | `PARITY_MATCH` | **95.4%** | 11.8 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/openxml-sdk__XMLMap.xlsx_diff.png) |
| excel | `poi__45540_form_Header.xlsx` | `COSMETIC_MINOR` | **94.4%** | 14.4 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/poi__45540_form_Header.xlsx_diff.png) |
| excel | `poi__46536.xlsx` | `PARITY_MATCH` | **95.8%** | 10.7 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/poi__46536.xlsx_diff.png) |
| excel | `poi__49156.xlsx` | `COSMETIC_MINOR` | **93.0%** | 17.9 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/poi__49156.xlsx_diff.png) |
| excel | `poi__60509.xlsx` | `COSMETIC_MINOR` | **93.0%** | 17.8 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/poi__60509.xlsx_diff.png) |
| excel | `poi__GroupTest.xlsx` | `COSMETIC_MINOR` | **94.9%** | 13.0 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/poi__GroupTest.xlsx_diff.png) |
| excel | `poi__SimpleWithComments.xlsx` | `PARITY_MATCH` | **95.5%** | 11.5 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/poi__SimpleWithComments.xlsx_diff.png) |
| excel | `poi__hello-world-signed.xlsx` | `PARITY_MATCH` | **95.9%** | 10.5 | 1178x798 | 1178x798 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/poi__hello-world-signed.xlsx_diff.png) |
| powerpoint | `libreoffice__TextFittingComparisonWithMSO_3.pptx` | `LAYOUT_DRIFT` | **85.0%** | 38.3 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__TextFittingComparisonWithMSO_3.pptx_diff.png) |
| powerpoint | `libreoffice__animation-sound-external.pptx` | `COSMETIC_MINOR` | **91.7%** | 21.2 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__animation-sound-external.pptx_diff.png) |
| powerpoint | `libreoffice__bnc887230.pptx` | `COSMETIC_MINOR` | **91.7%** | 21.2 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__bnc887230.pptx_diff.png) |
| powerpoint | `libreoffice__connector-shape-animations.pptx` | `COSMETIC_MINOR` | **90.0%** | 25.5 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__connector-shape-animations.pptx_diff.png) |
| powerpoint | `libreoffice__master-slides.pptx` | `CRITICAL_MISMATCH` | **47.8%** | 133.0 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__master-slides.pptx_diff.png) |
| powerpoint | `libreoffice__smartart-text.pptx` | `COSMETIC_MINOR` | **92.1%** | 20.1 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__smartart-text.pptx_diff.png) |
| powerpoint | `libreoffice__tdf103876.pptx` | `COSMETIC_MINOR` | **91.3%** | 22.1 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf103876.pptx_diff.png) |
| powerpoint | `libreoffice__tdf104201.pptx` | `COSMETIC_MINOR` | **90.6%** | 24.0 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf104201.pptx_diff.png) |
| powerpoint | `libreoffice__tdf104722.pptx` | `COSMETIC_MINOR` | **90.3%** | 24.9 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf104722.pptx_diff.png) |
| powerpoint | `libreoffice__tdf112089.pptx` | `COSMETIC_MINOR` | **88.7%** | 28.7 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf112089.pptx_diff.png) |
| powerpoint | `libreoffice__tdf126741.pptx` | `COSMETIC_MINOR` | **91.7%** | 21.2 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf126741.pptx_diff.png) |
| powerpoint | `libreoffice__tdf129372.pptx` | `COSMETIC_MINOR` | **91.7%** | 21.2 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf129372.pptx_diff.png) |
| powerpoint | `libreoffice__tdf136830.pptx` | `COSMETIC_MINOR` | **91.2%** | 22.4 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf136830.pptx_diff.png) |
| powerpoint | `libreoffice__tdf140852.pptx` | `COSMETIC_MINOR` | **90.8%** | 23.5 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf140852.pptx_diff.png) |
| powerpoint | `libreoffice__tdf143129.pptx` | `COSMETIC_MINOR` | **91.4%** | 21.9 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf143129.pptx_diff.png) |
| powerpoint | `libreoffice__tdf149206.pptx` | `COSMETIC_MINOR` | **91.2%** | 22.4 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf149206.pptx_diff.png) |
| powerpoint | `libreoffice__tdf164622.pptx` | `COSMETIC_MINOR` | **90.7%** | 23.8 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf164622.pptx_diff.png) |
| powerpoint | `openxml-sdk__Chart_3D (Column).pptx` | `COSMETIC_MINOR` | **86.2%** | 35.3 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/openxml-sdk__Chart_3D (Column).pptx_diff.png) |
| powerpoint | `openxml-sdk__Text_withShadow_200chars.pptx` | `COSMETIC_MINOR` | **88.4%** | 29.7 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/openxml-sdk__Text_withShadow_200chars.pptx_diff.png) |
| powerpoint | `openxml-sdk__cmpdThickThin_mainUln_UnderlineStrokeCompoundLineTypeThickThin.pptx` | `COSMETIC_MINOR` | **91.6%** | 21.4 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/openxml-sdk__cmpdThickThin_mainUln_UnderlineStrokeCompoundLineTypeThickThin.pptx_diff.png) |
| powerpoint | `openxml-sdk__main_bodyPr_rtlCol.pptx` | `COSMETIC_MINOR` | **91.1%** | 22.8 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/openxml-sdk__main_bodyPr_rtlCol.pptx_diff.png) |
| powerpoint | `openxml-sdk__marL51206400_mainPpr_LeftMarginMaximum.pptx` | `COSMETIC_MINOR` | **91.7%** | 21.2 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/openxml-sdk__marL51206400_mainPpr_LeftMarginMaximum.pptx_diff.png) |
| powerpoint | `openxml-sdk__sldsz-Slide Size-type-b4iso.pptx` | `COSMETIC_MINOR` | **91.2%** | 22.4 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/openxml-sdk__sldsz-Slide Size-type-b4iso.pptx_diff.png) |
| powerpoint | `poi__56812.pptx` | `COSMETIC_MINOR` | **91.0%** | 22.9 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/poi__56812.pptx_diff.png) |
| powerpoint | `poi__table-with-different-font-colors.pptx` | `COSMETIC_MINOR` | **89.4%** | 27.0 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/poi__table-with-different-font-colors.pptx_diff.png) |
| word | `libreoffice__A019_min.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1178x767 | - |
| word | `libreoffice__fdo52208.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1178x767 | - |
| word | `libreoffice__fdo55381.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1178x767 | - |
| word | `libreoffice__forum-mso-en-4208.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1178x767 | - |
| word | `libreoffice__nested-runs.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1178x767 | - |
| word | `libreoffice__sdt-ignored-footer.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1178x767 | - |
| word | `libreoffice__strict.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1178x767 | - |
| word | `libreoffice__tdf105035_framePrB.docx` | `LAYOUT_DRIFT` | **79.0%** | 53.7 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf105035_framePrB.docx_diff.png) |
| word | `libreoffice__tdf113182.docx` | `LAYOUT_DRIFT` | **77.9%** | 56.3 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf113182.docx_diff.png) |
| word | `libreoffice__tdf113183.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1178x767 | - |
| word | `libreoffice__tdf121670_columnsInSectionsOnly.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1178x767 | - |
| word | `libreoffice__tdf125881.docx` | `COSMETIC_MINOR` | **86.6%** | 34.1 | 1178x741 | 1178x741 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf125881.docx_diff.png) |
| word | `libreoffice__tdf131260.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1178x767 | - |
| word | `libreoffice__tdf132802.docx` | `COSMETIC_MINOR` | **87.0%** | 33.2 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf132802.docx_diff.png) |
| word | `libreoffice__tdf146973_signatureBlock.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1178x767 | - |
| word | `libreoffice__tdf153255.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1178x767 | - |
| word | `libreoffice__tdf154751_dualStrikethrough.docx` | `COSMETIC_MINOR` | **88.7%** | 28.8 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf154751_dualStrikethrough.docx_diff.png) |
| word | `libreoffice__tdf43100_tdf120715_cursorOnSpacesOverMargin.docx` | `LAYOUT_DRIFT` | **84.9%** | 38.6 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf43100_tdf120715_cursorOnSpacesOverMargin.docx_diff.png) |
| word | `libreoffice__tdf54095_SmartArtThemeTextColor.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1178x767 | - |
| word | `libreoffice__textframe-borders.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1178x767 | - |
| word | `openxml-sdk__Comment066.docx` | `LAYOUT_DRIFT` | **77.0%** | 58.7 | 1178x741 | 1178x741 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/openxml-sdk__Comment066.docx_diff.png) |
| word | `openxml-sdk__bullet-complex.docx` | `LAYOUT_DRIFT` | **81.8%** | 46.4 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/openxml-sdk__bullet-complex.docx_diff.png) |
| word | `poi__60316.docx` | `COSMETIC_MINOR` | **85.5%** | 37.0 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/poi__60316.docx_diff.png) |
| word | `poi__headerPic.docx` | `CRITICAL_MISMATCH` | **0.0%** | 255.0 | 1178x767 | 1178x767 | - |

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
  - Baseline size: (1178, 767), Candidate size: (1178, 767)
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
  - Baseline size: (1178, 767), Candidate size: (1178, 767)
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
  - Baseline size: (1178, 767), Candidate size: (1178, 767)
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
  - Baseline size: (1178, 767), Candidate size: (1178, 767)
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
  - Baseline size: (1178, 767), Candidate size: (1178, 767)
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
  - Baseline size: (1178, 767), Candidate size: (1178, 767)
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
  - Baseline size: (1178, 767), Candidate size: (1178, 767)
- **Acceptance Criteria**:
  - [ ] 1. Document `libreoffice__strict.docx` renders without errors or blank areas.
  - [ ] 2. Visual similarity with reference baseline improves to >= 90%.
  - [ ] 3. Automated regression test added in `tests/`.

### [TASK-DOC-08] fix(word): Resolve rendering discrepancy in `libreoffice__tdf105035_framePrB.docx`
- **Parent Epic**: Document Rendering Parity (MEDIUM Remediation)
- **Step**: Step 8 of N (Remediation Sequence)
- **Labels**: `type: bug`, `area: rendering`, `priority: medium`
- **Depends On**: `[TASK-DOC-07]`
- **Blocks**: None
- **Target Files**:
  - `src/atboffice/modules/writer/views/`
  - `src/atboffice/modules/writer/layout/`
  - `src/atboffice/modules/writer/io/`
- **Scope & Specification**:
  - Sample document: `libreoffice__tdf105035_framePrB.docx`
  - Observed Divergence: Canvas similarity 79.0% (category: LAYOUT_DRIFT) in libreoffice__tdf105035_framePrB.docx
  - Visual Diff: `/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf105035_framePrB.docx_diff.png`
  - Baseline size: (1178, 767), Candidate size: (1178, 767)
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
  - Observed Divergence: Canvas similarity 77.9% (category: LAYOUT_DRIFT) in libreoffice__tdf113182.docx
  - Visual Diff: `/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf113182.docx_diff.png`
  - Baseline size: (1178, 767), Candidate size: (1178, 767)
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
  - Baseline size: (1178, 767), Candidate size: (1178, 767)
- **Acceptance Criteria**:
  - [ ] 1. Document `libreoffice__tdf113183.docx` renders without errors or blank areas.
  - [ ] 2. Visual similarity with reference baseline improves to >= 90%.
  - [ ] 3. Automated regression test added in `tests/`.


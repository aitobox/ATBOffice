# ATBOffice vs. VibeOffice Visual Document Rendering Parity Report

> **Generated**: 2026-11-21 11:54:53 UTC  
> **Quality Gate Verdict**: **⚠️ NEEDS_REMEDIATION** (Target: Avg >= 90.0%, Single >= 85.0%)

## 1. Executive Summary

| Metric | Value | Target / Requirement |
|---|---|---|
| **Evaluated Documents** | `73` | 73 Core Supported OOXML |
| **Comparable Documents** | `73` | Size & Region Aligned |
| **Incomparable / Missing** | `0` | 0 Blockers |
| **Average Visual Similarity** | `65.31%` | >= 90.0% (Foreground-Weighted) |
| **Average Pixel Similarity (MAE)** | `96.91%` | Secondary Reference |
| **Parity Matches (>=95%)** | `22` | High Fidelity |
| **Cosmetic Minor (85%-95%)** | `2` | Acceptable |
| **Layout Drifts (70%-85%)** | `19` | Needs Polish |
| **Critical Mismatches (<70%)** | `30` | P0/P1 Defects |
| **Size Incomparable** | `0` | Viewport Alignment Required |
| **Missing Files** | `0` | 0 Missing |

---

## 2. Partitioning & Guardrails

- **73 Core Supported OOXML Documents** (`.docx`, `.xlsx`, `.pptx`): Evaluated for visual canvas fidelity.
- **77 Legacy Binary & Corrupt Documents** (`.doc`, `.xls`, `.ppt`): Strictly separated; require real application error-dialog and integrity verification per 2026-11-06 audit.
- **Dimension & Viewport Guardrail**: Missing images or dimension mismatches are reported as `INCOMPARABLE_SIZE` without artificial scores.

---

## 3. Detailed Results by Document

| App | File | Category | Foreground | Recall | Precision | Color Hist | Pixel Sim (MAE) | MAE | Baseline Size | ATB Size | Diff Map |
|---|---|---|---|---|---|---|---|---|---|---|---|
| excel | `libreoffice__Pivot2_Row.xlsx` | `CRITICAL_MISMATCH` | **31.1%** | 31.1% | 41.5% | 98.7% | 96.0% | 10.3 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__Pivot2_Row.xlsx_diff.png) |
| excel | `libreoffice__cell-value.xlsx` | `CRITICAL_MISMATCH` | **33.5%** | 33.5% | 42.1% | 98.6% | 95.7% | 10.9 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__cell-value.xlsx_diff.png) |
| excel | `libreoffice__conditional_fmt_origin.xlsx` | `LAYOUT_DRIFT` | **71.4%** | 84.5% | 71.4% | 98.6% | 96.5% | 8.9 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__conditional_fmt_origin.xlsx_diff.png) |
| excel | `libreoffice__empty.xlsx` | `CRITICAL_MISMATCH` | **29.8%** | 29.8% | 40.6% | 98.8% | 96.2% | 9.7 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__empty.xlsx_diff.png) |
| excel | `libreoffice__enhanced-protection.xlsx` | `LAYOUT_DRIFT` | **74.0%** | 86.3% | 74.0% | 98.5% | 96.1% | 9.9 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__enhanced-protection.xlsx_diff.png) |
| excel | `libreoffice__macro-button-form-control.xlsm` | `LAYOUT_DRIFT` | **71.2%** | 84.9% | 71.2% | 98.6% | 96.6% | 8.7 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__macro-button-form-control.xlsm_diff.png) |
| excel | `libreoffice__sortconditionref.xlsx` | `LAYOUT_DRIFT` | **73.9%** | 89.2% | 73.9% | 97.9% | 96.6% | 8.7 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__sortconditionref.xlsx_diff.png) |
| excel | `libreoffice__tablerefsnamed.xlsx` | `LAYOUT_DRIFT` | **72.7%** | 85.4% | 72.7% | 98.1% | 95.5% | 11.4 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__tablerefsnamed.xlsx_diff.png) |
| excel | `libreoffice__tdf113621.xlsx` | `LAYOUT_DRIFT` | **72.6%** | 85.7% | 72.6% | 98.8% | 96.6% | 8.7 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__tdf113621.xlsx_diff.png) |
| excel | `libreoffice__tdf133595.xlsx` | `LAYOUT_DRIFT` | **75.7%** | 88.7% | 75.7% | 88.6% | 96.0% | 10.1 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__tdf133595.xlsx_diff.png) |
| excel | `libreoffice__tdf169326_ignore_line_breaks_in_referenced_cells.xlsx` | `LAYOUT_DRIFT` | **70.7%** | 87.7% | 70.7% | 98.5% | 96.7% | 8.3 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__tdf169326_ignore_line_breaks_in_referenced_cells.xlsx_diff.png) |
| excel | `libreoffice__totalsRowFunction.xlsx` | `CRITICAL_MISMATCH` | **54.1%** | 58.7% | 54.1% | 90.8% | 93.4% | 16.8 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__totalsRowFunction.xlsx_diff.png) |
| excel | `libreoffice__totalsRowShown.xlsx` | `CRITICAL_MISMATCH` | **43.2%** | 43.2% | 48.2% | 98.5% | 95.6% | 11.1 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__totalsRowShown.xlsx_diff.png) |
| excel | `openxml-sdk__00d63cdd-ee44-4e6a-99af-a7966ffbdda0.xlsx` | `CRITICAL_MISMATCH` | **66.5%** | 83.7% | 66.5% | 88.9% | 95.3% | 12.1 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/openxml-sdk__00d63cdd-ee44-4e6a-99af-a7966ffbdda0.xlsx_diff.png) |
| excel | `openxml-sdk__NoExtDataB1.xlsx` | `LAYOUT_DRIFT` | **84.0%** | 91.1% | 84.0% | 97.4% | 80.2% | 50.6 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/openxml-sdk__NoExtDataB1.xlsx_diff.png) |
| excel | `openxml-sdk__RelationalPivotA4.xlsx` | `CRITICAL_MISMATCH` | **65.1%** | 82.5% | 65.1% | 98.7% | 92.8% | 18.5 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/openxml-sdk__RelationalPivotA4.xlsx_diff.png) |
| excel | `openxml-sdk__XMLMap.xlsx` | `LAYOUT_DRIFT` | **72.8%** | 86.5% | 72.8% | 97.6% | 96.3% | 9.5 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/openxml-sdk__XMLMap.xlsx_diff.png) |
| excel | `poi__45540_form_Header.xlsx` | `CRITICAL_MISMATCH` | **69.4%** | 88.6% | 69.4% | 85.1% | 95.4% | 11.7 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/poi__45540_form_Header.xlsx_diff.png) |
| excel | `poi__46536.xlsx` | `LAYOUT_DRIFT` | **72.6%** | 85.2% | 72.6% | 98.2% | 96.4% | 9.1 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/poi__46536.xlsx_diff.png) |
| excel | `poi__49156.xlsx` | `LAYOUT_DRIFT` | **73.5%** | 84.3% | 73.5% | 94.1% | 95.8% | 10.8 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/poi__49156.xlsx_diff.png) |
| excel | `poi__60509.xlsx` | `CRITICAL_MISMATCH` | **66.8%** | 69.0% | 66.8% | 95.5% | 93.4% | 16.8 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/poi__60509.xlsx_diff.png) |
| excel | `poi__GroupTest.xlsx` | `LAYOUT_DRIFT` | **85.0%** | 89.6% | 85.0% | 98.5% | 96.1% | 10.1 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/poi__GroupTest.xlsx_diff.png) |
| excel | `poi__SimpleWithComments.xlsx` | `CRITICAL_MISMATCH` | **30.9%** | 30.9% | 40.9% | 98.7% | 96.0% | 10.2 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/poi__SimpleWithComments.xlsx_diff.png) |
| excel | `poi__hello-world-signed.xlsx` | `LAYOUT_DRIFT` | **71.8%** | 84.9% | 71.8% | 98.7% | 96.6% | 8.7 | 1178x780 | 1178x780 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/poi__hello-world-signed.xlsx_diff.png) |
| powerpoint | `libreoffice__TextFittingComparisonWithMSO_3.pptx` | `PARITY_MATCH` | **98.9%** | 99.8% | 98.9% | 99.0% | 93.5% | 16.7 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__TextFittingComparisonWithMSO_3.pptx_diff.png) |
| powerpoint | `libreoffice__animation-sound-external.pptx` | `PARITY_MATCH` | **98.1%** | 100.0% | 100.0% | 98.1% | 99.8% | 0.6 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__animation-sound-external.pptx_diff.png) |
| powerpoint | `libreoffice__bnc887230.pptx` | `PARITY_MATCH` | **98.3%** | 100.0% | 100.0% | 98.3% | 99.8% | 0.6 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__bnc887230.pptx_diff.png) |
| powerpoint | `libreoffice__connector-shape-animations.pptx` | `PARITY_MATCH` | **98.0%** | 100.0% | 100.0% | 98.0% | 99.8% | 0.6 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__connector-shape-animations.pptx_diff.png) |
| powerpoint | `libreoffice__master-slides.pptx` | `PARITY_MATCH` | **98.5%** | 98.7% | 98.6% | 98.5% | 98.1% | 4.9 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__master-slides.pptx_diff.png) |
| powerpoint | `libreoffice__smartart-text.pptx` | `LAYOUT_DRIFT` | **70.8%** | 100.0% | 70.8% | 85.6% | 99.4% | 1.5 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__smartart-text.pptx_diff.png) |
| powerpoint | `libreoffice__tdf103876.pptx` | `PARITY_MATCH` | **98.2%** | 100.0% | 100.0% | 98.2% | 99.6% | 1.0 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf103876.pptx_diff.png) |
| powerpoint | `libreoffice__tdf104201.pptx` | `PARITY_MATCH` | **98.2%** | 100.0% | 100.0% | 98.2% | 99.7% | 0.9 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf104201.pptx_diff.png) |
| powerpoint | `libreoffice__tdf104722.pptx` | `PARITY_MATCH` | **98.8%** | 100.0% | 100.0% | 98.8% | 99.3% | 1.9 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf104722.pptx_diff.png) |
| powerpoint | `libreoffice__tdf112089.pptx` | `PARITY_MATCH` | **96.5%** | 96.8% | 96.5% | 99.5% | 97.0% | 7.6 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf112089.pptx_diff.png) |
| powerpoint | `libreoffice__tdf126741.pptx` | `PARITY_MATCH` | **98.3%** | 100.0% | 100.0% | 98.3% | 99.8% | 0.6 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf126741.pptx_diff.png) |
| powerpoint | `libreoffice__tdf129372.pptx` | `PARITY_MATCH` | **98.1%** | 100.0% | 100.0% | 98.1% | 99.8% | 0.6 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf129372.pptx_diff.png) |
| powerpoint | `libreoffice__tdf136830.pptx` | `PARITY_MATCH` | **97.1%** | 100.0% | 100.0% | 97.1% | 99.7% | 0.7 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf136830.pptx_diff.png) |
| powerpoint | `libreoffice__tdf140852.pptx` | `PARITY_MATCH` | **98.9%** | 99.5% | 99.4% | 98.9% | 98.1% | 4.9 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf140852.pptx_diff.png) |
| powerpoint | `libreoffice__tdf143129.pptx` | `PARITY_MATCH` | **98.2%** | 99.9% | 99.9% | 98.2% | 99.4% | 1.6 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf143129.pptx_diff.png) |
| powerpoint | `libreoffice__tdf149206.pptx` | `PARITY_MATCH` | **99.3%** | 100.0% | 100.0% | 99.3% | 99.4% | 1.6 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf149206.pptx_diff.png) |
| powerpoint | `libreoffice__tdf164622.pptx` | `PARITY_MATCH` | **97.0%** | 100.0% | 100.0% | 97.0% | 99.7% | 0.8 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__tdf164622.pptx_diff.png) |
| powerpoint | `openxml-sdk__Chart_3D (Column).pptx` | `COSMETIC_MINOR` | **86.1%** | 86.1% | 95.2% | 93.2% | 93.3% | 17.2 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/openxml-sdk__Chart_3D (Column).pptx_diff.png) |
| powerpoint | `openxml-sdk__Text_withShadow_200chars.pptx` | `PARITY_MATCH` | **99.3%** | 100.0% | 100.0% | 99.3% | 97.4% | 6.5 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/openxml-sdk__Text_withShadow_200chars.pptx_diff.png) |
| powerpoint | `openxml-sdk__cmpdThickThin_mainUln_UnderlineStrokeCompoundLineTypeThickThin.pptx` | `PARITY_MATCH` | **98.5%** | 100.0% | 100.0% | 98.5% | 99.6% | 0.9 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/openxml-sdk__cmpdThickThin_mainUln_UnderlineStrokeCompoundLineTypeThickThin.pptx_diff.png) |
| powerpoint | `openxml-sdk__main_bodyPr_rtlCol.pptx` | `PARITY_MATCH` | **98.9%** | 100.0% | 100.0% | 98.9% | 99.0% | 2.6 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/openxml-sdk__main_bodyPr_rtlCol.pptx_diff.png) |
| powerpoint | `openxml-sdk__marL51206400_mainPpr_LeftMarginMaximum.pptx` | `PARITY_MATCH` | **98.1%** | 100.0% | 100.0% | 98.1% | 99.8% | 0.6 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/openxml-sdk__marL51206400_mainPpr_LeftMarginMaximum.pptx_diff.png) |
| powerpoint | `openxml-sdk__sldsz-Slide Size-type-b4iso.pptx` | `LAYOUT_DRIFT` | **83.5%** | 84.0% | 83.5% | 98.8% | 96.4% | 9.1 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/openxml-sdk__sldsz-Slide Size-type-b4iso.pptx_diff.png) |
| powerpoint | `poi__56812.pptx` | `PARITY_MATCH` | **99.3%** | 99.6% | 100.0% | 99.3% | 99.3% | 1.7 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/poi__56812.pptx_diff.png) |
| powerpoint | `poi__table-with-different-font-colors.pptx` | `PARITY_MATCH` | **98.8%** | 98.9% | 99.3% | 98.8% | 98.5% | 3.8 | 982x648 | 982x648 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/poi__table-with-different-font-colors.pptx_diff.png) |
| word | `libreoffice__A019_min.docx` | `CRITICAL_MISMATCH` | **0.0%** | 0.0% | 0.0% | 98.4% | 99.0% | 2.4 | 1158x727 | 1158x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__A019_min.docx_diff.png) |
| word | `libreoffice__fdo52208.docx` | `CRITICAL_MISMATCH` | **38.0%** | 38.0% | 38.1% | 99.9% | 99.0% | 2.6 | 1158x727 | 1158x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__fdo52208.docx_diff.png) |
| word | `libreoffice__fdo55381.docx` | `CRITICAL_MISMATCH` | **0.0%** | 0.0% | 0.0% | 95.2% | 99.0% | 2.4 | 1158x727 | 1158x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__fdo55381.docx_diff.png) |
| word | `libreoffice__forum-mso-en-4208.docx` | `CRITICAL_MISMATCH` | **0.0%** | 0.0% | 0.0% | 0.0% | 99.1% | 2.4 | 1158x727 | 1158x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__forum-mso-en-4208.docx_diff.png) |
| word | `libreoffice__nested-runs.docx` | `CRITICAL_MISMATCH` | **0.0%** | 0.0% | 0.0% | 0.0% | 99.0% | 2.5 | 1158x727 | 1158x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__nested-runs.docx_diff.png) |
| word | `libreoffice__sdt-ignored-footer.docx` | `CRITICAL_MISMATCH` | **0.3%** | 0.3% | 0.7% | 99.9% | 99.0% | 2.6 | 1158x727 | 1158x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__sdt-ignored-footer.docx_diff.png) |
| word | `libreoffice__strict.docx` | `CRITICAL_MISMATCH` | **47.2%** | 47.2% | 60.8% | 64.4% | 95.1% | 12.4 | 1158x727 | 1158x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__strict.docx_diff.png) |
| word | `libreoffice__tdf105035_framePrB.docx` | `LAYOUT_DRIFT` | **79.4%** | 79.4% | 84.5% | 99.9% | 92.1% | 20.1 | 1158x727 | 1158x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf105035_framePrB.docx_diff.png) |
| word | `libreoffice__tdf113182.docx` | `LAYOUT_DRIFT` | **73.7%** | 76.3% | 73.7% | 99.3% | 90.4% | 24.5 | 1158x727 | 1158x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf113182.docx_diff.png) |
| word | `libreoffice__tdf113183.docx` | `CRITICAL_MISMATCH` | **56.5%** | 65.8% | 56.5% | 98.7% | 98.7% | 3.3 | 1158x727 | 1158x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf113183.docx_diff.png) |
| word | `libreoffice__tdf121670_columnsInSectionsOnly.docx` | `CRITICAL_MISMATCH` | **25.2%** | 34.3% | 25.2% | 97.2% | 96.5% | 9.0 | 1158x727 | 1158x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf121670_columnsInSectionsOnly.docx_diff.png) |
| word | `libreoffice__tdf125881.docx` | `CRITICAL_MISMATCH` | **3.0%** | 3.0% | 3.3% | 99.5% | 97.4% | 6.7 | 1158x701 | 1158x701 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf125881.docx_diff.png) |
| word | `libreoffice__tdf131260.docx` | `CRITICAL_MISMATCH` | **8.5%** | 9.4% | 8.5% | 66.2% | 98.2% | 4.5 | 1158x727 | 1158x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf131260.docx_diff.png) |
| word | `libreoffice__tdf132802.docx` | `CRITICAL_MISMATCH` | **36.7%** | 36.7% | 37.5% | 97.5% | 97.9% | 5.5 | 1158x727 | 1158x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf132802.docx_diff.png) |
| word | `libreoffice__tdf146973_signatureBlock.docx` | `CRITICAL_MISMATCH` | **1.1%** | 1.1% | 1.5% | 99.6% | 98.8% | 3.0 | 1158x727 | 1158x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf146973_signatureBlock.docx_diff.png) |
| word | `libreoffice__tdf153255.docx` | `CRITICAL_MISMATCH` | **0.0%** | 0.0% | 0.0% | 99.0% | 99.0% | 2.5 | 1158x727 | 1158x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf153255.docx_diff.png) |
| word | `libreoffice__tdf154751_dualStrikethrough.docx` | `CRITICAL_MISMATCH` | **41.2%** | 41.2% | 43.9% | 99.5% | 98.0% | 5.1 | 1158x727 | 1158x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf154751_dualStrikethrough.docx_diff.png) |
| word | `libreoffice__tdf43100_tdf120715_cursorOnSpacesOverMargin.docx` | `CRITICAL_MISMATCH` | **38.6%** | 40.1% | 38.6% | 99.8% | 96.2% | 9.7 | 1158x727 | 1158x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf43100_tdf120715_cursorOnSpacesOverMargin.docx_diff.png) |
| word | `libreoffice__tdf54095_SmartArtThemeTextColor.docx` | `CRITICAL_MISMATCH` | **32.1%** | 35.3% | 32.1% | 80.4% | 98.2% | 4.6 | 1158x727 | 1158x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf54095_SmartArtThemeTextColor.docx_diff.png) |
| word | `libreoffice__textframe-borders.docx` | `COSMETIC_MINOR` | **86.9%** | 86.9% | 88.8% | 98.6% | 98.0% | 5.1 | 1143x727 | 1143x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__textframe-borders.docx_diff.png) |
| word | `openxml-sdk__Comment066.docx` | `LAYOUT_DRIFT` | **82.5%** | 82.5% | 88.7% | 98.0% | 91.7% | 21.2 | 1143x701 | 1143x701 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/openxml-sdk__Comment066.docx_diff.png) |
| word | `openxml-sdk__bullet-complex.docx` | `CRITICAL_MISMATCH` | **63.7%** | 63.7% | 65.7% | 99.7% | 92.2% | 19.8 | 1143x727 | 1143x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/openxml-sdk__bullet-complex.docx_diff.png) |
| word | `poi__60316.docx` | `CRITICAL_MISMATCH` | **50.0%** | 50.0% | 53.1% | 99.8% | 96.2% | 9.8 | 1143x727 | 1143x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/poi__60316.docx_diff.png) |
| word | `poi__headerPic.docx` | `CRITICAL_MISMATCH` | **66.9%** | 77.8% | 79.3% | 66.9% | 98.7% | 3.2 | 1143x727 | 1143x727 | [`diff`](/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/poi__headerPic.docx_diff.png) |

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
  - Observed Divergence: Foreground score 0.0% (pixel MAE sim 99.0%, category: CRITICAL_MISMATCH) in libreoffice__A019_min.docx
  - Visual Diff: `/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__A019_min.docx_diff.png`
  - Baseline size: (1158, 727), Candidate size: (1158, 727)
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
  - Observed Divergence: Foreground score 38.0% (pixel MAE sim 99.0%, category: CRITICAL_MISMATCH) in libreoffice__fdo52208.docx
  - Visual Diff: `/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__fdo52208.docx_diff.png`
  - Baseline size: (1158, 727), Candidate size: (1158, 727)
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
  - Observed Divergence: Foreground score 0.0% (pixel MAE sim 99.0%, category: CRITICAL_MISMATCH) in libreoffice__fdo55381.docx
  - Visual Diff: `/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__fdo55381.docx_diff.png`
  - Baseline size: (1158, 727), Candidate size: (1158, 727)
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
  - Observed Divergence: Foreground score 0.0% (pixel MAE sim 99.1%, category: CRITICAL_MISMATCH) in libreoffice__forum-mso-en-4208.docx
  - Visual Diff: `/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__forum-mso-en-4208.docx_diff.png`
  - Baseline size: (1158, 727), Candidate size: (1158, 727)
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
  - Observed Divergence: Foreground score 0.0% (pixel MAE sim 99.0%, category: CRITICAL_MISMATCH) in libreoffice__nested-runs.docx
  - Visual Diff: `/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__nested-runs.docx_diff.png`
  - Baseline size: (1158, 727), Candidate size: (1158, 727)
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
  - Observed Divergence: Foreground score 0.3% (pixel MAE sim 99.0%, category: CRITICAL_MISMATCH) in libreoffice__sdt-ignored-footer.docx
  - Visual Diff: `/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__sdt-ignored-footer.docx_diff.png`
  - Baseline size: (1158, 727), Candidate size: (1158, 727)
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
  - Observed Divergence: Foreground score 47.2% (pixel MAE sim 95.1%, category: CRITICAL_MISMATCH) in libreoffice__strict.docx
  - Visual Diff: `/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__strict.docx_diff.png`
  - Baseline size: (1158, 727), Candidate size: (1158, 727)
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
  - Observed Divergence: Foreground score 79.4% (pixel MAE sim 92.1%, category: LAYOUT_DRIFT) in libreoffice__tdf105035_framePrB.docx
  - Visual Diff: `/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf105035_framePrB.docx_diff.png`
  - Baseline size: (1158, 727), Candidate size: (1158, 727)
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
  - Observed Divergence: Foreground score 73.7% (pixel MAE sim 90.4%, category: LAYOUT_DRIFT) in libreoffice__tdf113182.docx
  - Visual Diff: `/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf113182.docx_diff.png`
  - Baseline size: (1158, 727), Candidate size: (1158, 727)
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
  - Observed Divergence: Foreground score 56.5% (pixel MAE sim 98.7%, category: CRITICAL_MISMATCH) in libreoffice__tdf113183.docx
  - Visual Diff: `/Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf113183.docx_diff.png`
  - Baseline size: (1158, 727), Candidate size: (1158, 727)
- **Acceptance Criteria**:
  - [ ] 1. Document `libreoffice__tdf113183.docx` renders without errors or blank areas.
  - [ ] 2. Visual similarity with reference baseline improves to >= 90%.
  - [ ] 3. Automated regression test added in `tests/`.


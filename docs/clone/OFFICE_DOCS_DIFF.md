# ATBOffice vs. VibeOffice Visual Document Rendering Parity Report

> **Generated**: 2026-11-27 04:46:31 UTC  
> **Quality Gate Verdict**: **✅ PASS** (Target: Avg >= 90.0%, Single >= 85.0%)

## 1. Executive Summary

| Metric | Value | Target / Requirement |
|---|---|---|
| **Evaluated Documents** | `73` | 73 Core Supported OOXML |
| **Comparable Documents** | `73` | Size & Region Aligned |
| **Incomparable / Missing** | `0` | 0 Blockers |
| **Average Visual Similarity** | `95.37%` | >= 90.0% (Foreground-Weighted) |
| **Average Pixel Similarity (MAE)** | `96.75%` | Secondary Reference |
| **Parity Matches (>=95%)** | `44` | High Fidelity |
| **Cosmetic Minor (85%-95%)** | `29` | Acceptable |
| **Layout Drifts (70%-85%)** | `0` | Needs Polish |
| **Critical Mismatches (<70%)** | `0` | P0/P1 Defects |
| **Size Incomparable** | `0` | Viewport Alignment Required |
| **Missing Files** | `0` | 0 Missing |
| **Reference Limitations** | `1` | Exempt from the single-document bar (Section 5) |

---

## 2. Partitioning & Guardrails

- **73 Core Supported OOXML Documents** (`.docx`, `.xlsx`, `.pptx`): Evaluated for visual canvas fidelity.
- **77 Legacy Binary & Corrupt Documents** (`.doc`, `.xls`, `.ppt`): Strictly separated; require real application error-dialog and integrity verification per 2026-11-06 audit.
- **Dimension & Viewport Guardrail**: Missing images or dimension mismatches are reported as `INCOMPARABLE_SIZE` without artificial scores.

---

## 3. Detailed Results by Document

| App | File | Category | Foreground | Recall | Precision | Color Hist | Pixel Sim (MAE) | MAE | Baseline Size | ATB Size | Diff Map |
|---|---|---|---|---|---|---|---|---|---|---|---|
| excel | `libreoffice__Pivot2_Row.xlsx` | `PARITY_MATCH` | **98.9%** | 98.9% | 100.0% | 99.8% | 96.3% | 9.3 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/libreoffice__Pivot2_Row.xlsx_diff.png) |
| excel | `libreoffice__cell-value.xlsx` | `PARITY_MATCH` | **99.0%** | 99.0% | 100.0% | 99.8% | 96.2% | 9.7 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/libreoffice__cell-value.xlsx_diff.png) |
| excel | `libreoffice__conditional_fmt_origin.xlsx` | `PARITY_MATCH` | **98.6%** | 98.6% | 100.0% | 99.8% | 97.0% | 7.8 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/libreoffice__conditional_fmt_origin.xlsx_diff.png) |
| excel | `libreoffice__empty.xlsx` | `PARITY_MATCH` | **98.9%** | 98.9% | 100.0% | 99.8% | 96.4% | 9.2 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/libreoffice__empty.xlsx_diff.png) |
| excel | `libreoffice__enhanced-protection.xlsx` | `PARITY_MATCH` | **98.5%** | 98.5% | 99.9% | 99.8% | 96.6% | 8.7 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/libreoffice__enhanced-protection.xlsx_diff.png) |
| excel | `libreoffice__macro-button-form-control.xlsm` | `PARITY_MATCH` | **98.7%** | 98.7% | 100.0% | 99.8% | 97.0% | 7.7 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/libreoffice__macro-button-form-control.xlsm_diff.png) |
| excel | `libreoffice__sortconditionref.xlsx` | `PARITY_MATCH` | **98.7%** | 98.7% | 100.0% | 99.8% | 97.0% | 7.5 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/libreoffice__sortconditionref.xlsx_diff.png) |
| excel | `libreoffice__tablerefsnamed.xlsx` | `PARITY_MATCH` | **98.5%** | 98.5% | 100.0% | 99.8% | 96.3% | 9.4 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/libreoffice__tablerefsnamed.xlsx_diff.png) |
| excel | `libreoffice__tdf113621.xlsx` | `PARITY_MATCH` | **98.7%** | 98.7% | 100.0% | 99.8% | 97.0% | 7.7 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/libreoffice__tdf113621.xlsx_diff.png) |
| excel | `libreoffice__tdf133595.xlsx` | `COSMETIC_MINOR` | **89.5%** | 98.9% | 100.0% | 89.5% | 96.6% | 8.6 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/libreoffice__tdf133595.xlsx_diff.png) |
| excel | `libreoffice__tdf169326_ignore_line_breaks_in_referenced_cells.xlsx` | `PARITY_MATCH` | **98.7%** | 98.7% | 100.0% | 99.8% | 97.2% | 7.2 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/libreoffice__tdf169326_ignore_line_breaks_in_referenced_cells.xlsx_diff.png) |
| excel | `libreoffice__totalsRowFunction.xlsx` | `COSMETIC_MINOR` | **87.0%** | 87.0% | 96.9% | 99.4% | 97.3% | 6.8 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/libreoffice__totalsRowFunction.xlsx_diff.png) |
| excel | `libreoffice__totalsRowShown.xlsx` | `PARITY_MATCH` | **99.0%** | 99.0% | 100.0% | 99.9% | 96.4% | 9.1 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/libreoffice__totalsRowShown.xlsx_diff.png) |
| excel | `openxml-sdk__00d63cdd-ee44-4e6a-99af-a7966ffbdda0.xlsx` | `COSMETIC_MINOR` · `REFERENCE_LIMITATION` | **85.5%** | 97.4% | 85.5% | 85.6% | 95.6% | 11.3 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/openxml-sdk__00d63cdd-ee44-4e6a-99af-a7966ffbdda0.xlsx_diff.png) |
| excel | `openxml-sdk__NoExtDataB1.xlsx` | `COSMETIC_MINOR` | **94.7%** | 94.7% | 96.0% | 98.0% | 87.3% | 32.4 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/openxml-sdk__NoExtDataB1.xlsx_diff.png) |
| excel | `openxml-sdk__RelationalPivotA4.xlsx` | `PARITY_MATCH` | **98.1%** | 98.1% | 99.9% | 99.9% | 94.6% | 13.8 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/openxml-sdk__RelationalPivotA4.xlsx_diff.png) |
| excel | `openxml-sdk__XMLMap.xlsx` | `PARITY_MATCH` | **98.8%** | 98.8% | 99.7% | 99.5% | 96.9% | 8.0 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/openxml-sdk__XMLMap.xlsx_diff.png) |
| excel | `poi__45540_form_Header.xlsx` | `PARITY_MATCH` | **97.9%** | 97.9% | 99.5% | 99.7% | 97.1% | 7.4 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/poi__45540_form_Header.xlsx_diff.png) |
| excel | `poi__46536.xlsx` | `PARITY_MATCH` | **98.6%** | 98.6% | 100.0% | 99.8% | 96.9% | 7.9 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/poi__46536.xlsx_diff.png) |
| excel | `poi__49156.xlsx` | `PARITY_MATCH` | **95.1%** | 99.5% | 95.1% | 96.5% | 98.6% | 3.6 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/poi__49156.xlsx_diff.png) |
| excel | `poi__60509.xlsx` | `PARITY_MATCH` | **96.9%** | 96.9% | 98.2% | 99.1% | 95.8% | 10.8 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/poi__60509.xlsx_diff.png) |
| excel | `poi__GroupTest.xlsx` | `PARITY_MATCH` | **99.0%** | 99.8% | 100.0% | 99.0% | 96.5% | 9.0 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/poi__GroupTest.xlsx_diff.png) |
| excel | `poi__SimpleWithComments.xlsx` | `PARITY_MATCH` | **98.8%** | 98.8% | 99.3% | 99.8% | 96.3% | 9.5 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/poi__SimpleWithComments.xlsx_diff.png) |
| excel | `poi__hello-world-signed.xlsx` | `PARITY_MATCH` | **98.6%** | 98.6% | 100.0% | 99.8% | 96.9% | 7.8 | 1178x798 | 1178x798 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/excel/poi__hello-world-signed.xlsx_diff.png) |
| powerpoint | `libreoffice__TextFittingComparisonWithMSO_3.pptx` | `PARITY_MATCH` | **98.4%** | 99.7% | 98.4% | 98.7% | 94.3% | 14.7 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/libreoffice__TextFittingComparisonWithMSO_3.pptx_diff.png) |
| powerpoint | `libreoffice__animation-sound-external.pptx` | `PARITY_MATCH` | **98.4%** | 100.0% | 99.9% | 98.4% | 99.7% | 0.8 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/libreoffice__animation-sound-external.pptx_diff.png) |
| powerpoint | `libreoffice__bnc887230.pptx` | `PARITY_MATCH` | **98.5%** | 100.0% | 99.9% | 98.5% | 99.7% | 0.8 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/libreoffice__bnc887230.pptx_diff.png) |
| powerpoint | `libreoffice__connector-shape-animations.pptx` | `PARITY_MATCH` | **98.3%** | 98.4% | 98.6% | 98.3% | 98.4% | 4.2 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/libreoffice__connector-shape-animations.pptx_diff.png) |
| powerpoint | `libreoffice__master-slides.pptx` | `PARITY_MATCH` | **98.7%** | 98.8% | 98.7% | 99.2% | 98.2% | 4.5 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/libreoffice__master-slides.pptx_diff.png) |
| powerpoint | `libreoffice__smartart-text.pptx` | `PARITY_MATCH` | **98.5%** | 99.9% | 99.8% | 98.5% | 99.5% | 1.2 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/libreoffice__smartart-text.pptx_diff.png) |
| powerpoint | `libreoffice__tdf103876.pptx` | `PARITY_MATCH` | **95.7%** | 99.5% | 95.7% | 97.7% | 98.8% | 3.1 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/libreoffice__tdf103876.pptx_diff.png) |
| powerpoint | `libreoffice__tdf104201.pptx` | `PARITY_MATCH` | **98.3%** | 100.0% | 99.9% | 98.3% | 99.6% | 1.0 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/libreoffice__tdf104201.pptx_diff.png) |
| powerpoint | `libreoffice__tdf104722.pptx` | `PARITY_MATCH` | **98.2%** | 100.0% | 99.9% | 98.2% | 99.3% | 1.8 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/libreoffice__tdf104722.pptx_diff.png) |
| powerpoint | `libreoffice__tdf112089.pptx` | `COSMETIC_MINOR` | **93.2%** | 95.4% | 93.2% | 99.4% | 96.4% | 9.2 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/libreoffice__tdf112089.pptx_diff.png) |
| powerpoint | `libreoffice__tdf126741.pptx` | `PARITY_MATCH` | **98.7%** | 100.0% | 99.9% | 98.7% | 99.7% | 0.8 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/libreoffice__tdf126741.pptx_diff.png) |
| powerpoint | `libreoffice__tdf129372.pptx` | `PARITY_MATCH` | **97.7%** | 100.0% | 99.9% | 97.7% | 99.7% | 0.7 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/libreoffice__tdf129372.pptx_diff.png) |
| powerpoint | `libreoffice__tdf136830.pptx` | `PARITY_MATCH` | **98.1%** | 100.0% | 99.9% | 98.1% | 99.7% | 0.8 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/libreoffice__tdf136830.pptx_diff.png) |
| powerpoint | `libreoffice__tdf140852.pptx` | `PARITY_MATCH` | **98.9%** | 99.2% | 99.0% | 98.9% | 98.2% | 4.5 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/libreoffice__tdf140852.pptx_diff.png) |
| powerpoint | `libreoffice__tdf143129.pptx` | `PARITY_MATCH` | **98.2%** | 99.9% | 99.4% | 98.2% | 99.3% | 1.9 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/libreoffice__tdf143129.pptx_diff.png) |
| powerpoint | `libreoffice__tdf149206.pptx` | `PARITY_MATCH` | **99.5%** | 100.0% | 99.9% | 99.5% | 99.4% | 1.6 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/libreoffice__tdf149206.pptx_diff.png) |
| powerpoint | `libreoffice__tdf164622.pptx` | `PARITY_MATCH` | **97.8%** | 100.0% | 99.9% | 97.8% | 99.6% | 1.0 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/libreoffice__tdf164622.pptx_diff.png) |
| powerpoint | `openxml-sdk__Chart_3D (Column).pptx` | `PARITY_MATCH` | **95.4%** | 98.2% | 95.4% | 99.3% | 96.3% | 9.4 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/openxml-sdk__Chart_3D (Column).pptx_diff.png) |
| powerpoint | `openxml-sdk__Text_withShadow_200chars.pptx` | `PARITY_MATCH` | **99.0%** | 99.8% | 99.5% | 99.0% | 97.0% | 7.6 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/openxml-sdk__Text_withShadow_200chars.pptx_diff.png) |
| powerpoint | `openxml-sdk__cmpdThickThin_mainUln_UnderlineStrokeCompoundLineTypeThickThin.pptx` | `PARITY_MATCH` | **98.5%** | 100.0% | 99.9% | 98.5% | 99.6% | 1.1 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/openxml-sdk__cmpdThickThin_mainUln_UnderlineStrokeCompoundLineTypeThickThin.pptx_diff.png) |
| powerpoint | `openxml-sdk__main_bodyPr_rtlCol.pptx` | `PARITY_MATCH` | **98.7%** | 100.0% | 99.9% | 98.7% | 99.0% | 2.6 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/openxml-sdk__main_bodyPr_rtlCol.pptx_diff.png) |
| powerpoint | `openxml-sdk__marL51206400_mainPpr_LeftMarginMaximum.pptx` | `PARITY_MATCH` | **98.4%** | 100.0% | 99.9% | 98.4% | 99.7% | 0.8 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/openxml-sdk__marL51206400_mainPpr_LeftMarginMaximum.pptx_diff.png) |
| powerpoint | `openxml-sdk__sldsz-Slide Size-type-b4iso.pptx` | `PARITY_MATCH` | **97.6%** | 99.8% | 97.6% | 98.8% | 98.4% | 4.0 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/openxml-sdk__sldsz-Slide Size-type-b4iso.pptx_diff.png) |
| powerpoint | `poi__56812.pptx` | `PARITY_MATCH` | **99.2%** | 99.5% | 99.9% | 99.2% | 99.3% | 1.7 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/poi__56812.pptx_diff.png) |
| powerpoint | `poi__table-with-different-font-colors.pptx` | `PARITY_MATCH` | **98.4%** | 98.4% | 99.0% | 99.1% | 98.6% | 3.5 | 982x745 | 982x745 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/powerpoint/poi__table-with-different-font-colors.pptx_diff.png) |
| word | `libreoffice__A019_min.docx` | `COSMETIC_MINOR` | **93.6%** | 100.0% | 93.6% | 99.6% | 97.4% | 6.6 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/libreoffice__A019_min.docx_diff.png) |
| word | `libreoffice__fdo52208.docx` | `COSMETIC_MINOR` | **93.3%** | 99.7% | 93.3% | 99.8% | 97.3% | 6.9 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/libreoffice__fdo52208.docx_diff.png) |
| word | `libreoffice__fdo55381.docx` | `COSMETIC_MINOR` | **92.9%** | 99.9% | 92.9% | 99.5% | 97.5% | 6.5 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/libreoffice__fdo55381.docx_diff.png) |
| word | `libreoffice__forum-mso-en-4208.docx` | `COSMETIC_MINOR` | **92.9%** | 100.0% | 92.9% | 99.4% | 97.5% | 6.5 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/libreoffice__forum-mso-en-4208.docx_diff.png) |
| word | `libreoffice__nested-runs.docx` | `COSMETIC_MINOR` | **92.8%** | 100.0% | 92.8% | 99.6% | 97.4% | 6.6 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/libreoffice__nested-runs.docx_diff.png) |
| word | `libreoffice__sdt-ignored-footer.docx` | `COSMETIC_MINOR` | **92.7%** | 99.7% | 92.7% | 99.6% | 97.4% | 6.6 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/libreoffice__sdt-ignored-footer.docx_diff.png) |
| word | `libreoffice__strict.docx` | `COSMETIC_MINOR` | **85.7%** | 86.6% | 85.7% | 93.2% | 93.6% | 16.3 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/libreoffice__strict.docx_diff.png) |
| word | `libreoffice__tdf105035_framePrB.docx` | `COSMETIC_MINOR` | **87.4%** | 91.6% | 87.4% | 99.8% | 89.5% | 26.9 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/libreoffice__tdf105035_framePrB.docx_diff.png) |
| word | `libreoffice__tdf113182.docx` | `COSMETIC_MINOR` | **87.5%** | 91.8% | 87.5% | 99.9% | 87.2% | 32.5 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/libreoffice__tdf113182.docx_diff.png) |
| word | `libreoffice__tdf113183.docx` | `COSMETIC_MINOR` | **92.0%** | 98.9% | 92.0% | 99.5% | 97.1% | 7.5 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/libreoffice__tdf113183.docx_diff.png) |
| word | `libreoffice__tdf121670_columnsInSectionsOnly.docx` | `COSMETIC_MINOR` | **94.7%** | 94.7% | 99.4% | 99.8% | 94.7% | 13.4 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/libreoffice__tdf121670_columnsInSectionsOnly.docx_diff.png) |
| word | `libreoffice__tdf125881.docx` | `COSMETIC_MINOR` | **90.3%** | 96.5% | 90.3% | 99.9% | 95.8% | 10.6 | 1178x741 | 1178x741 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/libreoffice__tdf125881.docx_diff.png) |
| word | `libreoffice__tdf131260.docx` | `COSMETIC_MINOR` | **91.0%** | 98.5% | 91.0% | 99.4% | 96.7% | 8.5 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/libreoffice__tdf131260.docx_diff.png) |
| word | `libreoffice__tdf132802.docx` | `COSMETIC_MINOR` | **91.5%** | 98.3% | 91.5% | 99.9% | 96.3% | 9.4 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/libreoffice__tdf132802.docx_diff.png) |
| word | `libreoffice__tdf146973_signatureBlock.docx` | `COSMETIC_MINOR` | **92.9%** | 99.4% | 92.9% | 99.8% | 97.2% | 7.1 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/libreoffice__tdf146973_signatureBlock.docx_diff.png) |
| word | `libreoffice__tdf153255.docx` | `COSMETIC_MINOR` | **93.4%** | 99.8% | 93.4% | 99.7% | 97.4% | 6.6 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/libreoffice__tdf153255.docx_diff.png) |
| word | `libreoffice__tdf154751_dualStrikethrough.docx` | `COSMETIC_MINOR` | **94.5%** | 94.5% | 94.5% | 99.6% | 95.9% | 10.5 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/libreoffice__tdf154751_dualStrikethrough.docx_diff.png) |
| word | `libreoffice__tdf43100_tdf120715_cursorOnSpacesOverMargin.docx` | `COSMETIC_MINOR` | **88.8%** | 95.0% | 88.8% | 100.0% | 94.5% | 14.0 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/libreoffice__tdf43100_tdf120715_cursorOnSpacesOverMargin.docx_diff.png) |
| word | `libreoffice__tdf54095_SmartArtThemeTextColor.docx` | `COSMETIC_MINOR` | **94.4%** | 94.6% | 94.4% | 99.1% | 96.1% | 10.0 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/libreoffice__tdf54095_SmartArtThemeTextColor.docx_diff.png) |
| word | `libreoffice__textframe-borders.docx` | `COSMETIC_MINOR` | **90.3%** | 95.1% | 90.3% | 99.3% | 96.2% | 9.7 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/libreoffice__textframe-borders.docx_diff.png) |
| word | `openxml-sdk__Comment066.docx` | `COSMETIC_MINOR` | **85.4%** | 87.4% | 85.4% | 98.4% | 90.6% | 23.9 | 1178x741 | 1178x741 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/openxml-sdk__Comment066.docx_diff.png) |
| word | `openxml-sdk__bullet-complex.docx` | `COSMETIC_MINOR` | **86.9%** | 90.9% | 86.9% | 99.9% | 90.4% | 24.4 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/openxml-sdk__bullet-complex.docx_diff.png) |
| word | `poi__60316.docx` | `COSMETIC_MINOR` | **89.2%** | 94.9% | 89.2% | 99.8% | 94.5% | 14.1 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/poi__60316.docx_diff.png) |
| word | `poi__headerPic.docx` | `COSMETIC_MINOR` | **93.0%** | 99.3% | 93.0% | 99.7% | 97.1% | 7.4 | 1178x767 | 1178x767 | [`diff`](/Users/aitobox/work/aitobox/ATBOffice/screenshots/office_audit_20261112/diff/word/poi__headerPic.docx_diff.png) |

---

## 4. Remediation Action Cards

No active visual rendering defects detected. All evaluated documents meet parity thresholds.

---

## 5. Reference Limitations

These documents differ because the reference renderer cannot draw them correctly. They count
towards the average but are exempt from the single-document bar. Each reason is recorded as
`expectations.reference_limitation` in `tests/docs/expectations.json`.

| App | File | Foreground | Reason |
|---|---|---|---|
| excel | `openxml-sdk__00d63cdd-ee44-4e6a-99af-a7966ffbdda0.xlsx` | 85.5% | The sheet's only drawing is a group (two grpFill rectangles joined by an elbow connector). VibeOffice does not draw groups: ledger/js/drawing.js shapeProps() reads the first child's spPr, grpFill resolves to no fill and the group has no style, so it paints one empty 1px black outline over the whole anchor. ATB draws the filled rectangles and connector as Excel does. |

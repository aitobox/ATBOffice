# ATBOffice vs. VibeOffice Visual Document Rendering Parity Report

> **Generated**: 2026-11-11 22:51:25 UTC  
> **Quality Gate Verdict**: **✅ PASS** (Target: Avg >= 90.0%, Single >= 85.0%)

## 1. Executive Summary

| Metric | Value | Target / Requirement |
|---|---|---|
| **Evaluated Documents** | `24` | 73 Core Supported OOXML |
| **Comparable Documents** | `24` | Size & Region Aligned |
| **Incomparable / Missing** | `0` | 0 Blockers |
| **Average Visual Similarity** | `95.41%` | >= 90.0% |
| **Parity Matches (>=95%)** | `16` | High Fidelity |
| **Cosmetic Minor (85%-95%)** | `8` | Acceptable |
| **Layout Drifts (70%-85%)** | `0` | Needs Polish |
| **Critical Mismatches (<70%)** | `0` | P0/P1 Defects |
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
| word | `libreoffice__A019_min.docx` | `PARITY_MATCH` | **97.4%** | 6.6 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__A019_min.docx_diff.png) |
| word | `libreoffice__fdo52208.docx` | `PARITY_MATCH` | **97.4%** | 6.7 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__fdo52208.docx_diff.png) |
| word | `libreoffice__fdo55381.docx` | `PARITY_MATCH` | **97.4%** | 6.7 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__fdo55381.docx_diff.png) |
| word | `libreoffice__forum-mso-en-4208.docx` | `PARITY_MATCH` | **97.5%** | 6.5 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__forum-mso-en-4208.docx_diff.png) |
| word | `libreoffice__nested-runs.docx` | `PARITY_MATCH` | **97.1%** | 7.4 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__nested-runs.docx_diff.png) |
| word | `libreoffice__sdt-ignored-footer.docx` | `PARITY_MATCH` | **97.4%** | 6.7 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__sdt-ignored-footer.docx_diff.png) |
| word | `libreoffice__strict.docx` | `COSMETIC_MINOR` | **94.5%** | 14.0 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__strict.docx_diff.png) |
| word | `libreoffice__tdf105035_framePrB.docx` | `COSMETIC_MINOR` | **89.5%** | 26.7 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf105035_framePrB.docx_diff.png) |
| word | `libreoffice__tdf113182.docx` | `COSMETIC_MINOR` | **89.1%** | 27.7 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf113182.docx_diff.png) |
| word | `libreoffice__tdf113183.docx` | `PARITY_MATCH` | **97.1%** | 7.4 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf113183.docx_diff.png) |
| word | `libreoffice__tdf121670_columnsInSectionsOnly.docx` | `PARITY_MATCH` | **95.7%** | 11.1 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf121670_columnsInSectionsOnly.docx_diff.png) |
| word | `libreoffice__tdf125881.docx` | `PARITY_MATCH` | **95.8%** | 10.8 | 1178x741 | 1178x741 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf125881.docx_diff.png) |
| word | `libreoffice__tdf131260.docx` | `PARITY_MATCH` | **97.0%** | 7.7 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf131260.docx_diff.png) |
| word | `libreoffice__tdf132802.docx` | `PARITY_MATCH` | **96.5%** | 8.9 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf132802.docx_diff.png) |
| word | `libreoffice__tdf146973_signatureBlock.docx` | `PARITY_MATCH` | **97.3%** | 7.0 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf146973_signatureBlock.docx_diff.png) |
| word | `libreoffice__tdf153255.docx` | `PARITY_MATCH` | **97.3%** | 6.9 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf153255.docx_diff.png) |
| word | `libreoffice__tdf154751_dualStrikethrough.docx` | `PARITY_MATCH` | **96.8%** | 8.1 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf154751_dualStrikethrough.docx_diff.png) |
| word | `libreoffice__tdf43100_tdf120715_cursorOnSpacesOverMargin.docx` | `COSMETIC_MINOR` | **94.1%** | 14.9 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf43100_tdf120715_cursorOnSpacesOverMargin.docx_diff.png) |
| word | `libreoffice__tdf54095_SmartArtThemeTextColor.docx` | `PARITY_MATCH` | **96.7%** | 8.5 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__tdf54095_SmartArtThemeTextColor.docx_diff.png) |
| word | `libreoffice__textframe-borders.docx` | `COSMETIC_MINOR` | **95.0%** | 12.8 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__textframe-borders.docx_diff.png) |
| word | `openxml-sdk__Comment066.docx` | `COSMETIC_MINOR` | **91.0%** | 23.0 | 1178x741 | 1178x741 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/openxml-sdk__Comment066.docx_diff.png) |
| word | `openxml-sdk__bullet-complex.docx` | `COSMETIC_MINOR` | **91.4%** | 21.9 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/openxml-sdk__bullet-complex.docx_diff.png) |
| word | `poi__60316.docx` | `COSMETIC_MINOR` | **94.0%** | 15.4 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/poi__60316.docx_diff.png) |
| word | `poi__headerPic.docx` | `PARITY_MATCH` | **97.0%** | 7.6 | 1178x767 | 1178x767 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/poi__headerPic.docx_diff.png) |

---

## 4. Remediation Action Cards

No active visual rendering defects detected. All evaluated documents meet parity thresholds.

# ATBOffice vs. VibeOffice Visual Document Rendering Parity Report

> **Generated**: 2026-11-11 12:29:03 UTC  
> **Quality Gate Verdict**: **✅ PASS** (Target: Avg >= 90.0%, Single >= 85.0%)

## 1. Executive Summary

| Metric | Value | Target / Requirement |
|---|---|---|
| **Evaluated Documents** | `1` | 73 Core Supported OOXML |
| **Comparable Documents** | `1` | Size & Region Aligned |
| **Incomparable / Missing** | `0` | 0 Blockers |
| **Average Visual Similarity** | `92.33%` | >= 90.0% |
| **Parity Matches (>=95%)** | `0` | High Fidelity |
| **Cosmetic Minor (85%-95%)** | `1` | Acceptable |
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
| powerpoint | `libreoffice__TextFittingComparisonWithMSO_3.pptx` | `COSMETIC_MINOR` | **92.3%** | 19.6 | 982x745 | 982x745 | [`diff`](/Volumes/My Shared Files/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/powerpoint/libreoffice__TextFittingComparisonWithMSO_3.pptx_diff.png) |

---

## 4. Remediation Action Cards

No active visual rendering defects detected. All evaluated documents meet parity thresholds.

# Implementation Plan: Issue #345 - Phase 9 End-to-End Visual Rendering Parity, Corpus Audit, Toolbar Customization and Release Signoff

## Overview
Execute final acceptance and signoff for Phase 9: implement the classic Office 2003 `CustomizeToolbarsDialog` in `src/atboffice/ui/dialogs/customize_toolbars_dialog.py`, enforce strict i18n via `tests/test_phase9_i18n_strict_audit.py`, verify corpus audit (150/150 pass), verify dual-engine visual parity across 73 OOXML documents, implement E2E acceptance tests `tests/test_phase9_acceptance.py`, and regenerate `docs/clone/OFFICE_DOCS_DIFF.md` for release signoff.

---

## Proposed Changes

### 1. `src/atboffice/ui/dialogs/customize_toolbars_dialog.py` & `__init__.py`
- Implement `CustomizeToolbarsDialog(QDialog)`:
  - Tab 1: **Toolbars (`safe_tr("工具栏 (&B)")`)**:
    - List of toolbars (Standard, Formatting, Drawing, Tables and Borders, Reviewing, Picture, WordArt, Header/Footer, Mail Merge, Outlining) with checkboxes.
    - Interactive toolbar visibility toggling and selection tracking.
    - Buttons: New..., Rename..., Delete, Reset...
  - Tab 2: **Commands (`safe_tr("命令 (&C)")`)**:
    - Categories on left (File, Edit, View, Insert, Format, Tools, Table, Window, Help, Drawing).
    - Commands on right with action name, icon/shortcut indicators, and descriptions.
    - Selected command description area at bottom.
  - Tab 3: **Options (`safe_tr("选项 (&O)")`)**:
    - Checkbox: Show Standard and Formatting toolbars on two rows.
    - Checkbox: Always show full menus.
    - Checkbox: Show full menus after a short delay.
    - Checkbox: Large icons.
    - Checkbox: Show ScreenTips on toolbars.
    - Checkbox: Show shortcut keys in ScreenTips.
    - ComboBox: Menu animations (None, Random, Unfold, Slide).
    - Button: Reset menu and toolbar usage data.
  - Tab 4: **Keyboard (`safe_tr("键盘 (&K)")`)**:
    - Categories & Commands mapping.
    - Current keys list and "Press new shortcut key" input (`QKeySequenceEdit`).
    - Buttons: Assign, Remove, Reset All.
  - i18n & dynamic translation:
    - 100% of user-facing strings wrapped with `safe_tr()`.
    - `retranslate_ui()` dynamically updates all tab headers, labels, check boxes, buttons, and combo box items.
- Register `CustomizeToolbarsDialog` in `src/atboffice/ui/dialogs/__init__.py`.

### 2. `tests/test_phase9_i18n_strict_audit.py`
- Comprehensive i18n test suite verifying Phase 9 dialogs and widgets:
  - Tests `CustomizeToolbarsDialog` initialization and `retranslate_ui()`.
  - Verifies no untranslated fallback placeholders or raw English text in non-en contexts.
  - Scans newly added Phase 9 modules for missing `safe_tr()` / `tr()` calls.

### 3. `tests/test_phase9_acceptance.py`
- Complete E2E acceptance test suite:
  - `test_corpus_audit_strict_gate`: runs `scripts/run_corpus_audit.py --strict` to verify 150/150 clean pass.
  - `test_visual_parity_quality_gate`: asserts 73 OOXML documents evaluated, average similarity >= 93.5%, 0 critical mismatches, 0 layout drifts.
  - `test_customize_toolbars_dialog_workflow`: tests opening, tab switching, toolbar toggling, keyboard assignment, and `retranslate_ui()`.
  - `test_phase9_word_quire_acceptance`: verifies horizontal/vertical ruler, dynamic fields, and margin rendering.
  - `test_phase9_excel_ledger_acceptance`: verifies AutoFilter multi-criteria, Paste Special operations, PivotTable aggregation, and external formula cached value rendering.
  - `test_phase9_powerpoint_lectern_acceptance`: verifies SmartArt diagrams and SlideShow ink annotations/laser pointer overlay.
  - `test_phase9_suite_shell_acceptance`: verifies Office Clipboard multi-item stack and Tell Me action execution.

### 4. `docs/clone/OFFICE_DOCS_DIFF.md`
- Run `scripts/run_office_diff.py --all` to regenerate parity deliverable report.
- Confirm Quality Gate Verdict is `✅ PASS` with Phase 9 release signoff notes.

---

## Verification Commands
```bash
# 1. Strict Corpus Audit Gate (150/150 pass)
PYTHONPATH=src conda run -n ATBOffice python scripts/run_corpus_audit.py --strict

# 2. Strict i18n Audit Verification
QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/test_phase9_i18n_strict_audit.py -v

# 3. Phase 9 E2E Acceptance Test Suite
QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/test_phase9_acceptance.py -v

# 4. Full Pytest Regression Suite
QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/
```

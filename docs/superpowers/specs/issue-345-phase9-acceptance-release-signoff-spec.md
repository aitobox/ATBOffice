# Specification: Issue #345 - Phase 9 End-to-End Visual Rendering Parity, Corpus Audit, Toolbar Customization and Release Signoff

## 1. Overview & Objectives
This specification governs the final acceptance gate and release signoff for Phase 9 of ATBOffice (Epic #333).
The primary objectives are:
1. **Classic Office 2003 Toolbar Customization**: Implement `CustomizeToolbarsDialog` in `src/atboffice/ui/dialogs/customize_toolbars_dialog.py` (`Tools ▸ Customize...`) matching the classic 4-tab Office 2003 architecture (Toolbars, Commands, Options, Keyboard) with comprehensive i18n and `retranslate_ui()`.
2. **Strict i18n Audit**: Implement `tests/test_phase9_i18n_strict_audit.py` to audit and guarantee 100% `safe_tr()` / `tr()` coverage across all Phase 9 UI components and dialogs.
3. **Corpus Stability Audit Gate**: Verify `scripts/run_corpus_audit.py --strict` passes 150/150 without timeouts, crashes, or failures.
4. **Dual-Engine Visual Parity Gate**: Verify `scripts/run_office_diff.py --all` across the 73 supported OOXML documents, maintaining global average >= 93.5% with 0 critical mismatches and all documents meeting single-document parity thresholds.
5. **Phase 9 E2E Acceptance Test Suite**: Implement `tests/test_phase9_acceptance.py` validating end-to-end user workflows across Word/Quire, Excel/Ledger, PowerPoint/Lectern, and the Unified Suite Shell.
6. **Release Signoff & Parity Report**: Regenerate `docs/clone/OFFICE_DOCS_DIFF.md` documenting final quality gate status and Phase 9 completion.

---

## 2. Architecture & Detailed Components

### 2.1 Classic Office 2003 `CustomizeToolbarsDialog`
Located at `src/atboffice/ui/dialogs/customize_toolbars_dialog.py` and exported via `src/atboffice/ui/dialogs/__init__.py`.
- **Inheritance & Lifecycle**: `QDialog` modal with standard `Close` button and reset confirmation prompts.
- **Tab 1: Toolbars (`safe_tr("工具栏 (&B)")`)**:
  - `QListWidget` with checkboxes for all suite toolbars:
    - Standard (`safe_tr("常用")`)
    - Formatting (`safe_tr("格式")`)
    - Drawing (`safe_tr("绘图")`)
    - Tables and Borders (`safe_tr("表格和边框")`)
    - Reviewing (`safe_tr("审阅")`)
    - Picture (`safe_tr("图片")`)
    - WordArt (`safe_tr("艺术字")`)
    - Header and Footer (`safe_tr("页眉和页脚")`)
    - Mail Merge (`safe_tr("邮件合并")`)
    - Outlining (`safe_tr("大纲")`)
  - Action Buttons:
    - New... (`safe_tr("新建 (&N)...")`)
    - Rename... (`safe_tr("重命名 (&R)...")`)
    - Delete (`safe_tr("删除 (&D)")`)
    - Reset... (`safe_tr("重置 (&E)...")`)
- **Tab 2: Commands (`safe_tr("命令 (&C)")`)**:
  - Split two-column layout:
    - Left pane: Categories (`QListWidget`): File, Edit, View, Insert, Format, Tools, Table, Window, Help, Drawing.
    - Right pane: Commands (`QListWidget`): Actions available under selected category with icons and action names.
  - Interactive Preview & Description:
    - "Modify Selection" (`safe_tr("更改所选内容 (&M)")`) button and detailed descriptive hint area.
- **Tab 3: Options (`safe_tr("选项 (&O)")`)**:
  - Personalized Menus and Toolbars:
    - Show Standard and Formatting toolbars on two rows (`safe_tr("分两行显示“常用”和“格式”工具栏 (&S)")`)
    - Always show full menus (`safe_tr("始终显示完整菜单 (&M)")`)
    - Show full menus after a short delay (`safe_tr("简短的延时后显示完整菜单 (&U)")`)
  - Other Display Options:
    - Large icons (`safe_tr("大图标 (&L)")`)
    - Show ScreenTips on toolbars (`safe_tr("显示屏幕提示 (&T)")`)
    - Show shortcut keys in ScreenTips (`safe_tr("在屏幕提示中显示快捷键 (&K)")`)
    - Menu animations combo box (`safe_tr("菜单动画效果 (&A):")`): None (`safe_tr("(无)")`), Random (`safe_tr("随机")`), Unfold (`safe_tr("展开")`), Slide (`safe_tr("滑动")`).
- **Tab 4: Keyboard (`safe_tr("键盘 (&K)")`)**:
  - Categories & Commands selector.
  - Current shortcut keys list (`safe_tr("当前快捷键 (&U):")`).
  - Press new shortcut key sequence input (`safe_tr("请按新快捷键 (&N):")`).
  - Assign button (`safe_tr("指定 (&A)")`) & Remove button (`safe_tr("删除 (&R)")`) & Reset All (`safe_tr("全部重置 (&S)")`).
- **Internationalization (i18n)**:
  - 100% of UI strings wrapped with `safe_tr()`.
  - Full implementation of `retranslate_ui()` to handle dynamic runtime locale switches.

### 2.2 Strict i18n Audit Scanner (`tests/test_phase9_i18n_strict_audit.py`)
- Programmatically tests all newly registered dialogs and controls across Phase 9.
- Verifies that `retranslate_ui()` updates all tab labels, checkboxes, buttons, and group titles without raising exceptions or leaving raw placeholder keys.
- Confirms zero hardcoded untranslated Chinese or English text in the UI classes.

### 2.3 Strict Corpus Audit Gate (`scripts/run_corpus_audit.py --strict`)
- Executes strict corpus audit over 150 test documents (73 OOXML, 75 legacy binary, 1 encrypted, 1 corrupt).
- Quality Gate:
  - 150/150 completed without timeout or process crash.
  - 73 supported OOXML documents load with status `ok`.
  - 77 legacy/corrupt/encrypted documents fail safely with graceful status (`unsupported_legacy_format`, `encrypted_document`, `corrupt_archive`) without exceptions.

### 2.4 Visual Parity Gate & Report Regeneration (`scripts/run_office_diff.py --all`)
- Executes visual diff comparison across all 73 supported OOXML documents.
- Verifies average visual similarity >= 93.5%.
- Verifies 0 critical mismatches (< 70%) and 0 layout drifts.
- Regenerates `docs/clone/OFFICE_DOCS_DIFF.md` with final metrics, tables, and Phase 9 Release Signoff status.

### 2.5 End-to-End Acceptance Tests (`tests/test_phase9_acceptance.py`)
- Validates the complete integrated feature set implemented throughout Phase 9:
  1. **Suite Shell**:
     - `CustomizeToolbarsDialog` initialization, tab switching, toggle interactions, and `retranslate_ui()`.
     - Office Clipboard multi-item stack and dynamic paste.
     - Tell Me quick action search and execution.
  2. **Quire (Word)**:
     - Canvas Horizontal & Vertical Ruler measurement units, tab stops, and margin guides.
     - Dynamic fields (Page, NumPages, Date, Time, Author, Title) evaluation.
  3. **Ledger (Excel)**:
     - AutoFilter multi-column criteria evaluation, dropdowns, and row filtering.
     - Paste Special operations (Values, Formulas, Formats, Transpose, Add/Multiply).
     - PivotTable multi-field layout and aggregation.
     - Cached values fallback rendering for external formulas.
  4. **Lectern (PowerPoint)**:
     - SmartArt hierarchy and cycle diagram generation.
     - SlideShow fullscreen real-time ink annotations, laser pointer, and ink retention dialog.

---

## 3. Edge Cases & Safeguards
- **Headless / Offscreen Mode**: All tests must execute cleanly under `QT_QPA_PLATFORM=offscreen`.
- **Dialog Modal Interception**: Any modal dialogs or message boxes opened during automated runs must be mockable or handled non-blockingly.
- **Corpus File Integrity**: No test or script may corrupt or modify files under `tests/docs/`.
- **Zero Regressions**: All 1900+ existing pytest unit and integration tests must pass without regressions.

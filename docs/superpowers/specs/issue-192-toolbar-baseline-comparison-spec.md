# Specification: Issue #192 — [Phase 5] 建立三模块工具栏逐控件对照与截图基线

## 1. Context & Motivation

In Phase 5 of the ATBOffice migration (porting `.vibeoffice` from JavaScript to Python 3.12+ / PySide6), we must establish an authoritative, control-by-control baseline comparison matrix between the original Office 2003 Luna toolbars in `.vibeoffice` and the PySide6 implementation in `ATBOffice` across all three core modules:
- **Quire** (Word Processor — 10 toolbars)
- **Ledger** (Spreadsheet — 8 toolbars)
- **Lectern** (Presentation — 10 toolbars)

This baseline provides the empirical, traceable foundation for subsequent Phase 5 issues (#193, #194, #195, #196, #201) to verify visual, interactive, contextual, and architectural parity without speculation.

## 2. Scope & Target Files

### Source Files Under Audit
- Original JS implementations:
  - `.vibeoffice/public/quire/js/app.js` & `commands.js`
  - `.vibeoffice/public/ledger/js/app.js` & `commands.js`
  - `.vibeoffice/public/lectern/js/app.js` & `commands.js`
  - `.vibeoffice/public/common/ui.js`
  - Reference commit: `32ff53a5da0e75ebac11acdb0251cd3d8c7bf408`
- Target Python implementations:
  - `src/atboffice/ui/shell/quire_toolbars.py`
  - `src/atboffice/ui/shell/ledger_toolbars.py`
  - `src/atboffice/ui/shell/lectern_toolbars.py`
  - `src/atboffice/ui/components/toolbar.py` & `toolbar_buttons.py`
  - Baseline commit: `38664cabd0dcb88dabec91855eb0357dc30f0cdd`

### Output Artifacts
- Comparison Matrix Document: `docs/clone/evidence/phase5/toolbar_baseline_matrix.md`
- Audit Script: `scripts/audit_toolbars_parity.py`
- Screenshot Capture Script: `scripts/capture_atboffice_toolbars.py`
- Captured Visual Evidence: `docs/clone/evidence/phase5/screenshots/`
- Parity Tracking & Diff updates:
  - `docs/clone/CLONE_DIFF.md` (Update [TASK-504])
  - `docs/clone/features.csv`
- Automated Test Suite:
  - `tests/ui/test_toolbar_baseline_parity.py`

## 3. Detailed Technical Requirements

### 3.1 Control-by-Control Audit Dimensions
For every toolbar in Quire, Ledger, and Lectern, the baseline audit records:
1. **Toolbar Identifier**: Canonical ID (e.g. `standard`, `formatting`, `drawing`).
2. **Order / Index**: Exact sequential index of the item within the toolbar.
3. **Item Type**: Regular button, Dropdown button (`tbDrop`), Split button (`tbSplit`), Combobox (Font/Size/Zoom/Style), Color Picker, or Separator.
4. **Action ID / Command**: Command identifier (e.g., `new`, `open`, `bold`, `formatPainter`).
5. **Icon**: Icon resource name and presence check.
6. **Label & Tooltip**: Localized string, tooltip, and accelerator/mnemonic text.
7. **Shortcut**: Default accelerator key (e.g., `Ctrl+N`, `Ctrl+B`, `Ctrl+Z`).
8. **Context & Visibility**: Default visibility state (`true`, `false`, `auto`) and triggering context condition (e.g. table selection, shape selection, image selection).
9. **Implementation Status in ATBOffice**:
   - `WIRED`: Action registered, connected to handler, fully functional.
   - `STUB`: Action registered with docstring/toast fallback (e.g., #194 items).
   - `UI_ONLY`: Visual widget present, handler pending.
   - `MISSING`: Not yet present in target toolbar.

### 3.2 Visual & Screenshots Baseline
1. Reference original screenshots available under `.vibeoffice/screenshots/`:
   - `01_quire/045_toolbar_All_Visible__Full_Toolbars_Dock.png`
   - `02_ledger/038_toolbar_All_Visible__Full_Toolbars_Dock.png`
   - `03_lectern/036_toolbar_All_Visible__Full_Toolbars_Dock.png`
   - Individual pickers, combos, and dropdown palettes.
2. Target ATBOffice screenshots captured at matching conditions:
   - Window size: 1280×800 (standard) and 800×600 (narrow window / overflow testing).
   - Look & Theme: Office 2003 Luna (`luna_2003.py`).
   - All toolbars docked in `TopToolBarArea`.
   - Side-by-side or indexed catalog in `docs/clone/evidence/phase5/screenshots/INDEX.md`.

### 3.3 i18n & Dynamic Language Refresh
- 100% of toolbar controls, tooltips, and drop-down menu items must use `safe_tr()` / `tr()`.
- Validate that `retranslate_ui()` dynamically translates all toolbar titles, action texts, tooltips, and combobox entries across all 7 supported locales: `en`, `zh_CN`, `zh_TW`, `ja`, `fr`, `de`, `es`.

### 3.4 Automated Testing & Verification
- `tests/ui/test_toolbar_baseline_parity.py` validates:
  - Exact count and names of toolbars for all 3 applications.
  - Action registry completeness: every action in the toolbar must be registered in the window's `ActionRegistry`.
  - Non-empty tooltips and valid icons.
  - Clean language switching without missing translations or unhandled exceptions.
  - Docking invariant: all toolbars in `TopToolBarArea`, 0 in `BottomToolBarArea`.

## 4. Edge Cases & Robustness Analysis
- **Missing / Fallback Icons**: Fallback to standard Qt theme icon or text label if custom icon asset is absent, without raising exceptions.
- **Narrow Window Wrapping**: When window width shrinks to 800px, toolbars must cleanly wrap within `TopToolBarArea` or show chevron overflow indicators, never migrating to `BottomToolBarArea`.
- **Context Toolbar Toggling**: When context toolbars (e.g. `tables`, `picture`, `diagram`) become visible or hidden based on document selection, layout recalculation must not throw or cause visual flicker.
- **Dynamic Translation Memory Safety**: Rapid locale switching must not duplicate menu actions or leave dangling action pointers.

# [TASK-712] fix(commands): 清理可见空行为并完善动态本地化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix dead controls, missing handlers, document isolation, and dynamic localization across ActionRegistry, OutlineToolbar, ChartWizardDialog, ScenarioManagerDialog, LedgerOptionsDialog, and HyperlinkDialog, verified by comprehensive GUI tests and 9-locale support.

**Architecture:** Connect previously inert buttons and combos to concrete model-updating methods (`outline_level_changed`, series CRUD, scenario merge, custom lists, screentips); guarantee document mutation occurs only on dialog accept (`OK`), never on cancel; ensure `retranslate_ui()` updates all text across 9 locales without duplicate connections; provide explicit action capability explanation instead of placeholder toast.

**Tech Stack:** Python 3.12+, PySide6 (Qt6), pytest, pytest-qt, JSON catalogs in `src/atboffice/resources/locale/`.

**Spec:** `docs/superpowers/specs/issue-246-fix-visible-commands-spec.md`

## Global Constraints

- Language: Python 3.12+ with complete type hints.
- GUI: PySide6 (Qt6 bindings).
- i18n is mandatory: Wrap 100% of UI strings in `safe_tr()`, implement `retranslate_ui()`, and support all 9 locales: `zh-CN`, `zh-Hant`, `en`, `ja`, `ko`, `fr`, `de`, `es`, `ru`.
- Test verification command: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_visible_commands.py tests/test_i18n_phase6.py -ra`.
- Document safety: Confirm writes to document/sheet model; Cancel does not mutate document; switching documents clears stale references.

---

### Task 1: Wire OutlineToolbar Level Combo and OutlineViewWidget
**Files:**
- Modify: `src/atboffice/modules/writer/views/outline_view.py`
- Test: `tests/gui/test_phase7_visible_commands.py`

**Interfaces:**
- Consumes: `OutlineToolbar`, `OutlineViewWidget`, `Paragraph`, `Document`, `ensure_heading_style`.
- Produces: `OutlineToolbar.outline_level_changed: Signal(int)`, `OutlineViewWidget.set_selected_outline_level(level: int)`.

- [ ] **Step 1: Write failing test for outline level combo and view widget**
- [ ] **Step 2: Run test to confirm failure**
- [ ] **Step 3: Implement signal and handler in `OutlineToolbar` and `set_selected_outline_level` in `OutlineViewWidget`**
- [ ] **Step 4: Run test to verify pass**

---

### Task 2: Implement ChartWizardDialog Series Management and Document Isolation
**Files:**
- Modify: `src/atboffice/modules/spreadsheet/dialogs/chart_wizard.py`
- Test: `tests/gui/test_phase7_visible_commands.py`

**Interfaces:**
- Consumes: `ChartWizardDialog`, `SheetDataModel`, `FloatingObject`.
- Produces: Series add/delete/selection sync in Step 2 Tab 2; `get_chart_spec()["series"]`; `set_sheet_model()`.

- [ ] **Step 1: Write failing test for ChartWizard series add/delete and sheet isolation**
- [ ] **Step 2: Run test to confirm failure**
- [ ] **Step 3: Implement series list management, `btn_add_series`, `btn_del_series`, and `set_sheet_model`**
- [ ] **Step 4: Run test to verify pass**

---

### Task 3: Implement ScenarioManagerDialog Merge and Model Safety
**Files:**
- Modify: `src/atboffice/modules/spreadsheet/dialogs/scenario_manager_dialog.py`
- Test: `tests/gui/test_phase7_visible_commands.py`

**Interfaces:**
- Consumes: `ScenarioManagerDialog`, `SheetDataModel`.
- Produces: `MergeScenariosDialog`, `ScenarioManagerDialog._on_merge()`, `set_sheet_model()`.

- [ ] **Step 1: Write failing test for ScenarioManager merge and cancellation safety**
- [ ] **Step 2: Run test to confirm failure**
- [ ] **Step 3: Implement `MergeScenariosDialog`, wire `btn_merge`, and add `set_sheet_model`**
- [ ] **Step 4: Run test to verify pass**

---

### Task 4: Implement LedgerOptionsDialog Custom Lists and ScreenTips
**Files:**
- Modify: `src/atboffice/modules/spreadsheet/dialogs/options_dialog.py`
- Test: `tests/gui/test_phase7_visible_commands.py`

**Interfaces:**
- Consumes: `LedgerOptionsDialog`, `BUILTIN_CUSTOM_LISTS`.
- Produces: `btn_add_list`, `btn_del_list` slots, `list_custom_lists` selection sync, `chk_show_screentips` in options.

- [ ] **Step 1: Write failing test for custom lists and ScreenTips**
- [ ] **Step 2: Run test to confirm failure**
- [ ] **Step 3: Implement custom lists management, delete restriction for built-ins, and ScreenTips checkbox**
- [ ] **Step 4: Run test to verify pass**

---

### Task 5: Implement HyperlinkDialog ScreenTip Sub-dialog
**Files:**
- Modify: `src/atboffice/modules/writer/dialogs/reference_dialogs.py`
- Test: `tests/gui/test_phase7_visible_commands.py`

**Interfaces:**
- Consumes: `HyperlinkDialog`.
- Produces: `HyperlinkScreenTipDialog`, `btn_tip.clicked` connection, `get_hyperlink_data()["screentip"]`.

- [ ] **Step 1: Write failing test for Hyperlink ScreenTip sub-dialog**
- [ ] **Step 2: Run test to confirm failure**
- [ ] **Step 3: Implement `HyperlinkScreenTipDialog` and wire `btn_tip`**
- [ ] **Step 4: Run test to verify pass**

---

### Task 6: Enhance ActionRegistry Capabilities, Dynamic i18n, and Locale Catalogs
**Files:**
- Modify: `src/atboffice/core/action_registry.py`
- Modify: `src/atboffice/resources/locale/*.json`
- Test: `tests/gui/test_phase7_visible_commands.py`
- Test: `tests/test_i18n_phase6.py`

**Interfaces:**
- Consumes: `ActionRegistry`, `get_i18n_manager()`, `safe_tr()`.
- Produces: Action capability tracking, clean `retranslate_ui()` across 9 locales without duplicate connections, populated locale catalogs.

- [ ] **Step 1: Write failing test for ActionRegistry dynamic i18n and 9-locale catalog coverage**
- [ ] **Step 2: Run test to confirm failure**
- [ ] **Step 3: Update `ActionRegistry` and populate 9-locale JSON files with new translations**
- [ ] **Step 4: Run test to verify pass**

---

### Task 7: Full Verification Gate and `phase7_features.csv` Evidence Update
**Files:**
- Modify: `docs/clone/phase7_features.csv`
- Test: All tests passing

- [ ] **Step 1: Run full verification suite (`test_phase7_visible_commands.py` and `test_i18n_phase6.py`)**
- [ ] **Step 2: Update `phase7_features.csv` with verified status and test reference**

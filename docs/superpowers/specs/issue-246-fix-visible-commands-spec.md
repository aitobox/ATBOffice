# Design Spec: [TASK-712] fix(commands): 清理可见空行为并完善动态本地化

- **Issue**: [#246](https://github.com/aitobox/ATBOffice/issues/246)
- **Parent Epic**: [#234](https://github.com/aitobox/ATBOffice/issues/234)
- **Plan Task**: TASK-712
- **State**: brainstorming / spec approved (90% Autonomous Decision Rule)

---

## 1. Problem Statement & Scope

During the Phase 7 UI/UX fidelity and command audit, several visible controls in dialogs and toolbars were identified as having dead or missing interactions, placeholder fallbacks, or incomplete dynamic localization:

1. **Outline Level Combo (`OutlineToolbar._combo_outline_level`)**:
   `_on_outline_level_changed` was a no-op method without signal emission or document paragraph level modification.
2. **Chart Wizard Series (`ChartWizardDialog` Step 2 Tab 2)**:
   "添加(&A)" (`btn_add_series`) and "删除(&R)" (`btn_del_series`) buttons were not wired; switching series did not update series fields; series list was not exported in `get_chart_spec()`.
3. **Scenario Manager Merge (`ScenarioManagerDialog`)**:
   "合并(&M)..." (`btn_merge`) button was not wired to any slot; no scenario merge dialog existed.
4. **Options Dialog Custom Lists & ScreenTips (`LedgerOptionsDialog`)**:
   "自定义序列" tab had unwired Add (`btn_add_list`) and Delete (`btn_del_list`) buttons, and list selection did not populate entries. ScreenTips option was missing from options export.
5. **Hyperlink ScreenTip (`HyperlinkDialog.btn_tip`)**:
   "屏幕提示(&P)..." button was not connected to any dialog; `get_hyperlink_data` lacked `screentip` support.
6. **ActionRegistry Fallback & Dynamic Localization**:
   Actions without handlers fell back to a generic toast without capability documentation; `retranslate_ui` needed to ensure seamless dynamic locale switching across all 9 supported locales without connection leaks or unhandled Qt exceptions.
7. **Document Isolation on Dialog Confirm/Cancel**:
   Dialogs must mutate models only on accept (`OK`/`Finish`), never on reject (`Cancel`), and must support switching document/sheet references cleanly without stale references.

---

## 2. Architecture & Design Details

### 2.1 OutlineToolbar & OutlineViewWidget
- **Signal**: `outline_level_changed = Signal(int)` (0 = body text, 1..9 = Heading 1..9).
- **Slot in `OutlineToolbar`**: `_on_outline_level_changed` emits `outline_level_changed.emit(idx)`.
- **Method in `OutlineViewWidget`**: `set_selected_outline_level(level: int)`:
  - If `level == 0`: demotes paragraph to body text (`Normal`, outline_level = None).
  - If `level == 1`: promotes paragraph to Heading 1 (`Heading1`, outline_level = 0).
  - If `level in range(2, 10)`: sets style to `f"Heading{level}"` and outline_level to `level - 1`.
  - Reindexes document, updates widget canvas, emits `structure_changed`.
- **Dynamic Localization**: `retranslate_ui()` updates level names ("正文文本", "1 级".."9 级", "所有级别", "显示至 1 级".."显示至 9 级") safely.

### 2.2 ChartWizardDialog Series Management
- **State**: Maintain `self.series_list: list[dict[str, str]]`, tracking `name`, `values`, and `x_values`.
- **List Interaction**:
  - `list_series.currentRowChanged` syncs edits (`edit_series_name`, `edit_series_values`, `edit_series_x`).
  - Editing lines updates the current series in `series_list` and reflects in `list_series` display name.
- **Add / Delete Buttons**:
  - `btn_add_series` appends a new series dictionary, adds item to `list_series`, selects it.
  - `btn_del_series` deletes the current series (guarding minimum 1 series), selects adjacent item.
- **Spec Export**: `get_chart_spec()` returns `"series": self.series_list`.
- **Sheet Model Safety**:
  - Finish adds drawing object to sheet; Cancel leaves `drawings` unchanged.
  - `set_sheet_model(sheet_model)` clears or updates sheet model reference.

### 2.3 ScenarioManagerDialog Merge
- **Merge Dialog**: `MergeScenariosDialog` presents open sheets or source name selection.
- **Handler**: `_on_merge()` displays `MergeScenariosDialog`. On accept, merges non-duplicate scenarios into `self.scenarios`, refreshes `list_scenarios`, and emits `scenarios_updated`.
- **Sheet Model Safety**:
  - Applying scenario writes cell values; canceling does not alter cells.
  - `set_sheet_model(sheet_model)` updates sheet model reference.

### 2.4 LedgerOptionsDialog Custom Lists & ScreenTips
- **Custom Lists Management**:
  - `self.custom_lists: list[list[str]]` initializes with built-in lists + user custom lists.
  - `list_custom_lists.currentRowChanged` populates `edit_list_entries`. If built-in list or row 0 ("新序列"), `btn_del_list` is disabled; if user list, enabled.
  - `btn_add_list` parses lines from `edit_list_entries`, appends new custom list, selects it.
  - `btn_del_list` removes selected user custom list, resets selection to row 0.
- **ScreenTips Checkbox**:
  - `self.chk_show_screentips` in View tab, checked by default.
  - `get_options()` includes `"show_screentips": bool` and `"custom_lists": list`.

### 2.5 HyperlinkDialog ScreenTip
- **Sub-dialog**: `HyperlinkScreenTipDialog` provides `edit_tip: QLineEdit` for "屏幕提示文字(&S):".
- **Handler**: `btn_tip.clicked.connect(self._on_screentip)`. Stores `self.screentip`.
- **Data Export**: `get_hyperlink_data()` returns `"screentip": self.screentip`.

### 2.6 ActionRegistry & Dynamic i18n
- **Capability Explanation**: ActionRegistry supports registering capability status / disabled explanation instead of ambiguous generic toast.
- **Dynamic Localization**: `retranslate_ui()` dynamically re-translates labels and tooltips for all 9 locales (`zh-CN`, `zh-Hant`, `en`, `ja`, `ko`, `fr`, `de`, `es`, `ru`) without duplicating signal bindings.
- **Locale Catalogs**: Ensure all new phrases are populated in `src/atboffice/resources/locale/*.json`.

---

## 3. Verification & Acceptance Criteria
- Full test suite in `tests/gui/test_phase7_visible_commands.py`.
- Directed command passes with exit code 0:
  `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_visible_commands.py tests/test_i18n_phase6.py -ra`
- Update `docs/clone/phase7_features.csv` to record verification evidence.

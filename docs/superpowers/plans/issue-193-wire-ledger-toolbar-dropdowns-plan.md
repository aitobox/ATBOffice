# Implementation Plan: [Issue #193] 接通 Ledger 工具栏下拉及分裂按钮菜单

## Phase 1: Test Cases Definition (TDD Red Phase)
- [ ] File: `tests/ui/test_ledger_toolbar_wiring.py`
  - Test 1: `test_all_dropdown_and_split_actions_registered`: verify all menu items across 8 toolbars exist in `win.action_registry`.
  - Test 2: `test_autosum_dropdown_functions`: trigger `autoSum_average`, `autoSum_count`, `autoSum_max`, `autoSum_min` and check formula/value.
  - Test 3: `test_borders_dropdown_wiring`: trigger `border_top`, `border_left`, `border_right`, `border_thick_box`, `border_bottom_double`, verify cell borders.
  - Test 4: `test_border_line_color_actions`: trigger `border_color_red`, `border_color_blue`, verify cell border color.
  - Test 5: `test_list_toolbar_actions`: trigger `insertRows`, `insertCols`, `autoFilter`, `convertToRange`, verify cell shifts and model state.
  - Test 6: `test_chart_toolbar_type_dropdown`: trigger `chart_type_line`, `chart_type_pie`, verify chart type is applied.
  - Test 7: `test_drawing_z_order_actions`: trigger `bringToFront`, `sendToBack`, verify object layer z-order.
  - Test 8: `test_inapplicable_actions_disabled`: check that `undo_empty`, `redo_empty`, `draw_group`, `draw_ungroup` are disabled (`isEnabled() == False`).
  - Test 9: `test_toolbar_dropdown_retranslate_ui`: switch locale between `zh-CN`, `en`, `ja`, verify menu action texts retranslate properly.

## Phase 2: Component & Infrastructure Enhancements
- [ ] File: `src/atboffice/ui/components/toolbar_buttons.py`
  - Add `_raw_text` and `retranslate_ui(tr_func)` on `OfficeDropDownButton`.
- [ ] File: `src/atboffice/core/action_registry.py`
  - Ensure action registration, lookup, and state methods (`is_enabled`, `is_checked`) are robust and cleanly handled.

## Phase 3: Toolbar Builder Refactoring
- [ ] File: `src/atboffice/ui/shell/ledger_toolbars.py`
  - Refactor `_add_drop` and `_add_split` to register every menu item as a proper `ActionSpec` in `action_registry`.
  - Wire all 8 toolbars' dropdowns and split buttons with exact action IDs and i18n keys.
  - Update `retranslate_ledger_toolbars` to retranslate drop buttons and custom widgets.

## Phase 4: Business Logic & Command Binding
- [ ] File: `src/atboffice/ui/shell/ledger_window.py`
  - Implement `insert_rows`, `insert_columns`, `toggle_auto_filter`, `convert_table_to_range`, `set_chart_type`, `apply_border_color`.
  - Bind all new action IDs in `_bind_action_handlers`.
  - Remove legacy ad-hoc text-matching loop in `_setup_toolbars`.

## Phase 5: Verification & Regression Testing
- [ ] Run `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/ui/test_ledger_toolbar_wiring.py -v`
- [ ] Run full test suite: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`
- [ ] Advance state to `reviewing` and trigger `atb-github-code-reviewer`.

# Implementation Plan: [Phase 2] Ledger 8 套工具栏声明式构建与命令接入

- **Issue**: #100
- **Branch**: `agent/issue-100-ledger-toolbars`
- **Spec**: `docs/superpowers/specs/issue-100-ledger-toolbars-spec.md`

## Proposed Changes

### Task 1: Write TDD Tests (`tests/ui/test_ledger_toolbars.py`)
- Test 1: Verify `LedgerWindow.toolbars` exists with all 8 toolbars (`standard`, `formatting`, `borders`, `auditing`, `reviewing`, `list`, `chart`, `drawing`).
- Test 2: Verify `drawing` toolbar is docked at `Qt.ToolBarArea.BottomToolBarArea`.
- Test 3: Verify `ActionRegistry` integration and core command execution.
- Test 4: Verify special widgets: QComboBox instances (font, size, zoom), ColorPickerButton instances (font, fill, drawing fill), Split buttons, Drop buttons.
- Test 5: Verify contextual toolbar visibility (`is_chart`, `in_table`, manual overrides).
- Test 6: Verify dynamic retranslation with `retranslate_ui()`.

### Task 2: Implement `src/atboffice/ui/shell/ledger_toolbars.py`
- Implement `LedgerToolBarCluster` with 8 builder methods:
  - `_build_standard_toolbar()`
  - `_build_formatting_toolbar()`
  - `_build_borders_toolbar()`
  - `_build_auditing_toolbar()`
  - `_build_reviewing_toolbar()`
  - `_build_list_toolbar()`
  - `_build_chart_toolbar()`
  - `_build_drawing_toolbar()`
- Helper methods for registering actions, split buttons, and drop buttons.
- Export `build_ledger_toolbars()` and `retranslate_ledger_toolbars()`.

### Task 3: Update `src/atboffice/ui/shell/ledger_window.py`
- Instantiate and configure `ActionRegistry(self)`.
- Mount toolbars across `BottomToolBarArea` (drawing) and `TopToolBarArea` (standard, formatting, borders, auditing, reviewing, list, chart).
- Preserve backward-compatible attributes (`toolbar_standard`, `toolbar_formatting`, `act_bold`, `act_italic`, `act_underline`, `btn_font_color`, `btn_fill_color`).
- Implement `set_toolbar_mode` and `update_context_toolbars`.
- Connect selection and grid changes to `update_context_toolbars`.
- Implement `retranslate_ui()`.

### Task 4: Verification & Test Execution
- Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_ledger_toolbars.py -v`
- Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_dedicated_windows.py -v`
- Run full pytest test suite to ensure zero regressions.

### Task 5: State Transition to `reviewing`
- Update state machine to `reviewing` and chain-invoke `atb-github-code-reviewer`.

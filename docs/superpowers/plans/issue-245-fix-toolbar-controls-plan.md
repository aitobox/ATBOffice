# Implementation Plan: Issue #245 (TASK-711) - fix(toolbar): 逐控件校准图标箭头状态与命中区域

## Task 1: Create TDD Test Suite `tests/ui/test_phase7_toolbar_geometry.py`
- Create test file covering:
  1. `test_split_button_hit_testing_separation`: Click main -> action triggered once, menu closed. Click arrow -> menu opened once, action not triggered.
  2. `test_color_picker_hit_testing_and_recent_color`: Click main -> `color_applied` emitted with recent color, popup closed. Click arrow -> popup opened, `color_applied` not emitted directly. Picking a new color updates `current_color`.
  3. `test_toolbar_button_geometry_calibration`: Assert standard button height ~22px (±2px), split button width ~34px (±2px), grip width 7px, separator width 4px.
  4. `test_dynamic_enabled_synchronization`: Disabling action or button updates state and styling correctly.
  5. `test_multi_resolution_and_overflow`: 1440×900 and 1024×768 resolution tests with toolbar overflow handling.
  6. `test_nine_locales_toolbar_retranslate`: Iterate through all 9 supported locales (`zh-CN`, `zh-Hant`, `en`, `ja`, `ko`, `fr`, `de`, `es`, `ru`), verify `retranslate_ui` updates labels, tooltips, and popups without exceptions or truncation.
- Verification: Run test command `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/ui/test_phase7_toolbar_geometry.py -v` (expect red phase).

## Task 2: Enhance Luna QSS Stylesheet (`src/atboffice/ui/styles/luna_2003.py`)
- Add rules for `QToolButton::menu-button`, `QToolButton::menu-arrow`, and `QToolButton::menu-indicator`.
- Suppress default native arrow overlay to eliminate ghosting / double-arrow artifacts.
- Define 12px menu button subcontrol width for consistent hit-testing.
- Verification: Verify QSS contains new subcontrol definitions.

## Task 3: Calibrate `OfficeSplitButton` & `OfficeDropDownButton` (`src/atboffice/ui/components/toolbar_buttons.py`)
- Standardize `sizeHint()` to height 22px, split button width ~34px.
- Calibrate `paintEvent()`: 1px Luna vertical divider and centered 5×3px down-arrow triangle inside the 12px arrow area.
- Enhance `OfficeDropDownButton` with `raw_tip` storage so icon-only buttons can be translated via `retranslate_ui()`.
- Ensure arrow does not clip button text in localized long-string scenarios.
- Verification: Re-run unit tests.

## Task 4: Calibrate `ColorPickerButton` & `ColorPickerPopup` (`src/atboffice/ui/components/color_picker.py`)
- Standardize `sizeHint()` to `QSize(34, 22)`.
- Ensure main click applies `_current_color` (the most recent color); arrow click opens `ColorPickerPopup`.
- Draw 3px colored indicator bar at bottom of the main button area (`SC_ToolButton`).
- Implement `retranslate_ui(tr_func)` on both `ColorPickerButton` and `ColorPickerPopup`.
- Verification: Re-run unit tests.

## Task 5: Align Shell Toolbar Builders (`quire_toolbars.py`, `ledger_toolbars.py`, `lectern_toolbars.py`)
- Pass `raw_tip` to `add_drop_button()` in toolbar builders.
- Update `retranslate_ui()` in each toolbar module to iterate over `ColorPickerButton` instances and call their `retranslate_ui()`.
- Verification: Run `test_toolbar_baseline_parity.py`.

## Task 6: Comprehensive Verification & `phase7_features.csv` Update
- Run required command:
  `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/ui/test_phase7_toolbar_geometry.py tests/gui/test_window_toolbar_docking.py -ra`
- Run existing full regression suite.
- Update rows in `docs/clone/phase7_features.csv` to `verified` with evidence reference.

## Task 7: Transition to Review
- Update state machine to `reviewing`.
- Hand off to `atb-github-code-reviewer`.

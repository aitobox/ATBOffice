# Specification: Issue #245 (TASK-711) - fix(toolbar): 逐控件校准图标箭头状态与命中区域

## 1. Problem Statement & Background
In the ATBOffice Python/PySide6 implementation, the Office 2003 Luna toolbars across Quire (10 toolbars), Ledger (8 toolbars), and Lectern (10 toolbars) require rigorous 1:1 behavioral and visual calibration against `.vibeoffice` (`common/ui.js`, `icons.js`, and `app.js`):
1. **Hit-Testing Separation**:
   - For `OfficeSplitButton`: Clicking the left button body must execute the default action once without opening the dropdown menu; clicking the right arrow area (12px) must display the popup menu once without triggering the default action.
   - For `ColorPickerButton`: Clicking the main button body must apply the most recent color once; clicking the dropdown arrow must open the color palette popup once.
2. **Visual & State Hardening**:
   - Prevent duplicate arrow rendering / ghosting (自绘与原生绘制叠加). In QSS, suppress default Qt arrow (`QToolButton::menu-arrow { image: none; }`) while precisely styling `QToolButton::menu-button { width: 12px; border: none; }` and rendering the crisp Luna down-arrow triangle and 1px vertical divider.
   - Clean transitions for hover, pressed, checked, and disabled states without black boxes or pixel clipping.
   - Dynamic `setEnabled()` synchronization: toggling an action's enabled status immediately updates the button state.
3. **Geometry & Multi-Resolution / Layout Adaptation**:
   - Baseline geometry: Standard icon button width 22–24px, split button width 33–36px, height 22px (deviation ≤ 2 logical pixels). Dotted grip width 7px, separator width 4px.
   - Responsive operation under 1440×900 and 1024×768 (overflow) resolutions at DPR 1 and DPR 2.
4. **Localization (9 Locales)**:
   - Full support for `zh-CN`, `zh-Hant`, `en`, `ja`, `ko`, `fr`, `de`, `es`, `ru` with dynamic `retranslate_ui()`.
   - Prevent text truncation in dropdown buttons with text and retranslate all tooltips and popup options.

---

## 2. Technical Architecture & Component Design

### 2.1 `src/atboffice/ui/components/toolbar_buttons.py`
- **`OfficeSplitButton`**:
  - `sizeHint()` calibrated to `QSize(max(hint.width(), 34), 22)`.
  - Override `mousePressEvent` / `mouseReleaseEvent` to ensure strict separation between main button action and menu popup.
  - In `paintEvent`, use subcontrol rect `SC_ToolButtonMenu` (12px width from QSS) to draw the Luna vertical divider line and centered 5×3px down-arrow triangle without overlapping native graphics.
  - Implement `retranslate_ui(tr_func)` for localized mnemonic text and tooltips.
- **`OfficeDropDownButton`**:
  - Accepts `text`, `icon`, `menu`, and `tooltip` (`raw_tip`).
  - Calibrate `sizeHint()` to include adequate padding (12px on right) so text/icons never collide with the dropdown arrow.
  - In `retranslate_ui()`, retranslate both `self._raw_text` and `self._raw_tip`.

### 2.2 `src/atboffice/ui/components/color_picker.py`
- **`ColorPickerButton`**:
  - Inherits from `OfficeSplitButton` (or shares its geometry and hit-testing logic).
  - Main button click applies `_current_color` (the most recently selected color).
  - Arrow click displays `ColorPickerPopup`.
  - Draw the 3px colored indicator bar at the bottom of the main button area (`SC_ToolButton`).
  - Calibrate `sizeHint()` to `QSize(34, 22)`.
  - Implement `retranslate_ui(tr_func)` to update tooltips and popup buttons.
- **`ColorPickerPopup`**:
  - Implement `retranslate_ui(tr_func)` to retranslate "无填充颜色", "无线条颜色", "自动", "其他颜色...", and swatch tooltips across all 9 locales.

### 2.3 `src/atboffice/ui/styles/luna_2003.py`
- Add dedicated QSS rules for `QToolButton::menu-button` and `QToolButton::menu-arrow`:
  ```css
  QToolBar QToolButton[popupMode="1"] {
      padding-right: 12px;
  }
  QToolBar QToolButton::menu-button {
      border: none;
      background: transparent;
      width: 12px;
  }
  QToolBar QToolButton::menu-arrow {
      image: none;
      width: 0px;
      height: 0px;
  }
  QToolBar QToolButton::menu-indicator {
      image: none;
      width: 0px;
      height: 0px;
  }
  ```
- This guarantees uniform subcontrol sizing and prevents Qt's style engine from drawing a duplicate arrow underneath the custom painter.

### 2.4 Toolbar Assemblers (`quire_toolbars.py`, `ledger_toolbars.py`, `lectern_toolbars.py`)
- Pass `raw_tip` to `add_drop_button()` so icon-only dropdown buttons preserve their translation key during runtime language switching.
- Ensure all color picker buttons are tracked and refreshed during `retranslate_ui()`.

---

## 3. Verification & Acceptance Criteria
- Unit & GUI test suite: `tests/ui/test_phase7_toolbar_geometry.py` (new) and existing `tests/gui/test_window_toolbar_docking.py`.
- All tests pass with zero regressions.
- Update `docs/clone/phase7_features.csv` entries to `clone: yes`, `verification_status: verified`.

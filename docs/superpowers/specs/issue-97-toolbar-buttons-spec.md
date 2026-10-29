# Design Specification: Office 2003 Toolbar Buttons (OfficeSplitButton & OfficeDropDownButton)

## 1. Overview & Context
- **Issue**: #97 ([Phase 2] 复杂工具栏微件开发 (OfficeSplitButton 与 OfficeDropDownButton))
- **Epic**: #96 (ATBOffice 二期工程：1:1 完整全量移植与核心架构补完)
- **Goal**: Implement classic Office 2003 Luna-style complex toolbar buttons:
  1. `OfficeSplitButton`: A two-part split button where the primary action area triggers a default `QAction`, and the right arrow area opens a drop-down `QMenu`. Features the classic vertical separator divider between the action and arrow.
  2. `OfficeDropDownButton`: A unified drop-down button where clicking anywhere triggers the attached `QMenu`, featuring an integrated drop-down arrow and text/icon.
  3. Integrated toolbar methods on `OfficeToolBar`: `add_split_action(action, menu)` and `add_drop_button(text, icon, menu)`.

## 2. Requirements & Acceptance Criteria
- [x] `OfficeSplitButton(QToolButton)`:
  - Supports `MenuButtonPopup` mode.
  - Left area executes default action (or emits clicked).
  - Right area (arrow) shows drop-down menu.
  - Draws classic Office 2003 vertical separator line between main action and arrow.
  - Respects enable/disable state of `defaultAction`.
- [x] `OfficeDropDownButton(QToolButton)`:
  - Supports `InstantPopup` mode.
  - Clicking any area displays attached `QMenu`.
  - Displays icon, optional text, and downward arrow indicator.
- [x] Luna 2003 Visual Styling:
  - Follows Office 2003 Luna Blue / Silver color palette tokens.
  - Clean hover and pressed feedback for both button areas.
  - Standard button height (~22px - 24px).
- [x] Integration with `OfficeToolBar`:
  - `OfficeToolBar.add_split_action(action: QAction, menu: QMenu) -> OfficeSplitButton`
  - `OfficeToolBar.add_drop_button(text: str, icon: QIcon | None, menu: QMenu) -> OfficeDropDownButton`
- [x] i18n & Accessibility:
  - Uses `safe_tr()` for labels and tooltips.
  - Supports mnemonics via `format_mnemonic()`.
  - Accessible names and tooltips provided.
- [x] Comprehensive Test Suite:
  - Unit tests in `tests/ui/test_toolbar_buttons.py` covering clicks, popups, split behavior, disabled states, and toolbar integration.

## 3. Architecture & Class Design

### 3.1 `OfficeSplitButton`
```python
class OfficeSplitButton(QToolButton):
    def __init__(
        self,
        action: QAction | None = None,
        menu: QMenu | None = None,
        parent: QWidget | None = None,
    ) -> None: ...
```
- Base: `QToolButton`.
- PopupMode: `QToolButton.ToolButtonPopupMode.MenuButtonPopup`.
- Custom Paint:
  - Handles subcontrol rendering for `SC_ToolButton` (main action) and `SC_ToolButtonMenu` (dropdown arrow).
  - Draws a 1px separator line between the two subcontrols using Luna border tokens when hovered, or a subtle 3D divider.
  - Draws downward triangle in the arrow region.

### 3.2 `OfficeDropDownButton`
```python
class OfficeDropDownButton(QToolButton):
    def __init__(
        self,
        text: str = "",
        icon: QIcon | None = None,
        menu: QMenu | None = None,
        parent: QWidget | None = None,
    ) -> None: ...
```
- Base: `QToolButton`.
- PopupMode: `QToolButton.ToolButtonPopupMode.InstantPopup`.
- Formats mnemonic via `format_mnemonic()`.
- Automatically configures tooltips, icons, and menus.

### 3.3 `OfficeToolBar` Extensions
- In `src/atboffice/ui/components/toolbar.py`:
  - Import `OfficeSplitButton` and `OfficeDropDownButton`.
  - Add helper factory methods returning the created buttons.

## 4. Verification Plan
- Unit tests in `tests/ui/test_toolbar_buttons.py`
  - Test split button: clicking main button triggers action; clicking arrow triggers popup.
  - Test dropdown button: clicking anywhere triggers popup.
  - Test disabling action disables split button.
  - Test toolbar factory methods add buttons to toolbar properly.
- Run tests: `PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_toolbar_buttons.py -v`

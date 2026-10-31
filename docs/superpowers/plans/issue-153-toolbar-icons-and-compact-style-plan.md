# Implementation Plan: Toolbar 16×16 Vector Icons and Compact Style

- **Issue**: #153 ([Phase 4] 工具栏全量动作绑定 16×16 图标并启用 ToolButtonIconOnly 紧凑样式)
- **Spec**: `docs/superpowers/specs/issue-153-toolbar-icons-and-compact-style-spec.md`
- **Feature Branch**: `agent/issue-153-toolbar-icons-and-compact-style`

---

## Task 1: Write GUI Tests (TDD - Red Phase)
- **File**: `tests/gui/test_toolbars_icons.py`
- **Details**:
  - Test `OfficeToolBar` initializes with `ToolButtonIconOnly` and `QSize(16, 16)`.
  - Test `QuireToolBarCluster`: Verify toolbars standard, formatting, tables, reviewing, outlining, headerFooter, drawing, mailMerge, picture, wordart have icons attached to actions.
  - Test `LedgerToolBarCluster`: Verify standard, formatting, borders, auditing, reviewing, list, chart, drawing toolbars have icons attached.
  - Test `LecternToolBarCluster`: Verify standard, formatting, sorter, master, outlining, diagram, tables, picture, wordart, drawing toolbars have icons attached.
  - Test `ColorPickerButton` initializes with 16×16 icon and `MenuButtonPopup`.
  - Test that buttons in `OfficeToolBar` have accessible tooltips even when icon-only.
- **Verification Command**:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_toolbars_icons.py -v
  ```

---

## Task 2: Implement Component Style & Sizing Enhancements
- **Files**:
  - `src/atboffice/ui/components/toolbar.py`
  - `src/atboffice/ui/components/toolbar_buttons.py`
  - `src/atboffice/ui/components/color_picker.py`
- **Details**:
  - Set `self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)` and `self.setIconSize(QSize(16, 16))` in `OfficeToolBar.__init__`.
  - Ensure `OfficeSplitButton` and `OfficeDropDownButton` configure `setIconSize(QSize(16, 16))` and handle `ToolButtonIconOnly` vs `ToolButtonTextOnly` appropriately.
  - In `ColorPickerButton`, set icon via `get_office_icon("fontColor"|"highlight"|"fillColor")` and size to 16×16.

---

## Task 3: Wire Vector Icons in Quire, Ledger, and Lectern Toolbars
- **Files**:
  - `src/atboffice/ui/shell/quire_toolbars.py`
  - `src/atboffice/ui/shell/ledger_toolbars.py`
  - `src/atboffice/ui/shell/lectern_toolbars.py`
- **Details**:
  - Define unified icon alias mapping table (e.g., `sendMail -> mail`, `printPreview -> preview`, `spelling -> spell`, etc.).
  - Update `_reg_act`, `_add`, `_add_split` to resolve and attach `QIcon` from `get_office_icon(icon_name)`.
  - Update `_add_drop` to accept `icon` parameter and attach 16×16 Luna icons for dropdowns where applicable.

---

## Task 4: Verify Unit & GUI Tests Pass (TDD - Green Phase)
- **Command**:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_toolbars_icons.py -v
  ```
- **Expected Outcome**: All toolbar icon tests pass cleanly.

---

## Task 5: Full Regression & Code Style Check
- **Commands**:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice ruff check .
  PYTHONPATH=src conda run -n ATBOffice pytest tests/ -q
  ```
- **Expected Outcome**: Zero lint errors, 100% test pass.

---

## Task 6: Transition to Review
- Update `.github-agent-state.yml` to `reviewing`.
- Hand off execution to `atb-github-code-reviewer`.

# Specification: Toolbar 16×16 Vector Icons Binding and ToolButtonIconOnly Compact Style

- **Issue**: #153 ([Phase 4] 工具栏全量动作绑定 16×16 图标并启用 ToolButtonIconOnly 紧凑样式)
- **Parent Epic**: #151 (Phase 4)
- **Status**: In-Progress
- **Feature Branch**: `agent/issue-153-toolbar-icons-and-compact-style`
- **Target Files**:
  - `src/atboffice/ui/components/toolbar.py`
  - `src/atboffice/ui/components/toolbar_buttons.py`
  - `src/atboffice/ui/components/color_picker.py`
  - `src/atboffice/ui/shell/quire_toolbars.py`
  - `src/atboffice/ui/shell/ledger_toolbars.py`
  - `src/atboffice/ui/shell/lectern_toolbars.py`
  - `tests/gui/test_toolbars_icons.py`

---

## 1. Background & Objectives
In previous versions, `OfficeToolBar` did not set `ToolButtonIconOnly`, and the action registration in `quire_toolbars.py`, `ledger_toolbars.py`, and `lectern_toolbars.py` only provided text without attaching icons. Consequently, toolbar buttons rendered with large Chinese/English labels, causing immense toolbar clutter, wrapping, and severe aesthetic divergence from original Office 2003 / VibeOffice (which uses 16×16 Luna icons with 22×22 compact buttons and text reserved for tooltips).

Now that Issue #152 has completed the 16×16 Luna vector icon engine (`icons.py`, providing 346 icons), this task connects all toolbar actions to their respective vector icons, enforces `ToolButtonIconOnly` on all toolbars, and ensures full visual and functional parity.

---

## 2. Requirements & Architecture

### 2.1 OfficeToolBar Compact Sizing & Style
In `src/atboffice/ui/components/toolbar.py`:
- In `OfficeToolBar.__init__`:
  - Enforce `self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)`.
  - Enforce `self.setIconSize(QSize(16, 16))`.
  - Ensure grip handle, separators, and buttons fit cleanly within 22–26px toolbar height.

### 2.2 SplitButton and DropDownButton Enhancements
In `src/atboffice/ui/components/toolbar_buttons.py`:
- `OfficeSplitButton`:
  - Adhere to `setIconSize(QSize(16, 16))`.
  - Ensure main button displays the action's icon (16×16) with tooltip.
- `OfficeDropDownButton`:
  - When `icon` is provided and `text` is empty: set `ToolButtonIconOnly`.
  - When `text` is provided and `icon` is None: set `ToolButtonTextOnly` (e.g. "绘图(R) ▾", "自选图形(U) ▾").
  - When both are provided: set `ToolButtonTextBesideIcon`.

### 2.3 ColorPickerButton Icons
In `src/atboffice/ui/components/color_picker.py`:
- In `ColorPickerButton.__init__`:
  - Bind corresponding 16×16 Luna icon (`fontColor`, `highlight`, or `fillColor`) via `get_office_icon`.
  - Set `setIconSize(QSize(16, 16))`.

### 2.4 Quire, Ledger, and Lectern Toolbar Clusters
In `quire_toolbars.py`, `ledger_toolbars.py`, and `lectern_toolbars.py`:
- Update `_reg_act`, `_add`, `_add_split`, `_add_drop` to accept `icon: QIcon | str | None = None`.
- Provide an automatic action-to-icon resolution dictionary covering all standard command IDs (e.g., `sendMail -> mail`, `printPreview -> preview`, `spelling -> spell`, etc.). If `aid` is in `icons.py`, use it directly; otherwise use the alias mapping.
- For drop-down buttons (`_add_drop`), pass the appropriate icon where original VibeOffice used an icon (e.g. `table`, `columns`, `lineSpacing`, `chart`, etc.).
- Maintain 100% i18n wrapping with `safe_tr()` for labels, tooltips, and menu items.

---

## 3. Edge Cases & Error Handling
1. **Unknown Icon Key**:
   - If an action ID has no matching icon, `get_office_icon()` returns `QIcon()`. Qt handles null icons gracefully by falling back to text or blank space without throwing an exception.
2. **Accessibility & Screen Readers**:
   - Tooltips, status tips, and accessible names must retain the full text label and shortcut (e.g., `新建空白文档 (Ctrl+N)`), guaranteeing zero loss of usability when text is hidden from the button face.
3. **Dynamic Re-translation**:
   - `retranslate_ui` in `ActionRegistry` and the toolbar clusters must preserve icon bindings while updating tooltips and menu items.

---

## 4. Verification Plan
1. Unit & GUI Tests: `tests/gui/test_toolbars_icons.py`
   - Test `OfficeToolBar` has `toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly`.
   - Test `OfficeToolBar` has `iconSize() == QSize(16, 16)`.
   - Test Quire (10 toolbars), Ledger (8 toolbars), and Lectern (10 toolbars) have icons bound to their core actions (`new`, `open`, `save`, `cut`, `copy`, `paste`, `undo`, `redo`, `bold`, `italic`, `underline`, `alignLeft`, etc.).
   - Test `ColorPickerButton` instances load valid icons.
   - Test tooltips are non-empty on all icon-only buttons.
2. Full repository regression check: `pytest tests/` (all 1150+ tests pass).

# Office 2003 Toolbar Buttons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `OfficeSplitButton` and `OfficeDropDownButton` with classic Office 2003 Luna styling and integrate them into `OfficeToolBar`.

**Architecture:** Extend `QToolButton` with `MenuButtonPopup` and `InstantPopup` modes, customized Luna styling/drawing (divider line, down arrow), full mnemonic and `safe_tr` i18n support, and toolbar helper methods.

**Tech Stack:** Python 3.12+, PySide6 (Qt6), pytest-qt.

**Spec:** `docs/superpowers/specs/issue-97-toolbar-buttons-spec.md`

## Global Constraints
- Python 3.12+ with complete type hints
- Fusion style with Luna 2003 styling tokens
- Mandatory i18n via `safe_tr()` and mnemonic handling via `format_mnemonic()`
- Unit tests run with `PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_toolbar_buttons.py -v`

---

### Task 1: Implement `OfficeSplitButton` and `OfficeDropDownButton`

**Files:**
- Create: `src/atboffice/ui/components/toolbar_buttons.py`
- Test: `tests/ui/test_toolbar_buttons.py`

**Interfaces:**
- Produces:
  - `class OfficeSplitButton(QToolButton)`
    - `__init__(self, action: QAction | None = None, menu: QMenu | None = None, parent: QWidget | None = None)`
  - `class OfficeDropDownButton(QToolButton)`
    - `__init__(self, text: str = "", icon: QIcon | None = None, menu: QMenu | None = None, parent: QWidget | None = None)`

- [ ] **Step 1: Write the failing tests for `OfficeSplitButton` and `OfficeDropDownButton`**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `OfficeSplitButton` and `OfficeDropDownButton` in `src/atboffice/ui/components/toolbar_buttons.py`**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit progress**

---

### Task 2: Extend `OfficeToolBar` with Split and DropDown Action Methods

**Files:**
- Modify: `src/atboffice/ui/components/toolbar.py`
- Test: `tests/ui/test_toolbar_buttons.py`

**Interfaces:**
- Produces:
  - `OfficeToolBar.add_split_action(action: QAction, menu: QMenu) -> OfficeSplitButton`
  - `OfficeToolBar.add_drop_button(text: str, icon: QIcon | None, menu: QMenu) -> OfficeDropDownButton`

- [ ] **Step 1: Add toolbar integration tests**
- [ ] **Step 2: Implement methods in `src/atboffice/ui/components/toolbar.py`**
- [ ] **Step 3: Run tests to verify they pass**
- [ ] **Step 4: Commit progress**

---

### Task 3: Comprehensive Test Suite & Edge Case Coverage

**Files:**
- Modify: `tests/ui/test_toolbar_buttons.py`

- [ ] **Step 1: Add tests for disabled state, dynamic menu assignment, and keyboard/mouse interaction**
- [ ] **Step 2: Run full test suite to guarantee 100% pass**
- [ ] **Step 3: Commit progress**

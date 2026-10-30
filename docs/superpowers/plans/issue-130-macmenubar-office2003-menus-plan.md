# Implementation Plan: Issue #130 — 扩展 MacMenuBar 补全 Office 2003 完整菜单体系

## Overview
This plan implements the comprehensive Office 2003 9-menu bar system in `src/atboffice/ui/shell/mac_menu.py`, connects it to `ActionRegistry` for seamless two-way state synchronization with toolbars, supports dynamic application-type menu switching (`Table` / `Data` / `Slide Show`), and provides thorough TDD test coverage in `tests/ui/test_mac_menu.py`.

---

## Task 1: TDD Test Suite Creation (`tests/ui/test_mac_menu.py`)
- **Files**: `tests/ui/test_mac_menu.py`
- **Actions**:
  1. Write tests for 9-menu structure on `QuireWindow`, `LedgerWindow`, and `LecternWindow`.
  2. Write tests for dynamic `set_app_type` menu switching between `quire`, `ledger`, `lectern`, and `generic`.
  3. Write tests for `ActionRegistry` integration: verifying shared `QAction` instance between `MacMenuBar` and toolbars/window registry, confirming that `action_registry.set_enabled()` and `set_checked()` mutate the menu action immediately.
  4. Write tests for `retranslate_ui()` ensuring all menu titles and actions receive localized strings.
  5. Run `pytest tests/ui/test_mac_menu.py` to confirm failure (Red phase).

## Task 2: Implementation of 9-Menu Office 2003 Bar in `mac_menu.py`
- **Files**: `src/atboffice/ui/shell/mac_menu.py`
- **Actions**:
  1. Add `ActionRegistry` integration to `MacMenuBar.__init__`:
     - Inspect `getattr(parent, "action_registry", None)`; if present use it, otherwise create `ActionRegistry(self)`.
     - Implement `_reg_act(aid, alias, label, tip, shortcut, checkable, checked, handler)` helper to register into `ActionRegistry` and populate `self.action_map` under both primary ID and alias.
  2. Implement complete 9-menu structure:
     - `file`: New, Open, Save, Save As, Print, Print Preview, Close.
     - `edit`: Undo, Redo, Cut, Copy, Paste, Select All, Find, Replace, Format Cells (Ledger only).
     - `view`: Fullscreen, Zoom In, Zoom Out, Zoom Reset, Theme sub-menu (Luna Blue, Luna Silver).
     - `insert`: Page Break, Page Numbers, Date & Time, Symbol, Picture, AutoShapes, Hyperlink.
     - `format`: Font, Paragraph, Bullets, Numbering, Borders & Shading, Tabs, Styles & Formatting.
     - `tools`: Spelling & Grammar, Word Count, Language, Options.
     - `table` (Quire): Draw Table, Insert Table, Delete, Select, Merge Cells, Split Cells, Table Properties.
     - `data` (Ledger): Sort Ascending, Sort Descending, Filter, Validation, Subtotals, PivotTable.
     - `slideshow` (Lectern): View Show (F5), From Current Slide (Shift+F5), Set Up Show, Record Narration, Rehearse Timings, Slide Transition.
     - `window`: Minimize, Zoom, Bring All.
     - `help`: ATBOffice Help, About ATBOffice.
  3. Implement dynamic 7th menu switching via `set_app_type(app_type)`:
     - Keep track of active app-specific menu.
     - Insert before `Window` menu using `insertMenu(self.menu_map["window"].menuAction(), new_menu)`.
  4. Update `retranslate_ui()` with 100% `safe_tr()` localization on all menus and action labels/tooltips.
  5. Bind window callbacks in `_bind_window_slots(window)` for common slots.

## Task 3: Verification & Regression Testing
- **Actions**:
  1. Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_mac_menu.py -v` (Green phase).
  2. Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_mac_shell.py -v` to ensure backward compatibility.
  3. Run repository-wide test suite: `PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/` and unit tests.

## Task 4: Code Review and PR Handoff
- Advance state to `reviewing` and trigger `atb-github-code-reviewer`.

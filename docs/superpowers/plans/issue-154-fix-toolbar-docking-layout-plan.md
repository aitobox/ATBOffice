# Fix Application Window Toolbar Docking Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct toolbar docking layout across Quire, Ledger, and Lectern windows by eliminating all `BottomToolBarArea` attachments and structuring command bars in top rows.

**Architecture:** Relocate `drawing` and contextual toolbars from `BottomToolBarArea` to `TopToolBarArea` with logical line breaks (`addToolBarBreak`), ensuring the footer area is completely freed for document status and native controls (e.g., sheet tab bar in Ledger).

**Tech Stack:** Python 3.12, PySide6 (Qt6), pytest, pytest-qt.

**Spec:** `docs/superpowers/specs/issue-154-fix-toolbar-docking-layout-spec.md`

## Global Constraints
- Target branch is `main`.
- All UI text must continue using `safe_tr()`.
- Zero toolbars in `Qt.ToolBarArea.BottomToolBarArea`.
- All tests must pass cleanly.

---

### Task 1: Correct Toolbar Docking in QuireWindow

**Files:**
- Modify: `src/atboffice/ui/shell/quire_window.py:250-275`
- Modify: `tests/ui/test_quire_toolbars.py:40-47`

**Interfaces:**
- Consumes: `build_quire_toolbars`, `OfficeToolBar`, `Qt.ToolBarArea.TopToolBarArea`
- Produces: `QuireWindow._setup_toolbars` docking all toolbars in `TopToolBarArea`

- [ ] **Step 1: Update unit test to assert TopToolBarArea**
  Update `test_drawing_toolbar_docked_at_bottom` in `tests/ui/test_quire_toolbars.py` to `test_drawing_toolbar_docked_at_top` asserting `win.toolBarArea(drawing_tb) == Qt.ToolBarArea.TopToolBarArea`.

- [ ] **Step 2: Run test to verify failure**
  Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_quire_toolbars.py -k test_drawing_toolbar_docked_at_top -v`
  Expected: FAIL with `assert BottomToolBarArea == TopToolBarArea`

- [ ] **Step 3: Update QuireWindow toolbar docking**
  In `src/atboffice/ui/shell/quire_window.py`, remove `BottomToolBarArea` docking and organize rows using `addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)`:
  - Row 1: `standard`
  - Row 2: `formatting`
  - Row 3: `drawing` and other toolbars.

- [ ] **Step 4: Run test to verify pass**
  Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_quire_toolbars.py -v`
  Expected: PASS all tests.

- [ ] **Step 5: Commit changes**
  Commit: `git commit -am "fix(quire): dock drawing toolbar in top row and eliminate bottom footer"`

---

### Task 2: Correct Toolbar Docking in LedgerWindow

**Files:**
- Modify: `src/atboffice/ui/shell/ledger_window.py:260-280`
- Modify: `tests/ui/test_ledger_toolbars.py:38-46`

**Interfaces:**
- Consumes: `build_ledger_toolbars`, `OfficeToolBar`, `Qt.ToolBarArea.TopToolBarArea`
- Produces: `LedgerWindow._setup_toolbars` docking all toolbars in `TopToolBarArea`

- [ ] **Step 1: Update unit test to assert TopToolBarArea**
  Update `test_drawing_toolbar_docked_at_bottom` in `tests/ui/test_ledger_toolbars.py` to `test_drawing_toolbar_docked_at_top` asserting `win.toolBarArea(drawing_tb) == Qt.ToolBarArea.TopToolBarArea`.

- [ ] **Step 2: Run test to verify failure**
  Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_ledger_toolbars.py -k test_drawing_toolbar_docked_at_top -v`
  Expected: FAIL with `assert BottomToolBarArea == TopToolBarArea`

- [ ] **Step 3: Update LedgerWindow toolbar docking**
  In `src/atboffice/ui/shell/ledger_window.py`, remove `BottomToolBarArea` docking and organize rows:
  - Row 1: `standard`
  - Row 2: `formatting`
  - Row 3: `drawing` and other toolbars.

- [ ] **Step 4: Run test to verify pass**
  Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_ledger_toolbars.py -v`
  Expected: PASS all tests.

- [ ] **Step 5: Commit changes**
  Commit: `git commit -am "fix(ledger): dock drawing toolbar in top row and preserve clean bottom tab bar"`

---

### Task 3: Correct Toolbar Docking in LecternWindow

**Files:**
- Modify: `src/atboffice/ui/shell/lectern_window.py:495-520`
- Modify: `tests/ui/test_lectern_toolbars.py:40-48`

**Interfaces:**
- Consumes: `build_lectern_toolbars`, `OfficeToolBar`, `Qt.ToolBarArea.TopToolBarArea`
- Produces: `LecternWindow._setup_toolbars` docking all toolbars in `TopToolBarArea`

- [ ] **Step 1: Update unit test to assert TopToolBarArea**
  Update `test_drawing_toolbar_docked_at_bottom` in `tests/ui/test_lectern_toolbars.py` to `test_drawing_toolbar_docked_at_top` asserting `win.toolBarArea(drawing_tb) == Qt.ToolBarArea.TopToolBarArea`.

- [ ] **Step 2: Run test to verify failure**
  Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_lectern_toolbars.py -k test_drawing_toolbar_docked_at_top -v`
  Expected: FAIL with `assert BottomToolBarArea == TopToolBarArea`

- [ ] **Step 3: Update LecternWindow toolbar docking**
  In `src/atboffice/ui/shell/lectern_window.py`, remove `BottomToolBarArea` docking and organize rows:
  - Row 1: `standard`
  - Row 2: `formatting`
  - Row 3: `drawing` and presentation toolbars.

- [ ] **Step 4: Run test to verify pass**
  Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_lectern_toolbars.py -v`
  Expected: PASS all tests.

- [ ] **Step 5: Commit changes**
  Commit: `git commit -am "fix(lectern): dock drawing toolbar in top row and keep slide viewport clean"`

---

### Task 4: Implement Comprehensive Window Toolbar Docking GUI Regression Suite

**Files:**
- Create: `tests/gui/test_window_toolbar_docking.py`

**Interfaces:**
- Tests `QuireWindow`, `LedgerWindow`, `LecternWindow`
- Asserts that no toolbar resides in `BottomToolBarArea` across all 3 windows.
- Asserts that all toolbars belong to `TopToolBarArea`.
- Asserts that bottom space contains only status bar and native bottom widgets.

- [ ] **Step 1: Write GUI regression test file**
  Create `tests/gui/test_window_toolbar_docking.py` with tests for each window.

- [ ] **Step 2: Run test to verify pass**
  Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_window_toolbar_docking.py -v`
  Expected: PASS

- [ ] **Step 3: Commit changes**
  Commit: `git add tests/gui/test_window_toolbar_docking.py && git commit -m "test(gui): add comprehensive toolbar docking regression test suite"`

---

### Task 5: Project-Wide Verification & Transition to Review

- [ ] **Step 1: Run all affected test suites**
  Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_window_toolbar_docking.py tests/ui/test_quire_toolbars.py tests/ui/test_ledger_toolbars.py tests/ui/test_lectern_toolbars.py -v`
  Expected: All pass.

- [ ] **Step 2: Advance agent state machine to reviewing**
  Run: `python3 scripts/github_agent_helper.py set-state --state reviewing`

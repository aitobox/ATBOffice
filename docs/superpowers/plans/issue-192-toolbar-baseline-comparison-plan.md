# Implementation Plan: Issue #192 — [Phase 5] 建立三模块工具栏逐控件对照与截图基线

## Architecture Overview
This plan establishes an authoritative control-by-control baseline comparison matrix and visual screenshot library comparing `.vibeoffice` (Office 2003 Luna JS) and `ATBOffice` (PySide6 Python) across Quire, Ledger, and Lectern. It uses automated inspection scripts, PySide6 offscreen screenshot rendering, comprehensive unit/integration test suites, and updates the project's parity documentation.

---

### Task 1: Automated Toolbar Parity Audit Script & Matrix Generation

**Files:**
- Create: `scripts/audit_toolbars_parity.py`
- Output: `docs/clone/evidence/phase5/toolbar_baseline_matrix.md`

**Steps:**
- [ ] 1.1 Write `scripts/audit_toolbars_parity.py` to extract toolbar declarations from `.vibeoffice/public/{quire,ledger,lectern}/js/app.js` and introspect `src/atboffice/ui/shell/{quire,ledger,lectern}_toolbars.py`.
- [ ] 1.2 Inspect every toolbar:
  - Quire (10 toolbars: standard, formatting, tables, reviewing, outlining, headerFooter, drawing, mailMerge, picture, wordart)
  - Ledger (8 toolbars: standard, formatting, borders, auditing, reviewing, list, chart, drawing)
  - Lectern (10 toolbars: standard, formatting, sorter, master, outlining, diagram, tables, picture, wordart, drawing)
- [ ] 1.3 Record item order, widget kind, action ID, icon, label, shortcut, context visibility, and parity status (`WIRED`, `STUB`, `UI_ONLY`, `MISSING`).
- [ ] 1.4 Execute the script to generate `docs/clone/evidence/phase5/toolbar_baseline_matrix.md`.
- [ ] 1.5 Verify matrix completeness and cross-reference against `.vibeoffice` source code.

---

### Task 2: PySide6 Native Toolbar Screenshot Capture & Evidence Index

**Files:**
- Create: `scripts/capture_atboffice_toolbars.py`
- Output: `docs/clone/evidence/phase5/screenshots/*.png`
- Output: `docs/clone/evidence/phase5/screenshots/INDEX.md`

**Steps:**
- [ ] 2.1 Implement `scripts/capture_atboffice_toolbars.py` using PySide6 offscreen window rendering (`QWidget.grab()` / `QPixmap`).
- [ ] 2.2 Capture Quire, Ledger, and Lectern windows:
  - Standard viewport (1280×800) with default toolbars.
  - Standard viewport with all toolbars visible.
  - Narrow viewport (800×600) to verify toolbar wrapping and overflow handling.
  - Toolbar dock crops.
- [ ] 2.3 Save screenshots to `docs/clone/evidence/phase5/screenshots/`.
- [ ] 2.4 Generate `docs/clone/evidence/phase5/screenshots/INDEX.md` mapping ATBOffice screenshots to original `.vibeoffice/screenshots/`.
- [ ] 2.5 Verify images are non-empty and capture quality is crisp.

---

### Task 3: Comprehensive Toolbar Parity Test Suite (TDD)

**Files:**
- Create: `tests/ui/test_toolbar_baseline_parity.py`

**Steps:**
- [ ] 3.1 Write tests verifying toolbar counts and identities across Quire (10), Ledger (8), and Lectern (10).
- [ ] 3.2 Test that every toolbar action is registered in the parent window's `ActionRegistry`.
- [ ] 3.3 Test that all toolbar actions and buttons have valid, non-empty tooltips and proper icons.
- [ ] 3.4 Test that docking invariant holds: all toolbars are in `TopToolBarArea`, zero in `BottomToolBarArea`.
- [ ] 3.5 Test dynamic translation across all 7 supported locales (`en`, `zh_CN`, `zh_TW`, `ja`, `fr`, `de`, `es`) verifying that `retranslate_ui()` runs cleanly without exceptions.
- [ ] 3.6 Run `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/ui/test_toolbar_baseline_parity.py -v` and verify 100% pass.

---

### Task 4: Documentation & Parity Tracking Updates

**Files:**
- Modify: `docs/clone/CLONE_DIFF.md`
- Modify: `docs/clone/features.csv`

**Steps:**
- [ ] 4.1 Update `docs/clone/CLONE_DIFF.md` section `[TASK-504]` with findings, matrix references, and screenshot evidence links.
- [ ] 4.2 Update `docs/clone/features.csv` to reflect verified toolbar baseline parity.
- [ ] 4.3 Verify markdown links and table formatting.

---

### Task 5: Repository-Wide Verification & Quality Gate

**Steps:**
- [ ] 5.1 Run full pytest suite: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`
- [ ] 5.2 Confirm all test files pass with zero regressions.
- [ ] 5.3 Review `git status` and diff to ensure clean state before committing.

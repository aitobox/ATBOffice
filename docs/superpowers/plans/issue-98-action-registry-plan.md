# ActionRegistry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement data-driven `ActionRegistry` and `ActionSpec` command bus for ATBOffice menus and toolbars to enable bidirectional state synchronization and non-blocking fallback toasts.

**Architecture:** A centralized `ActionRegistry` (`QObject`) that registers declarative `ActionSpec` instances, returns reusable `QAction` objects, synchronizes state between Menus and ToolBars, and triggers safe fallback notifications via `statusBar().showMessage()` when actions have no bound handler.

**Tech Stack:** Python 3.12+, PySide6 (QtCore, QtGui, QtWidgets), pytest, pytest-qt.

**Spec:** `docs/superpowers/specs/issue-98-action-registry-spec.md`

## Global Constraints
- Zero external third-party dependencies outside standard PySide6 / Python stdlib.
- Full type annotations on all methods and attributes.
- 100% compliant with ruff linting (zero warnings or unused imports).
- Non-blocking fallback toast: never call `QMessageBox` or freeze automated tests.

---

### Task 1: ActionRegistry & ActionSpec Core Implementation

**Files:**
- Create: `src/atboffice/core/action_registry.py`
- Test: `tests/core/test_action_registry.py`

**Interfaces:**
- Produces: `class ActionSpec`: data model containing `id`, `label`, `icon`, `tip`, `shortcut`, `checkable`, `checked`, `enabled`, `is_split`, `is_drop`, `handler`
- Produces: `class ActionRegistry(QObject)`: methods `register_action`, `register_specs`, `get_action`, `has_action`, `set_enabled`, `set_checked`, `set_handler`, `trigger_action`, `retranslate_ui`

- [ ] **Step 1: Write failing tests in `tests/core/test_action_registry.py`**
- [ ] **Step 2: Run pytest to verify tests fail**
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/core/test_action_registry.py -v`
- [ ] **Step 3: Implement `ActionSpec` and `ActionRegistry` in `src/atboffice/core/action_registry.py`**
- [ ] **Step 4: Run pytest to verify all tests pass**
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/core/test_action_registry.py -v`
- [ ] **Step 5: Run full test suite & ruff check**
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/`
  `conda run -n ATBOffice ruff check .`
- [ ] **Step 6: Commit changes**
  `git commit -m "feat(#98): implement ActionRegistry command bus and ActionSpec"`

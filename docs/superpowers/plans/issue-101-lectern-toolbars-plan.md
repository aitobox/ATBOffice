# Implementation Plan: [Phase 2] Lectern 10 套工具栏声明式构建与命令接入 (Issue #101)

## Phase 1: Test Scaffolding (TDD)
- **File**: `tests/ui/test_lectern_toolbars.py`
- Write comprehensive tests asserting:
  1. `win.toolbars` exists and contains exactly the 10 expected keys: `standard`, `formatting`, `sorter`, `master`, `outlining`, `diagram`, `tables`, `picture`, `wordart`, `drawing`.
  2. Each toolbar is an `OfficeToolBar` with a localized window title.
  3. `win.toolBarArea(win.toolbars["drawing"]) == Qt.ToolBarArea.BottomToolBarArea`.
  4. `win.action_registry` is bound and registers key actions (`new`, `open`, `save`, `cut`, `copy`, `paste`, `undo`, `redo`, `bold`, `italic`, `underline`, `new_slide`, `start_slideshow`, `close_master`, etc.).
  5. Combos and ColorPickers exist on `standard`, `formatting`, and `drawing` toolbars.
  6. Contextual visibility rules:
     - Normal view: `standard`, `formatting`, `drawing` are visible; `sorter`, `master` are hidden.
     - View mode switches to `"sorter"`: `sorter` visible, `formatting`/`drawing` hidden.
     - View mode switches to `"master"`: `master` visible.
     - Object selection: selecting table shows `tables`; selecting image shows `picture`; selecting diagram shows `diagram`; selecting wordart shows `wordart`.
  7. Localized retranslation works via `retranslate_ui()`.
- Verify tests fail initially (Red).

## Phase 2: Implement Toolbar Cluster
- **File**: `src/atboffice/ui/shell/lectern_toolbars.py`
- Implement `LecternToolBarCluster`:
  - `_reg_act()`, `_add()`, `_add_drop()`, `_add_split()`.
  - 10 builder methods for `standard`, `formatting`, `sorter`, `master`, `outlining`, `diagram`, `tables`, `picture`, `wordart`, and `drawing`.
  - `build_lectern_toolbars(window, action_registry)`.
  - `retranslate_lectern_toolbars(toolbars, tr_func)`.
- Ensure 100% strings are wrapped in `safe_tr()`.

## Phase 3: Wire into LecternWindow
- **File**: `src/atboffice/ui/shell/lectern_window.py`
- Setup `ActionRegistry` on `LecternWindow` and bind command handlers.
- Refactor `_setup_toolbars()` to use `build_lectern_toolbars()`.
- Add `drawing` to `BottomToolBarArea`, others to `TopToolBarArea`.
- Retain backward compatibility properties and aliases (`toolbar_standard`, `act_bold`, `act_italic`, `act_underline`, etc.).
- Implement `set_toolbar_mode()` and `update_context_toolbars(context)`.
- Hook `set_view_mode()`, `scene.selectionChanged`, and `left_pane.currentChanged` to `update_context_toolbars()`.
- Update `retranslate_ui()` to invoke `retranslate_lectern_toolbars()`.

## Phase 4: Verification & Zero Regression
- Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_lectern_toolbars.py -v`.
- Run full test suite: `PYTHONPATH=src conda run -n ATBOffice pytest tests/`.
- Ensure all tests pass.

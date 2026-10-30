# Quire Toolbar Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fully wire Quire's 10-toolbar cluster actions to canvas formatting, table operations, review/revisions, and DOM controllers with two-way state synchronization.

**Architecture:** Extend `WriterCanvasView` with paragraph, character, list, table, and review editing operations; wire all ActionRegistry actions in `QuireWindow`; synchronize toolbar action checked states and combos dynamically on caret movement.

**Tech Stack:** Python 3.12+, PySide6 (Qt6), pytest, pytest-qt.

**Spec:** `docs/superpowers/specs/issue-131-wire-quire-toolbars-spec.md`

## Global Constraints
- Target branch: `main`, current feature branch: `agent/issue-131-wire-quire-toolbars`
- 100% type hints and idiomatic Python 3.12+ / Qt6 patterns
- Zero test regressions across existing suite
- i18n support with `safe_tr()` / `retranslate_ui()` for all new strings

---

### Task 1: Paragraph, Character, and List Formatting Operations

**Files:**
- Modify: `src/atboffice/modules/writer/views/canvas_view.py`
- Test: `tests/ui/test_quire_toolbar_wiring.py`

**Interfaces:**
- Consumes: `Document`, `Paragraph`, `ParagraphProperties`, `RunProperties`, `split_at`, `normalize`, `paras_between`, `reindex` from `atboffice.modules.writer.models.document`
- Produces:
  - `WriterCanvasView.set_paragraph_alignment(jc: str) -> None`
  - `WriterCanvasView.change_indent(delta_pt: float) -> None`
  - `WriterCanvasView.set_line_spacing(line: float, line_rule: str = "auto") -> None`
  - `WriterCanvasView.toggle_character_format(attr: str) -> None`
  - `WriterCanvasView.set_font_family(name: str) -> None`
  - `WriterCanvasView.set_font_size(size_pt: float) -> None`
  - `WriterCanvasView.set_font_color(color: str) -> None`
  - `WriterCanvasView.set_highlight_color(color: str | None) -> None`
  - `WriterCanvasView.toggle_list_style(kind: str) -> None`

- [ ] **Step 1: Write failing tests for formatting operations in `tests/ui/test_quire_toolbar_wiring.py`**
- [ ] **Step 2: Run pytest to verify tests fail with AttributeError**
- [ ] **Step 3: Implement formatting operations in `canvas_view.py`**
- [ ] **Step 4: Run pytest to verify tests pass**
- [ ] **Step 5: Git commit**

---

### Task 2: Table Operations and In-Table Context Detection

**Files:**
- Modify: `src/atboffice/modules/writer/views/canvas_view.py`
- Test: `tests/ui/test_quire_toolbar_wiring.py`

**Interfaces:**
- Consumes: `table_map`, `insert_rows`, `delete_rows`, `insert_cols`, `delete_cols`, `merge_cells`, `split_cells`, `create_simple_table` from `atboffice.modules.writer.models.table`
- Produces:
  - `WriterCanvasView.get_current_table_context() -> dict[str, Any] | None`
  - `WriterCanvasView.insert_table(rows: int = 2, cols: int = 2) -> None`
  - `WriterCanvasView.insert_table_row(above: bool = False) -> None`
  - `WriterCanvasView.insert_table_col(left: bool = False) -> None`
  - `WriterCanvasView.delete_table_row() -> None`
  - `WriterCanvasView.delete_table_col() -> None`
  - `WriterCanvasView.merge_table_cells() -> None`
  - `WriterCanvasView.split_table_cells(num_rows: int = 1, num_cols: int = 2) -> None`
  - `WriterCanvasView.distribute_table_rows() -> None`
  - `WriterCanvasView.distribute_table_cols() -> None`

- [ ] **Step 1: Write failing tests for table operations and context detection**
- [ ] **Step 2: Run pytest to verify tests fail**
- [ ] **Step 3: Implement table operations in `canvas_view.py`**
- [ ] **Step 4: Run pytest to verify tests pass**
- [ ] **Step 5: Git commit**

---

### Task 3: Revision, Comment, and Outline Operations

**Files:**
- Modify: `src/atboffice/modules/writer/views/canvas_view.py`
- Test: `tests/ui/test_quire_toolbar_wiring.py`

**Interfaces:**
- Consumes: `toggle_tracking`, `is_tracking`, `accept_revision`, `accept_all_revisions`, `reject_revision`, `reject_all_revisions`, `insert_comment`, `list_revisions` from `atboffice.modules.writer.models.revision`
- Produces:
  - `WriterCanvasView.toggle_track_changes() -> bool`
  - `WriterCanvasView.accept_current_revision(all_revisions: bool = False) -> None`
  - `WriterCanvasView.reject_current_revision(all_revisions: bool = False) -> None`
  - `WriterCanvasView.insert_comment(author: str = "User", text: str = "") -> None`
  - `WriterCanvasView.change_outline_level(delta: int) -> None`
  - `WriterCanvasView.set_outline_level(level: int | None) -> None`
  - `WriterCanvasView.move_paragraph(delta: int) -> None`

- [ ] **Step 1: Write failing tests for revision and outline operations**
- [ ] **Step 2: Run pytest to verify tests fail**
- [ ] **Step 3: Implement revision and outline methods in `canvas_view.py`**
- [ ] **Step 4: Run pytest to verify tests pass**
- [ ] **Step 5: Git commit**

---

### Task 4: Complete Action Wiring in `QuireWindow`

**Files:**
- Modify: `src/atboffice/ui/shell/quire_window.py`
- Test: `tests/ui/test_quire_toolbar_wiring.py`

**Interfaces:**
- Consumes: `ActionRegistry`, `WriterCanvasView`, `WriterView`
- Produces:
  - Full handler registration in `QuireWindow._bind_action_handlers()`
  - Connection of toolbar special widgets (combos, color pickers, drop menus) in `QuireWindow._setup_toolbars()`

- [ ] **Step 1: Write tests verifying triggering actions changes document state**
- [ ] **Step 2: Run pytest to verify failures**
- [ ] **Step 3: Update `quire_window.py` with complete action bindings and widget connections**
- [ ] **Step 4: Run pytest to verify passes**
- [ ] **Step 5: Git commit**

---

### Task 5: Dynamic State Synchronization on Caret Movement

**Files:**
- Modify: `src/atboffice/ui/shell/quire_window.py`
- Test: `tests/ui/test_quire_toolbar_wiring.py`

**Interfaces:**
- Consumes: `canvas_view.caret_moved`, `canvas_view.controller.selection_changed`
- Produces:
  - `QuireWindow._sync_toolbar_states() -> None`
  - Auto-activation of Table toolbar when caret enters table
  - Checked state sync for bold, italic, underline, alignment, bullets, numbering, trackChanges
  - Text sync for Font and Size combos without infinite loop

- [ ] **Step 1: Write tests verifying caret movement syncs toolbar checkable states and contextual tables toolbar**
- [ ] **Step 2: Run pytest to verify failures**
- [ ] **Step 3: Implement `_sync_toolbar_states()` and table context tracking**
- [ ] **Step 4: Run pytest to verify passes**
- [ ] **Step 5: Git commit**

---

### Task 6: Project-wide Verification and Quality Gate

**Files:**
- Run: `tests/ui/test_quire_toolbars.py`
- Run: `tests/ui/test_quire_toolbar_wiring.py`
- Run: `tests/` (full test suite)

- [ ] **Step 1: Run all tests in repository**
- [ ] **Step 2: Ensure zero failures or regressions**
- [ ] **Step 3: Update agent state machine to reviewing**

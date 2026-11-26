# Phase 12 Wave 1: P0 Robustness & Element-Edit Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate deterministic runtime crashes, broken lazy imports, keystroke pagination freezes, and unsafe Qt C++ lifetime/event paths across Quire, Ledger, and Lectern when opening documents and editing/inserting new elements.

**Architecture:** Fix all 4 confirmed broken lazy imports with an AST integrity gate; introduce a lightweight `core/fault_guard.py` module for `shiboken6.isValid()` checks, owner-bound `safe_single_shot`, and exception-isolating Qt event/slot guards; then harden element insertion, editing, undo, and round-trip save in Quire, Ledger, and Lectern backed by a cross-editor interactive stress test.

**Tech Stack:** Python 3.12+, PySide6 (Qt 6), shiboken6, lxml, pytest, ruff, mypy.

**Spec:** [2026-11-26-phase12-robustness-and-parity-design.md](file:///Users/aitobox/work/aitobox/ATBOffice/docs/superpowers/specs/2026-11-26-phase12-robustness-and-parity-design.md)

## Global Constraints

- Conda environment: activate/run via `conda run -n ATBOffice` (GUI tests with `QT_QPA_PLATFORM=offscreen`).
- Text is translated: every visible UI string uses `safe_tr()` with Chinese source text; windows/dialogs implement `retranslate_ui()`.
- Commands go through `ActionRegistry`; document edits go through `UndoService`.
- Theme: colors come from `ThemeTokens` / `ui/styles/luna_2003.py`; fonts from `ui_font()`.
- No test-only code paths: product code never checks `PYTEST_CURRENT_TEST`.
- Errors are visible or logged: never swallow exceptions silently; log with `logger.exception` or show a user-facing warning/status message.
- CI gates that must pass after Wave 1: `ruff check .`, `ruff format --check .`, `mypy src/atboffice/core`, `QT_QPA_PLATFORM=offscreen pytest -n auto`.

## File Structure

- `tests/test_lazy_imports_integrity.py` (create): AST import integrity audit across `src/atboffice/**/*.py` plus regression tests for the 4 fixed lazy imports.
- `src/atboffice/ui/shell/ledger_auditing.py` (modify): replace `to_a1` with `cell_name`; make comment insert/delete undoable.
- `src/atboffice/modules/writer/view.py` (modify): route `_on_new_comment` through undoable `self.canvas_view.insert_comment()`.
- `src/atboffice/modules/spreadsheet/calc/fn_dynamic.py` (modify): replace `parse_cell_reference` with `parse_range`.
- `src/atboffice/core/fault_guard.py` (create): `is_alive`, `safe_single_shot`, `guard_qt_slot`, `guard_qt_event` with `shiboken6.isValid()`, `CrashDiagnostics`, and `ActionRecorder` breadcrumb integration.
- `src/atboffice/ui/shell/base_window.py` (modify): track and stop registered owned timers inside `cleanup_resources()`.
- `tests/core/test_fault_guard.py` (create): unit tests for `is_alive`, `safe_single_shot` cancellation on owner destruction, and exception isolation in `guard_qt_slot`/`guard_qt_event`.
- `src/atboffice/modules/writer/models/styles.py` (modify): cache `num_level_def` lookup at module scope so `shibokensupport` import hook does not run on every numbered paragraph during every keystroke.
- `src/atboffice/modules/writer/views/canvas_editing.py` (modify): implement undoable `insert_shape`, `reorder_selected_object`, `nudge_selected_object`, `align_selected_objects`, and `rotate_selected_object`.
- `src/atboffice/modules/writer/views/canvas_input.py` (modify): decorate mouse/key event handlers with `@guard_qt_event` and ensure clicking off a selected float cleanly restores text editing focus.
- `tests/gui/test_quire_insert_shape_and_edit.py` (create): tests for Quire shape/textbox insertion, fast typing on numbered corpus docx, float ops, undo/redo, and save/reopen.
- `src/atboffice/ui/shell/ledger_objects.py` (modify): record drawing additions/edits into window `UndoService`.
- `src/atboffice/modules/spreadsheet/views/object_layer.py` (modify): guard paint/mouse/key events with `@guard_qt_event` and expose undo snapshot hooks for interactive drag/delete/paste.
- `tests/gui/test_ledger_object_undo_and_robustness.py` (create): tests for Ledger shape/textbox/picture/comment insert, drag/delete, undo/redo, and save/reopen.
- `src/atboffice/ui/shell/lectern_history.py` (modify): switch `note_edit` to `safe_single_shot`, add `cancel_pending()`, guard `flush()` and `snapshot_presentation()`.
- `src/atboffice/ui/shell/lectern_window.py` (modify): cancel `self.history` pending timers in `cleanup_resources()`.
- `src/atboffice/modules/presentation/views/slide_canvas.py` (modify): guard `SlideScene` mouse/key events with `@guard_qt_event` and `is_alive`.
- `tests/gui/test_lectern_history_and_scene_robustness.py` (create): tests for Lectern rapid edit + close safety, shape/textbox creation, undo/redo, and save/reopen.
- `tests/gui/test_phase12_element_edit_robustness.py` (create): cross-editor Wave 1 acceptance gate exercising all element types on real `.docx`, `.xlsx`, and `.pptx` corpus files with `CrashDiagnostics` & `sys.excepthook` assertions.

---

### Task 1: Fix 4 Broken Lazy Imports & Add AST Integrity Gate

**Files:**
- Modify: `src/atboffice/ui/shell/ledger_auditing.py:114-205`
- Modify: `src/atboffice/modules/writer/view.py:309-317`
- Modify: `src/atboffice/modules/spreadsheet/calc/fn_dynamic.py:787-804`
- Create: `tests/test_lazy_imports_integrity.py`

**Interfaces:**
- Consumes: `cell_name` and `parse_range` from `atboffice.modules.spreadsheet.calc.references`; `WriterCanvasView.insert_comment` from `atboffice.modules.writer.views.canvas_editing`.
- Produces: Passing AST import audit across `src/atboffice/**/*.py` and working `INDIRECT`, Ledger comment/validation cell formatting, and Quire review-toolbar new comment.

- [ ] **Step 1: Write the failing test**

Create `tests/test_lazy_imports_integrity.py`:

```python
"""AST and functional integrity tests for all lazy/inline imports in src/atboffice."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

from PySide6.QtWidgets import QDialog

from atboffice.modules.spreadsheet.calc.eval_context import EvalContext
from atboffice.modules.spreadsheet.calc.fn_dynamic import fn_indirect
from atboffice.modules.spreadsheet.calc.references import Ref
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "atboffice"


def test_all_lazy_atboffice_imports_resolve() -> None:
    """Every ``from atboffice... import ...`` in source must resolve its module and symbols."""
    broken: list[tuple[str, int, str, str]] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            if not node.module.startswith("atboffice."):
                continue
            try:
                mod = importlib.import_module(node.module)
            except Exception as exc:
                broken.append((str(path), node.lineno, node.module, f"MOD:{exc}"))
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                if hasattr(mod, alias.name):
                    continue
                try:
                    importlib.import_module(f"{node.module}.{alias.name}")
                except Exception:
                    broken.append(
                        (str(path), node.lineno, f"{node.module}.{alias.name}", "MISSING_SYMBOL")
                    )
    assert broken == [], f"Broken imports found: {broken}"


def test_indirect_formula_resolves_cell_reference() -> None:
    """fn_indirect must resolve both single cells and ranges via references.parse_range."""
    sheet = SheetDataModel("Sheet1")
    ctx = EvalContext(current_sheet="Sheet1", sheets={"Sheet1": sheet})
    ref = fn_indirect("B3", True, ctx=ctx)
    assert isinstance(ref, Ref)
    assert (ref.sheet, ref.r1, ref.c1, ref.r2, ref.c2) == ("Sheet1", 2, 1, 2, 1)


def test_ledger_comment_and_validation_resolve_without_import_error(
    qtbot, monkeypatch
) -> None:
    """Ledger insert_comment and data_validation must not fail on missing to_a1."""
    from atboffice.modules.spreadsheet.dialogs.comment_dialog import CommentDialog
    from atboffice.modules.spreadsheet.dialogs.data_validation_dialog import (
        DataValidationDialog,
    )
    from atboffice.ui.shell.ledger_window import LedgerWindow

    win = LedgerWindow()
    qtbot.addWidget(win)
    monkeypatch.setattr(CommentDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    monkeypatch.setattr(DataValidationDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    win.insert_comment()
    win.data_validation()
    win.set_modified(False)


def test_quire_review_toolbar_new_comment_inserts_comment(qtbot) -> None:
    """WriterView._on_new_comment must insert a comment via canvas_view instead of crashing."""
    from atboffice.ui.shell.quire_window import QuireWindow

    win = QuireWindow()
    qtbot.addWidget(win)
    win.writer_view._on_new_comment()
    assert len(win.writer_view.canvas_view.doc.comments) == 1
    win.set_modified(False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/test_lazy_imports_integrity.py -v`
Expected: FAIL on all 4 tests with `MISSING_SYMBOL` (`to_a1`, `add_comment`, `parse_cell_reference`) and `ImportError`.

- [ ] **Step 3: Write minimal implementation**

Edit `src/atboffice/ui/shell/ledger_auditing.py` lines 119–123 and 191–199:

```python
        cm = sheet.get_comment(r, c)
        from atboffice.modules.spreadsheet.calc.references import cell_name

        cell_ref = cell_name(r, c)
```

and:

```python
        pr = sel.primary_range
        from atboffice.modules.spreadsheet.calc.references import cell_name

        if pr.min_r == pr.max_r and pr.min_c == pr.max_c:
            sqref = cell_name(pr.min_r, pr.min_c)
        else:
            sqref = f"{cell_name(pr.min_r, pr.min_c)}:{cell_name(pr.max_r, pr.max_c)}"
```

Edit `src/atboffice/modules/writer/view.py` lines 309–317:

```python
    def _on_new_comment(self) -> None:
        """Insert new comment at caret via undoable canvas action."""
        self.canvas_view.insert_comment(author="Author", text=safe_tr("新批注"))
        self.review_pane.refresh_items()
```

Edit `src/atboffice/modules/spreadsheet/calc/fn_dynamic.py` lines 797–803:

```python
    from atboffice.modules.spreadsheet.calc.references import parse_range

    parsed = parse_range(s)
    if parsed is not None:
        return ctx.create_ref(
            sheet, parsed["r1"], parsed["c1"], parsed["r2"], parsed["c2"]
        )
    return REF
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/test_lazy_imports_integrity.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add tests/test_lazy_imports_integrity.py src/atboffice/ui/shell/ledger_auditing.py src/atboffice/modules/writer/view.py src/atboffice/modules/spreadsheet/calc/fn_dynamic.py
git commit -m "fix(stability): repair 4 broken lazy imports and add AST import integrity test"
```

---

### Task 2: Create Unified Qt Fault-Isolation & Lifetime Guard (`core/fault_guard.py`) + Window Teardown

**Files:**
- Create: `src/atboffice/core/fault_guard.py`
- Modify: `src/atboffice/ui/shell/base_window.py:53-86,956-993`
- Create: `tests/core/test_fault_guard.py`

**Interfaces:**
- Produces:
  - `is_alive(obj: Any) -> bool`
  - `safe_single_shot(delay_ms: int, owner: QObject | None, callback: Callable[[], Any]) -> QTimer | None`
  - `guard_qt_slot(component: str, action_name: str, default: Any = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]`
  - `guard_qt_event(component: str, event_name: str, default: bool = False) -> Callable[[Callable[..., Any]], Callable[..., Any]]`
  - `BaseOfficeWindow.register_owned_timer(timer: QTimer) -> None` and `BaseOfficeWindow.stop_owned_timers() -> None` called in `cleanup_resources()`.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_fault_guard.py`:

```python
"""Unit tests for core.fault_guard lifetime checks, safe timers, and exception isolation."""

from __future__ import annotations

import logging

import shiboken6
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMainWindow

from atboffice.core.diagnostics import ActionRecorder
from atboffice.core.fault_guard import (
    guard_qt_event,
    guard_qt_slot,
    is_alive,
    safe_single_shot,
)


def test_is_alive_handles_none_plain_and_deleted_qobject(qapp) -> None:
    assert is_alive(None) is False
    assert is_alive(object()) is True
    obj = QObject()
    assert is_alive(obj) is True
    shiboken6.delete(obj)
    assert is_alive(obj) is False


def test_is_alive_respects_closed_window_flag(qtbot) -> None:
    win = QMainWindow()
    qtbot.addWidget(win)
    assert is_alive(win) is True
    win._is_closed = True  # type: ignore[attr-defined]
    assert is_alive(win) is False


def test_safe_single_shot_skips_callback_when_owner_destroyed(qapp) -> None:
    owner = QObject()
    called: list[str] = []
    timer = safe_single_shot(0, owner, lambda: called.append("ran"))
    assert timer is not None
    shiboken6.delete(owner)
    qapp.processEvents()
    assert called == []


def test_guard_qt_slot_and_event_isolate_exceptions_and_record_breadcrumb(caplog) -> None:
    ActionRecorder.reset_instance()

    class Dummy(QObject):
        @guard_qt_slot("dummy", "explode", default="fallback")
        def boom_slot(self) -> str:
            raise RuntimeError("slot failed")

        @guard_qt_event("dummy", "mouse_press", default=True)
        def boom_event(self, _ev: object) -> bool:
            raise ValueError("event failed")

    d = Dummy()
    with caplog.at_level(logging.ERROR):
        assert d.boom_slot() == "fallback"
        assert d.boom_event(None) is True

    actions = [a["action"] for a in ActionRecorder.get_instance().get_recent_actions()]
    assert "qt_slot_error:explode" in actions
    assert "qt_event_error:mouse_press" in actions
    assert "slot failed" in caplog.text
    assert "event failed" in caplog.text


def test_base_window_stops_registered_owned_timers_on_cleanup(qtbot) -> None:
    from PySide6.QtCore import QTimer

    from atboffice.ui.shell.base_window import BaseOfficeWindow

    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    timer = QTimer()
    timer.start(10_000)
    win.register_owned_timer(timer)
    assert timer.isActive()
    win.cleanup_resources()
    assert not timer.isActive()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/core/test_fault_guard.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atboffice.core.fault_guard'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/atboffice/core/fault_guard.py`:

```python
"""Unified Qt C++ object lifetime checks, safe single-shot timers, and event/slot fault guards."""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

import shiboken6
from PySide6.QtCore import QObject, QTimer

from atboffice.core.diagnostics import record_action
from atboffice.core.i18n import safe_tr

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def is_alive(obj: Any) -> bool:
    """Return True if ``obj`` is usable (not None, valid Qt C++ wrapper, not closed)."""
    if obj is None:
        return False
    if isinstance(obj, QObject):
        try:
            if not shiboken6.isValid(obj):
                return False
        except Exception:
            return False
    if getattr(obj, "_is_closed", False):
        return False
    win_fn = getattr(obj, "window", None)
    if callable(win_fn):
        try:
            win = win_fn()
            if win is not None and win is not obj and getattr(win, "_is_closed", False):
                return False
        except Exception:
            return False
    return True


def _report_non_paint_error(owner: Any, label: str, exc: Exception) -> None:
    """Surface unexpected UI errors on statusBar when available without blocking painting."""
    if not is_alive(owner):
        return
    try:
        win = owner.window() if callable(getattr(owner, "window", None)) else owner
        if win is not None and is_alive(win) and callable(getattr(win, "statusBar", None)):
            sb = win.statusBar()
            if sb is not None:
                sb.showMessage(safe_tr("操作出现异常（已记录日志）：{0}").format(exc), 4000)
    except Exception:
        logger.debug("Failed to surface status bar error for %s", label, exc_info=True)


def safe_single_shot(
    delay_ms: int,
    owner: QObject | None,
    callback: Callable[[], Any],
) -> QTimer | None:
    """Schedule ``callback`` after ``delay_ms`` only while ``owner`` stays alive."""
    if not is_alive(owner):
        return None
    timer = QTimer(owner)
    timer.setSingleShot(True)

    def _fire() -> None:
        if not is_alive(owner):
            return
        try:
            callback()
        except Exception:
            logger.exception("Unhandled error in safe_single_shot callback")
            record_action("qt_timer_error", "fault_guard", {})

    timer.timeout.connect(_fire)
    if hasattr(owner, "destroyed"):
        owner.destroyed.connect(timer.stop)
    timer.start(max(0, int(delay_ms)))
    return timer


def guard_qt_slot(component: str, action_name: str, default: Any = None) -> Callable[[F], F]:
    """Decorator guarding Qt slots against dead C++ wrappers and unhandled Python exceptions."""

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            if not is_alive(self):
                return default
            try:
                return fn(self, *args, **kwargs)
            except Exception as exc:
                logger.exception("Error in Qt slot %s.%s", component, action_name)
                record_action(
                    f"qt_slot_error:{action_name}",
                    component,
                    {"error": f"{type(exc).__name__}: {exc}"},
                )
                _report_non_paint_error(self, action_name, exc)
                return default

        return wrapper  # type: ignore[return-value]

    return decorator


def guard_qt_event(component: str, event_name: str, default: bool = False) -> Callable[[F], F]:
    """Decorator guarding Qt event overrides against dead objects and unhandled exceptions."""

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            if not is_alive(self):
                return default
            try:
                return fn(self, *args, **kwargs)
            except Exception as exc:
                logger.exception("Error in Qt event %s.%s", component, event_name)
                record_action(
                    f"qt_event_error:{event_name}",
                    component,
                    {"error": f"{type(exc).__name__}: {exc}"},
                )
                if "paint" not in event_name.lower():
                    _report_non_paint_error(self, event_name, exc)
                return default

        return wrapper  # type: ignore[return-value]

    return decorator
```

Modify `src/atboffice/ui/shell/base_window.py`:
In `__init__` (after line 60):

```python
        self._owned_timers: list[QTimer] = []
```

Add helper methods right above `cleanup_resources` (around line 942) and invoke `self.stop_owned_timers()` inside `cleanup_resources()`:

```python
    def register_owned_timer(self, timer: QTimer) -> None:
        """Track a timer so ``cleanup_resources`` stops it even if not parented to self."""
        if timer not in self._owned_timers:
            self._owned_timers.append(timer)

    def stop_owned_timers(self) -> None:
        """Stop all timers explicitly registered with this window."""
        for timer in list(getattr(self, "_owned_timers", [])):
            try:
                if timer is not None and timer.isActive():
                    timer.stop()
            except Exception:
                pass
        if hasattr(self, "_owned_timers"):
            self._owned_timers.clear()
```

And in `cleanup_resources()` (before step 2 `findChildren(QTimer)`):

```python
        self.stop_owned_timers()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/core/test_fault_guard.py -v && conda run -n ATBOffice mypy src/atboffice/core`
Expected: PASS (5 passed) and mypy reports `Success: no issues found`.

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/core/fault_guard.py src/atboffice/ui/shell/base_window.py tests/core/test_fault_guard.py
git commit -m "feat(core): add unified Qt fault_guard and owned timer teardown"
```

---

### Task 3: Implement Quire `WriterCanvasView.insert_shape`, Floating-Object Ops & Fix Keystroke Pagination Freeze

**Files:**
- Modify: `src/atboffice/modules/writer/models/styles.py:1-20,400-435`
- Modify: `src/atboffice/modules/writer/views/canvas_editing.py:1-56,530-552`
- Modify: `src/atboffice/modules/writer/views/canvas_input.py:1-42,185-235,270-315,460-485`
- Create: `tests/gui/test_quire_insert_shape_and_edit.py`

**Interfaces:**
- Consumes: `ShapeItem`, `FloatProperties`, `PositionH`, `PositionV`, `WrapMode`, `DmlFill`, `DmlLine`, `guard_qt_event` (Task 2).
- Produces: `WriterCanvasView.insert_shape(shape_type: str) -> ShapeItem | None`, `reorder_selected_object(direction: str) -> bool`, `nudge_selected_object(dx: float, dy: float) -> bool`, `align_selected_objects(alignment: str) -> bool`, `rotate_selected_object(angle: float) -> bool`, and cached `_get_num_level_def()` in `styles.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/gui/test_quire_insert_shape_and_edit.py`:

```python
"""Regression tests for Quire insert_shape, float operations, and fast typing on numbered docs."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from atboffice.modules.writer.models.document import all_stories
from atboffice.modules.writer.models.drawing import ShapeItem
from atboffice.ui.shell.quire_window import QuireWindow

BULLET_DOC = Path(__file__).resolve().parents[1] / "docs/word/docx/openxml-sdk__bullet-complex.docx"


def _shape_items(doc) -> list[ShapeItem]:
    items: list[ShapeItem] = []
    for story in all_stories(doc):
        for para in story.paras:
            for run in para.runs:
                if isinstance(run, ShapeItem):
                    items.append(run)
    return items


def test_quire_insert_shape_and_float_ops_are_undoable_and_persist(
    qtbot, tmp_path
) -> None:
    win = QuireWindow()
    qtbot.addWidget(win)
    win.resize(1100, 800)
    win.show()
    canvas = win.writer_view.canvas_view

    win.insert_shape("rect")
    win.insert_shape("textbox")
    shapes = _shape_items(canvas.doc)
    assert len(shapes) == 2
    assert shapes[0].geometry == "rect"
    assert shapes[1].story is not None

    # Float manipulation ops work on selected shape and are undoable
    assert canvas.selected_float() is shapes[1]
    start_x = shapes[1].float_pr.pos_h.offset
    win.nudge_selected_object(12, 8)
    assert shapes[1].float_pr.pos_h.offset > start_x
    win.rotate_selected_object(15.0)
    assert shapes[1].rotation == 15.0

    win.undo()  # undo rotate
    assert shapes[1].rotation == 0.0
    win.undo()  # undo nudge
    assert shapes[1].float_pr.pos_h.offset == start_x
    win.undo()  # undo textbox insert
    assert len(_shape_items(canvas.doc)) == 1
    win.redo()
    assert len(_shape_items(canvas.doc)) == 2

    out = tmp_path / "with_shapes.docx"
    assert win.save_file(out, confirm_overwrite=False) is True
    assert out.stat().st_size > 0
    win.set_modified(False)


def test_quire_click_and_type_after_shape_on_numbered_docx_is_fast(
    qtbot, qapp
) -> None:
    win = QuireWindow()
    qtbot.addWidget(win)
    win.resize(1100, 800)
    win.show()
    assert win.open_file(BULLET_DOC) is True
    canvas = win.writer_view.canvas_view

    win.insert_shape("rect")
    win.insert_shape("textbox")
    QTest.mouseClick(
        canvas.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(300, 200),
    )
    t0 = time.monotonic()
    QTest.keyClicks(canvas, "Hello")
    qapp.processEvents()
    elapsed = time.monotonic() - t0
    assert elapsed < 2.0, f"Typing stalled for {elapsed:.2f}s"
    win.set_modified(False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_quire_insert_shape_and_edit.py -v`
Expected: FAIL (`len(shapes) == 0` because `WriterCanvasView` has no `insert_shape`, and `keyClicks` stalls > 2s due to per-paragraph `num_level_def` import hook).

- [ ] **Step 3: Write minimal implementation**

1. Edit `src/atboffice/modules/writer/models/styles.py`:
Add module cache right before `_apply_numbering_indent` and use it inside `_apply_numbering_indent`:

```python
_NUM_LEVEL_DEF: Any = None


def _get_num_level_def() -> Any:
    global _NUM_LEVEL_DEF
    if _NUM_LEVEL_DEF is None:
        from atboffice.modules.writer.layout.portions import num_level_def

        _NUM_LEVEL_DEF = num_level_def
    return _NUM_LEVEL_DEF
```

And replace line 413–415 with:

```python
    lvl = _get_num_level_def()(doc, num.id, num.lvl if num.lvl is not None else 0)
```

2. Edit `src/atboffice/modules/writer/views/canvas_editing.py`:
Import drawing models at the top:

```python
from atboffice.drawing.dml import DmlFill
from atboffice.drawing.shape_style import DmlLine
from atboffice.modules.writer.models.document import Story
from atboffice.modules.writer.models.drawing import (
    FloatProperties,
    PositionH,
    PositionV,
    ShapeItem,
    WrapMode,
)
```

Add shape mapping + methods at the end of `CanvasEditingMixin`:

```python
    _SHAPE_GEOM_MAP: dict[str, str] = {
        "rect": "rect",
        "basic": "roundRect",
        "oval": "ellipse",
        "line": "line",
        "arrow": "rightArrow",
        "connector": "straightConnector1",
        "flowchart": "flowChartProcess",
        "star": "star5",
        "callout": "wedgeRoundRectCallout",
        "textbox": "rect",
    }

    @_undoable("插入图形")
    def insert_shape(self, shape_type: str = "rect") -> ShapeItem | None:
        """Insert a floating DrawingML shape or text box anchored at the caret paragraph."""
        p = self.controller._paragraph_by_id(self.controller.pos.para_id)
        if p is None:
            if not self.doc.main.blocks:
                return None
            p = next((b for b in self.doc.main.blocks if isinstance(b, Paragraph)), None)
            if p is None:
                return None
        geom = self._SHAPE_GEOM_MAP.get(shape_type, shape_type or "rect")
        is_line = shape_type in ("line", "connector")
        is_textbox = shape_type == "textbox"
        width = 144.0
        height = 2.0 if is_line else 72.0
        story = (
            Story(blocks=[Paragraph(runs=[TextItem(text=safe_tr("文本框"))])])
            if is_textbox
            else None
        )
        fill = (
            DmlFill(kind="none")
            if is_line
            else DmlFill(kind="solid", color="#FFFFFF" if is_textbox else "#D9E2F3")
        )
        line = DmlLine(visible=True, color="#2F5597", width=1.25)
        next_id = max((getattr(r, "id", 0) for r in p.runs), default=0) + 1
        item = ShapeItem(
            id=next_id,
            name=f"{shape_type}_{next_id}",
            width=width,
            height=height,
            float_pr=FloatProperties(
                wrap=WrapMode.IN_FRONT,
                pos_h=PositionH(rel="margin", offset=72.0),
                pos_v=PositionV(rel="paragraph", offset=12.0),
                z_index=max((getattr(getattr(r, "float_pr", None), "z_index", 0) for r in p.runs), default=0) + 1,
            ),
            geometry=geom,
            fill=fill,
            line=line,
            story=story,
        )
        p.runs.append(item)
        self._on_formatting_applied()
        page_idx = 0
        if getattr(self, "pagination", None) and self.pagination.pages:
            from atboffice.modules.writer.views import float_edit

            for idx, page in enumerate(self.pagination.pages):
                if float_edit.box_for_item(page, item) is not None:
                    page_idx = idx
                    break
        self.select_float(page_idx, item)
        return item

    @_undoable("调整对象叠放次序")
    def reorder_selected_object(self, direction: str) -> bool:
        """Adjust z-order of the currently selected floating object."""
        item = self.selected_float()
        fp = getattr(item, "float_pr", None) if item is not None else None
        if fp is None:
            return False
        if direction in ("front", "bring_to_front"):
            fp.behind = False
            fp.z_index = fp.z_index + 10
        elif direction in ("back", "send_to_back"):
            fp.z_index = max(0, fp.z_index - 10)
        elif direction in ("forward", "bring_forward"):
            fp.z_index = fp.z_index + 1
        elif direction in ("backward", "send_backward"):
            fp.z_index = max(0, fp.z_index - 1)
        self._on_formatting_applied()
        return True

    @_undoable("微移对象")
    def nudge_selected_object(self, dx: float, dy: float) -> bool:
        """Move the currently selected floating object by (dx, dy) points."""
        item = self.selected_float()
        fp = getattr(item, "float_pr", None) if item is not None else None
        if fp is None:
            return False
        from atboffice.modules.writer.views import float_edit

        found = self._selected_float_box()
        fb_x = found[1].x if found is not None else fp.pos_h.offset
        fb_y = found[1].y if found is not None else fp.pos_v.offset
        float_edit.apply_move(item, fb_x, fb_y, float(dx), float(dy))
        self._on_formatting_applied()
        return True

    @_undoable("对齐对象")
    def align_selected_objects(self, alignment: str) -> bool:
        """Align the selected floating object horizontally or vertically on the page."""
        item = self.selected_float()
        fp = getattr(item, "float_pr", None) if item is not None else None
        if fp is None:
            return False
        if alignment in ("left", "center", "right"):
            fp.pos_h.rel = "margin"
            fp.pos_h.align = alignment
            fp.pos_h.percent = None
        elif alignment in ("top", "middle", "bottom"):
            fp.pos_v.rel = "margin"
            fp.pos_v.align = "center" if alignment == "middle" else alignment
            fp.pos_v.percent = None
        self._on_formatting_applied()
        return True

    @_undoable("旋转对象")
    def rotate_selected_object(self, angle: float) -> bool:
        """Rotate the selected floating object by ``angle`` degrees."""
        item = self.selected_float()
        if item is None:
            return False
        item.rotation = (float(getattr(item, "rotation", 0.0)) + float(angle)) % 360.0
        self._on_formatting_applied()
        return True
```

3. Edit `src/atboffice/modules/writer/views/canvas_input.py`:
Import `guard_qt_event` at the top and decorate the four input overrides:

```python
from atboffice.core.fault_guard import guard_qt_event
```

```python
    @guard_qt_event("writer_canvas", "mouse_press")
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle single-click, double-click, triple-click, and table divider resize."""
        ...
```

Wait — keep the full existing method bodies intact and wrap `mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent`, and `keyPressEvent` with `@guard_qt_event("writer_canvas", ...)`:

```python
    @guard_qt_event("writer_canvas", "mouse_press")
    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos_pt = self._event_pos(event)
        if event.button() == Qt.MouseButton.LeftButton:
            hit = self._hit_test_table_divider(pos_pt)
            if hit is not None:
                self._resizing_table = True
                self._resize_info = hit
                self._resize_guide_pos = pos_pt
                self.viewport().update()
                return

            page_idx, pt_doc = self.viewport_to_doc_coords(pos_pt)
            if self._float_press(page_idx, pt_doc):
                return
            self.setFocus()
            pos = self.controller.canvas_to_pos(page_idx, pt_doc)

            p = self.controller._paragraph_by_id(pos.para_id)
            if p:
                from atboffice.modules.writer.models.document import locate

                item_idx, _, _ = locate(p, pos.offset, side="after")
                if 0 <= item_idx < len(p.runs):
                    it = p.runs[item_idx]
                    link = getattr(it.r_pr, "link", None) if hasattr(it, "r_pr") else None
                    if link and isinstance(link, dict) and "anchor" in link:
                        if self.jump_to_bookmark(link["anchor"]):
                            return

            modifiers = event.modifiers()
            shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

            self._is_dragging = True
            self.setFocus()
            self.controller.set_pos(pos, extend_selection=shift)
            self.viewport().update()

    @guard_qt_event("writer_canvas", "mouse_move")
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        # Existing body preserved unchanged under @guard_qt_event
        ...
```

(Only add the `@guard_qt_event("writer_canvas", "mouse_move")`, `@guard_qt_event("writer_canvas", "mouse_release")`, and `@guard_qt_event("writer_canvas", "key_press")` decorators on `mouseMoveEvent`, `mouseReleaseEvent`, and `keyPressEvent` while keeping their existing bodies, plus `self.setFocus()` right after `if self._float_press(page_idx, pt_doc): return` in `mousePressEvent`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_quire_insert_shape_and_edit.py -v`
Expected: PASS (2 passed, typing completes well under 2s).

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/modules/writer/models/styles.py src/atboffice/modules/writer/views/canvas_editing.py src/atboffice/modules/writer/views/canvas_input.py tests/gui/test_quire_insert_shape_and_edit.py
git commit -m "fix(quire): implement undoable insert_shape and cache numbering lookup on keystrokes"
```

---

### Task 4: Harden Ledger Object-Layer Undo, Comment Undo & Event Guards

**Files:**
- Modify: `src/atboffice/ui/shell/ledger_objects.py:25-120,180-250`
- Modify: `src/atboffice/ui/shell/ledger_auditing.py:114-185`
- Modify: `src/atboffice/modules/spreadsheet/views/object_layer.py:1-45,610-645,738-920`
- Create: `tests/gui/test_ledger_object_undo_and_robustness.py`

**Interfaces:**
- Consumes: `UndoService` (`self.undo_service()`), `guard_qt_event` (Task 2).
- Produces: `LedgerObjectsMixin._record_drawing_edit(label: str, mutate: Callable[[], Any])`, undoable `insert_comment`/`delete_comment`, and `@guard_qt_event`-protected `SpreadsheetObjectLayer` event handlers that record drag/delete/paste into the window `UndoService`.

- [ ] **Step 1: Write the failing test**

Create `tests/gui/test_ledger_object_undo_and_robustness.py`:

```python
"""Tests for Ledger object-layer undo, comment undo, event guards, and XLSX round-trip."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

from atboffice.modules.spreadsheet.dialogs.comment_dialog import CommentDialog
from atboffice.ui.shell.ledger_window import LedgerWindow


def test_ledger_insert_shape_textbox_picture_and_comment_are_undoable_and_save(
    qtbot, tmp_path, monkeypatch
) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)
    win.resize(1100, 800)
    win.show()

    img = QImage(16, 16, QImage.Format.Format_RGBA8888)
    img.fill(QColor("#2F5597"))
    img_path = tmp_path / "sample.png"
    img.save(str(img_path), "PNG")

    monkeypatch.setattr(CommentDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(CommentDialog, "get_text", lambda self: "Audit note")
    monkeypatch.setattr(CommentDialog, "get_author", lambda self: "Tester")

    win.insert_shape("rect")
    win.insert_textbox()
    win.insert_picture(str(img_path))
    win.insert_comment()

    sheet = win.spreadsheet_view.model
    assert len(sheet.drawings) == 3
    assert sheet.get_comment(0, 0) is not None

    # Undo comment, picture, textbox
    win.undo()
    assert sheet.get_comment(0, 0) is None
    win.undo()
    assert len(sheet.drawings) == 2
    win.undo()
    assert len(sheet.drawings) == 1
    win.redo()
    win.redo()
    win.redo()
    assert len(sheet.drawings) == 3
    assert sheet.get_comment(0, 0) is not None

    # Interactive click/delete on object layer does not crash and returns focus cleanly
    layer = win.spreadsheet_view.object_layer
    rect = layer.get_object_rect(sheet.drawings[-1])
    QTest.mouseClick(layer, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, rect.center())
    QTest.keyClick(layer, Qt.Key.Key_Delete)
    assert len(sheet.drawings) == 2
    win.undo()
    assert len(sheet.drawings) == 3

    out = tmp_path / "objects.xlsx"
    assert win.save_file(out, confirm_overwrite=False) is True
    assert out.stat().st_size > 0

    reopened = LedgerWindow()
    qtbot.addWidget(reopened)
    assert reopened.open_file(out) is True
    assert reopened.spreadsheet_view.model.get_comment(0, 0) is not None
    assert len(reopened.spreadsheet_view.model.drawings) == 3
    win.set_modified(False)
    reopened.set_modified(False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_ledger_object_undo_and_robustness.py -v`
Expected: FAIL (`win.undo()` does not undo comment/drawing changes yet).

- [ ] **Step 3: Write minimal implementation**

1. In `src/atboffice/ui/shell/ledger_objects.py`, add `_record_drawing_edit` and use it in `insert_textbox`, `insert_shape`, `insert_image_bytes`, `bring_to_front`, `send_to_back`, `_apply_drawing_fill_color`, and `open_chart_wizard`:

```python
    def _record_drawing_edit(self, label: str, mutate: Any) -> Any:
        """Apply a sheet drawing mutation and record an UndoService snapshot step."""
        import copy as _copy

        sheet = getattr(self.spreadsheet_view, "model", None)
        layer = getattr(self.spreadsheet_view, "object_layer", None)
        svc = self.undo_service() if hasattr(self, "undo_service") else None
        if sheet is None or svc is None or not svc.is_recording:
            res = mutate()
            if layer is not None:
                layer.update()
            return res

        before = _copy.deepcopy(getattr(sheet, "drawings", []))
        with svc.paused():
            res = mutate()
        after = _copy.deepcopy(getattr(sheet, "drawings", []))

        def _restore(snapshot: list[Any]) -> None:
            sheet.drawings = _copy.deepcopy(snapshot)
            if layer is not None and getattr(layer, "model", None) is sheet:
                layer.set_model(sheet)
            self.spreadsheet_view.grid.viewport().update()

        if len(after) != len(before) or repr(after) != repr(before):
            svc.record(
                safe_tr(label),
                lambda s=before: _restore(s),
                lambda s=after: _restore(s),
            )
            self.set_modified(True)
        return res
```

Wrap `insert_textbox`, `insert_shape`, `insert_image_bytes`, `bring_to_front`, `send_to_back`, `_apply_drawing_fill_color`, and `open_chart_wizard` mutations in `self._record_drawing_edit(...)`:

```python
    def insert_textbox(self) -> None:
        """Insert floating text box at current selection."""
        sel = self.spreadsheet_view.selection
        r, c = sel.active_cell
        obj = FloatingObject(
            kind="textbox",
            text="TextBox",
            anchor_type=AnchorType.TWO_CELL,
            from_point=CellAnchorPoint(col=c, row=r),
            to_point=CellAnchorPoint(col=c + 2, row=r + 3),
        )

        def _add() -> None:
            self.spreadsheet_view.object_layer.add_object(obj)
            self.spreadsheet_view.object_layer.select_object(obj)

        self._record_drawing_edit("插入文本框", _add)
        self.set_modified(True)

    def insert_shape(self, kind: str = "rect") -> None:
        """Insert floating geometric shape at current selection."""
        sel = self.spreadsheet_view.selection
        r, c = sel.active_cell
        obj = FloatingObject(
            kind=kind,
            anchor_type=AnchorType.TWO_CELL,
            from_point=CellAnchorPoint(col=c, row=r),
            to_point=CellAnchorPoint(col=c + 2, row=r + 3),
        )

        def _add() -> None:
            self.spreadsheet_view.object_layer.add_object(obj)
            self.spreadsheet_view.object_layer.select_object(obj)

        self._record_drawing_edit("插入图形", _add)
        self.set_modified(True)
```

And in `insert_image_bytes`:

```python
        layer = self.spreadsheet_view.object_layer
        obj = FloatingObject(
            id=len(getattr(model, "drawings", []) or []) + 1,
            name=name or "Picture",
            kind="image",
            anchor_type=AnchorType.TWO_CELL,
            from_point=CellAnchorPoint(col=c, row=r),
            to_point=CellAnchorPoint(col=c + max(1, cols), row=r + max(1, rows)),
            image_data=data,
            image_mime=mime,
            lock_aspect=True,
        )

        def _add_img() -> None:
            layer.add_object(obj)
            layer.select_object(obj)

        self._record_drawing_edit("插入图片", _add_img)
        self.set_modified(True)
        return True
```

2. In `src/atboffice/ui/shell/ledger_auditing.py`, add `_record_comment_edit` and use it in `insert_comment` and `delete_comment`:

```python
    def _record_comment_edit(self, label: str, mutate: Any) -> Any:
        import copy as _copy

        sheet = self.spreadsheet_view.model
        svc = self.undo_service() if hasattr(self, "undo_service") else None
        if svc is None or not svc.is_recording:
            res = mutate()
            self.spreadsheet_view.grid.viewport().update()
            return res

        before_comments = _copy.deepcopy(sheet.comments)
        with svc.paused():
            res = mutate()
        after_comments = _copy.deepcopy(sheet.comments)

        def _restore_comments(snap: dict[Any, Any]) -> None:
            sheet.comments = _copy.deepcopy(snap)
            self.spreadsheet_view.grid.viewport().update()

        if after_comments != before_comments:
            svc.record(
                safe_tr(label),
                lambda s=before_comments: _restore_comments(s),
                lambda s=after_comments: _restore_comments(s),
            )
            self.set_modified(True)
        self.spreadsheet_view.grid.viewport().update()
        return res
```

3. In `src/atboffice/modules/spreadsheet/views/object_layer.py`, import `guard_qt_event` from `atboffice.core.fault_guard`, decorate `paintEvent`, `mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent`, and `keyPressEvent`, and record drawing snapshots via `_record_layer_snapshot`:

```python
    def _record_layer_snapshot(self, before: list[FloatingObject], label: str) -> None:
        sheet = self.model
        win = self.window()
        svc = win.undo_service() if hasattr(win, "undo_service") else None
        if sheet is None or svc is None or not svc.is_recording:
            return
        after = copy.deepcopy(getattr(sheet, "drawings", []))
        if len(after) == len(before) and repr(after) == repr(before):
            return

        def _restore(snap: list[FloatingObject]) -> None:
            sheet.drawings = copy.deepcopy(snap)
            self.set_model(sheet)
            grid = self._owner_grid()
            if grid is not None:
                grid.viewport().update()

        svc.record(
            safe_tr(label),
            lambda s=before: _restore(s),
            lambda s=after: _restore(s),
        )
        if hasattr(win, "set_modified"):
            win.set_modified(True)
```

Call `before = copy.deepcopy(getattr(self.model, "drawings", []))` before `remove_object`/`add_object`/drag start, and call `self._record_layer_snapshot(before, "删除对象" / "粘贴对象" / "调整对象")` after `delete_selected()`, `paste()`, and `mouseReleaseEvent()` when `_drag_mode != HandleType.NONE`.

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_ledger_object_undo_and_robustness.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/ui/shell/ledger_objects.py src/atboffice/ui/shell/ledger_auditing.py src/atboffice/modules/spreadsheet/views/object_layer.py tests/gui/test_ledger_object_undo_and_robustness.py
git commit -m "fix(ledger): make object layer and comments undoable and guard object_layer events"
```

---

### Task 5: Harden Lectern `PresentationHistory` Timer/Snapshot Safety & `SlideScene` Lifecycle

**Files:**
- Modify: `src/atboffice/ui/shell/lectern_history.py:40-146`
- Modify: `src/atboffice/ui/shell/lectern_window.py:2038-2075`
- Modify: `src/atboffice/modules/presentation/views/slide_canvas.py:1-50,585-680`
- Create: `tests/gui/test_lectern_history_and_scene_robustness.py`

**Interfaces:**
- Consumes: `is_alive`, `safe_single_shot`, `guard_qt_event` (Task 2).
- Produces: `PresentationHistory.cancel_pending() -> None`, guarded `PresentationHistory.flush()`, `LecternWindow.cleanup_resources()` cancelling history timers, and `@guard_qt_event`-guarded `SlideScene` mouse handlers.

- [ ] **Step 1: Write the failing test**

Create `tests/gui/test_lectern_history_and_scene_robustness.py`:

```python
"""Tests for Lectern PresentationHistory timer cancellation and SlideScene lifecycle safety."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from atboffice.ui.shell.lectern_window import LecternWindow


def test_lectern_rapid_edit_and_close_does_not_flush_after_close(
    qtbot, qapp, caplog
) -> None:
    win = LecternWindow()
    qtbot.addWidget(win)
    win.resize(1100, 800)
    win.show()
    qapp.processEvents()

    win.history.note_edit("canvas", "Edit before close")
    assert win.history._pending is True
    win.set_modified(False)
    win.close()
    qapp.processEvents()
    assert win.history._pending is False
    assert "Failed" not in caplog.text


def test_lectern_draw_shape_and_textbox_undo_redo_and_roundtrip(
    qtbot, qapp, tmp_path
) -> None:
    win = LecternWindow()
    qtbot.addWidget(win)
    win.resize(1100, 800)
    win.show()
    qapp.processEvents()

    ws = win.presentation_view.workspace
    canvas = ws.canvas_view
    slide = canvas.scene().slide
    initial_count = len(slide.shapes)

    win.set_drawing_tool({"kind": "shape", "geom": "rect"})
    QTest.mousePress(
        canvas.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(180, 160)
    )
    QTest.mouseMove(canvas.viewport(), QPoint(320, 260))
    QTest.mouseRelease(
        canvas.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(320, 260)
    )
    win.flush_pending_edits()

    win.set_drawing_tool({"kind": "textbox"})
    QTest.mousePress(
        canvas.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(120, 100)
    )
    QTest.mouseMove(canvas.viewport(), QPoint(260, 150))
    QTest.mouseRelease(
        canvas.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(260, 150)
    )
    win.flush_pending_edits()

    assert len(ws.current_slide.shapes) == initial_count + 2
    win.undo()
    assert len(ws.current_slide.shapes) == initial_count + 1
    win.redo()
    assert len(ws.current_slide.shapes) == initial_count + 2

    out = tmp_path / "shapes.pptx"
    assert win.save_file(out, confirm_overwrite=False) is True
    assert out.stat().st_size > 0
    win.set_modified(False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_lectern_history_and_scene_robustness.py -v`
Expected: FAIL because `win.close()` does not cancel `win.history._pending` (still True after close).

- [ ] **Step 3: Write minimal implementation**

1. Edit `src/atboffice/ui/shell/lectern_history.py`:
Import `logging` and `is_alive`, `safe_single_shot` from `atboffice.core.fault_guard`. Track `self._flush_timer: QTimer | None = None`, add `cancel_pending()`:

```python
    def cancel_pending(self) -> None:
        """Cancel any scheduled end-of-turn flush safely."""
        self._pending = False
        self._label = self._kind = None
        timer = getattr(self, "_flush_timer", None)
        self._flush_timer = None
        if timer is not None and is_alive(timer):
            try:
                timer.stop()
            except Exception:
                pass
```

Call `self.cancel_pending()` at the start of `reset()`. Replace `note_edit` and `flush` with:

```python
    def note_edit(self, kind: str = "edit", label: str | None = None) -> None:
        """Something may have changed the deck: record it at the end of this turn."""
        if (
            self._restoring
            or not self.service.is_recording
            or not is_alive(self)
            or not is_alive(self.window)
        ):
            return
        if label and not self._label:
            self._label = label
        if self._kind in (None, "edit"):
            self._kind = kind
        elif kind not in ("edit", self._kind):
            self._kind = "mixed"
        if not self._pending:
            self._pending = True
            self._flush_timer = safe_single_shot(0, self, self.flush)

    def flush(self) -> None:
        """Record the pending change now (before an undo, or at the end of the turn)."""
        self._flush_timer = None
        if not self._pending or not is_alive(self) or not is_alive(self.window):
            self._pending = False
            return
        self._pending = False
        label, kind = self._label, self._kind
        self._label = self._kind = None
        pres = self._presentation()
        if pres is not self._source:
            self.reset()
            return
        try:
            after = snapshot_presentation(pres)
        except Exception:
            logger.exception("Failed to snapshot presentation during undo recording")
            return
        if after == self._baseline:
            return
        before, self._baseline = self._baseline, after
        text = label or safe_tr(_KIND_LABELS.get(kind or "", "编辑"))
        merge_id = _MERGEABLE_KINDS.get(kind or "", -1)
        self.service.record(
            text,
            lambda: self._restore(before),
            lambda: self._restore(after),
            merge_id=merge_id,
            merge=_merge_steps if merge_id != -1 else None,
            data=kind,
        )
```

2. Edit `src/atboffice/ui/shell/lectern_window.py`:
Add `cleanup_resources` override calling `self.history.cancel_pending()` before `super().cleanup_resources()`:

```python
    def cleanup_resources(self) -> None:
        """Cancel pending history snapshots before base window teardown."""
        history = getattr(self, "history", None)
        if history is not None and hasattr(history, "cancel_pending"):
            history.cancel_pending()
        super().cleanup_resources()
```

3. Edit `src/atboffice/modules/presentation/views/slide_canvas.py`:
Import `guard_qt_event` and `is_alive` from `atboffice.core.fault_guard`, decorate `SlideScene.mousePressEvent`, `SlideScene.mouseMoveEvent`, and `SlideScene.mouseReleaseEvent` with `@guard_qt_event("lectern_scene", ...)`, and guard dragged-item access inside `mouseMoveEvent`:

```python
from atboffice.core.fault_guard import guard_qt_event, is_alive
```

```python
    @guard_qt_event("lectern_scene", "mouse_press")
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        ...

    @guard_qt_event("lectern_scene", "mouse_move")
    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        ...
        if is_dragging and is_alive(self._dragged_item):
            ...

    @guard_qt_event("lectern_scene", "mouse_release")
    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_lectern_history_and_scene_robustness.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/ui/shell/lectern_history.py src/atboffice/ui/shell/lectern_window.py src/atboffice/modules/presentation/views/slide_canvas.py tests/gui/test_lectern_history_and_scene_robustness.py
git commit -m "fix(lectern): guard PresentationHistory timers and SlideScene mouse lifecycle"
```

---

### Task 6: Wave 1 Cross-Editor Element-Insertion & Editing Robustness Acceptance Gate

**Files:**
- Create: `tests/gui/test_phase12_element_edit_robustness.py`

**Interfaces:**
- Consumes: All Wave 1 fixes from Tasks 1–5 and existing corpus documents in `tests/docs/`.
- Produces: Deterministic Wave 1 Gate test verifying 0 crashes, 0 uncaught exceptions, empty `crash.log`, and intact saved/reopened files across Quire, Ledger, and Lectern.

- [ ] **Step 1: Write the failing/gate test**

Create `tests/gui/test_phase12_element_edit_robustness.py`:

```python
"""Phase 12 Wave 1 gate: open real docx/xlsx/pptx, insert elements, edit, undo, save, reopen."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox

from atboffice.core.diagnostics import CrashDiagnostics
from atboffice.core.window_manager import WindowManager

DOCS = Path(__file__).resolve().parents[1] / "docs"

QUIRE_FILES = [
    DOCS / "word/docx/libreoffice__A019_min.docx",
    DOCS / "word/docx/openxml-sdk__bullet-complex.docx",
]
LEDGER_FILES = [
    DOCS / "excel/xlsx/libreoffice__cell-value.xlsx",
    DOCS / "excel/xlsx/libreoffice__totalsRowFunction.xlsx",
]
LECTERN_FILES = [
    DOCS / "powerpoint/pptx/libreoffice__master-slides.pptx",
    DOCS / "powerpoint/pptx/libreoffice__smartart-text.pptx",
]


@pytest.fixture
def guarded(qapp, tmp_path, monkeypatch):
    errors: list[str] = []
    prev_hook = sys.excepthook

    def hook(exc_type, exc, _tb):
        errors.append(f"{exc_type.__name__}: {exc}")

    sys.excepthook = hook
    crash = CrashDiagnostics(tmp_path / "crash.log")
    crash.enable()
    for name in ("critical", "warning", "information"):
        monkeypatch.setattr(QMessageBox, name, lambda *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Phase12", True))
    WindowManager.reset_instance()
    yield errors, tmp_path
    wm = WindowManager.get_instance()
    wm._is_quitting = True
    for win in list(wm.active_windows):
        win.set_modified(False)
        win.close()
    qapp.processEvents()
    WindowManager.reset_instance()
    sys.excepthook = prev_hook
    crash.disable()
    log = tmp_path / "crash.log"
    assert not log.exists() or log.read_text(encoding="utf-8").strip() == "", log.read_text()
    assert errors == []


def _png_bytes(tmp_path: Path) -> tuple[Path, bytes]:
    img = QImage(16, 16, QImage.Format.Format_RGBA8888)
    img.fill(QColor("#336699"))
    p = tmp_path / "probe.png"
    img.save(str(p), "PNG")
    return p, p.read_bytes()


def test_quire_open_insert_elements_edit_undo_save(qapp, guarded) -> None:
    from atboffice.ui.shell.quire_window import QuireWindow

    _errors, tmp_path = guarded
    _, png = _png_bytes(tmp_path)
    for idx, src in enumerate(p for p in QUIRE_FILES if p.exists()):
        win = QuireWindow()
        win.resize(1100, 800)
        win.show()
        assert win.open_file(src) is True
        canvas = win.writer_view.canvas_view
        canvas.insert_table(2, 2)
        win.insert_shape("rect")
        win.insert_shape("textbox")
        win.insert_image_bytes(png, "png", "probe")
        win.writer_view._on_new_comment()
        QTest.mouseClick(
            canvas.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(300, 200)
        )
        QTest.keyClicks(canvas, "Wave1Edit ")
        win.action_registry.trigger_action("bold")
        canvas.grab()
        for _ in range(4):
            win.undo()
        for _ in range(2):
            win.redo()
        out = tmp_path / f"quire_{idx}.docx"
        win._compat_confirmed = True
        assert win.save_file(out, confirm_overwrite=False) is True
        assert out.stat().st_size > 0
        again = QuireWindow()
        assert again.open_file(out) is True
        for w in (win, again):
            w.set_modified(False)
            w.close()
        qapp.processEvents()


def test_ledger_open_insert_elements_edit_undo_save(qapp, guarded, monkeypatch) -> None:
    from atboffice.modules.spreadsheet.dialogs.comment_dialog import CommentDialog
    from atboffice.ui.shell.ledger_window import LedgerWindow

    _errors, tmp_path = guarded
    img_path, _ = _png_bytes(tmp_path)
    monkeypatch.setattr(CommentDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(CommentDialog, "get_text", lambda self: "Cell note")
    monkeypatch.setattr(CommentDialog, "get_author", lambda self: "Tester")

    for idx, src in enumerate(p for p in LEDGER_FILES if p.exists()):
        win = LedgerWindow()
        win.resize(1100, 800)
        win.show()
        assert win.open_file(src) is True
        win.insert_shape("rect")
        win.insert_textbox()
        win.insert_picture(str(img_path))
        win.insert_comment()
        win.spreadsheet_view.model.set_cell_value(0, 0, '=INDIRECT("B1")')
        win.spreadsheet_view.grab()
        for _ in range(3):
            win.undo()
        for _ in range(2):
            win.redo()
        out = tmp_path / f"ledger_{idx}.xlsx"
        win._compat_confirmed = True
        assert win.save_file(out, confirm_overwrite=False) is True
        assert out.stat().st_size > 0
        again = LedgerWindow()
        assert again.open_file(out) is True
        for w in (win, again):
            w.set_modified(False)
            w.close()
        qapp.processEvents()


def test_lectern_open_insert_elements_edit_undo_save(qapp, guarded) -> None:
    from atboffice.ui.shell.lectern_window import LecternWindow

    _errors, tmp_path = guarded
    _, png = _png_bytes(tmp_path)
    for idx, src in enumerate(p for p in LECTERN_FILES if p.exists()):
        win = LecternWindow()
        win.resize(1100, 800)
        win.show()
        assert win.open_file(src) is True
        ws = win.presentation_view.workspace
        canvas = ws.canvas_view
        win.action_registry.trigger_action("newSlide")
        win.set_drawing_tool({"kind": "shape", "geom": "rect"})
        QTest.mousePress(
            canvas.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(180, 160)
        )
        QTest.mouseMove(canvas.viewport(), QPoint(300, 240))
        QTest.mouseRelease(
            canvas.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(300, 240)
        )
        win.insert_table(2, 2)
        win.insert_image_bytes(png, "png", "probe")
        win.insert_chart(edit_data=False)
        ws.insert_smartart("list")
        win.action_registry.trigger_action("insertComment")
        win.insert_wordart(png, {"text": "Wave1"})
        win.flush_pending_edits()
        ws.grab()
        for _ in range(4):
            win.undo()
        for _ in range(2):
            win.redo()
        out = tmp_path / f"lectern_{idx}.pptx"
        win._compat_confirmed = True
        assert win.save_file(out, confirm_overwrite=False) is True
        assert out.stat().st_size > 0
        again = LecternWindow()
        assert again.open_file(out) is True
        for w in (win, again):
            w.set_modified(False)
            w.close()
        qapp.processEvents()
```

- [ ] **Step 2: Run Gate 1 suite and CI checks**

Run:
```bash
conda run -n ATBOffice ruff check . && \
conda run -n ATBOffice ruff format --check . && \
conda run -n ATBOffice mypy src/atboffice/core && \
QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest \
  tests/test_lazy_imports_integrity.py \
  tests/core/test_fault_guard.py \
  tests/gui/test_quire_insert_shape_and_edit.py \
  tests/gui/test_ledger_object_undo_and_robustness.py \
  tests/gui/test_lectern_history_and_scene_robustness.py \
  tests/gui/test_phase12_element_edit_robustness.py \
  tests/gui/test_phase11_acceptance.py \
  tests/gui/test_undo_editors.py -v && \
QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest -n auto
```
Expected: All lint, type, Wave 1 gate tests, and full test suite PASS (exit code 0).

- [ ] **Step 3: Commit**

```bash
git add tests/gui/test_phase12_element_edit_robustness.py
git commit -m "test(acceptance): add Phase 12 Wave 1 cross-editor element-edit robustness gate"
```

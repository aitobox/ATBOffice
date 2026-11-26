"""AST and functional integrity tests for all lazy/inline imports in src/atboffice."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

from PySide6.QtWidgets import QDialog

from atboffice.modules.spreadsheet.calc.context import EvalContext, Ref
from atboffice.modules.spreadsheet.calc.fn_dynamic import fn_indirect

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
    ctx = EvalContext(current_sheet="Sheet1")
    ref = fn_indirect("B3", True, ctx=ctx)
    assert isinstance(ref, Ref)
    assert (ref.sheet, ref.r1, ref.c1, ref.r2, ref.c2) == ("Sheet1", 2, 1, 2, 1)

    range_ref = fn_indirect("A1:C4", True, ctx=ctx)
    assert isinstance(range_ref, Ref)
    assert (range_ref.sheet, range_ref.r1, range_ref.c1, range_ref.r2, range_ref.c2) == (
        "Sheet1",
        0,
        0,
        3,
        2,
    )


def test_ledger_comment_and_validation_resolve_without_import_error(qtbot, monkeypatch) -> None:
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

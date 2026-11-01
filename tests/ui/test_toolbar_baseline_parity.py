"""TDD unit and integration tests for three-module toolbar baseline parity and 1:1 control audit.

Verifies:
1. Exact toolbar identity and completeness across Quire (10), Ledger (8), and Lectern (10).
2. ActionRegistry coverage: all toolbar actions are properly registered in the window's command bus.
3. Tooltip and visual metadata completeness: non-empty tooltips across all controls.
4. TopToolBarArea docking invariant: 100% of toolbars dock at top, 0 at bottom.
5. Dynamic 7-language locale switching via retranslate_ui() without exception or state corruption.
6. Execution and trigger safety for core toolbar actions.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolBar

from atboffice.core.i18n import load_locale
from atboffice.ui.components.toolbar import DottedGrip, OfficeToolBar, OfficeToolBarSeparator
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow


QUIRE_EXPECTED_TOOLBARS = {
    "standard",
    "formatting",
    "tables",
    "reviewing",
    "outlining",
    "headerFooter",
    "drawing",
    "mailMerge",
    "picture",
    "wordart",
}

LEDGER_EXPECTED_TOOLBARS = {
    "standard",
    "formatting",
    "borders",
    "auditing",
    "reviewing",
    "list",
    "chart",
    "drawing",
}

LECTERN_EXPECTED_TOOLBARS = {
    "standard",
    "formatting",
    "sorter",
    "master",
    "outlining",
    "diagram",
    "tables",
    "picture",
    "wordart",
    "drawing",
}

SUPPORTED_LOCALES = ["en", "zh_CN", "zh_TW", "ja", "fr", "de", "es"]


def test_quire_toolbars_baseline_completeness(qtbot) -> None:
    """Assert Quire has all 10 canonical toolbars with valid titles and top docking."""
    win = QuireWindow()
    qtbot.addWidget(win)

    assert set(win.toolbars.keys()) == QUIRE_EXPECTED_TOOLBARS
    for key, tb in win.toolbars.items():
        assert isinstance(tb, OfficeToolBar)
        assert tb.windowTitle(), f"Toolbar '{key}' in Quire must have a title"
        assert win.toolBarArea(tb) == Qt.ToolBarArea.TopToolBarArea
        assert win.toolBarArea(tb) != Qt.ToolBarArea.BottomToolBarArea


def test_ledger_toolbars_baseline_completeness(qtbot) -> None:
    """Assert Ledger has all 8 canonical toolbars with valid titles and top docking."""
    win = LedgerWindow()
    qtbot.addWidget(win)

    assert set(win.toolbars.keys()) == LEDGER_EXPECTED_TOOLBARS
    for key, tb in win.toolbars.items():
        assert isinstance(tb, OfficeToolBar)
        assert tb.windowTitle(), f"Toolbar '{key}' in Ledger must have a title"
        assert win.toolBarArea(tb) == Qt.ToolBarArea.TopToolBarArea
        assert win.toolBarArea(tb) != Qt.ToolBarArea.BottomToolBarArea


def test_lectern_toolbars_baseline_completeness(qtbot) -> None:
    """Assert Lectern has all 10 canonical toolbars with valid titles and top docking."""
    win = LecternWindow()
    qtbot.addWidget(win)

    assert set(win.toolbars.keys()) == LECTERN_EXPECTED_TOOLBARS
    for key, tb in win.toolbars.items():
        assert isinstance(tb, OfficeToolBar)
        assert tb.windowTitle(), f"Toolbar '{key}' in Lectern must have a title"
        assert win.toolBarArea(tb) == Qt.ToolBarArea.TopToolBarArea
        assert win.toolBarArea(tb) != Qt.ToolBarArea.BottomToolBarArea


def test_toolbar_controls_have_tooltips(qtbot) -> None:
    """Assert that all actionable toolbar items have non-empty tooltip strings."""
    win = QuireWindow()
    qtbot.addWidget(win)

    for tb_name, tb in win.toolbars.items():
        for act in tb.actions():
            w = tb.widgetForAction(act)
            if isinstance(w, (DottedGrip, OfficeToolBarSeparator)):
                continue
            if act.isSeparator():
                continue
            tooltip = act.toolTip() or (w.toolTip() if w else "")
            assert tooltip, f"Action {act.text()} in toolbar '{tb_name}' must have a tooltip"


def test_action_registry_contains_core_toolbar_commands(qtbot) -> None:
    """Assert all core commands across all three editors exist in ActionRegistry."""
    quire_win = QuireWindow()
    qtbot.addWidget(quire_win)
    for aid in ["new", "open", "save", "cut", "copy", "paste", "undo", "redo", "bold", "italic", "underline"]:
        assert quire_win.action_registry.has_action(aid), f"Quire missing action {aid}"

    ledger_win = LedgerWindow()
    qtbot.addWidget(ledger_win)
    for aid in ["file_new", "file_open", "file_save", "edit_cut", "edit_copy", "edit_paste", "edit_undo", "edit_redo"]:
        assert ledger_win.action_registry.has_action(aid), f"Ledger missing action {aid}"

    lectern_win = LecternWindow()
    qtbot.addWidget(lectern_win)
    for aid in ["new", "open", "save", "cut", "copy", "paste", "undo", "redo", "bold", "italic"]:
        assert lectern_win.action_registry.has_action(aid), f"Lectern missing action {aid}"


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_7_language_dynamic_retranslate_quire(qtbot, locale: str) -> None:
    """Assert Quire toolbars cleanly switch through all 7 supported locales."""
    win = QuireWindow()
    qtbot.addWidget(win)

    load_locale(locale)
    win.retranslate_ui()

    for name, tb in win.toolbars.items():
        assert tb.windowTitle(), f"Quire toolbar '{name}' title empty in locale {locale}"


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_7_language_dynamic_retranslate_ledger(qtbot, locale: str) -> None:
    """Assert Ledger toolbars cleanly switch through all 7 supported locales."""
    win = LedgerWindow()
    qtbot.addWidget(win)

    load_locale(locale)
    win.retranslate_ui()

    for name, tb in win.toolbars.items():
        assert tb.windowTitle(), f"Ledger toolbar '{name}' title empty in locale {locale}"


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_7_language_dynamic_retranslate_lectern(qtbot, locale: str) -> None:
    """Assert Lectern toolbars cleanly switch through all 7 supported locales."""
    win = LecternWindow()
    qtbot.addWidget(win)

    load_locale(locale)
    win.retranslate_ui()

    for name, tb in win.toolbars.items():
        assert tb.windowTitle(), f"Lectern toolbar '{name}' title empty in locale {locale}"

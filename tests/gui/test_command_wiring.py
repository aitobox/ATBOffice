"""Every visible command does something, and a failing command says so."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox

from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow

WINDOWS = (QuireWindow, LedgerWindow, LecternWindow)


@pytest.fixture
def make_window(qtbot, qapp):
    created = []

    def make(cls):
        win = cls()
        qtbot.addWidget(win)
        win.show()
        qapp.processEvents()
        created.append(win)
        return win

    yield make
    for win in created:
        win.set_modified(False)


@pytest.mark.parametrize("cls", WINDOWS)
def test_every_visible_action_has_a_command(make_window, cls) -> None:
    win = make_window(cls)
    reg = win.action_registry
    missing = [
        aid
        for aid, action in reg._actions.items()
        if action.isVisible() and not reg.has_command(aid)
    ]
    assert missing == []


def test_a_failing_command_shows_a_warning(make_window, monkeypatch) -> None:
    win = make_window(QuireWindow)
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: shown.append(a))

    def boom() -> None:
        raise RuntimeError("disk full")

    win.action_registry.set_handler("save", boom)
    win.action_registry.get_action("save").trigger()
    assert len(shown) == 1
    assert "disk full" in shown[0][2]


def test_binding_a_handler_shows_a_hidden_action_again(make_window) -> None:
    win = make_window(QuireWindow)
    reg = win.action_registry
    hidden = [
        aid for aid, a in reg._actions.items() if not a.isVisible() and not reg.has_command(aid)
    ]
    assert hidden, "Quire should hide the spreadsheet-only commands"
    aid = hidden[0]
    reg.set_handler(aid, lambda: None)
    assert reg.get_action(aid).isVisible()

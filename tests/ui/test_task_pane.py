"""Tests for TaskPaneDock and standard task panes."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from atboffice.ui.components.task_pane import (
    TaskPaneDock,
)
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow


def test_task_pane_dock_initialization(qtbot):
    """Verify TaskPaneDock default setup and default panes."""
    dock = TaskPaneDock()
    qtbot.addWidget(dock)

    assert dock.windowTitle() == "任务窗格"
    assert dock.current_pane_id() == "getting-started"
    assert dock.get_pane("getting-started") is not None
    assert dock.get_pane("new") is not None

    # Verify header button initial states
    assert not dock.header.btn_back.isEnabled()
    assert not dock.header.btn_fwd.isEnabled()
    assert dock.header.btn_home.isEnabled()
    assert "开始使用" in dock.header.btn_title.text()


def test_task_pane_navigation_stack(qtbot):
    """Verify history navigation (show_pane, go_back, go_forward, go_home)."""
    dock = TaskPaneDock()
    qtbot.addWidget(dock)

    # Add custom pane 1 and pane 2
    p1 = QLabel("Custom Pane 1")
    p2 = QLabel("Custom Pane 2")
    dock.register_pane("pane1", "窗格 1", p1)
    dock.register_pane("pane2", "窗格 2", p2)

    # Initial state: getting-started (pos = 0)
    assert dock.current_pane_id() == "getting-started"
    assert not dock.header.btn_back.isEnabled()

    # Navigate to pane1
    dock.show_pane("pane1")
    assert dock.current_pane_id() == "pane1"
    assert "窗格 1" in dock.header.btn_title.text()
    assert dock.header.btn_back.isEnabled()
    assert not dock.header.btn_fwd.isEnabled()

    # Navigate to pane2
    dock.show_pane("pane2")
    assert dock.current_pane_id() == "pane2"
    assert "窗格 2" in dock.header.btn_title.text()

    # Go back -> pane1
    dock.go_back()
    assert dock.current_pane_id() == "pane1"
    assert dock.header.btn_fwd.isEnabled()

    # Go back -> getting-started
    dock.go_back()
    assert dock.current_pane_id() == "getting-started"
    assert not dock.header.btn_back.isEnabled()

    # Go forward -> pane1
    dock.go_forward()
    assert dock.current_pane_id() == "pane1"

    # Go home -> default (getting-started)
    dock.go_home()
    assert dock.current_pane_id() == "getting-started"


def test_task_pane_menu_builder(qtbot):
    """Verify menu builder correctly lists registered panes with current item check."""
    dock = TaskPaneDock()
    qtbot.addWidget(dock)

    p_hidden = QLabel("Hidden Pane")
    dock.register_pane("hidden_p", "隐藏窗格", p_hidden, hidden=True)

    items = dock._build_menu_items()
    ids = [i[0] for i in items]
    assert "getting-started" in ids
    assert "new" in ids
    assert "hidden_p" not in ids

    # Check that currently active pane has is_current=True
    current_matches = [i for i in items if i[0] == "getting-started"]
    assert len(current_matches) == 1
    assert current_matches[0][2] is True


def test_getting_started_and_new_pane_signals(qtbot):
    """Verify built-in pane action link signals."""
    dock = TaskPaneDock()
    qtbot.addWidget(dock)

    actions = []
    dock.action_requested.connect(actions.append)

    # Click more in getting started
    with qtbot.waitSignal(dock.action_requested, timeout=1000):
        dock.pane_getting_started.btn_more.click()
    assert "open_file" in actions

    # Click switch to new
    dock.pane_getting_started.btn_create_new.click()
    assert dock.current_pane_id() == "new"

    # Test search submission
    dock.pane_getting_started.edit_search.setText("formatting")
    with qtbot.waitSignal(dock.action_requested, timeout=1000):
        dock.pane_getting_started.btn_go.click()
    assert "search:formatting" in actions


def test_task_pane_toggle_visibility(qtbot):
    """Verify toggle_task_pane hides/shows dock."""
    dock = TaskPaneDock()
    qtbot.addWidget(dock)

    dock.show()
    assert dock.isVisible()

    dock.toggle_task_pane()
    assert dock.isHidden()

    dock.toggle_task_pane("new")
    assert dock.isVisible()
    assert dock.current_pane_id() == "new"


def test_task_pane_dock_integration_in_shell_windows(qtbot):
    """Verify TaskPaneDock is properly mounted in Quire, Ledger, and Lectern windows."""
    # 1. Quire
    quire = QuireWindow()
    qtbot.addWidget(quire)
    quire.show()
    assert quire.task_pane_dock is not None
    assert quire.dockWidgetArea(quire.task_pane_dock) == Qt.DockWidgetArea.RightDockWidgetArea
    quire.toggle_task_pane()
    assert not quire.task_pane_dock.isHidden()
    quire.toggle_task_pane()
    assert quire.task_pane_dock.isHidden()

    # 2. Ledger
    ledger = LedgerWindow()
    qtbot.addWidget(ledger)
    assert ledger.task_pane_dock is not None
    assert ledger.dockWidgetArea(ledger.task_pane_dock) == Qt.DockWidgetArea.RightDockWidgetArea

    # 3. Lectern
    lectern = LecternWindow()
    qtbot.addWidget(lectern)
    assert lectern.task_pane_dock is not None
    assert lectern.dockWidgetArea(lectern.task_pane_dock) == Qt.DockWidgetArea.RightDockWidgetArea

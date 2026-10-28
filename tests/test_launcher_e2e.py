"""End-to-end integration tests for launcher lifecycle, document coordination, and resurrection."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtGui import QFileOpenEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from atboffice.__main__ import main
from atboffice.core.app import create_application
from atboffice.core.recent_files import RecentFilesManager
from atboffice.core.window_manager import WindowManager
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow
from atboffice.ui.shell.start_center import StartCenterWindow


@pytest.fixture(autouse=True)
def setup_e2e_env(tmp_path: Path) -> Generator[None, None, None]:
    """Ensure clean WindowManager and RecentFilesManager state for each E2E test."""
    app = QApplication.instance()
    if app is not None:
        if hasattr(app, "_pending_files"):
            getattr(app, "_pending_files").clear()
        if hasattr(app, "_main_window"):
            setattr(app, "_main_window", None)

    WindowManager.reset_instance()
    storage = tmp_path / "e2e_recent.json"
    rf_mgr = RecentFilesManager(storage_path=storage)
    rf_mgr.clear_all()
    wm = WindowManager.get_instance()
    wm.recent_files = rf_mgr

    yield

    # Clean up any opened windows to prevent leakage across tests
    wm = WindowManager.get_instance()
    wm._is_quitting = True
    for win in list(wm.active_windows):
        try:
            win.set_modified(False)
            wm.unregister_window(win)
            win.close()
        except Exception:
            pass

    if wm.start_center is not None:
        try:
            wm.start_center.close()
        except Exception:
            pass

    app = QApplication.instance()
    if app is not None:
        if hasattr(app, "_pending_files"):
            getattr(app, "_pending_files").clear()
        if hasattr(app, "_main_window"):
            setattr(app, "_main_window", None)

    WindowManager.reset_instance()


def test_full_launch_open_close_resurrect_cycle(
    qtbot: pytest.QtBot, tmp_path: Path
) -> None:
    """Verify primary lifecycle: Start Center -> Quire -> Close -> Resurrect."""
    _app = create_application(["atboffice"])
    win_mgr = WindowManager.get_instance()

    # 1. Start Center shown
    sc = win_mgr.show_start_center()
    qtbot.addWidget(sc)
    assert sc.isVisible()

    # 2. Open Quire document -> Start Center hidden
    doc_path = tmp_path / "hello.docx"
    doc_path.touch()
    q_win = win_mgr.open_quire(doc_path)
    qtbot.addWidget(q_win)
    assert q_win.isVisible()
    assert not sc.isVisible()

    # 3. Close Quire document -> Start Center resurrected
    q_win.close()
    assert sc.isVisible()


def test_e2e_multi_document_coexistence_and_resurrection_order(
    qtbot: pytest.QtBot, tmp_path: Path
) -> None:
    """Verify multi-window coexistence and Start Center resurrection on last close."""
    _app = create_application(["atboffice"])
    win_mgr = WindowManager.get_instance()

    # 1. Show Start Center
    sc = win_mgr.show_start_center()
    qtbot.addWidget(sc)
    assert sc.isVisible()

    # 2. Open Quire, Ledger, and Lectern documents
    doc_quire = tmp_path / "report.docx"
    doc_quire.touch()
    q_win = win_mgr.open_quire(doc_quire)
    qtbot.addWidget(q_win)

    doc_ledger = tmp_path / "budget.xlsx"
    doc_ledger.touch()
    l_win = win_mgr.open_ledger(doc_ledger)
    qtbot.addWidget(l_win)

    doc_lectern = tmp_path / "slides.pptx"
    doc_lectern.touch()
    lec_win = win_mgr.open_lectern(doc_lectern)
    qtbot.addWidget(lec_win)

    # All document windows must be active and visible; Start Center must be hidden
    assert win_mgr.active_windows == {q_win, l_win, lec_win}
    assert len(win_mgr.active_windows) == 3
    assert q_win.isVisible()
    assert l_win.isVisible()
    assert lec_win.isVisible()
    assert not sc.isVisible()

    # 3. Close Quire -> 2 active windows remaining, Start Center still hidden
    q_win.close()
    assert win_mgr.active_windows == {l_win, lec_win}
    assert len(win_mgr.active_windows) == 2
    assert not sc.isVisible()

    # 4. Close Ledger -> 1 active window remaining, Start Center still hidden
    l_win.close()
    assert win_mgr.active_windows == {lec_win}
    assert len(win_mgr.active_windows) == 1
    assert not sc.isVisible()

    # 5. Close Lectern -> 0 active windows, Start Center resurrected
    lec_win.close()
    assert len(win_mgr.active_windows) == 0
    assert sc.isVisible()


def test_e2e_recent_files_recording_and_start_center_display(
    qtbot: pytest.QtBot, tmp_path: Path
) -> None:
    """Verify document open records to recents and populates Start Center on resurrect."""
    win_mgr = WindowManager.get_instance()

    # 1. Start with visible Start Center
    sc = win_mgr.show_start_center()
    qtbot.addWidget(sc)
    assert isinstance(sc, StartCenterWindow)
    assert sc.isVisible()

    # 2. Open Quire document
    doc1 = tmp_path / "contract.docx"
    doc1.touch()
    w1 = win_mgr.open_quire(doc1)
    qtbot.addWidget(w1)

    # 3. Open Ledger document
    doc2 = tmp_path / "revenue.xlsx"
    doc2.touch()
    w2 = win_mgr.open_ledger(doc2)
    qtbot.addWidget(w2)

    # Verify recent entries in memory & storage
    recent_items = win_mgr.recent_files.get_entries()
    assert len(recent_items) == 2
    paths = [item.path for item in recent_items]
    assert doc2.resolve() in paths
    assert doc1.resolve() in paths

    # 4. Close both windows to trigger Start Center resurrection
    w1.close()
    w2.close()
    assert sc.isVisible()

    # Start Center list widget must display the two recent files
    assert sc.recent_list_widget.count() == 2
    assert sc.recent_list_widget.isVisible()
    assert sc.empty_state_widget.isHidden()


def test_e2e_start_center_quick_launch_buttons(qtbot: pytest.QtBot) -> None:
    """Verify clicking quick launch buttons creates typed windows and hides Start Center."""
    win_mgr = WindowManager.get_instance()
    sc = win_mgr.show_start_center()
    qtbot.addWidget(sc)
    assert isinstance(sc, StartCenterWindow)
    assert sc.isVisible()

    # 1. Click Quire Quick Launch
    sc.btn_new_quire.click()
    assert len(win_mgr.active_windows) == 1
    q_win = next(iter(win_mgr.active_windows))
    qtbot.addWidget(q_win)
    assert isinstance(q_win, QuireWindow)
    assert q_win.isVisible()
    assert not sc.isVisible()

    # Close Quire and resurrect
    q_win.close()
    assert len(win_mgr.active_windows) == 0
    assert sc.isVisible()

    # 2. Click Ledger Quick Launch
    sc.btn_new_ledger.click()
    assert len(win_mgr.active_windows) == 1
    l_win = next(iter(win_mgr.active_windows))
    qtbot.addWidget(l_win)
    assert isinstance(l_win, LedgerWindow)
    assert l_win.isVisible()
    assert not sc.isVisible()

    # Close Ledger and resurrect
    l_win.close()
    assert len(win_mgr.active_windows) == 0
    assert sc.isVisible()

    # 3. Click Lectern Quick Launch
    sc.btn_new_lectern.click()
    assert len(win_mgr.active_windows) == 1
    lec_win = next(iter(win_mgr.active_windows))
    qtbot.addWidget(lec_win)
    assert isinstance(lec_win, LecternWindow)
    assert lec_win.isVisible()
    assert not sc.isVisible()

    # Close Lectern and resurrect
    lec_win.close()
    assert len(win_mgr.active_windows) == 0
    assert sc.isVisible()


def test_e2e_start_center_recent_item_activation(
    qtbot: pytest.QtBot, tmp_path: Path
) -> None:
    """Verify activating an item in recent files list opens the document."""
    win_mgr = WindowManager.get_instance()

    test_file = tmp_path / "quarterly_presentation.pptx"
    test_file.touch()

    # Seed recent files
    win_mgr.recent_files.add_file(test_file, "lectern")

    sc = win_mgr.show_start_center()
    qtbot.addWidget(sc)
    assert isinstance(sc, StartCenterWindow)
    assert sc.recent_list_widget.count() == 1

    first_item = sc.recent_list_widget.item(0)
    assert first_item is not None

    # Activate recent item via itemActivated signal
    sc.recent_list_widget.itemActivated.emit(first_item)

    assert len(win_mgr.active_windows) == 1
    opened_win = next(iter(win_mgr.active_windows))
    qtbot.addWidget(opened_win)
    assert isinstance(opened_win, LecternWindow)
    assert opened_win.current_file_path == test_file.resolve()
    assert not sc.isVisible()

    # Close document window -> Start Center resurrects
    opened_win.close()
    assert sc.isVisible()


def test_e2e_cli_router_main_launch(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    """Verify launching via CLI main() routes directly to document window."""
    win_mgr = WindowManager.get_instance()

    target_sheet = tmp_path / "accounts.xlsx"
    target_sheet.touch()

    # Invoke CLI main without starting blocking event loop
    ret = main(["atboffice", str(target_sheet)], exec_app=False)
    assert ret == 0

    assert len(win_mgr.active_windows) == 1
    win = next(iter(win_mgr.active_windows))
    qtbot.addWidget(win)
    assert isinstance(win, LedgerWindow)
    assert win.current_file_path == target_sheet.resolve()
    assert win.isVisible()

    # Closing CLI-opened window resurrects Start Center
    win.close()
    assert len(win_mgr.active_windows) == 0
    sc = win_mgr.start_center
    assert sc is not None
    qtbot.addWidget(sc)
    assert sc.isVisible()


def test_e2e_atomic_quit_application_cancellation_and_exit(
    qtbot: pytest.QtBot, tmp_path: Path
) -> None:
    """Verify quit_application atomically halts exit on cancel and closes cleanly on discard."""
    win_mgr = WindowManager.get_instance()

    f1 = tmp_path / "notes.txt"
    f1.touch()
    f2 = tmp_path / "data.csv"
    f2.touch()

    w1 = win_mgr.open_quire(f1)
    w2 = win_mgr.open_ledger(f2)
    qtbot.addWidget(w1)
    qtbot.addWidget(w2)

    assert len(win_mgr.active_windows) == 2

    # Mark w1 dirty
    w1.set_modified(True)

    # 1. Simulate Cancel on prompt
    with patch.object(
        QMessageBox,
        "warning",
        return_value=QMessageBox.StandardButton.Cancel,
    ):
        with patch.object(QApplication, "quit") as mock_quit:
            clean = win_mgr.quit_application()
            assert clean is False
            mock_quit.assert_not_called()
            assert len(win_mgr.active_windows) == 2

    # 2. Simulate Discard on prompt
    with patch.object(
        QMessageBox,
        "warning",
        return_value=QMessageBox.StandardButton.Discard,
    ):
        with patch.object(QApplication, "quit") as mock_quit:
            clean = win_mgr.quit_application()
            assert clean is True
            mock_quit.assert_called_once()
            assert len(win_mgr.active_windows) == 0


def test_e2e_mac_file_open_event_dispatch(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    """Verify application-level QFileOpenEvent (macOS Finder click) dispatches to WindowManager."""
    app = create_application(["atboffice"])
    win_mgr = WindowManager.get_instance()

    test_doc = tmp_path / "external_open.docx"
    test_doc.touch()

    # Show Start Center first
    sc = win_mgr.show_start_center()
    qtbot.addWidget(sc)
    assert sc.isVisible()

    # Connect signal to open file via WindowManager
    opened_paths: list[str] = []

    def handle_open(path: str) -> None:
        opened_paths.append(path)
        win_mgr.open_file_auto(path)

    app.file_open_requested.connect(handle_open)

    try:
        # Simulate macOS QFileOpenEvent
        open_ev = QFileOpenEvent(str(test_doc))
        app.event(open_ev)

        assert str(test_doc) in opened_paths
        assert len(win_mgr.active_windows) == 1
        doc_win = next(iter(win_mgr.active_windows))
        qtbot.addWidget(doc_win)
        assert isinstance(doc_win, QuireWindow)
        assert doc_win.isVisible()
        assert not sc.isVisible()

        # Close document window -> Start Center resurrects
        doc_win.close()
        assert sc.isVisible()
    finally:
        try:
            app.file_open_requested.disconnect(handle_open)
        except Exception:
            pass

"""Tests for WindowManager lifecycle, app routing, and auto-resurrection."""

from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from atboffice.core.recent_files import RecentFilesManager
from atboffice.core.window_manager import WindowManager
from atboffice.ui.shell.base_window import BaseOfficeWindow


@pytest.fixture(autouse=True)
def reset_window_manager(tmp_path: Path):
    """Ensure clean WindowManager singleton state for each test."""
    WindowManager.reset_instance()
    storage = tmp_path / "recent_test.json"
    RecentFilesManager(storage_path=storage).clear_all()
    yield
    WindowManager.reset_instance()


def test_window_manager_singleton():
    """Verify WindowManager singleton accessor and instance retrieval."""
    mgr1 = WindowManager.get_instance()
    mgr2 = WindowManager.get_instance()
    assert mgr1 is mgr2

    WindowManager.reset_instance()
    mgr3 = WindowManager.get_instance()
    assert mgr3 is not mgr1


def test_window_manager_detect_app_type():
    """Verify file extension routing to corresponding office module."""
    mgr = WindowManager()

    # Quire formats
    assert mgr.detect_app_type("doc.docx") == "quire"
    assert mgr.detect_app_type("sample.DOC") == "quire"
    assert mgr.detect_app_type("memo.odt") == "quire"
    assert mgr.detect_app_type("report.rtf") == "quire"
    assert mgr.detect_app_type("notes.txt") == "quire"
    assert mgr.detect_app_type(Path("/path/to/notes.TXT")) == "quire"

    # Ledger formats
    assert mgr.detect_app_type("sheet.xlsx") == "ledger"
    assert mgr.detect_app_type("calc.xls") == "ledger"
    assert mgr.detect_app_type("sheet.csv") == "ledger"
    assert mgr.detect_app_type("data.tsv") == "ledger"
    assert mgr.detect_app_type("table.ods") == "ledger"
    assert mgr.detect_app_type(Path("DATA.CSV")) == "ledger"

    # Lectern formats
    assert mgr.detect_app_type("slide.pptx") == "lectern"
    assert mgr.detect_app_type("deck.ppt") == "lectern"
    assert mgr.detect_app_type("pres.odp") == "lectern"
    assert mgr.detect_app_type(Path("SHOW.PPTX")) == "lectern"

    # Generic / Unknown formats
    assert mgr.detect_app_type("unknown.xyz") == "generic"
    assert mgr.detect_app_type("noextension") == "generic"
    assert mgr.detect_app_type("") == "generic"


def test_window_manager_register_and_resurrect(qtbot):
    """Closing the last active window resurrects the Start Center."""
    mgr = WindowManager()

    # Mock start center
    sc = BaseOfficeWindow()
    qtbot.addWidget(sc)
    mgr._start_center = sc
    sc.hide()

    w1 = BaseOfficeWindow()
    qtbot.addWidget(w1)
    mgr.register_window(w1)
    assert len(mgr.active_windows) == 1

    # Closing the only window should resurrect start center
    mgr.unregister_window(w1)
    assert len(mgr.active_windows) == 0
    assert sc.isVisible()


def test_window_manager_multiple_windows_lifecycle(qtbot):
    """Start Center is only resurrected when ALL active windows are closed."""
    mgr = WindowManager()

    sc = BaseOfficeWindow()
    qtbot.addWidget(sc)
    mgr._start_center = sc
    sc.hide()

    w1 = BaseOfficeWindow()
    w2 = BaseOfficeWindow()
    qtbot.addWidget(w1)
    qtbot.addWidget(w2)

    mgr.register_window(w1)
    mgr.register_window(w2)
    assert len(mgr.active_windows) == 2

    # Closing w1 should not resurrect start center yet
    mgr.unregister_window(w1)
    assert len(mgr.active_windows) == 1
    assert not sc.isVisible()

    # Closing w2 (last window) triggers resurrection
    mgr.unregister_window(w2)
    assert len(mgr.active_windows) == 0
    assert sc.isVisible()


def test_window_manager_signal_connection_on_window_closed(qtbot):
    """Window closeEvent triggers window_closed signal and unregisters."""
    mgr = WindowManager()

    sc = BaseOfficeWindow()
    qtbot.addWidget(sc)
    mgr._start_center = sc
    sc.hide()

    w1 = BaseOfficeWindow()
    qtbot.addWidget(w1)
    mgr.register_window(w1)
    assert w1 in mgr.active_windows

    # Trigger closeEvent directly
    w1.close()
    assert w1 not in mgr.active_windows
    assert sc.isVisible()


def test_window_manager_open_windows(qtbot, tmp_path: Path):
    """Test opening Quire, Ledger, and Lectern windows with path registration."""
    mgr = WindowManager()
    mgr.recent_files = RecentFilesManager(storage_path=tmp_path / "recents.json")

    # Start center should hide when a new window opens
    sc = mgr.show_start_center()
    qtbot.addWidget(sc)
    assert sc.isVisible()

    doc_path = tmp_path / "test.docx"
    doc_path.touch()

    win_quire = mgr.open_quire(doc_path)
    qtbot.addWidget(win_quire)
    assert win_quire in mgr.active_windows
    assert win_quire.current_file_path == doc_path.resolve()
    assert not sc.isVisible()

    # Recent files should be updated
    recent_entries = mgr.recent_files.get_entries()
    assert len(recent_entries) == 1
    assert recent_entries[0].app == "quire"
    assert recent_entries[0].path == doc_path.resolve()

    # Open Ledger
    sheet_path = tmp_path / "data.xlsx"
    sheet_path.touch()
    win_ledger = mgr.open_ledger(sheet_path)
    qtbot.addWidget(win_ledger)
    assert win_ledger in mgr.active_windows

    # Open Lectern
    pres_path = tmp_path / "pres.pptx"
    pres_path.touch()
    win_lectern = mgr.open_lectern(pres_path)
    qtbot.addWidget(win_lectern)
    assert win_lectern in mgr.active_windows

    assert len(mgr.active_windows) == 3


def test_window_manager_open_file_auto(qtbot, tmp_path: Path):
    """Test open_file_auto routes by file extension."""
    mgr = WindowManager()
    mgr.recent_files = RecentFilesManager(storage_path=tmp_path / "recents.json")

    f_doc = tmp_path / "doc.docx"
    f_doc.touch()
    w1 = mgr.open_file_auto(f_doc)
    qtbot.addWidget(w1)
    assert w1 in mgr.active_windows

    f_sheet = tmp_path / "sheet.csv"
    f_sheet.touch()
    w2 = mgr.open_file_auto(f_sheet)
    qtbot.addWidget(w2)
    assert w2 in mgr.active_windows

    f_generic = tmp_path / "random.xyz"
    f_generic.touch()
    w3 = mgr.open_file_auto(f_generic)
    qtbot.addWidget(w3)
    assert w3 in mgr.active_windows


def test_window_manager_quit_application_clean(qtbot):
    """quit_application succeeds when all windows are clean."""
    mgr = WindowManager()

    w1 = BaseOfficeWindow()
    w2 = BaseOfficeWindow()
    qtbot.addWidget(w1)
    qtbot.addWidget(w2)
    mgr.register_window(w1)
    mgr.register_window(w2)

    with patch.object(QApplication, "quit") as mock_quit:
        result = mgr.quit_application()
        assert result is True
        mock_quit.assert_called_once()
        assert len(mgr.active_windows) == 0


def test_window_manager_quit_application_cancelled_by_dirty_window(qtbot):
    """quit_application aborts immediately if user cancels saving a dirty window."""
    mgr = WindowManager()

    w1 = BaseOfficeWindow()
    w2 = BaseOfficeWindow()
    qtbot.addWidget(w1)
    qtbot.addWidget(w2)
    mgr.register_window(w1)
    mgr.register_window(w2)

    w1.set_modified(True)

    # Simulate user clicking Cancel in QMessageBox
    with patch.object(
        QMessageBox,
        "warning",
        return_value=QMessageBox.StandardButton.Cancel,
    ):
        with patch.object(QApplication, "quit") as mock_quit:
            result = mgr.quit_application()
            assert result is False
            mock_quit.assert_not_called()
            # Windows must remain intact
            assert len(mgr.active_windows) == 2

    w1.set_modified(False)


def test_window_manager_quit_application_discard_dirty_window(qtbot):
    """quit_application proceeds if user discards changes on dirty window."""
    mgr = WindowManager()

    w1 = BaseOfficeWindow()
    qtbot.addWidget(w1)
    mgr.register_window(w1)
    w1.set_modified(True)

    with patch.object(
        QMessageBox,
        "warning",
        return_value=QMessageBox.StandardButton.Discard,
    ):
        with patch.object(QApplication, "quit") as mock_quit:
            result = mgr.quit_application()
            assert result is True
            mock_quit.assert_called_once()
            assert len(mgr.active_windows) == 0

"""GUI tests for macOS native shell, menu bar, and lifecycle management."""

from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtGui import QCloseEvent, QFileOpenEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QMessageBox

from atboffice.core.app import ATBApplication
from atboffice.ui.shell.mac_menu import MacMenuBar
from atboffice.ui.shell.main_window import MainWindow


class TestATBApplication:
    def test_app_retina_policy_and_init(self, qapp: ATBApplication) -> None:
        assert isinstance(qapp, QApplication)
        assert hasattr(qapp, "file_open_requested")
        assert hasattr(qapp, "register_main_window")

    def test_file_open_event_dispatch_and_queue(self, qapp: ATBApplication) -> None:
        qapp.register_main_window(None)
        qapp._pending_files.clear()
        received_files: list[str] = []
        qapp.file_open_requested.connect(received_files.append)

        # 1. Send event before main window is registered
        ev = QFileOpenEvent("sample_pending.xlsx")
        handled = qapp.event(ev)
        assert handled is True
        assert "sample_pending.xlsx" in received_files
        assert "sample_pending.xlsx" in qapp.pending_files

        # 2. Register main window and verify pending queue is flushed
        mock_window = MagicMock()
        mock_window.open_file.return_value = True
        qapp.register_main_window(mock_window)

        mock_window.open_file.assert_called_with("sample_pending.xlsx")
        assert len(qapp.pending_files) == 0

        # 3. Send event while main window is registered
        ev2 = QFileOpenEvent("live_opened.xlsx")
        qapp.event(ev2)
        mock_window.open_file.assert_called_with("live_opened.xlsx")

        # Clean up
        qapp.register_main_window(None)
        qapp._pending_files.clear()


class TestMacMenuBar:
    def test_mac_menu_structure_and_shortcuts(self, qapp: ATBApplication, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        menu_bar = window.menuBar()
        assert isinstance(menu_bar, MacMenuBar)

        # Check menus
        actions = menu_bar.actions()
        menu_titles = [a.text() for a in actions]
        assert "文件" in menu_titles or "File" in menu_titles
        assert "编辑" in menu_titles or "Edit" in menu_titles
        assert "视图" in menu_titles or "View" in menu_titles
        assert "窗口" in menu_titles or "Window" in menu_titles
        assert "帮助" in menu_titles or "Help" in menu_titles

        # Check specific shortcuts
        action_map = menu_bar.action_map
        assert "file_new" in action_map
        assert "file_open" in action_map
        assert "file_save" in action_map
        assert "file_save_as" in action_map
        assert "file_close" in action_map
        assert "edit_undo" in action_map
        assert "edit_redo" in action_map
        assert "edit_cut" in action_map
        assert "edit_copy" in action_map
        assert "edit_paste" in action_map
        assert "edit_format_cells" in action_map

        # Check key bindings
        save_seq = QKeySequence(QKeySequence.StandardKey.Save).toString()
        save_as_seq = QKeySequence(QKeySequence.StandardKey.SaveAs).toString()
        ctrl_1_seq = QKeySequence("Ctrl+1").toString()
        assert action_map["file_save"].shortcut().toString() == save_seq
        assert action_map["file_save_as"].shortcut().toString() == save_as_seq
        assert action_map["edit_format_cells"].shortcut().toString() == ctrl_1_seq

    def test_menu_retranslate(self, qapp: ATBApplication, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        menu_bar = window.menuBar()
        assert isinstance(menu_bar, MacMenuBar)
        menu_bar.retranslate_ui()
        assert menu_bar.action_map["file_save"].text() != ""


class TestMainWindowLifecycle:
    def test_main_window_has_three_modules(self, qapp: ATBApplication, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        tabs = window.centralWidget()
        assert tabs.count() == 3

    def test_window_dirty_lifecycle(self, qapp: ATBApplication, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        assert window.is_modified is False
        assert window.isWindowModified() is False

        window.set_modified(True)
        assert window.is_modified is True
        assert window.isWindowModified() is True

        window.set_modified(False)
        assert window.is_modified is False
        assert window.isWindowModified() is False

    def test_open_file_and_save(self, qapp: ATBApplication, qtbot, tmp_path: Path) -> None:
        window = MainWindow()
        qtbot.addWidget(window)

        test_file = tmp_path / "test_ledger.xlsx"
        test_file.write_text("dummy")

        assert window.open_file(str(test_file)) is True
        assert window.current_file_path == test_file
        assert test_file.name in window.windowTitle()

        # Mark modified then save
        window.set_modified(True)
        assert window.save_file() is True
        assert window.is_modified is False

    def test_close_event_unmodified(self, qapp: ATBApplication, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.set_modified(False)

        close_event = QCloseEvent()
        window.closeEvent(close_event)
        assert close_event.isAccepted()

    def test_close_event_modified_cancel(self, qapp: ATBApplication, qtbot, monkeypatch) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.set_modified(True)

        # Simulate user clicking Cancel
        monkeypatch.setattr(
            QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.StandardButton.Cancel
        )

        close_event = QCloseEvent()
        window.closeEvent(close_event)
        assert not close_event.isAccepted()
        window.set_modified(False)

    def test_close_event_modified_discard(self, qapp: ATBApplication, qtbot, monkeypatch) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.set_modified(True)

        # Simulate user clicking Discard (Don't Save)
        monkeypatch.setattr(
            QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.StandardButton.Discard
        )

        close_event = QCloseEvent()
        window.closeEvent(close_event)
        assert close_event.isAccepted()

    def test_cli_file_open_dispatch(
        self, qapp: ATBApplication, tmp_path: Path, monkeypatch
    ) -> None:
        from atboffice import __main__ as main_entry

        test_file = tmp_path / "cli_opened.xlsx"
        test_file.write_text("data")

        monkeypatch.setattr(main_entry.MainWindow, "show", lambda self: None)

        exit_code = main_entry.main(["atboffice", str(test_file)], exec_app=False)
        assert exit_code == 0

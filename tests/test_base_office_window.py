"""Tests for BaseOfficeWindow lifecycle, dirty state, theme, and prompts."""

from pathlib import Path

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMessageBox

from atboffice.ui.shell.base_window import BaseOfficeWindow


def test_base_office_window_title_and_dirty(qtbot) -> None:
    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    assert not win.is_modified
    assert "[*]" in win.windowTitle()

    win.set_modified(True)
    assert win.is_modified
    assert win.isWindowModified()

    win.current_file_path = Path("/tmp/sample.docx")
    win.update_window_title()
    assert "sample.docx" in win.windowTitle()


def test_base_office_window_close_signal(qtbot) -> None:
    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    closed_signals: list[BaseOfficeWindow] = []
    win.window_closed.connect(closed_signals.append)

    ev = QCloseEvent()
    win.closeEvent(ev)
    assert ev.isAccepted()
    assert len(closed_signals) == 1
    assert closed_signals[0] is win


def test_base_office_window_theme_application(qtbot) -> None:
    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    assert win.current_theme == "blue"

    win.apply_theme("silver")
    assert win.current_theme == "silver"
    # Re-apply blue
    win.apply_theme("blue")
    assert win.current_theme == "blue"


def test_base_office_window_maybe_save_prompt_unmodified(qtbot) -> None:
    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    win.set_modified(False)
    # Should return True without showing any dialog
    assert win.maybe_save_prompt() is True


def test_base_office_window_maybe_save_prompt_save(qtbot, monkeypatch, tmp_path: Path) -> None:
    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    test_file = tmp_path / "saved_doc.docx"
    win.current_file_path = test_file
    win.set_modified(True)

    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.StandardButton.Save
    )

    assert win.maybe_save_prompt() is True
    assert win.is_modified is False
    assert test_file.exists()


def test_base_office_window_maybe_save_prompt_discard(qtbot, monkeypatch) -> None:
    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    win.set_modified(True)

    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.StandardButton.Discard
    )

    assert win.maybe_save_prompt() is True
    # Remains modified (didn't save)
    assert win.is_modified is True


def test_base_office_window_maybe_save_prompt_cancel(qtbot, monkeypatch) -> None:
    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    win.set_modified(True)

    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.StandardButton.Cancel
    )

    assert win.maybe_save_prompt() is False


def test_base_office_window_close_event_ignored_on_cancel(
    qtbot, monkeypatch
) -> None:
    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    win.set_modified(True)

    closed_signals: list[BaseOfficeWindow] = []
    win.window_closed.connect(closed_signals.append)

    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.StandardButton.Cancel
    )

    ev = QCloseEvent()
    win.closeEvent(ev)
    assert not ev.isAccepted()
    assert len(closed_signals) == 0


def test_base_office_window_save_file_as_cancel(qtbot, monkeypatch) -> None:
    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    win.set_modified(True)

    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *args, **kwargs: ("", "")
    )

    assert win.save_file() is False
    assert win.is_modified is True


def test_base_office_window_save_file_as_success(
    qtbot, monkeypatch, tmp_path: Path
) -> None:
    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    win.set_modified(True)
    target_file = tmp_path / "new_doc.docx"

    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(target_file), "")
    )

    assert win.save_file() is True
    assert win.is_modified is False
    assert win.current_file_path == target_file
    assert target_file.exists()


def test_base_office_window_save_file_as_prepopulates_path(
    qtbot, monkeypatch, tmp_path: Path
) -> None:
    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    existing_file = tmp_path / "existing.docx"
    win.current_file_path = existing_file

    from PySide6.QtWidgets import QFileDialog

    passed_paths: list[str] = []

    def fake_get_save_file_name(parent, title, default_path, filter_str):
        passed_paths.append(default_path)
        return (str(tmp_path / "new_name.docx"), "")

    monkeypatch.setattr(QFileDialog, "getSaveFileName", fake_get_save_file_name)

    assert win.save_file_as() is True
    assert passed_paths == [str(existing_file)]


def test_base_office_window_retranslate_ui(qtbot) -> None:
    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    win.current_file_path = Path("/tmp/sample.docx")
    win.retranslate_ui()
    assert "sample.docx" in win.windowTitle()


def test_base_office_window_custom_subclass(qtbot) -> None:
    class CustomWindow(BaseOfficeWindow):
        app_name = "Quire"

    win = CustomWindow()
    qtbot.addWidget(win)
    assert "Quire [*]" in win.windowTitle()

    win.current_file_path = Path("/tmp/notes.docx")
    win.update_window_title()
    assert "notes.docx — Quire [*]" in win.windowTitle()


def test_base_office_window_save_failure_handling(
    qtbot, monkeypatch, tmp_path: Path
) -> None:
    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    test_file = tmp_path / "protected.docx"
    win.current_file_path = test_file
    win.set_modified(True)

    # Simulate do_save raising PermissionError
    def failing_save(path: Path) -> bool:
        raise PermissionError("Permission denied")

    win.do_save = failing_save  # type: ignore[assignment]

    critical_called = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda *args, **kwargs: critical_called.append(True),
    )

    assert win.save_file() is False
    assert len(critical_called) == 1
    assert win.is_modified is True

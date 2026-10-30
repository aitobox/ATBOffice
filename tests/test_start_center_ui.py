"""Tests for StartCenterWindow UI components, recent files, and drag-drop support."""

from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QMessageBox, QPushButton

from atboffice.core.recent_files import RecentFilesManager
from atboffice.core.window_manager import WindowManager
from atboffice.ui.shell.start_center import StartCenterWindow


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path: Path):
    """Ensure clean WindowManager and RecentFilesManager state for each test."""
    WindowManager.reset_instance()
    storage = tmp_path / "test_recent.json"
    rf_mgr = RecentFilesManager(storage_path=storage)
    rf_mgr.clear_all()
    wm = WindowManager.get_instance()
    wm.recent_files = rf_mgr
    yield
    WindowManager.reset_instance()


def test_start_center_window_ui_init(qtbot):
    """Test initial UI setup and required widget attributes."""
    win = StartCenterWindow()
    qtbot.addWidget(win)

    assert win.acceptDrops() is True
    assert "Start Center" in win.windowTitle() or "启动中心" in win.windowTitle()
    assert isinstance(win.btn_new_quire, QPushButton)
    assert isinstance(win.btn_new_ledger, QPushButton)
    assert isinstance(win.btn_new_lectern, QPushButton)
    assert isinstance(win.btn_open_file, QPushButton)
    assert win.recent_list_widget is not None
    assert win.stacked_widget is not None


def test_start_center_drag_drop_accepts_urls(qtbot, tmp_path: Path):
    """Test dragEnterEvent accepts file URLs and ignores invalid mimes."""
    win = StartCenterWindow()
    qtbot.addWidget(win)

    sample_doc = tmp_path / "test.docx"
    sample_doc.touch()

    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(str(sample_doc))])

    event = QDragEnterEvent(
        QPoint(10, 10),
        Qt.DropAction.CopyAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    win.dragEnterEvent(event)
    assert event.isAccepted()

    # Reject non-URL mime data
    text_mime = QMimeData()
    text_mime.setText("plain text")
    reject_event = QDragEnterEvent(
        QPoint(10, 10),
        Qt.DropAction.CopyAction,
        text_mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    win.dragEnterEvent(reject_event)
    assert not reject_event.isAccepted()


def test_start_center_drop_event_opens_file(qtbot, tmp_path: Path):
    """Test dropEvent parses URLs and routes to WindowManager.open_file_auto."""
    win = StartCenterWindow()
    qtbot.addWidget(win)

    sample_file = tmp_path / "sample.xlsx"
    sample_file.touch()

    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(str(sample_file))])

    event = QDropEvent(
        QPoint(10, 10),
        Qt.DropAction.CopyAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    with patch.object(WindowManager.get_instance(), "open_file_auto") as mock_open:
        win.dropEvent(event)
        assert event.isAccepted()
        mock_open.assert_called_once_with(sample_file.resolve())


def test_start_center_navigation_toggle(qtbot):
    """Test switching between Recent Files and Templates view pages."""
    win = StartCenterWindow()
    qtbot.addWidget(win)

    assert win.stacked_widget.currentIndex() == 0  # Recent files default

    win.btn_nav_templates.click()
    assert win.stacked_widget.currentIndex() == 1

    win.btn_nav_recent.click()
    assert win.stacked_widget.currentIndex() == 0


def test_start_center_recent_files_listing_and_empty_state(qtbot, tmp_path: Path):
    """Test recent files list refresh and empty state visibility."""
    win = StartCenterWindow()
    qtbot.addWidget(win)
    win.show()

    wm = WindowManager.get_instance()
    wm.recent_files.clear_all()
    win.refresh_recent_files()

    assert win.recent_list_widget.count() == 0
    assert not win.empty_state_widget.isHidden()
    assert win.empty_state_widget.isVisible()
    assert not win.btn_clear_recent.isEnabled()

    # Add items
    file1 = tmp_path / "doc1.docx"
    file1.touch()
    wm.recent_files.add_file(file1, "quire")

    file2 = tmp_path / "sheet1.xlsx"
    file2.touch()
    wm.recent_files.add_file(file2, "ledger")

    win.refresh_recent_files()
    assert win.recent_list_widget.count() == 2
    assert win.empty_state_widget.isHidden()
    assert not win.empty_state_widget.isVisible()
    assert win.recent_list_widget.isVisible()
    assert win.btn_clear_recent.isEnabled()


def test_start_center_open_recent_item_existing(qtbot, tmp_path: Path):
    """Test activating an existing recent item opens the document."""
    win = StartCenterWindow()
    qtbot.addWidget(win)

    sample = tmp_path / "demo.docx"
    sample.touch()

    wm = WindowManager.get_instance()
    wm.recent_files.add_file(sample, "quire")
    win.refresh_recent_files()

    item = win.recent_list_widget.item(0)
    with patch.object(wm, "open_file_auto") as mock_open:
        win._on_recent_item_activated(item)
        mock_open.assert_called_once_with(sample.resolve())


def test_start_center_open_recent_item_missing_prompts_remove(qtbot, tmp_path: Path):
    """Test activating a missing file prompts user to remove it from history."""
    win = StartCenterWindow()
    qtbot.addWidget(win)

    missing = tmp_path / "deleted.docx"
    wm = WindowManager.get_instance()
    wm.recent_files.add_file(missing, "quire")
    win.refresh_recent_files()
    assert win.recent_list_widget.count() == 1

    item = win.recent_list_widget.item(0)

    # When user clicks Yes to remove
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        win._on_recent_item_activated(item)
        assert win.recent_list_widget.count() == 0
        assert len(wm.recent_files.get_entries()) == 0


def test_start_center_clear_recent_files(qtbot, tmp_path: Path):
    """Test clearing all recent files with confirmation."""
    win = StartCenterWindow()
    qtbot.addWidget(win)

    wm = WindowManager.get_instance()
    f1 = tmp_path / "f1.docx"
    f1.touch()
    wm.recent_files.add_file(f1, "quire")
    win.refresh_recent_files()
    assert win.recent_list_widget.count() == 1

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        win.btn_clear_recent.click()
        assert win.recent_list_widget.count() == 0
        assert len(wm.recent_files.get_entries()) == 0


def test_start_center_quick_launch_buttons(qtbot):
    """Test quick launch buttons invoke WindowManager factory methods."""
    win = StartCenterWindow()
    qtbot.addWidget(win)
    wm = WindowManager.get_instance()

    with patch.object(wm, "open_quire") as mock_quire:
        win.btn_new_quire.click()
        mock_quire.assert_called_once()

    with patch.object(wm, "open_ledger") as mock_ledger:
        win.btn_new_ledger.click()
        mock_ledger.assert_called_once()

    with patch.object(wm, "open_lectern") as mock_lectern:
        win.btn_new_lectern.click()
        mock_lectern.assert_called_once()


def test_start_center_open_file_dialog_success(qtbot, tmp_path: Path):
    """Test clicking open file button opens document when file is chosen."""
    win = StartCenterWindow()
    qtbot.addWidget(win)
    sample_file = tmp_path / "budget.xlsx"
    sample_file.touch()

    wm = WindowManager.get_instance()
    with patch(
        "atboffice.ui.shell.start_center.QFileDialog.getOpenFileName",
        return_value=(str(sample_file), "All Files (*)"),
    ), patch.object(wm, "open_file_auto") as mock_open:
        win.btn_open_file.click()
        mock_open.assert_called_once_with(sample_file.resolve())


def test_start_center_open_file_dialog_cancelled(qtbot):
    """Test clicking open file button does nothing when user cancels dialog."""
    win = StartCenterWindow()
    qtbot.addWidget(win)

    wm = WindowManager.get_instance()
    with patch(
        "atboffice.ui.shell.start_center.QFileDialog.getOpenFileName",
        return_value=("", ""),
    ), patch.object(wm, "open_file_auto") as mock_open:
        win.btn_open_file.click()
        mock_open.assert_not_called()


def test_start_center_remove_single_item(qtbot, tmp_path: Path):
    """Test removing a specific item via row remove button."""
    win = StartCenterWindow()
    qtbot.addWidget(win)

    wm = WindowManager.get_instance()
    f1 = tmp_path / "item1.docx"
    f1.touch()
    f2 = tmp_path / "item2.xlsx"
    f2.touch()
    wm.recent_files.add_file(f1, "quire")
    wm.recent_files.add_file(f2, "ledger")
    win.refresh_recent_files()
    assert win.recent_list_widget.count() == 2

    # Remove f1
    win._remove_recent_item(f1.resolve())
    assert win.recent_list_widget.count() == 1
    remaining_paths = [e.path for e in wm.recent_files.get_entries()]
    assert f1.resolve() not in remaining_paths
    assert f2.resolve() in remaining_paths


def test_start_center_retranslate_ui(qtbot):
    """Test retranslate_ui updates localized labels, titles, and refreshes recents."""
    win = StartCenterWindow()
    qtbot.addWidget(win)

    with patch.object(win, "refresh_recent_files") as mock_refresh:
        win.retranslate_ui()
        mock_refresh.assert_called_once()

    assert "ATBOffice" in win.windowTitle()
    assert win.lbl_recent_title.text() != ""
    assert win.lbl_templates_title.text() != ""
    assert win.btn_clear_recent.text() != ""


def test_start_center_recent_item_activated_invoked_exactly_once(qtbot, tmp_path: Path):
    """Test activating a recent item emits itemActivated and opens document exactly once."""
    win = StartCenterWindow()
    qtbot.addWidget(win)

    sample = tmp_path / "single_open.docx"
    sample.touch()

    wm = WindowManager.get_instance()
    wm.recent_files.add_file(sample, "quire")
    win.refresh_recent_files()

    item = win.recent_list_widget.item(0)
    with patch.object(wm, "open_file_auto") as mock_open:
        win.recent_list_widget.itemActivated.emit(item)
        assert mock_open.call_count == 1


def test_start_center_template_card_mouse_press(qtbot):
    """Test TemplateCard triggers callback on LeftButton mouse press with QMouseEvent."""
    from unittest.mock import MagicMock

    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QMouseEvent

    from atboffice.ui.shell.start_center import TemplateCard

    mock_cb = MagicMock()
    card = TemplateCard("Test", "Subtitle", "📄", mock_cb)
    qtbot.addWidget(card)

    left_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(10.0, 10.0),
        QPointF(10.0, 10.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    card.mousePressEvent(left_event)
    mock_cb.assert_called_once()


def test_start_center_settings_and_about(qtbot):
    """Test settings and about buttons triggers without error."""
    win = StartCenterWindow()
    qtbot.addWidget(win)

    with patch.object(win, "show_options_dialog") as mock_opts:
        win.btn_settings.click()
        mock_opts.assert_called_once()

    with patch.object(win, "show_about") as mock_about:
        win.btn_about.click()
        mock_about.assert_called_once()


def test_start_center_window_manager_show(qtbot):
    """Test WindowManager.show_start_center instantiates StartCenterWindow."""
    wm = WindowManager.get_instance()
    sc = wm.show_start_center()
    qtbot.addWidget(sc)

    assert isinstance(sc, StartCenterWindow)
    assert sc.isVisible()
    assert wm.start_center is sc

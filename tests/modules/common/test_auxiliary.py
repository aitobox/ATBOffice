"""Unit tests for auxiliary components: Clipart, Scout Assistant, and Release Updater."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPixmap

from atboffice.core.updater import (
    UpdateCheckWorker,
    UpdateDialog,
    VersionInfo,
    compare_versions,
)
from atboffice.modules.common.assistant_scout import (
    ScoutBalloon,
    ScoutWidget,
    get_scout_assistant,
    toggle_assistant,
)
from atboffice.modules.common.clipart_dialog import (
    CLIPART_DATABASE,
    ClipartCategory,
    ClipartDialog,
    ClipartItem,
    get_clipart_by_id,
    render_clipart_pixmap,
    search_clipart,
)

# ============================================================================
# 1. Clipart Gallery Tests
# ============================================================================


def test_clipart_database_integrity():
    """Verify that all 24 built-in vector cliparts are properly configured."""
    assert len(CLIPART_DATABASE) == 24

    for item in CLIPART_DATABASE:
        assert isinstance(item, ClipartItem)
        assert item.id.startswith("clip")
        assert len(item.name_en) > 0
        assert len(item.name_zh) > 0
        assert item.category in ClipartCategory
        assert "<path" in item.svg_body or "<rect" in item.svg_body or "<circle" in item.svg_body
        xml = item.to_svg_xml()
        assert xml.startswith("<svg") and xml.endswith("</svg>")


def test_clipart_search_and_filter():
    """Verify search by keyword (EN/ZH) and filtering by category."""
    # Search by English keyword
    results_rocket = search_clipart("rocket")
    assert any(c.id == "clip2" for c in results_rocket)

    # Search by Chinese keyword
    results_bulb = search_clipart("灯泡")
    assert any(c.id == "clip0" for c in results_bulb)

    # Empty search query returns all
    assert len(search_clipart("")) == 24

    # Category filtering
    biz_items = search_clipart("", category=ClipartCategory.BUSINESS)
    assert len(biz_items) > 0
    assert all(c.category == ClipartCategory.BUSINESS for c in biz_items)

    tech_items = search_clipart("", category=ClipartCategory.TECHNOLOGY)
    assert len(tech_items) > 0
    assert all(c.category == ClipartCategory.TECHNOLOGY for c in tech_items)


def test_clipart_rendering(qapp):
    """Verify that vector clipart renders to QPixmap with crisp dimensions."""
    item = get_clipart_by_id("clip0")
    assert item is not None

    pixmap = render_clipart_pixmap(item, size=128)
    assert isinstance(pixmap, QPixmap)
    assert not pixmap.isNull()
    assert pixmap.width() == 128
    assert pixmap.height() == 128


def test_clipart_dialog_ui(qapp):
    """Verify ClipartDialog creation, filtering, and item selection."""
    dialog = ClipartDialog()
    assert dialog.windowTitle() != ""

    # Check category combo count
    assert dialog.combo_category.count() >= 5

    # Change search text
    dialog.edit_search.setText("Globe")
    assert dialog.list_widget.count() >= 1

    # Clear search
    dialog.edit_search.clear()
    assert dialog.list_widget.count() == 24

    # Select first item
    dialog.list_widget.setCurrentRow(0)
    selected = dialog.get_selected_clipart()
    assert selected is not None

    dialog.close()


# ============================================================================
# 2. Scout Desktop Assistant Tests
# ============================================================================


def test_scout_assistant_widget(qapp):
    """Verify ScoutWidget flags, animation timers, and balloon interaction."""
    scout = ScoutWidget()

    # Frameless and Stay on top flags
    flags = scout.windowFlags()
    assert bool(flags & Qt.WindowType.FramelessWindowHint)
    assert bool(flags & Qt.WindowType.Tool)

    # Size
    assert scout.width() >= 120
    assert scout.height() >= 120

    # Balloon creation
    assert scout.balloon is not None
    assert isinstance(scout.balloon, ScoutBalloon)
    assert not scout.balloon.isVisible()

    # Show speech
    scout.speak("Hello ATBOffice!")
    assert scout.balloon.isVisible()
    assert "Hello ATBOffice!" in scout.balloon.label_text.text()

    # Play trick animation
    scout.play_trick()
    assert scout.is_animating

    # Move and drag
    initial_pos = scout.pos()
    scout.move(initial_pos + QPoint(20, 20))
    assert scout.pos() == initial_pos + QPoint(20, 20)

    scout.close()


def test_scout_manager_singleton(qapp):
    """Verify global scout assistant singleton and toggle function."""
    scout1 = get_scout_assistant()
    scout2 = get_scout_assistant()
    assert scout1 is scout2

    # Test toggle
    is_visible = scout1.isVisible()
    toggle_assistant()
    assert scout1.isVisible() != is_visible
    toggle_assistant()
    assert scout1.isVisible() == is_visible

    scout1.hide()


# ============================================================================
# 3. Release Updater Tests
# ============================================================================


def test_updater_version_comparison():
    """Verify SemVer comparison logic for releases."""
    # Newer version
    assert compare_versions("0.4.0", "0.4.1") == 1
    assert compare_versions("v0.4.0", "v1.0.0") == 1
    assert compare_versions("0.4.0", "v0.5.0") == 1
    assert compare_versions("0.4.0-alpha", "0.4.0") == 1

    # Same version
    assert compare_versions("0.4.0", "0.4.0") == 0
    assert compare_versions("v0.4.0", "0.4.0") == 0
    assert compare_versions("1.2.3", "v1.2.3") == 0

    # Older version
    assert compare_versions("1.0.0", "0.9.9") == -1
    assert compare_versions("v2.1.0", "v2.0.9") == -1


def test_updater_worker_success(qapp):
    """Test UpdateCheckWorker successfully fetching a new version."""
    mock_payload = {
        "tag_name": "v99.0.0",
        "name": "ATBOffice 99.0.0 Mega Release",
        "body": "## What's Changed\n* Added amazing new features\n* Performance boost",
        "html_url": "https://github.com/aitobox/ATBOffice/releases/tag/v99.0.0",
        "published_at": "2026-10-31T12:00:00Z",
    }

    worker = UpdateCheckWorker(current_version="0.4.0")

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    results = []

    def on_complete(has_update: bool, info: VersionInfo):
        results.append((has_update, info))

    worker.check_completed.connect(on_complete)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        worker.run()

    assert len(results) == 1
    has_update, info = results[0]
    assert has_update is True
    assert info.version == "99.0.0"
    assert info.html_url == "https://github.com/aitobox/ATBOffice/releases/tag/v99.0.0"


def test_updater_worker_network_failure(qapp):
    """Test UpdateCheckWorker gracefully handling network errors."""
    worker = UpdateCheckWorker(current_version="0.4.0")
    errors = []

    def on_failed(err_msg: str):
        errors.append(err_msg)

    worker.check_failed.connect(on_failed)

    with patch("urllib.request.urlopen", side_effect=URLError("DNS resolution failed")):
        worker.run()

    assert len(errors) == 1
    assert "DNS resolution failed" in errors[0] or "网络" in errors[0]


def test_update_dialog_ui(qapp):
    """Verify UpdateDialog displays version info and release notes."""
    info = VersionInfo(
        version="1.0.0",
        tag_name="v1.0.0",
        name="ATBOffice 1.0.0 Official",
        body="Initial stable release with full feature parity.",
        html_url="https://github.com/aitobox/ATBOffice/releases/tag/v1.0.0",
        published_at="2026-10-31",
    )
    dlg = UpdateDialog(info, current_version="0.4.0")
    assert "1.0.0" in dlg.label_version.text()
    assert "Initial stable release" in dlg.text_notes.toPlainText()
    dlg.close()


def test_menu_and_base_window_integration(qapp):
    """Verify mac_menu actions and base_window slots integration."""
    from atboffice.ui.shell.base_window import BaseOfficeWindow
    from atboffice.ui.shell.mac_menu import MacMenuBar

    menu_bar = MacMenuBar()
    assert "insert_clipart" in menu_bar.action_map
    assert "help_assistant" in menu_bar.action_map
    assert "check_updates" in menu_bar.action_map

    # Verify BaseOfficeWindow has target methods
    assert hasattr(BaseOfficeWindow, "open_clipart_dialog")
    assert hasattr(BaseOfficeWindow, "toggle_assistant")
    assert hasattr(BaseOfficeWindow, "check_for_updates")

    # Verify slot connections
    mock_window = MagicMock()
    menu_bar._bind_window_slots(mock_window)

    menu_bar.action_map["insert_clipart"].trigger()
    mock_window.open_clipart_dialog.assert_called_once()

    menu_bar.action_map["help_assistant"].trigger()
    mock_window.toggle_assistant.assert_called_once()

    menu_bar.action_map["check_updates"].trigger()
    mock_window.check_for_updates.assert_called_once()

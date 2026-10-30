"""Tests for Options preferences dialog, AppSettings, and ThemeDialog."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from atboffice.core.i18n import get_i18n_manager, load_locale
from atboffice.core.settings import DEFAULT_SETTINGS, AppSettings, get_app_settings
from atboffice.core.window_manager import WindowManager
from atboffice.ui.dialogs.options_dialog import OptionsDialog
from atboffice.ui.dialogs.theme_dialog import ThemeDialog
from atboffice.ui.shell.base_window import BaseOfficeWindow
from atboffice.ui.shell.mac_menu import MacMenuBar
from atboffice.ui.shell.start_center import StartCenterWindow
from atboffice.ui.styles.luna_2003 import (
    THEMES,
    apply_luna_theme,
    apply_theme_globally,
    get_luna_stylesheet,
)


@pytest.fixture(autouse=True)
def clean_settings_and_locale(tmp_path: Path):
    """Ensure each test runs with a clean isolated QSettings scope and default locale."""
    # Use temporary file format / organization for testing
    org_name = "ATBOfficeTest"
    app_name = "ATBOfficeTestApp"
    AppSettings._instance = AppSettings(org_name, app_name)
    app_settings = AppSettings.get_instance()
    app_settings.reset_defaults()

    load_locale("zh-CN")

    yield app_settings

    # Cleanup
    qset = QSettings(org_name, app_name)
    qset.clear()
    qset.sync()
    AppSettings.reset_instance()
    load_locale("zh-CN")


def test_app_settings_get_set_defaults_and_reset(clean_settings_and_locale):
    """Verify AppSettings typed access, defaults fallback, and full reset."""
    settings = clean_settings_and_locale

    # Check defaults
    assert settings.get_value("general/recent_files_limit") == 20
    assert settings.get_value("save/auto_save_interval") == 10
    assert settings.get_value("theme/active_theme") == "blue"
    assert settings.get_value("edit/show_gridlines") is True

    # Mutate values
    settings.set_value("general/recent_files_limit", 35)
    settings.set_value("save/auto_save_interval", 25)
    settings.set_value("theme/active_theme", "silver")
    settings.set_value("edit/show_gridlines", False)

    assert settings.get_value("general/recent_files_limit") == 35
    assert settings.get_value("save/auto_save_interval") == 25
    assert settings.get_value("theme/active_theme") == "silver"
    assert settings.get_value("edit/show_gridlines") is False

    # Reset
    settings.reset_defaults()
    assert settings.get_value("general/recent_files_limit") == 20
    assert settings.get_value("save/auto_save_interval") == 10
    assert settings.get_value("theme/active_theme") == "blue"
    assert settings.get_value("edit/show_gridlines") is True


def test_options_dialog_init_and_tabs(qapp):
    """Verify OptionsDialog initializes with all 5 tabs and expected control states."""
    dialog = OptionsDialog()
    assert dialog.tab_widget.count() == 5
    assert dialog.tab_widget.tabText(0) in ("常规", "General")
    assert dialog.tab_widget.tabText(1) in ("视图", "View")
    assert dialog.tab_widget.tabText(2) in ("编辑", "Edit")
    assert dialog.tab_widget.tabText(3) in ("保存", "Save")
    assert dialog.tab_widget.tabText(4) in ("语言", "Language")

    assert dialog.spin_recent_limit.value() == 20
    assert dialog.spin_auto_save.value() == 10
    assert dialog.rb_start_center.isChecked()
    assert dialog.chk_show_gridlines.isChecked()


def test_options_dialog_modify_and_save_persistence(qapp):
    """Verify modifying fields in OptionsDialog updates AppSettings and WindowManager."""
    dialog = OptionsDialog()

    # Modify values
    dialog.spin_recent_limit.setValue(45)
    dialog.spin_auto_save.setValue(18)
    dialog.txt_default_path.setText("/tmp/test_workspace")
    dialog.rb_start_new_doc.setChecked(True)
    dialog.chk_show_gridlines.setChecked(False)

    dialog.save_to_settings()

    settings = get_app_settings()
    assert settings.get_value("general/recent_files_limit") == 45
    assert settings.get_value("save/auto_save_interval") == 18
    assert settings.get_value("general/default_open_path") == "/tmp/test_workspace"
    assert settings.get_value("general/start_behavior") == "new_doc"
    assert settings.get_value("edit/show_gridlines") is False

    # Check WindowManager recent files limit sync
    wm = WindowManager.get_instance()
    assert wm.recent_files.max_items == 45


def test_options_dialog_restore_defaults(qapp):
    """Verify Restore Defaults button resets dialog controls to defaults."""
    dialog = OptionsDialog()
    dialog.spin_recent_limit.setValue(99)
    dialog.spin_auto_save.setValue(59)
    dialog.rb_start_new_doc.setChecked(True)

    dialog._on_restore_defaults()

    assert dialog.spin_recent_limit.value() == DEFAULT_SETTINGS["general/recent_files_limit"]
    assert dialog.spin_auto_save.value() == DEFAULT_SETTINGS["save/auto_save_interval"]
    assert dialog.rb_start_center.isChecked()


def test_options_dialog_language_change_triggers_retranslate(qapp):
    """Verify switching language dynamically triggers retranslation across application."""
    dialog = OptionsDialog()

    # Switch to English
    idx_en = -1
    for i in range(dialog.combo_language.count()):
        if dialog.combo_language.itemData(i) == "en":
            idx_en = i
            break
    assert idx_en >= 0
    dialog.combo_language.setCurrentIndex(idx_en)
    dialog.save_to_settings()

    assert get_i18n_manager().current_locale == "en"
    assert dialog.windowTitle() == "Options"
    assert dialog.tab_widget.tabText(0) == "General"

    # Switch back to zh-CN
    idx_zh = -1
    for i in range(dialog.combo_language.count()):
        if dialog.combo_language.itemData(i) == "zh-CN":
            idx_zh = i
            break
    assert idx_zh >= 0
    dialog.combo_language.setCurrentIndex(idx_zh)
    dialog.save_to_settings()

    assert get_i18n_manager().current_locale == "zh-CN"
    assert dialog.tab_widget.tabText(0) == "常规"


def test_theme_dialog_cards_and_selection(qapp):
    """Verify ThemeDialog displays 4 cards, live preview, and acceptance."""
    theme_dialog = ThemeDialog()
    assert len(theme_dialog.cards) == 4
    for key in ("blue", "silver", "olive", "classic"):
        assert key in theme_dialog.cards

    # Select silver
    theme_dialog._on_card_selected("silver")
    assert theme_dialog.selected_theme == "silver"
    assert theme_dialog.cards["silver"].is_selected

    # Accept
    theme_dialog._on_accept()
    settings = get_app_settings()
    assert settings.get_value("theme/active_theme") == "silver"

    # Rejection restores previous theme
    theme_dialog2 = ThemeDialog()
    theme_dialog2._on_card_selected("olive")
    theme_dialog2._on_reject()
    assert settings.get_value("theme/active_theme") == "silver"


def test_theme_dialog_retranslate_ui(qapp):
    """Verify ThemeDialog handles dynamic language retranslation."""
    theme_dialog = ThemeDialog()
    load_locale("en")
    theme_dialog.retranslate_ui()
    assert theme_dialog.windowTitle() == "Themes" or "Theme" in theme_dialog.windowTitle()

    load_locale("zh-CN")
    theme_dialog.retranslate_ui()
    assert theme_dialog.windowTitle() == "外观主题选择器"


def test_apply_theme_globally_and_hot_reload(qapp):
    """Verify apply_theme_globally updates window themes across all 4 themes."""
    win = BaseOfficeWindow()
    win.show()

    # Blue
    apply_theme_globally("blue")
    assert win.current_theme == "blue"

    # Silver
    apply_theme_globally("silver")
    assert win.current_theme == "silver"

    # Olive
    apply_theme_globally("olive")
    assert win.current_theme == "olive"

    # Classic
    apply_theme_globally("classic")
    assert win.current_theme == "classic"

    # Verify stylesheet generation for all 4 themes
    for t in ("blue", "silver", "olive", "classic"):
        qss = get_luna_stylesheet(t)
        assert len(qss) > 200
        assert "QMainWindow" in qss
        assert "QToolBar" in qss

    win.close()
    apply_theme_globally("blue")


def test_start_center_settings_button_wiring(qapp):
    """Verify clicking settings button in Start Center opens OptionsDialog."""
    sc = StartCenterWindow()
    sc.show()

    with patch("atboffice.ui.dialogs.options_dialog.OptionsDialog.exec") as mock_exec:
        sc.btn_settings.click()
        assert mock_exec.called

    sc.close()


def test_mac_menu_tools_options_and_theme_actions(qapp):
    """Verify macOS menu bar has tools_options and all theme action handlers connected."""
    win = BaseOfficeWindow()
    win.action_registry = None
    menu = MacMenuBar(win)

    assert "tools_options" in menu.action_map
    assert "theme_selector" in menu.action_map
    assert "theme_luna_blue" in menu.action_map
    assert "theme_luna_silver" in menu.action_map
    assert "theme_luna_olive" in menu.action_map
    assert "theme_classic" in menu.action_map

    # Test triggering tools_options
    with patch.object(win, "show_options_dialog") as mock_opts:
        menu.action_map["tools_options"].trigger()
        assert mock_opts.called

    # Test triggering theme_selector
    with patch.object(win, "show_theme_dialog") as mock_theme_dlg:
        menu.action_map["theme_selector"].trigger()
        assert mock_theme_dlg.called

    # Test switching themes via menu
    menu.action_map["theme_luna_olive"].trigger()
    assert win.current_theme == "olive"

    menu.action_map["theme_classic"].trigger()
    assert win.current_theme == "classic"

    win.close()
    apply_theme_globally("blue")

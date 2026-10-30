"""Unit and integration tests for MacMenuBar 9-menu Office 2003 system and ActionRegistry sync."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QMainWindow

from atboffice.core.action_registry import ActionRegistry, ActionSpec
from atboffice.ui.shell.mac_menu import MacMenuBar, setup_mac_menu


@pytest.fixture
def qapp():
    """Ensure QApplication instance is initialized."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestMacMenuBarStructure:
    def test_quire_menu_structure(self, qapp) -> None:
        """Quire window must display 9 menus including Table menu."""
        win = QMainWindow()
        ar = ActionRegistry(win)
        win.action_registry = ar
        win.app_type = "quire"

        menu_bar = MacMenuBar(win, app_type="quire")
        titles = [a.text() for a in menu_bar.actions() if a.isVisible()]

        assert len(titles) == 9
        assert any(t in titles for t in ["文件", "File"])
        assert any(t in titles for t in ["编辑", "Edit"])
        assert any(t in titles for t in ["视图", "View"])
        assert any(t in titles for t in ["插入", "Insert"])
        assert any(t in titles for t in ["格式", "Format"])
        assert any(t in titles for t in ["工具", "Tools"])
        assert any(t in titles for t in ["表格", "Table"])
        assert any(t in titles for t in ["窗口", "Window"])
        assert any(t in titles for t in ["帮助", "Help"])

        # Table actions registered
        assert "table_draw" in menu_bar.action_map
        assert "table_insert" in menu_bar.action_map
        assert "table_merge" in menu_bar.action_map
        assert "table_split" in menu_bar.action_map
        assert "table_properties" in menu_bar.action_map

    def test_ledger_menu_structure(self, qapp) -> None:
        """Ledger window must display 9 menus including Data menu."""
        win = QMainWindow()
        ar = ActionRegistry(win)
        win.action_registry = ar
        win.app_type = "ledger"

        menu_bar = MacMenuBar(win, app_type="ledger")
        titles = [a.text() for a in menu_bar.actions() if a.isVisible()]

        assert len(titles) == 9
        assert any(t in titles for t in ["数据", "Data"])
        assert "data_sort_asc" in menu_bar.action_map
        assert "data_sort_desc" in menu_bar.action_map
        assert "data_filter" in menu_bar.action_map
        assert "data_validation" in menu_bar.action_map
        assert "data_subtotals" in menu_bar.action_map
        assert "data_pivottable" in menu_bar.action_map

        # Format cells visible in ledger
        assert menu_bar.action_map["edit_format_cells"].isVisible() is True

    def test_lectern_menu_structure(self, qapp) -> None:
        """Lectern window must display 9 menus including Slide Show menu."""
        win = QMainWindow()
        ar = ActionRegistry(win)
        win.action_registry = ar
        win.app_type = "lectern"

        menu_bar = MacMenuBar(win, app_type="lectern")
        titles = [a.text() for a in menu_bar.actions() if a.isVisible()]

        assert len(titles) == 9
        assert any(t in titles for t in ["幻灯片放映", "Slide Show"])
        assert "slideshow_start" in menu_bar.action_map
        assert "slideshow_current" in menu_bar.action_map
        assert "slideshow_setup" in menu_bar.action_map
        assert "slideshow_transition" in menu_bar.action_map

        # Format cells hidden in lectern
        assert menu_bar.action_map["edit_format_cells"].isVisible() is False

    def test_generic_menu_structure(self, qapp) -> None:
        """Generic window displays 8 menus without app-specific 7th menu."""
        win = QMainWindow()
        menu_bar = MacMenuBar(win, app_type="generic")
        titles = [a.text() for a in menu_bar.actions() if a.isVisible()]

        assert len(titles) == 8
        assert not any(t in titles for t in ["表格", "Table"])
        assert not any(t in titles for t in ["数据", "Data"])
        assert not any(t in titles for t in ["幻灯片放映", "Slide Show"])


class TestMacMenuBarDynamicSwitching:
    def test_set_app_type_switches_menu(self, qapp) -> None:
        """Dynamically switching app_type correctly replaces the 7th menu before Window."""
        win = QMainWindow()
        menu_bar = MacMenuBar(win, app_type="generic")
        assert len([a.text() for a in menu_bar.actions() if a.isVisible()]) == 8

        # Switch to quire -> 9 menus with Table
        menu_bar.set_app_type("quire")
        titles_quire = [a.text() for a in menu_bar.actions() if a.isVisible()]
        assert len(titles_quire) == 9
        assert titles_quire[6] == "表格" or "Table" in titles_quire[6]
        assert titles_quire[7] == "窗口" or "Window" in titles_quire[7]

        # Switch to ledger -> 9 menus with Data
        menu_bar.set_app_type("ledger")
        titles_ledger = [a.text() for a in menu_bar.actions() if a.isVisible()]
        assert len(titles_ledger) == 9
        assert titles_ledger[6] == "数据" or "Data" in titles_ledger[6]
        assert titles_ledger[7] == "窗口" or "Window" in titles_ledger[7]

        # Switch to lectern -> 9 menus with Slide Show
        menu_bar.set_app_type("lectern")
        titles_lectern = [a.text() for a in menu_bar.actions() if a.isVisible()]
        assert len(titles_lectern) == 9
        assert titles_lectern[6] == "幻灯片放映" or "Slide Show" in titles_lectern[6]
        assert titles_lectern[7] == "窗口" or "Window" in titles_lectern[7]

        # Switch back to generic -> 8 menus
        menu_bar.set_app_type("generic")
        titles_generic = [a.text() for a in menu_bar.actions() if a.isVisible()]
        assert len(titles_generic) == 8


class TestMacMenuBarActionRegistrySync:
    def test_shared_action_instances(self, qapp) -> None:
        """Actions in menu bar are shared with ActionRegistry."""
        win = QMainWindow()
        ar = ActionRegistry(win)
        win.action_registry = ar
        menu_bar = setup_mac_menu(win, app_type="quire")

        # Action from registry matches action in menu_bar
        act_new = ar.get_action("new")
        assert act_new is not None
        assert menu_bar.action_map["file_new"] is act_new
        assert menu_bar.action_map["new"] is act_new

    def test_bidirectional_enabled_and_checked_sync(self, qapp) -> None:
        """ActionRegistry enabled and checked state changes reflect in menu actions."""
        win = QMainWindow()
        ar = ActionRegistry(win)
        win.action_registry = ar
        menu_bar = setup_mac_menu(win, app_type="quire")

        act_save = menu_bar.action_map["file_save"]
        assert act_save.isEnabled() is True

        # Disable via registry
        ar.set_enabled("save", False)
        assert act_save.isEnabled() is False

        # Re-enable via registry
        ar.set_enabled("save", True)
        assert act_save.isEnabled() is True

        # Toggle checkable action
        act_bullets = menu_bar.action_map["format_bullets"]
        assert act_bullets.isChecked() is False
        ar.set_checked("bullets", True)
        assert act_bullets.isChecked() is True

    def test_retranslate_ui(self, qapp) -> None:
        """Retranslate updates all menu titles and action text."""
        win = QMainWindow()
        menu_bar = MacMenuBar(win, app_type="quire")
        menu_bar.retranslate_ui()

        for key, act in menu_bar.action_map.items():
            assert act.text() != ""

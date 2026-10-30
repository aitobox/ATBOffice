"""macOS native system menu bar and HIG-compliant shortcut dispatcher."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenu, QMenuBar

from atboffice.core.i18n import safe_tr as core_safe_tr

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMainWindow


def safe_tr(text: str) -> str:
    """Translate UI text safely for macOS menu bar."""
    return core_safe_tr(text)


class MacMenuBar(QMenuBar):
    """System menu bar adhering to Apple Human Interface Guidelines."""

    def __init__(
        self,
        parent: QMainWindow | None = None,
        app_type: str = "generic",
    ) -> None:
        super().__init__(parent)
        self.setNativeMenuBar(True)

        if app_type != "generic":
            self.app_type = app_type
        else:
            self.app_type = getattr(parent, "app_type", "generic")

        self.action_map: dict[str, QAction] = {}
        self.menu_map: dict[str, QMenu] = {}
        self.sep_format_cells: QAction | None = None

        self._build_menus()
        self.retranslate_ui()
        self._bind_window_slots(parent)

    def _update_format_cells_visibility(self) -> None:
        """Update visibility of format cells action and separator based on app context."""
        is_ledger = self.app_type == "ledger"
        if "edit_format_cells" in self.action_map:
            self.action_map["edit_format_cells"].setVisible(is_ledger)
        if self.sep_format_cells is not None:
            self.sep_format_cells.setVisible(is_ledger)

    def set_app_type(self, app_type: str) -> None:
        """Switch application context dynamically and update labels/visibility."""
        self.app_type = app_type
        self._update_format_cells_visibility()
        self.retranslate_ui()

    def _build_menus(self) -> None:
        """Create menu hierarchy and register standard actions."""
        # 1. File Menu
        menu_file = self.addMenu("")
        self.menu_map["file"] = menu_file

        self.action_map["file_new"] = menu_file.addAction("")
        self.action_map["file_new"].setShortcut(QKeySequence.StandardKey.New)

        self.action_map["file_open"] = menu_file.addAction("")
        self.action_map["file_open"].setShortcut(QKeySequence.StandardKey.Open)

        menu_file.addSeparator()

        self.action_map["file_save"] = menu_file.addAction("")
        self.action_map["file_save"].setShortcut(QKeySequence.StandardKey.Save)

        self.action_map["file_save_as"] = menu_file.addAction("")
        self.action_map["file_save_as"].setShortcut(QKeySequence.StandardKey.SaveAs)

        menu_file.addSeparator()

        self.action_map["file_close"] = menu_file.addAction("")
        self.action_map["file_close"].setShortcut(QKeySequence.StandardKey.Close)

        # 2. Edit Menu
        menu_edit = self.addMenu("")
        self.menu_map["edit"] = menu_edit

        self.action_map["edit_undo"] = menu_edit.addAction("")
        self.action_map["edit_undo"].setShortcut(QKeySequence.StandardKey.Undo)

        self.action_map["edit_redo"] = menu_edit.addAction("")
        self.action_map["edit_redo"].setShortcut(QKeySequence.StandardKey.Redo)

        menu_edit.addSeparator()

        self.action_map["edit_cut"] = menu_edit.addAction("")
        self.action_map["edit_cut"].setShortcut(QKeySequence.StandardKey.Cut)

        self.action_map["edit_copy"] = menu_edit.addAction("")
        self.action_map["edit_copy"].setShortcut(QKeySequence.StandardKey.Copy)

        self.action_map["edit_paste"] = menu_edit.addAction("")
        self.action_map["edit_paste"].setShortcut(QKeySequence.StandardKey.Paste)

        menu_edit.addSeparator()

        self.action_map["edit_find"] = menu_edit.addAction("")
        self.action_map["edit_find"].setShortcut(QKeySequence.StandardKey.Find)

        self.action_map["edit_replace"] = menu_edit.addAction("")
        self.action_map["edit_replace"].setShortcut(QKeySequence.StandardKey.Replace)

        self.sep_format_cells = menu_edit.addSeparator()

        self.action_map["edit_format_cells"] = menu_edit.addAction("")
        self.action_map["edit_format_cells"].setShortcut(QKeySequence("Ctrl+1"))
        self._update_format_cells_visibility()

        # 3. View Menu
        menu_view = self.addMenu("")
        self.menu_map["view"] = menu_view

        self.action_map["view_fullscreen"] = menu_view.addAction("")
        self.action_map["view_fullscreen"].setShortcut(
            QKeySequence.StandardKey.FullScreen
        )

        self.action_map["view_zoom_in"] = menu_view.addAction("")
        self.action_map["view_zoom_in"].setShortcut(QKeySequence.StandardKey.ZoomIn)

        self.action_map["view_zoom_out"] = menu_view.addAction("")
        self.action_map["view_zoom_out"].setShortcut(QKeySequence.StandardKey.ZoomOut)

        self.action_map["view_zoom_reset"] = menu_view.addAction("")
        self.action_map["view_zoom_reset"].setShortcut(QKeySequence("Ctrl+0"))

        menu_view.addSeparator()

        # Themes Sub-menu
        menu_theme = menu_view.addMenu("")
        self.menu_map["theme"] = menu_theme

        self.action_map["theme_luna_blue"] = menu_theme.addAction("")
        self.action_map["theme_luna_blue"].setCheckable(True)
        self.action_map["theme_luna_blue"].setChecked(True)

        self.action_map["theme_luna_silver"] = menu_theme.addAction("")
        self.action_map["theme_luna_silver"].setCheckable(True)

        # 4. Window Menu
        menu_window = self.addMenu("")
        self.menu_map["window"] = menu_window

        self.action_map["window_minimize"] = menu_window.addAction("")
        self.action_map["window_minimize"].setShortcut(QKeySequence("Ctrl+M"))

        self.action_map["window_zoom"] = menu_window.addAction("")

        menu_window.addSeparator()

        self.action_map["window_bring_all"] = menu_window.addAction("")

        # 5. Help Menu
        menu_help = self.addMenu("")
        self.menu_map["help"] = menu_help

        self.action_map["help_contents"] = menu_help.addAction("")
        self.action_map["help_contents"].setShortcut(
            QKeySequence.StandardKey.HelpContents
        )

        self.action_map["help_about"] = menu_help.addAction("")

    def _bind_window_slots(self, window: QMainWindow | None) -> None:
        """Bind action signals to target window callback handlers."""
        if window is None:
            return

        def connect_if(action_key: str, attr_name: str) -> None:
            if action_key in self.action_map and hasattr(window, attr_name):
                slot = getattr(window, attr_name)
                if callable(slot):
                    self.action_map[action_key].triggered.connect(slot)

        connect_if("file_new", "new_file")
        connect_if("file_open", "open_file_dialog")
        connect_if("file_save", "save_file")
        connect_if("file_save_as", "save_file_as")
        connect_if("file_close", "close")

        connect_if("edit_undo", "undo")
        connect_if("edit_redo", "redo")
        connect_if("edit_cut", "cut")
        connect_if("edit_copy", "copy")
        connect_if("edit_paste", "paste")
        connect_if("edit_find", "open_find_dialog")
        connect_if("edit_replace", "open_replace_dialog")
        connect_if("edit_format_cells", "format_cells")

        connect_if("view_fullscreen", "toggle_fullscreen")
        connect_if("view_zoom_in", "zoom_in")
        connect_if("view_zoom_out", "zoom_out")
        connect_if("view_zoom_reset", "zoom_reset")

        if "theme_luna_blue" in self.action_map and hasattr(window, "set_theme"):
            self.action_map["theme_luna_blue"].triggered.connect(
                lambda: window.set_theme("blue")
            )
        if "theme_luna_silver" in self.action_map and hasattr(window, "set_theme"):
            self.action_map["theme_luna_silver"].triggered.connect(
                lambda: window.set_theme("silver")
            )

        connect_if("window_minimize", "showMinimized")
        connect_if("window_zoom", "toggle_maximized")
        connect_if("window_bring_all", "raise_")

        connect_if("help_contents", "show_help")
        connect_if("help_about", "show_about")

    def retranslate_ui(self) -> None:
        """Translate all menus and actions dynamically."""
        self._update_format_cells_visibility()

        if "file" in self.menu_map:
            self.menu_map["file"].setTitle(safe_tr("文件"))
        if "edit" in self.menu_map:
            self.menu_map["edit"].setTitle(safe_tr("编辑"))
        if "view" in self.menu_map:
            self.menu_map["view"].setTitle(safe_tr("视图"))
        if "theme" in self.menu_map:
            self.menu_map["theme"].setTitle(safe_tr("主题"))
        if "window" in self.menu_map:
            self.menu_map["window"].setTitle(safe_tr("窗口"))
        if "help" in self.menu_map:
            self.menu_map["help"].setTitle(safe_tr("帮助"))

        if self.app_type == "quire":
            new_text, new_tip = safe_tr("新建文档"), safe_tr("创建空白文档")
            save_text, save_tip = safe_tr("保存当前文档"), safe_tr("保存当前文本文档")
            close_text, close_tip = safe_tr("关闭文档"), safe_tr("关闭当前文档窗口")
        elif self.app_type == "ledger":
            new_text, new_tip = safe_tr("新建工作簿"), safe_tr("创建空白工作簿")
            save_text, save_tip = safe_tr("保存当前工作簿"), safe_tr("保存当前电子表格")
            close_text, close_tip = safe_tr("关闭工作簿"), safe_tr("关闭当前工作簿窗口")
        elif self.app_type == "lectern":
            new_text, new_tip = safe_tr("新建演示文稿"), safe_tr("创建空白演示文稿")
            save_text, save_tip = safe_tr("保存当前演示文稿"), safe_tr("保存当前幻灯片演示")
            close_text, close_tip = safe_tr("关闭演示文稿"), safe_tr("关闭当前演示窗口")
        else:
            new_text, new_tip = safe_tr("新建"), safe_tr("创建新文件")
            save_text, save_tip = safe_tr("保存"), safe_tr("保存当前文件")
            close_text, close_tip = safe_tr("关闭"), safe_tr("关闭当前窗口")

        translations: dict[str, tuple[str, str]] = {
            "file_new": (new_text, new_tip),
            "file_open": (safe_tr("打开…"), safe_tr("打开现有文档或文件")),
            "file_save": (save_text, save_tip),
            "file_save_as": (safe_tr("另存为…"), safe_tr("将当前文件保存到新路径")),
            "file_close": (close_text, close_tip),
            "edit_undo": (safe_tr("撤销"), safe_tr("撤销上一步操作")),
            "edit_redo": (safe_tr("重做"), safe_tr("恢复撤销的操作")),
            "edit_cut": (safe_tr("剪切"), safe_tr("剪切选中内容")),
            "edit_copy": (safe_tr("复制"), safe_tr("复制选中内容")),
            "edit_paste": (safe_tr("粘贴"), safe_tr("粘贴剪贴板内容")),
            "edit_find": (safe_tr("查找…"), safe_tr("在当前文档或工作表中查找文本")),
            "edit_replace": (safe_tr("替换…"), safe_tr("查找并替换指定文本")),
            "edit_format_cells": (
                safe_tr("设置单元格格式…"),
                safe_tr("打开单元格格式设置对话框"),
            ),
            "view_fullscreen": (safe_tr("全屏切换"), safe_tr("进入或退出全屏模式")),
            "view_zoom_in": (safe_tr("放大"), safe_tr("放大视图")),
            "view_zoom_out": (safe_tr("缩小"), safe_tr("缩小视图")),
            "view_zoom_reset": (safe_tr("实际大小"), safe_tr("重置视图比例")),
            "theme_luna_blue": (
                safe_tr("Office 2003 经典蓝"),
                safe_tr("切换为经典 Luna 蓝色视觉风格"),
            ),
            "theme_luna_silver": (
                safe_tr("Office 2003 典雅银"),
                safe_tr("切换为经典 Luna 银色视觉风格"),
            ),
            "window_minimize": (safe_tr("最小化"), safe_tr("将窗口最小化到程序坞")),
            "window_zoom": (safe_tr("缩放窗口"), safe_tr("最大化或恢复窗口尺寸")),
            "window_bring_all": (
                safe_tr("前置全部窗口"),
                safe_tr("将应用程序所有窗口移到最前面"),
            ),
            "help_contents": (safe_tr("ATBOffice 帮助"), safe_tr("打开用户帮助文档")),
            "help_about": (safe_tr("关于 ATBOffice"), safe_tr("查看应用程序版本信息")),
        }

        for key, (text, tooltip) in translations.items():
            if key in self.action_map:
                action = self.action_map[key]
                action.setText(text)
                action.setToolTip(tooltip)
                action.setStatusTip(tooltip)


def setup_mac_menu(window: QMainWindow, app_type: str = "generic") -> MacMenuBar:
    """Configure native macOS menu bar on the given window."""
    menu_bar = MacMenuBar(window, app_type=app_type)
    window.setMenuBar(menu_bar)
    return menu_bar

"""macOS native system menu bar and HIG-compliant shortcut dispatcher."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenu, QMenuBar

from atboffice.core.action_registry import ActionRegistry, ActionSpec
from atboffice.core.i18n import safe_tr as core_safe_tr

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMainWindow


def safe_tr(text: str) -> str:
    """Translate UI text safely for macOS menu bar."""
    return core_safe_tr(text)


class MacMenuBar(QMenuBar):
    """System menu bar adhering to Apple HIG and Office 2003 9-menu layout."""

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

        # Connect or create centralized ActionRegistry
        has_reg = (
            parent is not None
            and hasattr(parent, "action_registry")
            and parent.action_registry is not None
        )
        if has_reg:
            self.action_registry: ActionRegistry = parent.action_registry
        else:
            self.action_registry = ActionRegistry(self)

        self.action_map: dict[str, QAction] = {}
        self.menu_map: dict[str, QMenu] = {}
        self.app_menu: QMenu | None = None
        self.sep_format_cells: QAction | None = None

        self._build_menus()
        self._update_app_menu()
        self.retranslate_ui()
        self._bind_window_slots(parent)

    def _reg_act(
        self,
        menu: QMenu,
        aid: str,
        alias: str | None = None,
        label: str = "",
        tip: str = "",
        shortcut: Any = None,
        checkable: bool = False,
        checked: bool = False,
        enabled: bool = True,
    ) -> QAction:
        """Register action in ActionRegistry, register aliases, and add to menu."""
        spec = ActionSpec(
            id=aid,
            label=label,
            tip=tip,
            shortcut=shortcut,
            checkable=checkable,
            checked=checked,
            enabled=enabled,
        )
        action = self.action_registry.register_action(spec, parent=self)
        menu.addAction(action)

        self.action_map[aid] = action
        if alias:
            self.action_map[alias] = action
            self.action_registry._actions[alias] = action

        return action

    def _update_format_cells_visibility(self) -> None:
        """Update visibility of format cells action and separator based on app context."""
        is_ledger = self.app_type == "ledger"
        if "edit_format_cells" in self.action_map:
            self.action_map["edit_format_cells"].setVisible(is_ledger)
        if "format_cells" in self.action_map:
            self.action_map["format_cells"].setVisible(is_ledger)
        if self.sep_format_cells is not None:
            self.sep_format_cells.setVisible(is_ledger)

    def _update_app_menu(self) -> None:
        """Dynamically attach application-specific 7th menu before Window menu."""
        if self.app_menu is not None:
            self.removeAction(self.app_menu.menuAction())
            self.app_menu = None

        target_menu_key: str | None = None
        if self.app_type == "quire":
            target_menu_key = "table"
        elif self.app_type == "ledger":
            target_menu_key = "data"
        elif self.app_type == "lectern":
            target_menu_key = "slideshow"

        if target_menu_key and target_menu_key in self.menu_map:
            new_menu = self.menu_map[target_menu_key]
            if "window" in self.menu_map:
                self.insertMenu(self.menu_map["window"].menuAction(), new_menu)
            else:
                self.addMenu(new_menu)
            self.app_menu = new_menu

    def set_app_type(self, app_type: str) -> None:
        """Switch application context dynamically and update labels/visibility."""
        self.app_type = app_type
        self._update_app_menu()
        self._update_format_cells_visibility()
        self.retranslate_ui()

    def _build_menus(self) -> None:
        """Create full Office 2003 9-menu hierarchy and register standard actions."""
        # 1. File Menu
        menu_file = self.addMenu("")
        self.menu_map["file"] = menu_file

        self._reg_act(
            menu_file, "new", "file_new", shortcut=QKeySequence.StandardKey.New
        )
        self._reg_act(
            menu_file, "open", "file_open", shortcut=QKeySequence.StandardKey.Open
        )
        menu_file.addSeparator()

        self._reg_act(
            menu_file, "save", "file_save", shortcut=QKeySequence.StandardKey.Save
        )
        self._reg_act(
            menu_file, "save_as", "file_save_as", shortcut=QKeySequence.StandardKey.SaveAs
        )
        menu_file.addSeparator()

        self._reg_act(
            menu_file, "print", "file_print", shortcut=QKeySequence.StandardKey.Print
        )
        self._reg_act(
            menu_file, "printPreview", "file_print_preview"
        )
        menu_file.addSeparator()

        self._reg_act(
            menu_file, "close", "file_close", shortcut=QKeySequence.StandardKey.Close
        )

        # 2. Edit Menu
        menu_edit = self.addMenu("")
        self.menu_map["edit"] = menu_edit

        self._reg_act(
            menu_edit, "undo", "edit_undo", shortcut=QKeySequence.StandardKey.Undo
        )
        self._reg_act(
            menu_edit, "redo", "edit_redo", shortcut=QKeySequence.StandardKey.Redo
        )
        menu_edit.addSeparator()

        self._reg_act(
            menu_edit, "cut", "edit_cut", shortcut=QKeySequence.StandardKey.Cut
        )
        self._reg_act(
            menu_edit, "copy", "edit_copy", shortcut=QKeySequence.StandardKey.Copy
        )
        self._reg_act(
            menu_edit, "paste", "edit_paste", shortcut=QKeySequence.StandardKey.Paste
        )
        menu_edit.addSeparator()

        self._reg_act(
            menu_edit,
            "selectAll",
            "edit_select_all",
            shortcut=QKeySequence.StandardKey.SelectAll,
        )
        self._reg_act(
            menu_edit, "find", "edit_find", shortcut=QKeySequence.StandardKey.Find
        )
        self._reg_act(
            menu_edit, "replace", "edit_replace", shortcut=QKeySequence.StandardKey.Replace
        )

        self.sep_format_cells = menu_edit.addSeparator()
        self._reg_act(
            menu_edit, "format_cells", "edit_format_cells", shortcut=QKeySequence("Ctrl+1")
        )

        # 3. View Menu
        menu_view = self.addMenu("")
        self.menu_map["view"] = menu_view

        self._reg_act(
            menu_view,
            "view_fullscreen",
            "view_fullscreen",
            shortcut=QKeySequence.StandardKey.FullScreen,
        )
        menu_view.addSeparator()

        self._reg_act(
            menu_view, "zoom_in", "view_zoom_in", shortcut=QKeySequence.StandardKey.ZoomIn
        )
        self._reg_act(
            menu_view, "zoom_out", "view_zoom_out", shortcut=QKeySequence.StandardKey.ZoomOut
        )
        self._reg_act(
            menu_view, "zoom_reset", "view_zoom_reset", shortcut=QKeySequence("Ctrl+0")
        )
        menu_view.addSeparator()

        # Themes Sub-menu
        menu_theme = menu_view.addMenu("")
        self.menu_map["theme"] = menu_theme

        self._reg_act(
            menu_theme, "theme_luna_blue", "theme_luna_blue", checkable=True, checked=True
        )
        self._reg_act(
            menu_theme, "theme_luna_silver", "theme_luna_silver", checkable=True, checked=False
        )
        self._reg_act(
            menu_theme, "theme_luna_olive", "theme_luna_olive", checkable=True, checked=False
        )
        self._reg_act(
            menu_theme, "theme_classic", "theme_classic", checkable=True, checked=False
        )
        menu_theme.addSeparator()
        self._reg_act(menu_theme, "theme_selector", "theme_selector")

        # 4. Insert Menu
        menu_insert = self.addMenu("")
        self.menu_map["insert"] = menu_insert

        self._reg_act(
            menu_insert,
            "insert_page_break",
            "insert_page_break",
            shortcut=QKeySequence("Ctrl+Return"),
        )
        self._reg_act(
            menu_insert,
            "insert_page_number",
            "insert_page_number",
            shortcut=QKeySequence("Alt+Shift+P"),
        )
        self._reg_act(
            menu_insert,
            "insert_date_time",
            "insert_date_time",
            shortcut=QKeySequence("Alt+Shift+D"),
        )
        self._reg_act(menu_insert, "insert_symbol", "insert_symbol")
        menu_insert.addSeparator()

        self._reg_act(menu_insert, "insert_picture", "insert_picture")
        self._reg_act(menu_insert, "insert_shape", "insert_shape")
        menu_insert.addSeparator()

        self._reg_act(
            menu_insert, "hyperlink", "insert_hyperlink", shortcut=QKeySequence("Ctrl+K")
        )

        # 5. Format Menu
        menu_format = self.addMenu("")
        self.menu_map["format"] = menu_format

        self._reg_act(
            menu_format, "format_font", "format_font", shortcut=QKeySequence("Ctrl+D")
        )
        self._reg_act(menu_format, "format_paragraph", "format_paragraph")
        menu_format.addSeparator()

        self._reg_act(menu_format, "bullets", "format_bullets", checkable=True)
        self._reg_act(menu_format, "numbering", "format_numbering", checkable=True)
        menu_format.addSeparator()

        self._reg_act(menu_format, "format_borders", "format_borders")
        self._reg_act(menu_format, "format_tabs", "format_tabs")
        self._reg_act(menu_format, "stylesPane", "format_styles")

        # 6. Tools Menu
        menu_tools = self.addMenu("")
        self.menu_map["tools"] = menu_tools

        self._reg_act(
            menu_tools, "spelling", "tools_spelling", shortcut=QKeySequence("F7")
        )
        self._reg_act(menu_tools, "tools_word_count", "tools_word_count")
        self._reg_act(menu_tools, "tools_language", "tools_language")
        menu_tools.addSeparator()

        self._reg_act(menu_tools, "tools_options", "tools_options")

        # 7. App-specific standalone menu instances (prepared but dynamically mounted)
        # 7a. Table Menu (Quire)
        menu_table = QMenu(self)
        self.menu_map["table"] = menu_table

        self._reg_act(menu_table, "drawTable", "table_draw")
        self._reg_act(menu_table, "table_insert", "table_insert")
        self._reg_act(menu_table, "table_delete", "table_delete")
        self._reg_act(menu_table, "table_select", "table_select")
        menu_table.addSeparator()
        self._reg_act(menu_table, "mergeCells", "table_merge")
        self._reg_act(menu_table, "splitCells", "table_split")
        menu_table.addSeparator()
        self._reg_act(menu_table, "table_properties", "table_properties")

        # 7b. Data Menu (Ledger)
        menu_data = QMenu(self)
        self.menu_map["data"] = menu_data

        self._reg_act(menu_data, "sortAsc", "data_sort_asc")
        self._reg_act(menu_data, "sortDesc", "data_sort_desc")
        menu_data.addSeparator()
        self._reg_act(menu_data, "data_filter", "data_filter")
        self._reg_act(menu_data, "data_validation", "data_validation")
        menu_data.addSeparator()
        self._reg_act(menu_data, "data_subtotals", "data_subtotals")
        self._reg_act(menu_data, "data_pivottable", "data_pivottable")

        # 7c. Slide Show Menu (Lectern)
        menu_slideshow = QMenu(self)
        self.menu_map["slideshow"] = menu_slideshow

        self._reg_act(
            menu_slideshow, "start_slideshow", "slideshow_start", shortcut=QKeySequence("F5")
        )
        self._reg_act(
            menu_slideshow,
            "start_slideshow_current",
            "slideshow_current",
            shortcut=QKeySequence("Shift+F5"),
        )
        menu_slideshow.addSeparator()
        self._reg_act(menu_slideshow, "slideshow_setup", "slideshow_setup")
        self._reg_act(menu_slideshow, "slideshow_record", "slideshow_record")
        self._reg_act(menu_slideshow, "slideshow_rehearse", "slideshow_rehearse")
        menu_slideshow.addSeparator()
        self._reg_act(menu_slideshow, "slideshow_transition", "slideshow_transition")

        # 8. Window Menu
        menu_window = self.addMenu("")
        self.menu_map["window"] = menu_window

        self._reg_act(
            menu_window, "window_minimize", "window_minimize", shortcut=QKeySequence("Ctrl+M")
        )
        self._reg_act(menu_window, "window_zoom", "window_zoom")
        menu_window.addSeparator()
        self._reg_act(menu_window, "window_bring_all", "window_bring_all")

        # 9. Help Menu
        menu_help = self.addMenu("")
        self.menu_map["help"] = menu_help

        self._reg_act(
            menu_help, "help", "help_contents", shortcut=QKeySequence.StandardKey.HelpContents
        )
        self._reg_act(menu_help, "about", "help_about")

    def _bind_window_slots(self, window: QMainWindow | None) -> None:
        """Bind action signals to target window callback handlers."""
        if window is None:
            return

        def connect_if(action_key: str, attr_name: str) -> None:
            if action_key in self.action_map and hasattr(window, attr_name):
                try:
                    self.action_map[action_key].triggered.connect(
                        lambda *args, w=window, a=attr_name: getattr(w, a)()
                    )
                except Exception:
                    pass

        connect_if("file_new", "new_file")
        connect_if("file_open", "open_file_dialog")
        connect_if("file_save", "save_file")
        connect_if("file_save_as", "save_file_as")
        connect_if("file_print", "print_document")
        connect_if("file_print", "print_workbook")
        connect_if("file_print_preview", "print_preview")
        connect_if("file_close", "close")

        connect_if("edit_undo", "undo")
        connect_if("edit_redo", "redo")
        connect_if("edit_cut", "cut")
        connect_if("edit_copy", "copy")
        connect_if("edit_paste", "paste")
        connect_if("edit_select_all", "select_all")
        connect_if("edit_find", "open_find_dialog")
        connect_if("edit_replace", "open_replace_dialog")
        connect_if("edit_format_cells", "format_cells")

        connect_if("view_fullscreen", "toggle_fullscreen")
        connect_if("view_zoom_in", "zoom_in")
        connect_if("view_zoom_out", "zoom_out")
        connect_if("view_zoom_reset", "zoom_reset")

        if hasattr(window, "set_theme"):
            if "theme_luna_blue" in self.action_map:
                self.action_map["theme_luna_blue"].triggered.connect(
                    lambda: window.set_theme("blue")
                )
            if "theme_luna_silver" in self.action_map:
                self.action_map["theme_luna_silver"].triggered.connect(
                    lambda: window.set_theme("silver")
                )
            if "theme_luna_olive" in self.action_map:
                self.action_map["theme_luna_olive"].triggered.connect(
                    lambda: window.set_theme("olive")
                )
            if "theme_classic" in self.action_map:
                self.action_map["theme_classic"].triggered.connect(
                    lambda: window.set_theme("classic")
                )

        if hasattr(window, "show_theme_dialog"):
            if "theme_selector" in self.action_map:
                self.action_map["theme_selector"].triggered.connect(
                    lambda *args, w=window: getattr(w, "show_theme_dialog")()
                )

        connect_if("tools_options", "show_options_dialog")

        connect_if("window_minimize", "showMinimized")
        connect_if("window_zoom", "toggle_maximized")
        connect_if("window_bring_all", "raise_")

        connect_if("help_contents", "show_help")
        connect_if("help_about", "show_about")

    def retranslate_ui(self) -> None:
        """Translate all menus and actions dynamically."""
        self._update_format_cells_visibility()

        # Top-level menu titles
        if "file" in self.menu_map:
            self.menu_map["file"].setTitle(safe_tr("文件"))
        if "edit" in self.menu_map:
            self.menu_map["edit"].setTitle(safe_tr("编辑"))
        if "view" in self.menu_map:
            self.menu_map["view"].setTitle(safe_tr("视图"))
        if "theme" in self.menu_map:
            self.menu_map["theme"].setTitle(safe_tr("主题"))
        if "insert" in self.menu_map:
            self.menu_map["insert"].setTitle(safe_tr("插入"))
        if "format" in self.menu_map:
            self.menu_map["format"].setTitle(safe_tr("格式"))
        if "tools" in self.menu_map:
            self.menu_map["tools"].setTitle(safe_tr("工具"))
        if "table" in self.menu_map:
            self.menu_map["table"].setTitle(safe_tr("表格"))
        if "data" in self.menu_map:
            self.menu_map["data"].setTitle(safe_tr("数据"))
        if "slideshow" in self.menu_map:
            self.menu_map["slideshow"].setTitle(safe_tr("幻灯片放映"))
        if "window" in self.menu_map:
            self.menu_map["window"].setTitle(safe_tr("窗口"))
        if "help" in self.menu_map:
            self.menu_map["help"].setTitle(safe_tr("帮助"))

        # App-contextual document labels
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
            # File
            "file_new": (new_text, new_tip),
            "new": (new_text, new_tip),
            "file_open": (safe_tr("打开…"), safe_tr("打开现有文档或文件")),
            "open": (safe_tr("打开…"), safe_tr("打开现有文档或文件")),
            "file_save": (save_text, save_tip),
            "save": (save_text, save_tip),
            "file_save_as": (safe_tr("另存为…"), safe_tr("将当前文件保存到新路径")),
            "save_as": (safe_tr("另存为…"), safe_tr("将当前文件保存到新路径")),
            "file_print": (safe_tr("打印…"), safe_tr("调用打印机配置打印文档")),
            "print": (safe_tr("打印…"), safe_tr("调用打印机配置打印文档")),
            "file_print_preview": (
                safe_tr("打印预览"),
                safe_tr("打开全功能交互式打印预览视口"),
            ),
            "printPreview": (
                safe_tr("打印预览"),
                safe_tr("打开全功能交互式打印预览视口"),
            ),
            "file_close": (close_text, close_tip),
            "close": (close_text, close_tip),
            # Edit
            "edit_undo": (safe_tr("撤销"), safe_tr("撤销上一步操作")),
            "undo": (safe_tr("撤销"), safe_tr("撤销上一步操作")),
            "edit_redo": (safe_tr("重做"), safe_tr("恢复撤销的操作")),
            "redo": (safe_tr("重做"), safe_tr("恢复撤销的操作")),
            "edit_cut": (safe_tr("剪切"), safe_tr("剪切选中内容")),
            "cut": (safe_tr("剪切"), safe_tr("剪切选中内容")),
            "edit_copy": (safe_tr("复制"), safe_tr("复制选中内容")),
            "copy": (safe_tr("复制"), safe_tr("复制选中内容")),
            "edit_paste": (safe_tr("粘贴"), safe_tr("粘贴剪贴板内容")),
            "paste": (safe_tr("粘贴"), safe_tr("粘贴剪贴板内容")),
            "edit_select_all": (safe_tr("全选"), safe_tr("选定当前文档全部内容")),
            "selectAll": (safe_tr("全选"), safe_tr("选定当前文档全部内容")),
            "edit_find": (safe_tr("查找…"), safe_tr("在当前文档或工作表中查找文本")),
            "find": (safe_tr("查找…"), safe_tr("在当前文档或工作表中查找文本")),
            "edit_replace": (safe_tr("替换…"), safe_tr("查找并替换指定文本")),
            "replace": (safe_tr("替换…"), safe_tr("查找并替换指定文本")),
            "edit_format_cells": (
                safe_tr("设置单元格格式…"),
                safe_tr("打开单元格格式设置对话框"),
            ),
            "format_cells": (
                safe_tr("设置单元格格式…"),
                safe_tr("打开单元格格式设置对话框"),
            ),
            # View
            "view_fullscreen": (safe_tr("全屏切换"), safe_tr("进入或退出全屏模式")),
            "view_zoom_in": (safe_tr("放大"), safe_tr("放大视图")),
            "zoom_in": (safe_tr("放大"), safe_tr("放大视图")),
            "view_zoom_out": (safe_tr("缩小"), safe_tr("缩小视图")),
            "zoom_out": (safe_tr("缩小"), safe_tr("缩小视图")),
            "view_zoom_reset": (safe_tr("实际大小"), safe_tr("重置视图比例")),
            "zoom_reset": (safe_tr("实际大小"), safe_tr("重置视图比例")),
            "theme_luna_blue": (
                safe_tr("Office 2003 经典蓝"),
                safe_tr("切换为经典 Luna 蓝色视觉风格"),
            ),
            "theme_luna_silver": (
                safe_tr("Office 2003 典雅银"),
                safe_tr("切换为经典 Luna 银色视觉风格"),
            ),
            "theme_luna_olive": (
                safe_tr("Office 2003 橄榄绿"),
                safe_tr("切换为经典 Luna 橄榄绿视觉风格"),
            ),
            "theme_classic": (
                safe_tr("Windows 经典"),
                safe_tr("切换为经典 Windows 灰阶视觉风格"),
            ),
            "theme_selector": (
                safe_tr("主题选择器…"),
                safe_tr("打开外观主题卡片预览与实时切换对话框"),
            ),
            # Insert
            "insert_page_break": (
                safe_tr("分页符"),
                safe_tr("在光标所在处插入分页符"),
            ),
            "insert_page_number": (
                safe_tr("页码…"),
                safe_tr("插入文档当前页码及总页数"),
            ),
            "insert_date_time": (
                safe_tr("日期和时间…"),
                safe_tr("插入系统当前格式化日期和时间"),
            ),
            "insert_symbol": (safe_tr("特殊符号…"), safe_tr("插入特殊符号或常用字符")),
            "insert_picture": (
                safe_tr("图片来自文件…"),
                safe_tr("从本地磁盘导入图像至画布"),
            ),
            "insert_shape": (
                safe_tr("自选图形"),
                safe_tr("插入矩形、线条、箭头等几何矢量图形"),
            ),
            "insert_hyperlink": (
                safe_tr("超链接…"),
                safe_tr("插入或编辑网页、书签跳转超链接"),
            ),
            "hyperlink": (
                safe_tr("超链接…"),
                safe_tr("插入或编辑网页、书签跳转超链接"),
            ),
            # Format
            "format_font": (safe_tr("字体…"), safe_tr("设置文本字体、字号、字形与特效")),
            "format_paragraph": (
                safe_tr("段落…"),
                safe_tr("设置行距、段前段后间距与缩进对齐"),
            ),
            "format_bullets": (
                safe_tr("项目符号"),
                safe_tr("开启或关闭段落项目符号列表"),
            ),
            "bullets": (safe_tr("项目符号"), safe_tr("开启或关闭段落项目符号列表")),
            "format_numbering": (
                safe_tr("项目编号"),
                safe_tr("开启或关闭段落顺序编号列表"),
            ),
            "numbering": (
                safe_tr("项目编号"),
                safe_tr("开启或关闭段落顺序编号列表"),
            ),
            "format_borders": (
                safe_tr("边框和底纹…"),
                safe_tr("配置表格或段落的边框样式与填充底纹"),
            ),
            "format_tabs": (
                safe_tr("制表位…"),
                safe_tr("设置水平标尺上的制表位对齐与前导符"),
            ),
            "format_styles": (
                safe_tr("样式和格式…"),
                safe_tr("打开样式面板应用正文或标题层级样式"),
            ),
            "stylesPane": (
                safe_tr("样式和格式…"),
                safe_tr("打开样式面板应用正文或标题层级样式"),
            ),
            # Tools
            "tools_spelling": (
                safe_tr("拼写和语法检查…"),
                safe_tr("运行词典校对并审查拼写错误 (F7)"),
            ),
            "spelling": (
                safe_tr("拼写和语法检查…"),
                safe_tr("运行词典校对并审查拼写错误 (F7)"),
            ),
            "tools_word_count": (
                safe_tr("字数统计…"),
                safe_tr("统计文档页数、字数、段落数及字符数"),
            ),
            "tools_language": (
                safe_tr("语言选择…"),
                safe_tr("配置文本校对及界面显示语言"),
            ),
            "tools_options": (
                safe_tr("选项…"),
                safe_tr("设置全局偏好、自动保存周期与外观主题"),
            ),
            # Table (Quire)
            "table_draw": (safe_tr("绘制表格"), safe_tr("使用画笔自由绘制表格线网格")),
            "drawTable": (safe_tr("绘制表格"), safe_tr("使用画笔自由绘制表格线网格")),
            "table_insert": (
                safe_tr("插入表格…"),
                safe_tr("指定行数与列数快速插入规整网格"),
            ),
            "table_delete": (
                safe_tr("删除表格"),
                safe_tr("删除当前选中的行、列或整个表格"),
            ),
            "table_select": (
                safe_tr("选定单元格"),
                safe_tr("选定光标所在的行、列或单元格"),
            ),
            "table_merge": (
                safe_tr("合并单元格"),
                safe_tr("将选中的多个连续单元格合并为单个单元格"),
            ),
            "mergeCells": (
                safe_tr("合并单元格"),
                safe_tr("将选中的多个连续单元格合并为单个单元格"),
            ),
            "table_split": (
                safe_tr("拆分单元格…"),
                safe_tr("将单元格按行列数重新拆分为多个小单元格"),
            ),
            "splitCells": (
                safe_tr("拆分单元格…"),
                safe_tr("将单元格按行列数重新拆分为多个小单元格"),
            ),
            "table_properties": (
                safe_tr("表格属性…"),
                safe_tr("配置表格尺寸、对齐方式、文本环绕及边距"),
            ),
            # Data (Ledger)
            "data_sort_asc": (
                safe_tr("升序排序"),
                safe_tr("按选中列的值进行递增从小到大排序"),
            ),
            "sortAsc": (
                safe_tr("升序排序"),
                safe_tr("按选中列的值进行递增从小到大排序"),
            ),
            "data_sort_desc": (
                safe_tr("降序排序"),
                safe_tr("按选中列的值进行递减从大到小排序"),
            ),
            "sortDesc": (
                safe_tr("降序排序"),
                safe_tr("按选中列的值进行递减从大到小排序"),
            ),
            "data_filter": (
                safe_tr("自动筛选"),
                safe_tr("在表头显示下拉箭头以快速筛选行数据"),
            ),
            "data_validation": (
                safe_tr("数据有效性…"),
                safe_tr("限制输入范围并设置错误警报提示"),
            ),
            "data_subtotals": (
                safe_tr("分类汇总…"),
                safe_tr("自动对分组行计算求和或平均值汇总"),
            ),
            "data_pivottable": (
                safe_tr("数据透视表向导…"),
                safe_tr("从现有工作表数据创建多维交互汇总视图"),
            ),
            # Slide Show (Lectern)
            "slideshow_start": (
                safe_tr("观看放映"),
                safe_tr("从第 1 张幻灯片开始全屏播放 (F5)"),
            ),
            "start_slideshow": (
                safe_tr("观看放映"),
                safe_tr("从第 1 张幻灯片开始全屏播放 (F5)"),
            ),
            "slideshow_current": (
                safe_tr("从当前幻灯片放映"),
                safe_tr("从当前选中页开始全屏放映 (Shift+F5)"),
            ),
            "start_slideshow_current": (
                safe_tr("从当前幻灯片放映"),
                safe_tr("从当前选中页开始全屏放映 (Shift+F5)"),
            ),
            "slideshow_setup": (
                safe_tr("设置放映方式…"),
                safe_tr("配置放映类型、循环播放模式与换片方式"),
            ),
            "slideshow_record": (
                safe_tr("录制旁白…"),
                safe_tr("在幻灯片播放过程中同步录制语音解说"),
            ),
            "slideshow_rehearse": (
                safe_tr("排练计时"),
                safe_tr("演练演示文稿并记录每张幻灯片切换间隔"),
            ),
            "slideshow_transition": (
                safe_tr("幻灯片切换…"),
                safe_tr("配置选定幻灯片的入场转场动效与声音")),
            # Window
            "window_minimize": (safe_tr("最小化"), safe_tr("将窗口最小化到程序坞")),
            "window_zoom": (safe_tr("缩放窗口"), safe_tr("最大化或恢复窗口尺寸")),
            "window_bring_all": (
                safe_tr("前置全部窗口"),
                safe_tr("将应用程序所有窗口移到最前面"),
            ),
            # Help
            "help_contents": (safe_tr("ATBOffice 帮助"), safe_tr("打开用户帮助文档")),
            "help": (safe_tr("ATBOffice 帮助"), safe_tr("打开用户帮助文档")),
            "help_about": (safe_tr("关于 ATBOffice"), safe_tr("查看应用程序版本信息")),
            "about": (safe_tr("关于 ATBOffice"), safe_tr("查看应用程序版本信息")),
        }

        for key, (text, tooltip) in translations.items():
            if key in self.action_map:
                action = self.action_map[key]
                action.setText(text)
                action.setToolTip(tooltip)
                action.setStatusTip(tooltip)
                if hasattr(self, "action_registry") and self.action_registry is not None:
                    spec = self.action_registry._specs.get(key)
                    if spec is not None:
                        spec.label = text
                        spec.tip = tooltip


def setup_mac_menu(window: QMainWindow, app_type: str = "generic") -> MacMenuBar:
    """Configure native macOS menu bar on the given window."""
    menu_bar = MacMenuBar(window, app_type=app_type)
    window.setMenuBar(menu_bar)
    return menu_bar

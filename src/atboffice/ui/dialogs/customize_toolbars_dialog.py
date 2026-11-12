"""Classic Office 2003 Tools ▸ Customize... dialog (CustomizeToolbarsDialog).

Provides full toolbar visibility management, command browsing and execution,
personalized menus & toolbar display options, and keyboard shortcut customization.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


def safe_tr(text: str) -> str:
    """Translate UI string with standard context."""
    return QCoreApplication.translate("CustomizeToolbarsDialog", text)


class CustomizeToolbarsDialog(QDialog):
    """Classic 4-tab Office 2003 Customize dialog (Toolbars, Commands, Options, Keyboard)."""

    toolbar_toggled = Signal(str, bool)
    shortcut_assigned = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("自定义"))
        self.resize(520, 480)

        self._active_category = "File"
        self._custom_toolbars: list[str] = []
        self._command_shortcuts: dict[str, str] = {
            "New": "Ctrl+N",
            "Open": "Ctrl+O",
            "Save": "Ctrl+S",
            "Print": "Ctrl+P",
            "Cut": "Ctrl+X",
            "Copy": "Ctrl+C",
            "Paste": "Ctrl+V",
            "Undo": "Ctrl+Z",
            "Redo": "Ctrl+Y",
            "Select All": "Ctrl+A",
            "Find": "Ctrl+F",
            "Replace": "Ctrl+H",
        }

        self._init_data()
        self._init_ui()
        self.retranslate_ui()

    def _init_data(self) -> None:
        """Initialize built-in toolbar definitions and categorized commands."""
        self.built_in_toolbars = [
            ("Standard", safe_tr("常用"), True),
            ("Formatting", safe_tr("格式"), True),
            ("Drawing", safe_tr("绘图"), True),
            ("Tables and Borders", safe_tr("表格和边框"), False),
            ("Reviewing", safe_tr("审阅"), False),
            ("Picture", safe_tr("图片"), False),
            ("WordArt", safe_tr("艺术字"), False),
            ("Header and Footer", safe_tr("页眉和页脚"), False),
            ("Mail Merge", safe_tr("邮件合并"), False),
            ("Outlining", safe_tr("大纲"), False),
        ]

        self.categories_map: dict[str, list[tuple[str, str, str]]] = {
            "File": [
                ("New", safe_tr("新建"), safe_tr("创建新文档。")),
                ("Open", safe_tr("打开"), safe_tr("打开现有文档。")),
                ("Close", safe_tr("关闭"), safe_tr("关闭当前文档。")),
                ("Save", safe_tr("保存"), safe_tr("保存活动文档。")),
                ("Save As", safe_tr("另存为"), safe_tr("用不同名称或格式保存文档。")),
                ("Page Setup", safe_tr("页面设置"), safe_tr("设置边距、纸张大小和方向。")),
                ("Print Preview", safe_tr("打印预览"), safe_tr("在打印前预览页面外观。")),
                ("Print", safe_tr("打印"), safe_tr("打印活动文档。")),
                ("Exit", safe_tr("退出"), safe_tr("退出应用程序。")),
            ],
            "Edit": [
                ("Undo", safe_tr("撤消"), safe_tr("撤消上一步操作。")),
                ("Redo", safe_tr("重做"), safe_tr("重新执行上一步撤消的操作。")),
                ("Cut", safe_tr("剪切"), safe_tr("剪切选定内容并放入剪贴板。")),
                ("Copy", safe_tr("复制"), safe_tr("复制选定内容并放入剪贴板。")),
                ("Paste", safe_tr("粘贴"), safe_tr("插入剪贴板内容。")),
                ("Paste Special", safe_tr("选择性粘贴"), safe_tr("选择特定格式粘贴剪贴板内容。")),
                ("Select All", safe_tr("全选"), safe_tr("选择文档中的全部内容。")),
                ("Find", safe_tr("查找"), safe_tr("查找指定的文本或格式。")),
                ("Replace", safe_tr("替换"), safe_tr("替换指定的文本。")),
            ],
            "View": [
                ("Normal", safe_tr("普通视图"), safe_tr("切换到普通视图。")),
                ("Print Layout", safe_tr("页面视图"), safe_tr("查看文档在打印页面上的排版。")),
                ("Outline", safe_tr("大纲视图"), safe_tr("以大纲形式查看文档结构。")),
                ("Toolbars", safe_tr("工具栏"), safe_tr("显示或隐藏工具栏。")),
                ("Ruler", safe_tr("标尺"), safe_tr("显示或隐藏标尺。")),
                ("Full Screen", safe_tr("全屏显示"), safe_tr("全屏显示文档以获得最大阅读空间。")),
                ("Zoom", safe_tr("显示比例"), safe_tr("缩放文档显示比例。")),
            ],
            "Insert": [
                ("Break", safe_tr("分隔符"), safe_tr("插入分页符或分节符。")),
                ("Page Numbers", safe_tr("页码"), safe_tr("插入页码。")),
                ("Date and Time", safe_tr("日期和时间"), safe_tr("插入当前日期和时间。")),
                ("Symbol", safe_tr("符号"), safe_tr("插入特殊字符和符号。")),
                ("Picture", safe_tr("图片"), safe_tr("从文件插入图片。")),
                ("Hyperlink", safe_tr("超链接"), safe_tr("插入指向网页或文件的超链接。")),
            ],
            "Format": [
                ("Font", safe_tr("字体"), safe_tr("更改选定文字的字体和字符间距。")),
                ("Paragraph", safe_tr("段落"), safe_tr("设置段落缩进、对齐方式和行距。")),
                (
                    "Bullets and Numbering",
                    safe_tr("项目符号和编号"),
                    safe_tr("为选定段落添加项目符号或编号。"),
                ),
                (
                    "Borders and Shading",
                    safe_tr("边框和底纹"),
                    safe_tr("为所选文字或表格添加边框和底纹。"),
                ),
                ("Columns", safe_tr("分栏"), safe_tr("将页面内容分为多栏。")),
                ("Style", safe_tr("样式"), safe_tr("应用或创建格式样式。")),
            ],
            "Tools": [
                ("Spelling and Grammar", safe_tr("拼写和语法"), safe_tr("检查文档的拼写和语法。")),
                ("Language", safe_tr("语言"), safe_tr("设置文档校对语言。")),
                ("Word Count", safe_tr("字数统计"), safe_tr("统计文档的字数、字符数和段落数。")),
                ("AutoCorrect", safe_tr("自动更正选项"), safe_tr("自定义输入时的自动更正规则。")),
                ("Customize", safe_tr("自定义"), safe_tr("自定义工具栏、菜单和快捷键。")),
                ("Options", safe_tr("选项"), safe_tr("配置应用程序常规偏好设置。")),
            ],
            "Table": [
                ("Insert Table", safe_tr("插入表格"), safe_tr("创建指定行数和列数的表格。")),
                ("Delete Table", safe_tr("删除表格"), safe_tr("删除当前选中的表格。")),
                ("Select Table", safe_tr("选定表格"), safe_tr("选择整个表格。")),
                ("Merge Cells", safe_tr("合并单元格"), safe_tr("将选定的多个单元格合并为一个。")),
                ("Split Cells", safe_tr("拆分单元格"), safe_tr("将单元格拆分为多个单元格。")),
            ],
            "Window": [
                ("New Window", safe_tr("新建窗口"), safe_tr("为活动文档打开一个新窗口。")),
                ("Arrange All", safe_tr("全部重排"), safe_tr("在屏幕上平铺所有打开的文档窗口。")),
                ("Split", safe_tr("拆分"), safe_tr("将活动窗口拆分为两个窗格。")),
            ],
            "Help": [
                ("Help", safe_tr("帮助"), safe_tr("打开帮助系统。")),
                ("About", safe_tr("关于"), safe_tr("显示应用程序版本和许可信息。")),
            ],
            "Drawing": [
                ("Line", safe_tr("线条"), safe_tr("绘制直线。")),
                ("Arrow", safe_tr("箭头"), safe_tr("绘制带箭头的线条。")),
                ("Rectangle", safe_tr("矩形"), safe_tr("绘制矩形形状。")),
                ("Oval", safe_tr("椭圆"), safe_tr("绘制圆形或椭圆形状。")),
                ("Text Box", safe_tr("文本框"), safe_tr("插入可在其中放置文字的文本框。")),
                ("WordArt", safe_tr("艺术字"), safe_tr("创建带有特殊效果的艺术字。")),
            ],
        }

    def _init_ui(self) -> None:
        """Create tab structure and controls."""
        main_layout = QVBoxLayout(self)

        self.tab_widget = QTabWidget(self)

        # Tab 1: Toolbars
        self._init_toolbars_tab()
        # Tab 2: Commands
        self._init_commands_tab()
        # Tab 3: Options
        self._init_options_tab()
        # Tab 4: Keyboard
        self._init_keyboard_tab()

        main_layout.addWidget(self.tab_widget)

        # Bottom Close Button
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        self.button_box.rejected.connect(self.accept)
        main_layout.addWidget(self.button_box)

    def _init_toolbars_tab(self) -> None:
        """Tab 1: Toolbars list with interactive checkboxes and management buttons."""
        self.tab_toolbars = QWidget()
        layout = QHBoxLayout(self.tab_toolbars)

        v_list = QVBoxLayout()
        self.lbl_toolbars_hint = QLabel(self.tab_toolbars)
        v_list.addWidget(self.lbl_toolbars_hint)

        self.list_toolbars = QListWidget(self.tab_toolbars)
        for key, name, checked in self.built_in_toolbars:
            item = QListWidgetItem(name, self.list_toolbars)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, key)
        self.list_toolbars.itemChanged.connect(self._on_toolbar_item_changed)
        v_list.addWidget(self.list_toolbars)
        layout.addLayout(v_list, stretch=1)

        # Action buttons on right
        v_btns = QVBoxLayout()
        self.btn_new_toolbar = QPushButton(self.tab_toolbars)
        self.btn_rename_toolbar = QPushButton(self.tab_toolbars)
        self.btn_delete_toolbar = QPushButton(self.tab_toolbars)
        self.btn_reset_toolbar = QPushButton(self.tab_toolbars)

        self.btn_new_toolbar.clicked.connect(self._on_new_toolbar)
        self.btn_rename_toolbar.clicked.connect(self._on_rename_toolbar)
        self.btn_delete_toolbar.clicked.connect(self._on_delete_toolbar)
        self.btn_reset_toolbar.clicked.connect(self._on_reset_toolbars)

        v_btns.addWidget(self.btn_new_toolbar)
        v_btns.addWidget(self.btn_rename_toolbar)
        v_btns.addWidget(self.btn_delete_toolbar)
        v_btns.addWidget(self.btn_reset_toolbar)
        v_btns.addStretch()
        layout.addLayout(v_btns)

        self.tab_widget.addTab(self.tab_toolbars, "")

    def _init_commands_tab(self) -> None:
        """Tab 2: Categories on the left, Commands on the right, Description below."""
        self.tab_commands = QWidget()
        layout = QVBoxLayout(self.tab_commands)

        self.lbl_commands_hint = QLabel(self.tab_commands)
        self.lbl_commands_hint.setWordWrap(True)
        layout.addWidget(self.lbl_commands_hint)

        h_split = QHBoxLayout()

        # Left: Categories
        v_cat = QVBoxLayout()
        self.lbl_categories = QLabel(self.tab_commands)
        v_cat.addWidget(self.lbl_categories)
        self.list_categories = QListWidget(self.tab_commands)
        for cat_key in self.categories_map:
            item = QListWidgetItem(cat_key, self.list_categories)
            item.setData(Qt.ItemDataRole.UserRole, cat_key)
        self.list_categories.currentRowChanged.connect(self._on_category_changed)
        v_cat.addWidget(self.list_categories)
        h_split.addLayout(v_cat, stretch=1)

        # Right: Commands
        v_cmd = QVBoxLayout()
        self.lbl_commands = QLabel(self.tab_commands)
        v_cmd.addWidget(self.lbl_commands)
        self.list_commands = QListWidget(self.tab_commands)
        self.list_commands.currentRowChanged.connect(self._on_command_changed)
        v_cmd.addWidget(self.list_commands)
        h_split.addLayout(v_cmd, stretch=2)

        layout.addLayout(h_split)

        # Description hint box
        self.lbl_desc_title = QLabel(self.tab_commands)
        layout.addWidget(self.lbl_desc_title)
        self.txt_description = QTextEdit(self.tab_commands)
        self.txt_description.setReadOnly(True)
        self.txt_description.setMaximumHeight(65)
        layout.addWidget(self.txt_description)

        self.tab_widget.addTab(self.tab_commands, "")

    def _init_options_tab(self) -> None:
        """Tab 3: Personalized menus and toolbar checkboxes & animations."""
        self.tab_options = QWidget()
        layout = QVBoxLayout(self.tab_options)

        # Group 1: Personalized Menus and Toolbars
        self.grp_personalized = QGroupBox(self.tab_options)
        l_grp1 = QVBoxLayout(self.grp_personalized)
        self.chk_two_rows = QCheckBox(self.grp_personalized)
        self.chk_two_rows.setChecked(True)
        self.chk_always_full_menus = QCheckBox(self.grp_personalized)
        self.chk_always_full_menus.setChecked(True)
        self.chk_menu_delay = QCheckBox(self.grp_personalized)
        self.chk_menu_delay.setChecked(False)
        self.btn_reset_usage = QPushButton(self.grp_personalized)
        self.btn_reset_usage.clicked.connect(self._on_reset_usage)

        l_grp1.addWidget(self.chk_two_rows)
        l_grp1.addWidget(self.chk_always_full_menus)
        l_grp1.addWidget(self.chk_menu_delay)
        l_grp1.addWidget(self.btn_reset_usage)
        layout.addWidget(self.grp_personalized)

        # Group 2: Other options
        self.grp_other = QGroupBox(self.tab_options)
        l_grp2 = QVBoxLayout(self.grp_other)
        self.chk_large_icons = QCheckBox(self.grp_other)
        self.chk_screentips = QCheckBox(self.grp_other)
        self.chk_screentips.setChecked(True)
        self.chk_shortcut_tips = QCheckBox(self.grp_other)
        self.chk_shortcut_tips.setChecked(True)

        h_anim = QHBoxLayout()
        self.lbl_animations = QLabel(self.grp_other)
        self.combo_animations = QComboBox(self.grp_other)
        self.combo_animations.addItems(["(None)", "Random", "Unfold", "Slide"])
        h_anim.addWidget(self.lbl_animations)
        h_anim.addWidget(self.combo_animations)
        h_anim.addStretch()

        l_grp2.addWidget(self.chk_large_icons)
        l_grp2.addWidget(self.chk_screentips)
        l_grp2.addWidget(self.chk_shortcut_tips)
        l_grp2.addLayout(h_anim)
        layout.addWidget(self.grp_other)

        layout.addStretch()
        self.tab_widget.addTab(self.tab_options, "")

    def _init_keyboard_tab(self) -> None:
        """Tab 4: Keyboard shortcuts customization."""
        self.tab_keyboard = QWidget()
        layout = QVBoxLayout(self.tab_keyboard)

        self.lbl_keyboard_hint = QLabel(self.tab_keyboard)
        layout.addWidget(self.lbl_keyboard_hint)

        f_layout = QFormLayout()

        # Category combo
        self.lbl_kb_category = QLabel(self.tab_keyboard)
        self.combo_kb_category = QComboBox(self.tab_keyboard)
        for cat_key in self.categories_map:
            self.combo_kb_category.addItem(cat_key, cat_key)
        self.combo_kb_category.currentIndexChanged.connect(self._on_kb_category_changed)
        f_layout.addRow(self.lbl_kb_category, self.combo_kb_category)

        # Command combo
        self.lbl_kb_command = QLabel(self.tab_keyboard)
        self.combo_kb_command = QComboBox(self.tab_keyboard)
        self.combo_kb_command.currentIndexChanged.connect(self._on_kb_command_changed)
        f_layout.addRow(self.lbl_kb_command, self.combo_kb_command)

        # Current shortcut label
        self.lbl_curr_shortcut_title = QLabel(self.tab_keyboard)
        self.lbl_curr_shortcut = QLabel(safe_tr("无"), self.tab_keyboard)
        f_layout.addRow(self.lbl_curr_shortcut_title, self.lbl_curr_shortcut)

        # New shortcut input
        self.lbl_new_shortcut = QLabel(self.tab_keyboard)
        self.edit_key_seq = QKeySequenceEdit(self.tab_keyboard)
        f_layout.addRow(self.lbl_new_shortcut, self.edit_key_seq)

        layout.addLayout(f_layout)

        # Buttons
        h_kb_btns = QHBoxLayout()
        self.btn_assign_key = QPushButton(self.tab_keyboard)
        self.btn_remove_key = QPushButton(self.tab_keyboard)
        self.btn_reset_all_keys = QPushButton(self.tab_keyboard)

        self.btn_assign_key.clicked.connect(self._on_assign_key)
        self.btn_remove_key.clicked.connect(self._on_remove_key)
        self.btn_reset_all_keys.clicked.connect(self._on_reset_all_keys)

        h_kb_btns.addWidget(self.btn_assign_key)
        h_kb_btns.addWidget(self.btn_remove_key)
        h_kb_btns.addWidget(self.btn_reset_all_keys)
        h_kb_btns.addStretch()
        layout.addLayout(h_kb_btns)

        layout.addStretch()
        self.tab_widget.addTab(self.tab_keyboard, "")

    def _on_toolbar_item_changed(self, item: QListWidgetItem) -> None:
        """Handle toolbar checkbox toggling."""
        name = item.text()
        checked = item.checkState() == Qt.CheckState.Checked
        self.toolbar_toggled.emit(name, checked)

    def _on_new_toolbar(self) -> None:
        """Create a user-defined custom toolbar."""
        name, ok = QInputDialog.getText(
            self,
            safe_tr("新建工具栏"),
            safe_tr("工具栏名称(&T):"),
            QLineEdit.EchoMode.Normal,
            safe_tr("自定义 1"),
        )
        if ok and name.strip():
            tb_name = name.strip()
            self._custom_toolbars.append(tb_name)
            item = QListWidgetItem(tb_name, self.list_toolbars)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, f"custom_{tb_name}")
            self.list_toolbars.setCurrentItem(item)

    def _on_rename_toolbar(self) -> None:
        """Rename selected custom toolbar."""
        item = self.list_toolbars.currentItem()
        if not item:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if not key or not str(key).startswith("custom_"):
            QMessageBox.information(
                self,
                safe_tr("自定义"),
                safe_tr("无法重命名内置工具栏。"),
            )
            return

        name, ok = QInputDialog.getText(
            self,
            safe_tr("重命名工具栏"),
            safe_tr("新工具栏名称(&T):"),
            QLineEdit.EchoMode.Normal,
            item.text(),
        )
        if ok and name.strip():
            item.setText(name.strip())

    def _on_delete_toolbar(self) -> None:
        """Delete selected custom toolbar."""
        item = self.list_toolbars.currentItem()
        if not item:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if not key or not str(key).startswith("custom_"):
            QMessageBox.information(
                self,
                safe_tr("自定义"),
                safe_tr("无法删除内置工具栏。"),
            )
            return

        row = self.list_toolbars.row(item)
        self.list_toolbars.takeItem(row)

    def _on_reset_toolbars(self) -> None:
        """Reset built-in toolbars to default visibility."""
        for i in range(self.list_toolbars.count()):
            item = self.list_toolbars.item(i)
            key = item.data(Qt.ItemDataRole.UserRole)
            for b_key, _, default_checked in self.built_in_toolbars:
                if key == b_key:
                    item.setCheckState(
                        Qt.CheckState.Checked if default_checked else Qt.CheckState.Unchecked
                    )
                    break

    def _on_category_changed(self, row: int) -> None:
        """Populate commands list based on selected category."""
        item = self.list_categories.item(row)
        if not item:
            return
        cat_key = item.data(Qt.ItemDataRole.UserRole)
        self._active_category = cat_key
        self.list_commands.clear()

        cmds = self.categories_map.get(cat_key, [])
        for cmd_key, cmd_name, desc in cmds:
            c_item = QListWidgetItem(cmd_name, self.list_commands)
            c_item.setData(Qt.ItemDataRole.UserRole, cmd_key)
            c_item.setData(Qt.ItemDataRole.ToolTipRole, desc)

        if self.list_commands.count() > 0:
            self.list_commands.setCurrentRow(0)

    def _on_command_changed(self, row: int) -> None:
        """Show command description in preview text area."""
        item = self.list_commands.item(row)
        if not item:
            self.txt_description.clear()
            return
        desc = item.data(Qt.ItemDataRole.ToolTipRole) or ""
        self.txt_description.setText(str(desc))

    def _on_reset_usage(self) -> None:
        """Reset menu and toolbar usage statistics."""
        QMessageBox.information(
            self,
            safe_tr("自定义"),
            safe_tr("已将菜单和工具栏使用情况数据重置为默认值。"),
        )

    def _on_kb_category_changed(self, idx: int) -> None:
        """Update keyboard commands combo when category changes."""
        cat_key = self.combo_kb_category.itemData(idx)
        self.combo_kb_command.clear()
        cmds = self.categories_map.get(cat_key, [])
        for cmd_key, cmd_name, _ in cmds:
            self.combo_kb_command.addItem(cmd_name, cmd_key)

    def _on_kb_command_changed(self, idx: int) -> None:
        """Update current shortcut indicator when command changes."""
        cmd_key = self.combo_kb_command.itemData(idx)
        shortcut = self._command_shortcuts.get(cmd_key, "")
        self.lbl_curr_shortcut.setText(shortcut or safe_tr("无"))

    def _on_assign_key(self) -> None:
        """Assign input shortcut key to current command."""
        seq = self.edit_key_seq.keySequence()
        if seq.isEmpty():
            return
        cmd_key = self.combo_kb_command.currentData()
        key_str = seq.toString(QKeySequence.SequenceFormat.PortableText)
        self._command_shortcuts[cmd_key] = key_str
        self.lbl_curr_shortcut.setText(key_str)
        self.shortcut_assigned.emit(cmd_key, key_str)
        self.edit_key_seq.clear()

    def _on_remove_key(self) -> None:
        """Remove shortcut key from current command."""
        cmd_key = self.combo_kb_command.currentData()
        if cmd_key in self._command_shortcuts:
            del self._command_shortcuts[cmd_key]
        self.lbl_curr_shortcut.setText(safe_tr("无"))

    def _on_reset_all_keys(self) -> None:
        """Reset all keyboard shortcuts to factory defaults."""
        self._command_shortcuts = {
            "New": "Ctrl+N",
            "Open": "Ctrl+O",
            "Save": "Ctrl+S",
            "Print": "Ctrl+P",
            "Cut": "Ctrl+X",
            "Copy": "Ctrl+C",
            "Paste": "Ctrl+V",
            "Undo": "Ctrl+Z",
            "Redo": "Ctrl+Y",
            "Select All": "Ctrl+A",
            "Find": "Ctrl+F",
            "Replace": "Ctrl+H",
        }
        self._on_kb_command_changed(self.combo_kb_command.currentIndex())

    def retranslate_ui(self) -> None:
        """Update user-facing localized strings across all tabs."""
        self.setWindowTitle(safe_tr("自定义"))

        # Tabs
        self.tab_widget.setTabText(0, safe_tr("工具栏 (&B)"))
        self.tab_widget.setTabText(1, safe_tr("命令 (&C)"))
        self.tab_widget.setTabText(2, safe_tr("选项 (&O)"))
        self.tab_widget.setTabText(3, safe_tr("键盘 (&K)"))

        # Tab 1
        self.lbl_toolbars_hint.setText(safe_tr("工具栏 (&T):"))
        self.btn_new_toolbar.setText(safe_tr("新建 (&N)..."))
        self.btn_rename_toolbar.setText(safe_tr("重命名 (&R)..."))
        self.btn_delete_toolbar.setText(safe_tr("删除 (&D)"))
        self.btn_reset_toolbar.setText(safe_tr("重置 (&E)..."))

        # Tab 2
        self.lbl_commands_hint.setText(
            safe_tr("要向工具栏添加命令，请选择一个类别，然后将命令从该对话框拖至工具栏。")
        )
        self.lbl_categories.setText(safe_tr("类别 (&G):"))
        self.lbl_commands.setText(safe_tr("命令 (&D):"))
        self.lbl_desc_title.setText(safe_tr("说明:"))

        # Update category item labels
        category_translations = {
            "File": safe_tr("文件"),
            "Edit": safe_tr("编辑"),
            "View": safe_tr("视图"),
            "Insert": safe_tr("插入"),
            "Format": safe_tr("格式"),
            "Tools": safe_tr("工具"),
            "Table": safe_tr("表格"),
            "Window": safe_tr("窗口"),
            "Help": safe_tr("帮助"),
            "Drawing": safe_tr("绘图"),
        }
        for i in range(self.list_categories.count()):
            item = self.list_categories.item(i)
            k = item.data(Qt.ItemDataRole.UserRole)
            if k in category_translations:
                item.setText(category_translations[k])

        # Tab 3
        self.grp_personalized.setTitle(safe_tr("个性化菜单和工具栏"))
        self.chk_two_rows.setText(safe_tr("分两行显示“常用”和“格式”工具栏 (&S)"))
        self.chk_always_full_menus.setText(safe_tr("始终显示完整菜单 (&M)"))
        self.chk_menu_delay.setText(safe_tr("简短的延时后显示完整菜单 (&U)"))
        self.btn_reset_usage.setText(safe_tr("重置菜单和工具栏使用情况数据 (&R)"))

        self.grp_other.setTitle(safe_tr("其他"))
        self.chk_large_icons.setText(safe_tr("大图标 (&L)"))
        self.chk_screentips.setText(safe_tr("显示屏幕提示 (&T)"))
        self.chk_shortcut_tips.setText(safe_tr("在屏幕提示中显示快捷键 (&K)"))
        self.lbl_animations.setText(safe_tr("菜单动画效果 (&A):"))

        cur_anim = self.combo_animations.currentIndex()
        self.combo_animations.clear()
        self.combo_animations.addItems([
            safe_tr("(无)"),
            safe_tr("随机"),
            safe_tr("展开"),
            safe_tr("滑动"),
        ])
        if cur_anim >= 0 and cur_anim < self.combo_animations.count():
            self.combo_animations.setCurrentIndex(cur_anim)

        # Tab 4
        self.lbl_keyboard_hint.setText(safe_tr("指定键盘快捷键"))
        self.lbl_kb_category.setText(safe_tr("类别 (&C):"))
        self.lbl_kb_command.setText(safe_tr("命令 (&O):"))
        self.lbl_curr_shortcut_title.setText(safe_tr("当前快捷键 (&U):"))
        self.lbl_new_shortcut.setText(safe_tr("请按新快捷键 (&N):"))
        self.btn_assign_key.setText(safe_tr("指定 (&A)"))
        self.btn_remove_key.setText(safe_tr("删除 (&R)"))
        self.btn_reset_all_keys.setText(safe_tr("全部重置 (&S)..."))

        # Re-trigger category selection to update commands tab
        if self.list_categories.currentRow() < 0 and self.list_categories.count() > 0:
            self.list_categories.setCurrentRow(0)
        else:
            self._on_category_changed(self.list_categories.currentRow())

        if self.combo_kb_category.currentIndex() < 0 and self.combo_kb_category.count() > 0:
            self.combo_kb_category.setCurrentIndex(0)

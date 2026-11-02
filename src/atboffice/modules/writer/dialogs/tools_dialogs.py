"""Tools & Options Dialogs for Quire Writer.

Includes:
- AutoCorrectDialog: AutoCorrect options (自动更正选项，3标签)
- QuireOptionsDialog: Quire Tools Options (工具选项，10标签)
- CustomizeDialog: Customize Toolbars & Commands (自定义，4标签)
- EnvelopesLabelsDialog: Envelopes and Labels (信封和标签，2标签)
- LetterWizardDialog: Letter Creation Wizard (信件向导，4步骤)
- AutoSummarizeDialog: AutoSummarize document (自动摘要)
- HyphenationDialog: Hyphenation settings (断字设置)
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("ToolsDialogs", text)


class AutoCorrectDialog(QDialog):
    """AutoCorrect Options dialog with 3 tabs (自动更正)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("自动更正"))
        self.resize(460, 420)

        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget(self)

        # Tab 1: AutoCorrect
        self.tab_ac = QWidget(self.tab_widget)
        l_ac = QVBoxLayout(self.tab_ac)

        self.chk_two_caps = QCheckBox(safe_tr("更正前两个字母连续大写(&C)"), self.tab_ac)
        self.chk_sentence_cap = QCheckBox(safe_tr("句首字母大写(&S)"), self.tab_ac)
        self.chk_table_cell_cap = QCheckBox(safe_tr("表格单元格的首字母大写(&T)"), self.tab_ac)
        self.chk_day_cap = QCheckBox(safe_tr("英文星期首字母大写(&D)"), self.tab_ac)
        self.chk_caps_lock = QCheckBox(safe_tr("更正意外使用大写锁定键的情况(&A)"), self.tab_ac)
        self.chk_replace_type = QCheckBox(safe_tr("键入时自动替换(&R)"), self.tab_ac)

        self.chk_two_caps.setChecked(True)
        self.chk_sentence_cap.setChecked(True)
        self.chk_table_cell_cap.setChecked(True)
        self.chk_day_cap.setChecked(True)
        self.chk_caps_lock.setChecked(True)
        self.chk_replace_type.setChecked(True)

        l_ac.addWidget(self.chk_two_caps)
        l_ac.addWidget(self.chk_sentence_cap)
        l_ac.addWidget(self.chk_table_cell_cap)
        l_ac.addWidget(self.chk_day_cap)
        l_ac.addWidget(self.chk_caps_lock)
        l_ac.addWidget(self.chk_replace_type)

        # Replacement inputs & table
        h_inp = QHBoxLayout()
        self.edit_replace = QLineEdit(self.tab_ac)
        self.edit_replace.setPlaceholderText(safe_tr("替换"))
        self.edit_with = QLineEdit(self.tab_ac)
        self.edit_with.setPlaceholderText(safe_tr("替换为"))
        self.btn_add_rule = QPushButton(safe_tr("添加(&D)"), self.tab_ac)
        self.btn_del_rule = QPushButton(safe_tr("删除(&E)"), self.tab_ac)
        self.btn_add_rule.clicked.connect(self._add_rule)
        self.btn_del_rule.clicked.connect(self._delete_rule)

        h_inp.addWidget(self.edit_replace)
        h_inp.addWidget(self.edit_with)
        h_inp.addWidget(self.btn_add_rule)
        h_inp.addWidget(self.btn_del_rule)
        l_ac.addLayout(h_inp)

        self.table_rules = QTableWidget(self.tab_ac)
        self.table_rules.setColumnCount(2)
        self.table_rules.setHorizontalHeaderLabels([safe_tr("替换"), safe_tr("替换为")])
        self.table_rules.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        initial_rules = [
            ("(c)", "©"),
            ("(r)", "®"),
            ("(tm)", "™"),
            ("-->", "→"),
            ("<--", "←"),
            ("...", "…"),
            ("teh", "the"),
            ("adn", "and"),
        ]
        self.table_rules.setRowCount(len(initial_rules))
        for r, (src, dst) in enumerate(initial_rules):
            self.table_rules.setItem(r, 0, QTableWidgetItem(src))
            self.table_rules.setItem(r, 1, QTableWidgetItem(dst))

        l_ac.addWidget(self.table_rules)
        self.tab_widget.addTab(self.tab_ac, safe_tr("自动更正"))

        # Tab 2: AutoFormat As You Type
        self.tab_af = QWidget(self.tab_widget)
        l_af = QVBoxLayout(self.tab_af)
        grp_replace = QGroupBox(safe_tr("键入时替换"), self.tab_af)
        l_grp_r = QVBoxLayout(grp_replace)
        self.chk_quotes = QCheckBox(safe_tr("“直引号”替换为“弯引号”(&Q)"), grp_replace)
        self.chk_fractions = QCheckBox(safe_tr("分数字符 (1/2) 替换为分数 (&F)"), grp_replace)
        self.chk_emphasis = QCheckBox(safe_tr("*加粗* 和 _倾斜_ 替换为实际格式 (&B)"), grp_replace)
        self.chk_hyperlinks = QCheckBox(
            safe_tr("Internet 及网络路径替换为超链接 (&I)"), grp_replace
        )
        self.chk_quotes.setChecked(True)
        self.chk_fractions.setChecked(True)
        self.chk_emphasis.setChecked(True)
        self.chk_hyperlinks.setChecked(True)
        l_grp_r.addWidget(self.chk_quotes)
        l_grp_r.addWidget(self.chk_fractions)
        l_grp_r.addWidget(self.chk_emphasis)
        l_grp_r.addWidget(self.chk_hyperlinks)
        l_af.addWidget(grp_replace)

        grp_apply = QGroupBox(safe_tr("键入时应用"), self.tab_af)
        l_grp_a = QVBoxLayout(grp_apply)
        self.chk_auto_bullet = QCheckBox(safe_tr("自动项目符号列表(&U)"), grp_apply)
        self.chk_auto_number = QCheckBox(safe_tr("自动编号列表(&N)"), grp_apply)
        self.chk_auto_border = QCheckBox(safe_tr("边框线(&O)"), grp_apply)
        self.chk_auto_bullet.setChecked(True)
        self.chk_auto_number.setChecked(True)
        self.chk_auto_border.setChecked(True)
        l_grp_a.addWidget(self.chk_auto_bullet)
        l_grp_a.addWidget(self.chk_auto_number)
        l_grp_a.addWidget(self.chk_auto_border)
        l_af.addWidget(grp_apply)
        l_af.addStretch()
        self.tab_widget.addTab(self.tab_af, safe_tr("键入时自动套用格式"))

        # Tab 3: AutoText
        self.tab_at = QWidget(self.tab_widget)
        l_at = QVBoxLayout(self.tab_at)
        self.edit_autotext = QLineEdit(self.tab_at)
        self.edit_autotext.setPlaceholderText(safe_tr("输入自动图文集词条名称"))
        self.list_autotext = QListWidget(self.tab_at)
        self.list_autotext.addItems([
            "致谢",
            "此致",
            "敬礼",
            "顺祝商祺",
            "Best regards,",
            "Sincerely yours,",
            "Confidential",
        ])
        l_at.addWidget(QLabel(safe_tr("自动图文集词条(&E):"), self.tab_at))
        l_at.addWidget(self.edit_autotext)
        l_at.addWidget(self.list_autotext)
        self.tab_widget.addTab(self.tab_at, safe_tr("自动图文集"))

        main_layout.addWidget(self.tab_widget)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def _add_rule(self) -> None:
        src = self.edit_replace.text().strip()
        dst = self.edit_with.text().strip()
        if src and dst:
            row = self.table_rules.rowCount()
            self.table_rules.insertRow(row)
            self.table_rules.setItem(row, 0, QTableWidgetItem(src))
            self.table_rules.setItem(row, 1, QTableWidgetItem(dst))
            self.edit_replace.clear()
            self.edit_with.clear()

    def _delete_rule(self) -> None:
        row = self.table_rules.currentRow()
        if row >= 0:
            self.table_rules.removeRow(row)

    def get_autocorrect_settings(self) -> dict[str, Any]:
        rules = {}
        for r in range(self.table_rules.rowCount()):
            k = self.table_rules.item(r, 0).text()
            v = self.table_rules.item(r, 1).text()
            rules[k] = v
        return {
            "two_caps": self.chk_two_caps.isChecked(),
            "sentence_cap": self.chk_sentence_cap.isChecked(),
            "table_cell_cap": self.chk_table_cell_cap.isChecked(),
            "day_cap": self.chk_day_cap.isChecked(),
            "caps_lock": self.chk_caps_lock.isChecked(),
            "replace_type": self.chk_replace_type.isChecked(),
            "smart_quotes": self.chk_quotes.isChecked(),
            "smart_fractions": self.chk_fractions.isChecked(),
            "rules": rules,
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("自动更正"))
        self.tab_widget.setTabText(0, safe_tr("自动更正"))
        self.tab_widget.setTabText(1, safe_tr("键入时自动套用格式"))
        self.tab_widget.setTabText(2, safe_tr("自动图文集"))


class QuireOptionsDialog(QDialog):
    """Quire Tools Options dialog with 10 tabs (工具选项)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("选项"))
        self.resize(520, 480)

        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget(self)

        # Tab 1: View
        self.tab_view = QWidget(self.tab_widget)
        l_v = QVBoxLayout(self.tab_view)
        grp_show = QGroupBox(safe_tr("显示"), self.tab_view)
        l_g_show = QGridLayout(grp_show)
        self.chk_startup_pane = QCheckBox(safe_tr("启动任务窗格"), grp_show)
        self.chk_highlight = QCheckBox(safe_tr("突出显示"), grp_show)
        self.chk_bookmarks = QCheckBox(safe_tr("书签"), grp_show)
        self.chk_status_bar = QCheckBox(safe_tr("状态栏"), grp_show)
        self.chk_screen_tips = QCheckBox(safe_tr("屏幕提示"), grp_show)
        self.chk_field_codes = QCheckBox(safe_tr("域代码"), grp_show)
        self.chk_startup_pane.setChecked(True)
        self.chk_highlight.setChecked(True)
        self.chk_status_bar.setChecked(True)
        self.chk_screen_tips.setChecked(True)
        l_g_show.addWidget(self.chk_startup_pane, 0, 0)
        l_g_show.addWidget(self.chk_highlight, 0, 1)
        l_g_show.addWidget(self.chk_bookmarks, 1, 0)
        l_g_show.addWidget(self.chk_status_bar, 1, 1)
        l_g_show.addWidget(self.chk_screen_tips, 2, 0)
        l_g_show.addWidget(self.chk_field_codes, 2, 1)
        l_v.addWidget(grp_show)

        grp_marks = QGroupBox(safe_tr("格式标记"), self.tab_view)
        l_g_marks = QVBoxLayout(grp_marks)
        self.chk_all_marks = QCheckBox(safe_tr("全部(&A)"), grp_marks)
        self.chk_hidden_text = QCheckBox(safe_tr("隐藏文字(&H)"), grp_marks)
        l_g_marks.addWidget(self.chk_all_marks)
        l_g_marks.addWidget(self.chk_hidden_text)
        l_v.addWidget(grp_marks)
        l_v.addStretch()
        self.tab_widget.addTab(self.tab_view, safe_tr("视图"))

        # Tab 2: General
        self.tab_gen = QWidget(self.tab_widget)
        f_gen = QFormLayout(self.tab_gen)
        self.combo_units = QComboBox(self.tab_gen)
        self.combo_units.addItems([
            safe_tr("英寸"),
            safe_tr("厘米"),
            safe_tr("毫米"),
            safe_tr("磅"),
            safe_tr("十二点活字"),
        ])
        self.combo_units.setCurrentIndex(1)  # 厘米
        self.spin_recent = QSpinBox(self.tab_gen)
        self.spin_recent.setRange(0, 9)
        self.spin_recent.setValue(4)
        self.chk_sound = QCheckBox(safe_tr("提供声音反馈"), self.tab_gen)
        f_gen.addRow(safe_tr("度量衡单位(&M):"), self.combo_units)
        f_gen.addRow(safe_tr("列出最近使用过的文件数量(&R):"), self.spin_recent)
        f_gen.addRow("", self.chk_sound)
        self.tab_widget.addTab(self.tab_gen, safe_tr("常规"))

        # Tab 3: Edit
        self.tab_edit = QWidget(self.tab_widget)
        l_edit = QVBoxLayout(self.tab_edit)
        self.chk_type_replace = QCheckBox(safe_tr("键入内容替换所选内容(&T)"), self.tab_edit)
        self.chk_drag_drop = QCheckBox(safe_tr("拖放式文字编辑(&D)"), self.tab_edit)
        self.chk_ctrl_click = QCheckBox(safe_tr("按住 CTRL 键单击以跟踪超链接(&H)"), self.tab_edit)
        self.chk_smart_para = QCheckBox(safe_tr("使用智能段落选择(&S)"), self.tab_edit)
        self.chk_overtype = QCheckBox(safe_tr("改写模式(&O)"), self.tab_edit)
        self.chk_type_replace.setChecked(True)
        self.chk_drag_drop.setChecked(True)
        self.chk_ctrl_click.setChecked(True)
        self.chk_smart_para.setChecked(True)
        l_edit.addWidget(self.chk_type_replace)
        l_edit.addWidget(self.chk_drag_drop)
        l_edit.addWidget(self.chk_ctrl_click)
        l_edit.addWidget(self.chk_smart_para)
        l_edit.addWidget(self.chk_overtype)
        l_edit.addStretch()
        self.tab_widget.addTab(self.tab_edit, safe_tr("编辑"))

        # Tab 4: Print
        self.tab_print = QWidget(self.tab_widget)
        l_print = QVBoxLayout(self.tab_print)
        self.chk_update_fields = QCheckBox(safe_tr("更新域(&U)"), self.tab_print)
        self.chk_print_bg = QCheckBox(safe_tr("背景色和图像(&B)"), self.tab_print)
        self.chk_print_props = QCheckBox(safe_tr("文档属性(&P)"), self.tab_print)
        self.chk_print_hidden = QCheckBox(safe_tr("隐藏文字(&H)"), self.tab_print)
        self.chk_print_drawings = QCheckBox(safe_tr("绘图对象(&D)"), self.tab_print)
        self.chk_print_bg.setChecked(True)
        self.chk_print_drawings.setChecked(True)
        l_print.addWidget(self.chk_update_fields)
        l_print.addWidget(self.chk_print_bg)
        l_print.addWidget(self.chk_print_props)
        l_print.addWidget(self.chk_print_hidden)
        l_print.addWidget(self.chk_print_drawings)
        l_print.addStretch()
        self.tab_widget.addTab(self.tab_print, safe_tr("打印"))

        # Tab 5: Save
        self.tab_save = QWidget(self.tab_widget)
        f_save = QFormLayout(self.tab_save)
        self.spin_autorecover = QSpinBox(self.tab_save)
        self.spin_autorecover.setRange(1, 120)
        self.spin_autorecover.setValue(10)
        self.spin_autorecover.setSuffix(safe_tr(" 分钟"))
        self.combo_save_format = QComboBox(self.tab_save)
        self.combo_save_format.addItems([
            "Word 文档 (*.docx)",
            "Word 模板 (*.dotx)",
            "RTF 格式 (*.rtf)",
            "纯文本 (*.txt)",
        ])
        f_save.addRow(safe_tr("保存自动恢复信息时间间隔(&A):"), self.spin_autorecover)
        f_save.addRow(safe_tr("将 Word 文件保存为(&S):"), self.combo_save_format)
        self.tab_widget.addTab(self.tab_save, safe_tr("保存"))

        # Tab 6: Security
        self.tab_sec = QWidget(self.tab_widget)
        f_sec = QFormLayout(self.tab_sec)
        self.edit_password = QLineEdit(self.tab_sec)
        self.edit_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.chk_remove_personal = QCheckBox(
            safe_tr("保存时从文件属性中删除个人信息(&R)"), self.tab_sec
        )
        self.chk_warn_tracked = QCheckBox(
            safe_tr("打印、保存或发送包含修订/批注的文件之前发出警告(&W)"), self.tab_sec
        )
        f_sec.addRow(safe_tr("打开文件时的密码(&P):"), self.edit_password)
        f_sec.addRow("", self.chk_remove_personal)
        f_sec.addRow("", self.chk_warn_tracked)
        self.tab_widget.addTab(self.tab_sec, safe_tr("安全性"))

        # Tab 7: Spelling & Grammar
        self.tab_spell = QWidget(self.tab_widget)
        l_spell = QVBoxLayout(self.tab_spell)
        self.chk_spell_as_type = QCheckBox(safe_tr("键入时检查拼写(&S)"), self.tab_spell)
        self.chk_ignore_caps = QCheckBox(safe_tr("忽略全部大写的单词(&U)"), self.tab_spell)
        self.chk_ignore_nums = QCheckBox(safe_tr("忽略包含数字的单词(&N)"), self.tab_spell)
        self.chk_grammar_as_type = QCheckBox(safe_tr("键入时检查语法(&G)"), self.tab_spell)
        self.chk_spell_as_type.setChecked(True)
        self.chk_ignore_caps.setChecked(True)
        self.chk_ignore_nums.setChecked(True)
        self.chk_grammar_as_type.setChecked(True)
        l_spell.addWidget(self.chk_spell_as_type)
        l_spell.addWidget(self.chk_ignore_caps)
        l_spell.addWidget(self.chk_ignore_nums)
        l_spell.addWidget(self.chk_grammar_as_type)
        l_spell.addStretch()
        self.tab_widget.addTab(self.tab_spell, safe_tr("拼写和语法"))

        # Tab 8: Track Changes
        self.tab_track = QWidget(self.tab_widget)
        f_track = QFormLayout(self.tab_track)
        self.combo_ins_color = QComboBox(self.tab_track)
        self.combo_ins_color.addItems([
            safe_tr("按作者"),
            safe_tr("红色"),
            safe_tr("蓝色"),
            safe_tr("绿色"),
        ])
        self.combo_balloons = QComboBox(self.tab_track)
        self.combo_balloons.addItems([
            safe_tr("仅用于批注和格式设置"),
            safe_tr("始终"),
            safe_tr("从不"),
        ])
        f_track.addRow(safe_tr("插入标记颜色:"), self.combo_ins_color)
        f_track.addRow(safe_tr("使用批注框:"), self.combo_balloons)
        self.tab_widget.addTab(self.tab_track, safe_tr("修订"))

        # Tab 9: User Information
        self.tab_user = QWidget(self.tab_widget)
        f_user = QFormLayout(self.tab_user)
        self.edit_user_name = QLineEdit(self.tab_user)
        self.edit_user_initials = QLineEdit(self.tab_user)
        self.edit_user_addr = QPlainTextEdit(self.tab_user)
        self.edit_user_addr.setMaximumHeight(80)
        f_user.addRow(safe_tr("姓名(&N):"), self.edit_user_name)
        f_user.addRow(safe_tr("缩写(&I):"), self.edit_user_initials)
        f_user.addRow(safe_tr("通讯地址(&A):"), self.edit_user_addr)
        self.tab_widget.addTab(self.tab_user, safe_tr("用户信息"))

        # Tab 10: Compatibility
        self.tab_compat = QWidget(self.tab_widget)
        f_compat = QFormLayout(self.tab_compat)
        self.combo_compat = QComboBox(self.tab_compat)
        self.combo_compat.addItems([
            "Microsoft Word 2003",
            "Microsoft Word 2007",
            "Microsoft Word 2010",
            "Microsoft Word 2013 and later",
        ])
        f_compat.addRow(safe_tr("推荐选项适于(&R):"), self.combo_compat)
        self.tab_widget.addTab(self.tab_compat, safe_tr("兼容性"))

        main_layout.addWidget(self.tab_widget)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def get_options_data(self) -> dict[str, Any]:
        return {
            "startup_pane": self.chk_startup_pane.isChecked(),
            "status_bar": self.chk_status_bar.isChecked(),
            "units": self.combo_units.currentText(),
            "recent_count": self.spin_recent.value(),
            "type_replaces": self.chk_type_replace.isChecked(),
            "autorecover_min": self.spin_autorecover.value(),
            "save_format": self.combo_save_format.currentText(),
            "password": self.edit_password.text(),
            "spell_check": self.chk_spell_as_type.isChecked(),
            "user_name": self.edit_user_name.text(),
            "compat_mode": self.combo_compat.currentText(),
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("选项"))
        labels = [
            safe_tr("视图"),
            safe_tr("常规"),
            safe_tr("编辑"),
            safe_tr("打印"),
            safe_tr("保存"),
            safe_tr("安全性"),
            safe_tr("拼写和语法"),
            safe_tr("修订"),
            safe_tr("用户信息"),
            safe_tr("兼容性"),
        ]
        for i, lab in enumerate(labels):
            self.tab_widget.setTabText(i, lab)


class CustomizeDialog(QDialog):
    """Customize Toolbars & Commands dialog with 4 tabs (自定义)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("自定义"))
        self.resize(460, 380)

        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget(self)

        # Tab 1: Toolbars
        self.tab_tbs = QWidget(self.tab_widget)
        l_tbs = QVBoxLayout(self.tab_tbs)
        self.list_tbs = QListWidget(self.tab_tbs)
        toolbars = [
            safe_tr("常用"),
            safe_tr("格式"),
            safe_tr("绘图"),
            safe_tr("表格与边框"),
            safe_tr("审阅"),
            safe_tr("图片"),
            safe_tr("大纲"),
            safe_tr("页眉和页脚"),
            safe_tr("邮件合并"),
            safe_tr("艺术字"),
        ]
        for tb in toolbars:
            it = QListWidgetItem(tb, self.list_tbs)
            it.setCheckState(Qt.CheckState.Checked)
        l_tbs.addWidget(QLabel(safe_tr("工具栏(&T):"), self.tab_tbs))
        l_tbs.addWidget(self.list_tbs)
        self.tab_widget.addTab(self.tab_tbs, safe_tr("工具栏"))

        # Tab 2: Commands
        self.tab_cmds = QWidget(self.tab_widget)
        h_cmds = QHBoxLayout(self.tab_cmds)
        v_cat = QVBoxLayout()
        v_cat.addWidget(QLabel(safe_tr("类别(&G):"), self.tab_cmds))
        self.list_cats = QListWidget(self.tab_cmds)
        self.list_cats.addItems([
            safe_tr("文件"),
            safe_tr("编辑"),
            safe_tr("视图"),
            safe_tr("插入"),
            safe_tr("格式"),
            safe_tr("工具"),
            safe_tr("表格"),
            safe_tr("窗口"),
            safe_tr("帮助"),
        ])
        v_cat.addWidget(self.list_cats)
        h_cmds.addLayout(v_cat)

        v_cmd = QVBoxLayout()
        v_cmd.addWidget(QLabel(safe_tr("命令(&D):"), self.tab_cmds))
        self.list_cmds = QListWidget(self.tab_cmds)
        self.list_cmds.addItems([
            safe_tr("新建"),
            safe_tr("打开"),
            safe_tr("关闭"),
            safe_tr("保存"),
            safe_tr("另存为"),
            safe_tr("打印"),
            safe_tr("打印预览"),
        ])
        v_cmd.addWidget(self.list_cmds)
        h_cmds.addLayout(v_cmd)
        self.tab_widget.addTab(self.tab_cmds, safe_tr("命令"))

        # Tab 3: Options
        self.tab_opts = QWidget(self.tab_widget)
        l_opts = QVBoxLayout(self.tab_opts)
        self.chk_large_icons = QCheckBox(safe_tr("大图标(&L)"), self.tab_opts)
        self.chk_screen_tips = QCheckBox(safe_tr("在工具栏上显示屏幕提示(&T)"), self.tab_opts)
        self.chk_shortcut_tips = QCheckBox(safe_tr("在屏幕提示中包含快捷键(&K)"), self.tab_opts)
        self.chk_screen_tips.setChecked(True)
        l_opts.addWidget(self.chk_large_icons)
        l_opts.addWidget(self.chk_screen_tips)
        l_opts.addWidget(self.chk_shortcut_tips)
        l_opts.addStretch()
        self.tab_widget.addTab(self.tab_opts, safe_tr("选项"))

        # Tab 4: Keyboard
        self.tab_kb = QWidget(self.tab_widget)
        f_kb = QFormLayout(self.tab_kb)
        self.edit_new_key = QLineEdit(self.tab_kb)
        self.edit_new_key.setPlaceholderText(safe_tr("请按新快捷键"))
        self.lbl_curr_key = QLabel(safe_tr("当前快捷键: 无"), self.tab_kb)
        self.btn_assign = QPushButton(safe_tr("指定(&A)"), self.tab_kb)
        f_kb.addRow(self.lbl_curr_key)
        f_kb.addRow(safe_tr("按新快捷键(&N):"), self.edit_new_key)
        f_kb.addRow("", self.btn_assign)
        self.tab_widget.addTab(self.tab_kb, safe_tr("键盘"))

        main_layout.addWidget(self.tab_widget)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("自定义"))
        self.tab_widget.setTabText(0, safe_tr("工具栏"))
        self.tab_widget.setTabText(1, safe_tr("命令"))
        self.tab_widget.setTabText(2, safe_tr("选项"))
        self.tab_widget.setTabText(3, safe_tr("键盘"))


class EnvelopesLabelsDialog(QDialog):
    """Envelopes and Labels dialog with 2 tabs (信封和标签)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("信封和标签"))
        self.resize(460, 380)

        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget(self)

        # Tab 1: Envelopes
        self.tab_env = QWidget(self.tab_widget)
        l_env = QVBoxLayout(self.tab_env)
        self.edit_delivery = QPlainTextEdit(self.tab_env)
        self.edit_delivery.setMaximumHeight(80)
        self.edit_return = QPlainTextEdit(self.tab_env)
        self.edit_return.setMaximumHeight(70)
        self.chk_omit = QCheckBox(safe_tr("忽略(&O)"), self.tab_env)
        self.combo_size = QComboBox(self.tab_env)
        self.combo_size.addItems([
            "Size 10 (4 1/8 x 9 1/2 in)",
            "DL (110 x 220 mm)",
            "C5 (162 x 229 mm)",
            "Monarch (3 7/8 x 7 1/2 in)",
        ])
        l_env.addWidget(QLabel(safe_tr("收件人地址(&D):"), self.tab_env))
        l_env.addWidget(self.edit_delivery)
        l_env.addWidget(QLabel(safe_tr("寄件人地址(&R):"), self.tab_env))
        l_env.addWidget(self.edit_return)
        l_env.addWidget(self.chk_omit)
        h_size = QHBoxLayout()
        h_size.addWidget(QLabel(safe_tr("信封大小:"), self.tab_env))
        h_size.addWidget(self.combo_size)
        l_env.addLayout(h_size)
        self.tab_widget.addTab(self.tab_env, safe_tr("信封"))

        # Tab 2: Labels
        self.tab_lab = QWidget(self.tab_widget)
        l_lab = QVBoxLayout(self.tab_lab)
        self.edit_lab_addr = QPlainTextEdit(self.tab_lab)
        self.edit_lab_addr.setMaximumHeight(90)
        self.radio_full_page = QRadioButton(safe_tr("整页相同标签(&F)"), self.tab_lab)
        self.radio_single = QRadioButton(safe_tr("单张标签(&S)"), self.tab_lab)
        self.radio_full_page.setChecked(True)
        l_lab.addWidget(QLabel(safe_tr("标签地址(&A):"), self.tab_lab))
        l_lab.addWidget(self.edit_lab_addr)
        l_lab.addWidget(self.radio_full_page)
        l_lab.addWidget(self.radio_single)
        l_lab.addStretch()
        self.tab_widget.addTab(self.tab_lab, safe_tr("标签"))

        main_layout.addWidget(self.tab_widget)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def get_envelope_data(self) -> dict[str, Any]:
        return {
            "tab": "envelopes" if self.tab_widget.currentIndex() == 0 else "labels",
            "delivery": self.edit_delivery.toPlainText(),
            "return_addr": self.edit_return.toPlainText(),
            "omit_return": self.chk_omit.isChecked(),
            "size": self.combo_size.currentText(),
            "label_addr": self.edit_lab_addr.toPlainText(),
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("信封和标签"))
        self.tab_widget.setTabText(0, safe_tr("信封"))
        self.tab_widget.setTabText(1, safe_tr("标签"))


class LetterWizardDialog(QDialog):
    """Letter Creation Wizard with 4 steps/tabs (信件向导)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("信件向导"))
        self.resize(460, 360)

        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget(self)

        # Tab 1: Letter Format
        self.tab_fmt = QWidget(self.tab_widget)
        f_fmt = QFormLayout(self.tab_fmt)
        self.chk_date = QCheckBox(safe_tr("日期行(&D):"), self.tab_fmt)
        self.chk_date.setChecked(True)
        self.combo_date_format = QComboBox(self.tab_fmt)
        self.combo_date_format.addItems(["yyyy年M月d日", "yyyy-MM-dd", "MMMM d, yyyy"])
        self.combo_style = QComboBox(self.tab_fmt)
        self.combo_style.addItems([
            safe_tr("全齐式 (Full block)"),
            safe_tr("折中式 (Modified block)"),
            safe_tr("半折中式 (Semi-block)"),
        ])
        f_fmt.addRow(self.chk_date, self.combo_date_format)
        f_fmt.addRow(safe_tr("信件样式(&S):"), self.combo_style)
        self.tab_widget.addTab(self.tab_fmt, safe_tr("信件格式"))

        # Tab 2: Recipient Info
        self.tab_rec = QWidget(self.tab_widget)
        f_rec = QFormLayout(self.tab_rec)
        self.edit_r_name = QLineEdit(self.tab_rec)
        self.edit_r_addr = QPlainTextEdit(self.tab_rec)
        self.edit_r_addr.setMaximumHeight(80)
        self.edit_r_salutation = QLineEdit(self.tab_rec)
        self.edit_r_salutation.setText(safe_tr("尊敬的客户:"))
        f_rec.addRow(safe_tr("收件人姓名(&R):"), self.edit_r_name)
        f_rec.addRow(safe_tr("收件人地址(&D):"), self.edit_r_addr)
        f_rec.addRow(safe_tr("称谓(&S):"), self.edit_r_salutation)
        self.tab_widget.addTab(self.tab_rec, safe_tr("收件人信息"))

        # Tab 3: Other Elements
        self.tab_oth = QWidget(self.tab_widget)
        f_oth = QFormLayout(self.tab_oth)
        self.edit_ref = QLineEdit(self.tab_oth)
        self.edit_subject = QLineEdit(self.tab_oth)
        f_oth.addRow(safe_tr("参考号(&L):"), self.edit_ref)
        f_oth.addRow(safe_tr("主题(&J):"), self.edit_subject)
        self.tab_widget.addTab(self.tab_oth, safe_tr("其他元素"))

        # Tab 4: Sender Info
        self.tab_snd = QWidget(self.tab_widget)
        f_snd = QFormLayout(self.tab_snd)
        self.edit_s_name = QLineEdit(self.tab_snd)
        self.edit_s_addr = QPlainTextEdit(self.tab_snd)
        self.edit_s_addr.setMaximumHeight(80)
        self.edit_s_closing = QLineEdit(self.tab_snd)
        self.edit_s_closing.setText(safe_tr("顺祝商祺"))
        f_snd.addRow(safe_tr("发件人姓名(&S):"), self.edit_s_name)
        f_snd.addRow(safe_tr("发件人地址(&A):"), self.edit_s_addr)
        f_snd.addRow(safe_tr("结束语(&C):"), self.edit_s_closing)
        self.tab_widget.addTab(self.tab_snd, safe_tr("发件人信息"))

        main_layout.addWidget(self.tab_widget)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def get_letter_data(self) -> dict[str, Any]:
        return {
            "date_line": self.chk_date.isChecked(),
            "date_format": self.combo_date_format.currentText(),
            "style": self.combo_style.currentText(),
            "recipient_name": self.edit_r_name.text(),
            "recipient_addr": self.edit_r_addr.toPlainText(),
            "salutation": self.edit_r_salutation.text(),
            "subject": self.edit_subject.text(),
            "sender_name": self.edit_s_name.text(),
            "sender_addr": self.edit_s_addr.toPlainText(),
            "closing": self.edit_s_closing.text(),
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("信件向导"))
        self.tab_widget.setTabText(0, safe_tr("信件格式"))
        self.tab_widget.setTabText(1, safe_tr("收件人信息"))
        self.tab_widget.setTabText(2, safe_tr("其他元素"))
        self.tab_widget.setTabText(3, safe_tr("发件人信息"))


class AutoSummarizeDialog(QDialog):
    """AutoSummarize Document Content dialog (自动摘要)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("自动编写摘要"))
        self.resize(340, 260)

        layout = QVBoxLayout(self)

        self.grp_type = QGroupBox(safe_tr("摘要类型"), self)
        l_type = QVBoxLayout(self.grp_type)
        self.radio_highlight = QRadioButton(safe_tr("突出显示关键点(&H)"), self.grp_type)
        self.radio_top = QRadioButton(safe_tr("在文档顶端插入执行摘要(&I)"), self.grp_type)
        self.radio_new = QRadioButton(safe_tr("创建新文档并放入摘要(&C)"), self.grp_type)
        self.radio_hide = QRadioButton(safe_tr("隐藏摘要以外的所有内容(&E)"), self.grp_type)
        self.radio_highlight.setChecked(True)
        l_type.addWidget(self.radio_highlight)
        l_type.addWidget(self.radio_top)
        l_type.addWidget(self.radio_new)
        l_type.addWidget(self.radio_hide)
        layout.addWidget(self.grp_type)

        f_len = QFormLayout()
        self.combo_length = QComboBox(self)
        self.combo_length.addItems([
            "10 句话",
            "20 句话",
            "100 字或更少",
            "500 字或更少",
            "10%",
            "25%",
            "50%",
            "75%",
        ])
        self.combo_length.setCurrentIndex(5)  # 25%
        self.chk_update_stats = QCheckBox(safe_tr("更新文档统计信息(&U)"), self)
        f_len.addRow(safe_tr("相当于原长的百分比(&P):"), self.combo_length)
        f_len.addRow("", self.chk_update_stats)
        layout.addLayout(f_len)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_summarize_data(self) -> dict[str, Any]:
        mode = "highlight"
        if self.radio_top.isChecked():
            mode = "top"
        elif self.radio_new.isChecked():
            mode = "new"
        elif self.radio_hide.isChecked():
            mode = "hide"
        return {
            "mode": mode,
            "length": self.combo_length.currentText(),
            "update_stats": self.chk_update_stats.isChecked(),
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("自动编写摘要"))
        self.grp_type.setTitle(safe_tr("摘要类型"))
        self.radio_highlight.setText(safe_tr("突出显示关键点(&H)"))
        self.radio_top.setText(safe_tr("在文档顶端插入执行摘要(&I)"))
        self.radio_new.setText(safe_tr("创建新文档并放入摘要(&C)"))
        self.radio_hide.setText(safe_tr("隐藏摘要以外的所有内容(&E)"))


class HyphenationDialog(QDialog):
    """Hyphenation Settings dialog (断字)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("断字"))
        self.resize(300, 180)

        layout = QVBoxLayout(self)

        self.chk_auto = QCheckBox(safe_tr("自动断字(&A)"), self)
        self.chk_caps = QCheckBox(safe_tr("大写字母单词断字(&C)"), self)
        self.chk_caps.setChecked(True)
        layout.addWidget(self.chk_auto)
        layout.addWidget(self.chk_caps)

        f_layout = QFormLayout()
        self.spin_zone = QDoubleSpinBox(self)
        self.spin_zone.setRange(0.0, 50.0)
        self.spin_zone.setValue(18.0)
        self.spin_zone.setSuffix(safe_tr(" pt"))

        self.spin_limit = QSpinBox(self)
        self.spin_limit.setRange(0, 10)
        self.spin_limit.setValue(0)
        self.spin_limit.setSpecialValueText(safe_tr("不限制"))

        f_layout.addRow(safe_tr("断字区(&Z):"), self.spin_zone)
        f_layout.addRow(safe_tr("连续连字符限制(&L):"), self.spin_limit)
        layout.addLayout(f_layout)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_hyphenation_settings(self) -> dict[str, Any]:
        return {
            "auto": self.chk_auto.isChecked(),
            "hyphenate_caps": self.chk_caps.isChecked(),
            "zone_pt": self.spin_zone.value(),
            "limit": self.spin_limit.value(),
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("断字"))
        self.chk_auto.setText(safe_tr("自动断字(&A)"))
        self.chk_caps.setText(safe_tr("大写字母单词断字(&C)"))
        self.spin_limit.setSpecialValueText(safe_tr("不限制"))

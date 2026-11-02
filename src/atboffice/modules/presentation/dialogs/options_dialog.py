"""PowerPoint 2003 Classic Tools -> Options Dialog for Lectern."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely for LecternOptionsDialog."""
    return QCoreApplication.translate("LecternOptionsDialog", text)


class LecternOptionsDialog(QDialog):
    """Lectern Tools -> Options dialog configuring application and document preferences."""

    def __init__(
        self,
        options: dict[str, Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.options: dict[str, Any] = dict(options or {})
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle(safe_tr("选项"))
        self.resize(460, 380)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        self.tabs = QTabWidget(self)

        self._build_view_tab()
        self._build_general_tab()
        self._build_edit_tab()
        self._build_spelling_tab()
        self._build_security_tab()

        main_layout.addWidget(self.tabs, 1)

        # OK / Cancel Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self._load_options()

    # --- 1. View Tab ---
    def _build_view_tab(self) -> None:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        # Show group
        self.grp_view_show = QGroupBox(safe_tr("显示"), tab)
        show_layout = QVBoxLayout(self.grp_view_show)
        self.chk_startup_pane = QCheckBox(safe_tr("启动任务窗格(&T)"), tab)
        self.chk_layout_pane = QCheckBox(safe_tr("插入新幻灯片时显示幻灯片版式任务窗格(&S)"), tab)
        self.chk_pane_follows = QCheckBox(safe_tr("任务窗格跟随所选对象(&O)"), tab)
        self.chk_status_bar = QCheckBox(safe_tr("状态栏(&U)"), tab)
        self.chk_vertical_ruler = QCheckBox(safe_tr("垂直标尺(&V)"), tab)

        show_layout.addWidget(self.chk_startup_pane)
        show_layout.addWidget(self.chk_layout_pane)
        show_layout.addWidget(self.chk_pane_follows)
        show_layout.addWidget(self.chk_status_bar)
        show_layout.addWidget(self.chk_vertical_ruler)
        layout.addWidget(self.grp_view_show)

        # Slide Show group
        self.grp_view_show_opts = QGroupBox(safe_tr("幻灯片放映"), tab)
        show_opts_layout = QVBoxLayout(self.grp_view_show_opts)
        self.chk_popup_menu_click = QCheckBox(safe_tr("单击鼠标右键显示快捷菜单(&P)"), tab)
        self.chk_popup_menu_button = QCheckBox(safe_tr("显示快捷菜单按钮(&B)"), tab)
        self.chk_end_black_slide = QCheckBox(safe_tr("以黑屏幻灯片结束(&E)"), tab)

        show_opts_layout.addWidget(self.chk_popup_menu_click)
        show_opts_layout.addWidget(self.chk_popup_menu_button)
        show_opts_layout.addWidget(self.chk_end_black_slide)
        layout.addWidget(self.grp_view_show_opts)
        layout.addStretch()

        self.tabs.addTab(tab, safe_tr("视图"))

    # --- 2. General Tab ---
    def _build_general_tab(self) -> None:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        # User information
        self.grp_user_info = QGroupBox(safe_tr("用户信息"), tab)
        user_layout = QVBoxLayout(self.grp_user_info)

        row_name = QHBoxLayout()
        self.lbl_user_name = QLabel(safe_tr("姓名(&N):"), tab)
        self.edit_user_name = QLineEdit(tab)
        row_name.addWidget(self.lbl_user_name)
        row_name.addWidget(self.edit_user_name)
        user_layout.addLayout(row_name)

        row_initials = QHBoxLayout()
        self.lbl_initials = QLabel(safe_tr("缩写(&I):"), tab)
        self.edit_initials = QLineEdit(tab)
        self.edit_initials.setMaximumWidth(80)
        row_initials.addWidget(self.lbl_initials)
        row_initials.addWidget(self.edit_initials)
        row_initials.addStretch()
        user_layout.addLayout(row_initials)

        layout.addWidget(self.grp_user_info)

        # Recent files
        row_recent = QHBoxLayout()
        self.chk_recent = QCheckBox(safe_tr("最近使用的文件列表(&R):"), tab)
        self.spin_recent = QSpinBox(tab)
        self.spin_recent.setRange(1, 9)
        self.spin_recent.setValue(4)
        row_recent.addWidget(self.chk_recent)
        row_recent.addWidget(self.spin_recent)
        row_recent.addStretch()
        layout.addLayout(row_recent)
        layout.addStretch()

        self.tabs.addTab(tab, safe_tr("常规"))

    # --- 3. Edit Tab ---
    def _build_edit_tab(self) -> None:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        # Text group
        self.grp_edit_text = QGroupBox(safe_tr("文字"), tab)
        text_layout = QVBoxLayout(self.grp_edit_text)
        self.chk_smart_quotes = QCheckBox(safe_tr("将直引号替换为弯引号(&Q)"), tab)
        self.chk_autocorrect = QCheckBox(safe_tr("键入时自动更正(&A)"), tab)
        self.chk_cap_sentence = QCheckBox(safe_tr("句首字母大写(&C)"), tab)

        text_layout.addWidget(self.chk_smart_quotes)
        text_layout.addWidget(self.chk_autocorrect)
        text_layout.addWidget(self.chk_cap_sentence)
        layout.addWidget(self.grp_edit_text)

        # Undo group
        self.grp_undo = QGroupBox(safe_tr("撤消"), tab)
        undo_layout = QHBoxLayout(self.grp_undo)
        self.lbl_max_undos = QLabel(safe_tr("最大撤消次数(&U):"), tab)
        self.spin_max_undos = QSpinBox(tab)
        self.spin_max_undos.setRange(3, 150)
        self.spin_max_undos.setValue(20)
        undo_layout.addWidget(self.lbl_max_undos)
        undo_layout.addWidget(self.spin_max_undos)
        undo_layout.addStretch()
        layout.addWidget(self.grp_undo)
        layout.addStretch()

        self.tabs.addTab(tab, safe_tr("编辑"))

    # --- 4. Spelling and Style Tab ---
    def _build_spelling_tab(self) -> None:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        self.grp_spelling = QGroupBox(safe_tr("拼写"), tab)
        spelling_layout = QVBoxLayout(self.grp_spelling)
        self.chk_check_spelling = QCheckBox(safe_tr("键入时检查拼写(&S)"), tab)
        self.chk_ignore_uppercase = QCheckBox(safe_tr("忽略全部大写的单词(&P)"), tab)
        self.chk_ignore_numbers = QCheckBox(safe_tr("忽略包含数字的单词(&N)"), tab)

        spelling_layout.addWidget(self.chk_check_spelling)
        spelling_layout.addWidget(self.chk_ignore_uppercase)
        spelling_layout.addWidget(self.chk_ignore_numbers)
        layout.addWidget(self.grp_spelling)
        layout.addStretch()

        self.tabs.addTab(tab, safe_tr("拼写与样式"))

    # --- 5. Security Tab ---
    def _build_security_tab(self) -> None:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        self.grp_security = QGroupBox(safe_tr("此文档的文件加密设置"), tab)
        sec_layout = QVBoxLayout(self.grp_security)

        r_open = QHBoxLayout()
        self.lbl_pw_open = QLabel(safe_tr("打开文件时的密码(&O):"), tab)
        self.edit_pw_open = QLineEdit(tab)
        self.edit_pw_open.setEchoMode(QLineEdit.EchoMode.Password)
        r_open.addWidget(self.lbl_pw_open)
        r_open.addWidget(self.edit_pw_open)
        sec_layout.addLayout(r_open)

        r_mod = QHBoxLayout()
        self.lbl_pw_modify = QLabel(safe_tr("修改文件时的密码(&M):"), tab)
        self.edit_pw_modify = QLineEdit(tab)
        self.edit_pw_modify.setEchoMode(QLineEdit.EchoMode.Password)
        r_mod.addWidget(self.lbl_pw_modify)
        r_mod.addWidget(self.edit_pw_modify)
        sec_layout.addLayout(r_mod)

        layout.addWidget(self.grp_security)
        layout.addStretch()

        self.tabs.addTab(tab, safe_tr("安全性"))

    def _load_options(self) -> None:
        o = self.options
        self.chk_startup_pane.setChecked(bool(o.get("startup_pane", True)))
        self.chk_layout_pane.setChecked(bool(o.get("layout_pane_on_new", True)))
        self.chk_pane_follows.setChecked(bool(o.get("pane_follows", False)))
        self.chk_status_bar.setChecked(bool(o.get("status_bar", True)))
        self.chk_vertical_ruler.setChecked(bool(o.get("vertical_ruler", True)))

        self.chk_popup_menu_click.setChecked(bool(o.get("popup_menu_click", True)))
        self.chk_popup_menu_button.setChecked(bool(o.get("popup_menu_button", True)))
        self.chk_end_black_slide.setChecked(bool(o.get("end_black_slide", True)))

        self.edit_user_name.setText(str(o.get("user_name", "")))
        self.edit_initials.setText(str(o.get("initials", "")))
        self.chk_recent.setChecked(bool(o.get("show_recent", True)))
        self.spin_recent.setValue(int(o.get("recent_count", 4)))

        self.chk_smart_quotes.setChecked(bool(o.get("smart_quotes", True)))
        self.chk_autocorrect.setChecked(bool(o.get("autocorrect", True)))
        self.chk_cap_sentence.setChecked(bool(o.get("cap_sentence", True)))
        self.spin_max_undos.setValue(int(o.get("max_undos", 20)))

        self.chk_check_spelling.setChecked(bool(o.get("check_spelling", True)))
        self.chk_ignore_uppercase.setChecked(bool(o.get("ignore_uppercase", True)))
        self.chk_ignore_numbers.setChecked(bool(o.get("ignore_numbers", False)))

        self.edit_pw_open.setText(str(o.get("pw_open", "")))
        self.edit_pw_modify.setText(str(o.get("pw_modify", "")))

    def _on_accept(self) -> None:
        self.options = self.get_options()
        self.accept()

    def get_options(self) -> dict[str, Any]:
        """Return full dictionary of updated option preferences."""
        return {
            "startup_pane": self.chk_startup_pane.isChecked(),
            "layout_pane_on_new": self.chk_layout_pane.isChecked(),
            "pane_follows": self.chk_pane_follows.isChecked(),
            "status_bar": self.chk_status_bar.isChecked(),
            "vertical_ruler": self.chk_vertical_ruler.isChecked(),
            "popup_menu_click": self.chk_popup_menu_click.isChecked(),
            "popup_menu_button": self.chk_popup_menu_button.isChecked(),
            "end_black_slide": self.chk_end_black_slide.isChecked(),
            "user_name": self.edit_user_name.text(),
            "initials": self.edit_initials.text(),
            "show_recent": self.chk_recent.isChecked(),
            "recent_count": self.spin_recent.value(),
            "smart_quotes": self.chk_smart_quotes.isChecked(),
            "autocorrect": self.chk_autocorrect.isChecked(),
            "cap_sentence": self.chk_cap_sentence.isChecked(),
            "max_undos": self.spin_max_undos.value(),
            "check_spelling": self.chk_check_spelling.isChecked(),
            "ignore_uppercase": self.chk_ignore_uppercase.isChecked(),
            "ignore_numbers": self.chk_ignore_numbers.isChecked(),
            "pw_open": self.edit_pw_open.text(),
            "pw_modify": self.edit_pw_modify.text(),
        }

    def set_options(self, opts: dict[str, Any]) -> None:
        """Set new option preferences and update controls."""
        self.options = dict(opts)
        self._load_options()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("选项"))
        self.tabs.setTabText(0, safe_tr("视图"))
        self.tabs.setTabText(1, safe_tr("常规"))
        self.tabs.setTabText(2, safe_tr("编辑"))
        self.tabs.setTabText(3, safe_tr("拼写与样式"))
        self.tabs.setTabText(4, safe_tr("安全性"))
        self.grp_view_show.setTitle(safe_tr("显示"))
        self.grp_view_show_opts.setTitle(safe_tr("幻灯片放映"))
        self.grp_user_info.setTitle(safe_tr("用户信息"))
        self.lbl_user_name.setText(safe_tr("姓名(&N):"))
        self.lbl_initials.setText(safe_tr("缩写(&I):"))
        self.chk_recent.setText(safe_tr("最近使用的文件列表(&R):"))
        self.grp_edit_text.setTitle(safe_tr("文字"))
        self.grp_undo.setTitle(safe_tr("撤消"))
        self.lbl_max_undos.setText(safe_tr("最大撤消次数(&U):"))
        self.grp_spelling.setTitle(safe_tr("拼写"))
        self.grp_security.setTitle(safe_tr("此文档的文件加密设置"))
        self.lbl_pw_open.setText(safe_tr("打开文件时的密码(&O):"))
        self.lbl_pw_modify.setText(safe_tr("修改文件时的密码(&M):"))

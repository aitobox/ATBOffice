"""Comprehensive multi-tab Options preference dialog for ATBOffice."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from atboffice.core.i18n import (
    LOCALE_DISPLAY_NAMES,
    SUPPORTED_LOCALES,
    load_locale,
    safe_tr,
)
from atboffice.core.settings import DEFAULT_SETTINGS, get_app_settings
from atboffice.core.window_manager import WindowManager

if TYPE_CHECKING:
    pass


class OptionsDialog(QDialog):
    """Universal multi-tab preferences configuration dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = get_app_settings()
        self._build_ui()
        self.load_from_settings()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        self.resize(540, 420)
        self.setMinimumSize(480, 360)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        self.tab_widget = QTabWidget(self)
        main_layout.addWidget(self.tab_widget)

        # Tab 1: General
        self.tab_general = QWidget()
        self._build_general_tab()
        self.tab_widget.addTab(self.tab_general, "")

        # Tab 2: View
        self.tab_view = QWidget()
        self._build_view_tab()
        self.tab_widget.addTab(self.tab_view, "")

        # Tab 3: Edit
        self.tab_edit = QWidget()
        self._build_edit_tab()
        self.tab_widget.addTab(self.tab_edit, "")

        # Tab 4: Save
        self.tab_save = QWidget()
        self._build_save_tab()
        self.tab_widget.addTab(self.tab_save, "")

        # Tab 5: Language
        self.tab_language = QWidget()
        self._build_language_tab()
        self.tab_widget.addTab(self.tab_language, "")

        # Bottom Button Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        self.btn_restore_defaults = QPushButton(safe_tr("恢复默认设置"), self)
        self.btn_restore_defaults.clicked.connect(self._on_restore_defaults)
        bottom_bar.addWidget(self.btn_restore_defaults)

        bottom_bar.addStretch(1)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply,
            self,
        )
        self.button_box.accepted.connect(self._on_ok)
        self.button_box.rejected.connect(self.reject)
        btn_apply = self.button_box.button(QDialogButtonBox.StandardButton.Apply)
        if btn_apply is not None:
            btn_apply.clicked.connect(self._on_apply)
        bottom_bar.addWidget(self.button_box)

        main_layout.addLayout(bottom_bar)

    # -------------------------------------------------------------------------
    # Tab Builders
    # -------------------------------------------------------------------------
    def _build_general_tab(self) -> None:
        layout = QVBoxLayout(self.tab_general)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)

        # Default Open Path
        path_box = QHBoxLayout()
        self.txt_default_path = QLineEdit(self.tab_general)
        path_box.addWidget(self.txt_default_path)
        self.btn_browse_path = QPushButton(safe_tr("浏览…"), self.tab_general)
        self.btn_browse_path.clicked.connect(self._on_browse_path)
        path_box.addWidget(self.btn_browse_path)

        self.lbl_default_path = QLabel(safe_tr("默认打开位置："), self.tab_general)
        form.addRow(self.lbl_default_path, path_box)

        # Recent Files Limit
        self.spin_recent_limit = QSpinBox(self.tab_general)
        self.spin_recent_limit.setRange(5, 100)
        self.spin_recent_limit.setValue(20)
        self.lbl_recent_limit = QLabel(safe_tr("最近文件保留上限："), self.tab_general)
        form.addRow(self.lbl_recent_limit, self.spin_recent_limit)

        layout.addLayout(form)

        # Startup Behavior Group
        self.grp_startup = QGroupBox(safe_tr("启动行为"), self.tab_general)
        grp_layout = QVBoxLayout(self.grp_startup)
        grp_layout.setSpacing(8)

        self.rb_start_center = QRadioButton(
            safe_tr("显示启动中心（推荐）"), self.grp_startup
        )
        self.rb_start_new_doc = QRadioButton(
            safe_tr("直接新建空白文档"), self.grp_startup
        )
        self.start_group = QButtonGroup(self.tab_general)
        self.start_group.addButton(self.rb_start_center, 0)
        self.start_group.addButton(self.rb_start_new_doc, 1)
        self.rb_start_center.setChecked(True)

        grp_layout.addWidget(self.rb_start_center)
        grp_layout.addWidget(self.rb_start_new_doc)
        layout.addWidget(self.grp_startup)
        layout.addStretch(1)

    def _build_view_tab(self) -> None:
        layout = QVBoxLayout(self.tab_view)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)

        # UI Scale
        self.combo_ui_scale = QComboBox(self.tab_view)
        self.combo_ui_scale.addItems(["100%", "125%", "150%", "200%"])
        self.lbl_ui_scale = QLabel(safe_tr("界面缩放比率："), self.tab_view)
        form.addRow(self.lbl_ui_scale, self.combo_ui_scale)

        # Status Bar Tip Duration
        self.spin_status_timeout = QSpinBox(self.tab_view)
        self.spin_status_timeout.setRange(1000, 10000)
        self.spin_status_timeout.setSingleStep(500)
        self.spin_status_timeout.setValue(3000)
        self.spin_status_timeout.setSuffix(" ms")
        self.lbl_status_timeout = QLabel(safe_tr("状态栏提示显示时间："), self.tab_view)
        form.addRow(self.lbl_status_timeout, self.spin_status_timeout)

        layout.addLayout(form)

        # Theme Section
        self.grp_theme_view = QGroupBox(safe_tr("外观与主题"), self.tab_view)
        theme_layout = QHBoxLayout(self.grp_theme_view)
        self.lbl_theme_desc = QLabel(
            safe_tr("ATBOffice 包含 4 款经典 Office 2003 质感外观配色。"),
            self.grp_theme_view,
        )
        theme_layout.addWidget(self.lbl_theme_desc)
        theme_layout.addStretch(1)
        self.btn_open_theme_dialog = QPushButton(
            safe_tr("打开主题选择器…"), self.grp_theme_view
        )
        self.btn_open_theme_dialog.clicked.connect(self._on_open_theme_dialog)
        theme_layout.addWidget(self.btn_open_theme_dialog)
        layout.addWidget(self.grp_theme_view)

        layout.addStretch(1)

    def _build_edit_tab(self) -> None:
        layout = QVBoxLayout(self.tab_edit)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)

        # Default Font
        self.combo_font_family = QFontComboBox(self.tab_edit)
        self.lbl_font_family = QLabel(safe_tr("默认字体："), self.tab_edit)
        form.addRow(self.lbl_font_family, self.combo_font_family)

        # Default Font Size
        self.spin_font_size = QSpinBox(self.tab_edit)
        self.spin_font_size.setRange(6, 72)
        self.spin_font_size.setValue(12)
        self.spin_font_size.setSuffix(" pt")
        self.lbl_font_size = QLabel(safe_tr("默认字号："), self.tab_edit)
        form.addRow(self.lbl_font_size, self.spin_font_size)

        layout.addLayout(form)

        # Show Gridlines
        self.chk_show_gridlines = QCheckBox(
            safe_tr("在 Ledger 电子表格中默认显示单元格网格线"), self.tab_edit
        )
        self.chk_show_gridlines.setChecked(True)
        layout.addWidget(self.chk_show_gridlines)

        layout.addStretch(1)

    def _build_save_tab(self) -> None:
        layout = QVBoxLayout(self.tab_save)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)

        # Auto save interval
        self.spin_auto_save = QSpinBox(self.tab_save)
        self.spin_auto_save.setRange(1, 60)
        self.spin_auto_save.setValue(10)
        self.lbl_auto_save = QLabel(
            safe_tr("自动恢复信息保存时间间隔："), self.tab_save
        )
        form.addRow(self.lbl_auto_save, self.spin_auto_save)

        # Default Save Format
        self.combo_save_format = QComboBox(self.tab_save)
        self.combo_save_format.addItems(["docx", "xlsx", "pptx", "odt", "ods", "odp"])
        self.lbl_save_format = QLabel(safe_tr("默认保存文件格式："), self.tab_save)
        form.addRow(self.lbl_save_format, self.combo_save_format)

        layout.addLayout(form)
        layout.addStretch(1)

    def _build_language_tab(self) -> None:
        layout = QVBoxLayout(self.tab_language)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)

        self.combo_language = QComboBox(self.tab_language)
        for loc in SUPPORTED_LOCALES:
            disp = LOCALE_DISPLAY_NAMES.get(loc, loc)
            self.combo_language.addItem(disp, userData=loc)

        self.lbl_language = QLabel(safe_tr("界面显示语言："), self.tab_language)
        form.addRow(self.lbl_language, self.combo_language)

        layout.addLayout(form)

        self.lbl_lang_hint = QLabel(
            safe_tr("更改语言并点击应用或确定后，所有窗口将立即动态重绘并刷新语言。"),
            self.tab_language,
        )
        self.lbl_lang_hint.setWordWrap(True)
        self.lbl_lang_hint.setStyleSheet("color: #64748B; font-size: 11px;")
        layout.addWidget(self.lbl_lang_hint)

        layout.addStretch(1)

    # -------------------------------------------------------------------------
    # Data Loading and Saving
    # -------------------------------------------------------------------------
    def load_from_settings(self) -> None:
        """Load stored settings values into dialog controls."""
        # General
        def_path = self.settings.get_value("general/default_open_path", str(Path.home()))
        self.txt_default_path.setText(str(def_path))
        self.spin_recent_limit.setValue(
            int(self.settings.get_value("general/recent_files_limit", 20))
        )
        start_beh = str(self.settings.get_value("general/start_behavior", "start_center"))
        if start_beh == "new_doc":
            self.rb_start_new_doc.setChecked(True)
        else:
            self.rb_start_center.setChecked(True)

        # View
        ui_scale = str(self.settings.get_value("view/ui_scale", "100%"))
        scale_idx = self.combo_ui_scale.findText(ui_scale)
        if scale_idx >= 0:
            self.combo_ui_scale.setCurrentIndex(scale_idx)
        self.spin_status_timeout.setValue(
            int(self.settings.get_value("view/status_bar_timeout", 3000))
        )

        # Edit
        font_family = str(self.settings.get_value("edit/default_font_family", "Tahoma"))
        font_idx = self.combo_font_family.findText(font_family)
        if font_idx >= 0:
            self.combo_font_family.setCurrentIndex(font_idx)
        self.spin_font_size.setValue(int(self.settings.get_value("edit/default_font_size", 12)))
        self.chk_show_gridlines.setChecked(
            bool(self.settings.get_value("edit/show_gridlines", True))
        )

        # Save
        self.spin_auto_save.setValue(int(self.settings.get_value("save/auto_save_interval", 10)))
        save_fmt = str(self.settings.get_value("save/default_save_format", "docx"))
        fmt_idx = self.combo_save_format.findText(save_fmt)
        if fmt_idx >= 0:
            self.combo_save_format.setCurrentIndex(fmt_idx)

        # Language
        current_loc = str(self.settings.get_value("locale/language", "zh-CN"))
        for i in range(self.combo_language.count()):
            if self.combo_language.itemData(i) == current_loc:
                self.combo_language.setCurrentIndex(i)
                break

    def save_to_settings(self) -> None:
        """Persist dialog controls to AppSettings and synchronize managers."""
        # General
        self.settings.set_value("general/default_open_path", self.txt_default_path.text())
        recent_limit = self.spin_recent_limit.value()
        self.settings.set_value("general/recent_files_limit", recent_limit)
        WindowManager.get_instance().recent_files.set_max_items(recent_limit)

        start_beh = "new_doc" if self.rb_start_new_doc.isChecked() else "start_center"
        self.settings.set_value("general/start_behavior", start_beh)

        # View
        self.settings.set_value("view/ui_scale", self.combo_ui_scale.currentText())
        self.settings.set_value("view/status_bar_timeout", self.spin_status_timeout.value())

        # Edit
        self.settings.set_value("edit/default_font_family", self.combo_font_family.currentText())
        self.settings.set_value("edit/default_font_size", self.spin_font_size.value())
        self.settings.set_value("edit/show_gridlines", self.chk_show_gridlines.isChecked())

        # Save
        self.settings.set_value("save/auto_save_interval", self.spin_auto_save.value())
        self.settings.set_value("save/default_save_format", self.combo_save_format.currentText())

        # Language
        new_loc = self.combo_language.currentData()
        if new_loc:
            old_loc = self.settings.get_value("locale/language", "zh-CN")
            self.settings.set_value("locale/language", new_loc)
            if new_loc != old_loc:
                load_locale(new_loc)
                self.retranslate_ui()

        self.settings.sync()

    # -------------------------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------------------------
    def _on_browse_path(self) -> None:
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return
        selected = QFileDialog.getExistingDirectory(
            self,
            safe_tr("选择默认打开位置"),
            self.txt_default_path.text() or str(Path.home()),
        )
        if selected:
            self.txt_default_path.setText(selected)

    def _on_open_theme_dialog(self) -> None:
        from atboffice.ui.dialogs.theme_dialog import ThemeDialog

        dlg = ThemeDialog(self)
        dlg.exec()

    def _on_restore_defaults(self) -> None:
        """Restore all controls to default preset settings."""
        self.txt_default_path.setText(str(DEFAULT_SETTINGS["general/default_open_path"]))
        self.spin_recent_limit.setValue(int(DEFAULT_SETTINGS["general/recent_files_limit"]))
        self.rb_start_center.setChecked(True)

        scale_idx = self.combo_ui_scale.findText(str(DEFAULT_SETTINGS["view/ui_scale"]))
        if scale_idx >= 0:
            self.combo_ui_scale.setCurrentIndex(scale_idx)
        self.spin_status_timeout.setValue(int(DEFAULT_SETTINGS["view/status_bar_timeout"]))

        font_idx = self.combo_font_family.findText(
            str(DEFAULT_SETTINGS["edit/default_font_family"])
        )
        if font_idx >= 0:
            self.combo_font_family.setCurrentIndex(font_idx)
        self.spin_font_size.setValue(int(DEFAULT_SETTINGS["edit/default_font_size"]))
        self.chk_show_gridlines.setChecked(bool(DEFAULT_SETTINGS["edit/show_gridlines"]))

        self.spin_auto_save.setValue(int(DEFAULT_SETTINGS["save/auto_save_interval"]))
        fmt_idx = self.combo_save_format.findText(
            str(DEFAULT_SETTINGS["save/default_save_format"])
        )
        if fmt_idx >= 0:
            self.combo_save_format.setCurrentIndex(fmt_idx)

        def_loc = str(DEFAULT_SETTINGS["locale/language"])
        for i in range(self.combo_language.count()):
            if self.combo_language.itemData(i) == def_loc:
                self.combo_language.setCurrentIndex(i)
                break

    def _on_apply(self) -> None:
        self.save_to_settings()

    def _on_ok(self) -> None:
        self.save_to_settings()
        self.accept()

    def retranslate_ui(self) -> None:
        """Update localized UI strings dynamically across all tabs."""
        self.setWindowTitle(safe_tr("Options"))

        # Tabs
        self.tab_widget.setTabText(0, safe_tr("General"))
        self.tab_widget.setTabText(1, safe_tr("View"))
        self.tab_widget.setTabText(2, safe_tr("Edit"))
        self.tab_widget.setTabText(3, safe_tr("Save"))
        self.tab_widget.setTabText(4, safe_tr("Language"))

        # General
        self.lbl_default_path.setText(safe_tr("默认打开位置："))
        self.btn_browse_path.setText(safe_tr("浏览…"))
        self.lbl_recent_limit.setText(safe_tr("最近文件保留上限："))
        self.spin_recent_limit.setSuffix(" " + safe_tr("个文件"))
        self.grp_startup.setTitle(safe_tr("启动行为"))
        self.rb_start_center.setText(safe_tr("显示启动中心（推荐）"))
        self.rb_start_new_doc.setText(safe_tr("直接新建空白文档"))

        # View
        self.lbl_ui_scale.setText(safe_tr("界面缩放比率："))
        self.lbl_status_timeout.setText(safe_tr("状态栏提示显示时间："))
        self.grp_theme_view.setTitle(safe_tr("外观与主题"))
        self.lbl_theme_desc.setText(
            safe_tr("ATBOffice 包含 4 款经典 Office 2003 质感外观配色。")
        )
        self.btn_open_theme_dialog.setText(safe_tr("打开主题选择器…"))

        # Edit
        self.lbl_font_family.setText(safe_tr("默认字体："))
        self.lbl_font_size.setText(safe_tr("默认字号："))
        self.chk_show_gridlines.setText(
            safe_tr("在 Ledger 电子表格中默认显示单元格网格线")
        )

        # Save
        self.lbl_auto_save.setText(safe_tr("自动恢复信息保存时间间隔："))
        self.spin_auto_save.setSuffix(" " + safe_tr("分钟"))
        self.lbl_save_format.setText(safe_tr("默认保存文件格式："))

        # Language
        self.lbl_language.setText(safe_tr("界面显示语言："))
        self.lbl_lang_hint.setText(
            safe_tr("更改语言并点击应用或确定后，所有窗口将立即动态重绘并刷新语言。")
        )

        # Buttons
        self.btn_restore_defaults.setText(safe_tr("恢复默认设置"))

"""Classic Office 2003 styled modeless Find and Replace dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from atboffice.core.search import SearchController, SearchOptions

if TYPE_CHECKING:
    from atboffice.core.search import SearchMatch


def safe_tr(text: str) -> str:
    """Translate UI text safely for Find & Replace dialog."""
    return QCoreApplication.translate("FindReplaceDialog", text)


class FindReplaceDialog(QDialog):
    """Office 2003 Luna styled tabbed Find and Replace modeless dialog."""

    def __init__(
        self,
        controller: SearchController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller or SearchController(self)
        self.setModal(False)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowTitleHint
        )
        self.resize(480, 260)

        # Connect controller signals
        self.controller.no_match_found.connect(self._on_no_match_found)
        self.controller.replace_completed.connect(self._on_replace_completed)
        self.controller.status_message.connect(self._on_status_message)

        self._build_ui()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Left: Tab widget for Find and Replace
        self.tab_widget = QTabWidget(self)
        main_layout.addWidget(self.tab_widget, 1)

        # Tab 1: Find Tab
        self.find_tab = QWidget()
        self._build_find_tab()
        self.tab_widget.addTab(self.find_tab, "")

        # Tab 2: Replace Tab
        self.replace_tab = QWidget()
        self._build_replace_tab()
        self.tab_widget.addTab(self.replace_tab, "")

        # Right: Action Buttons column
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(6)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.btn_find_next = QPushButton(self)
        self.btn_find_next.setDefault(True)
        self.btn_find_next.clicked.connect(self._do_find_next)
        btn_layout.addWidget(self.btn_find_next)

        self.btn_replace = QPushButton(self)
        self.btn_replace.clicked.connect(self._do_replace)
        btn_layout.addWidget(self.btn_replace)

        self.btn_replace_all = QPushButton(self)
        self.btn_replace_all.clicked.connect(self._do_replace_all)
        btn_layout.addWidget(self.btn_replace_all)

        self.btn_close = QPushButton(self)
        self.btn_close.clicked.connect(self.close)
        btn_layout.addWidget(self.btn_close)

        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        # Tab switch listener to enable/disable replace buttons
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

    def _build_find_tab(self) -> None:
        layout = QVBoxLayout(self.find_tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Row 1: Find What
        row_find = QHBoxLayout()
        self.lbl_find_what = QLabel(self.find_tab)
        self.find_edit = QLineEdit(self.find_tab)
        self.lbl_find_what.setBuddy(self.find_edit)
        self.find_edit.returnPressed.connect(self._do_find_next)
        row_find.addWidget(self.lbl_find_what)
        row_find.addWidget(self.find_edit, 1)
        layout.addLayout(row_find)

        # Row 2: Options & Direction
        opts_layout = QHBoxLayout()

        # Options group
        self.group_options = QGroupBox(self.find_tab)
        vbox_opts = QVBoxLayout(self.group_options)
        self.case_checkbox = QCheckBox(self.group_options)
        self.whole_word_checkbox = QCheckBox(self.group_options)
        self.regex_checkbox = QCheckBox(self.group_options)
        vbox_opts.addWidget(self.case_checkbox)
        vbox_opts.addWidget(self.whole_word_checkbox)
        vbox_opts.addWidget(self.regex_checkbox)
        opts_layout.addWidget(self.group_options)

        # Direction group
        self.group_direction = QGroupBox(self.find_tab)
        vbox_dir = QVBoxLayout(self.group_direction)
        self.dir_button_group = QButtonGroup(self.group_direction)
        self.radio_down = QRadioButton(self.group_direction)
        self.radio_up = QRadioButton(self.group_direction)
        self.radio_down.setChecked(True)
        self.dir_button_group.addButton(self.radio_down)
        self.dir_button_group.addButton(self.radio_up)
        vbox_dir.addWidget(self.radio_down)
        vbox_dir.addWidget(self.radio_up)
        vbox_dir.addStretch()
        opts_layout.addWidget(self.group_direction)

        layout.addLayout(opts_layout)
        layout.addStretch()

    def _build_replace_tab(self) -> None:
        layout = QVBoxLayout(self.replace_tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Form layout for Find What & Replace With
        grid = QGridLayout()
        grid.setSpacing(6)

        self.lbl_repl_find_what = QLabel(self.replace_tab)
        self.replace_find_edit = QLineEdit(self.replace_tab)
        self.lbl_repl_find_what.setBuddy(self.replace_find_edit)
        self.replace_find_edit.returnPressed.connect(self._do_find_next)
        grid.addWidget(self.lbl_repl_find_what, 0, 0)
        grid.addWidget(self.replace_find_edit, 0, 1)

        self.lbl_replace_with = QLabel(self.replace_tab)
        self.replace_edit = QLineEdit(self.replace_tab)
        self.lbl_replace_with.setBuddy(self.replace_edit)
        self.replace_edit.returnPressed.connect(self._do_replace)
        grid.addWidget(self.lbl_replace_with, 1, 0)
        grid.addWidget(self.replace_edit, 1, 1)

        layout.addLayout(grid)

        # Synchronize text between find_edit and replace_find_edit
        self.find_edit.textChanged.connect(self.replace_find_edit.setText)
        self.replace_find_edit.textChanged.connect(self.find_edit.setText)

        # Options mirror on replace tab
        self.group_repl_options = QGroupBox(self.replace_tab)
        vbox_repl_opts = QVBoxLayout(self.group_repl_options)
        self.repl_case_checkbox = QCheckBox(self.group_repl_options)
        self.repl_whole_word_checkbox = QCheckBox(self.group_repl_options)
        self.repl_regex_checkbox = QCheckBox(self.group_repl_options)
        vbox_repl_opts.addWidget(self.repl_case_checkbox)
        vbox_repl_opts.addWidget(self.repl_whole_word_checkbox)
        vbox_repl_opts.addWidget(self.repl_regex_checkbox)

        # Synchronize checkbox states between tabs
        self.case_checkbox.toggled.connect(self.repl_case_checkbox.setChecked)
        self.repl_case_checkbox.toggled.connect(self.case_checkbox.setChecked)
        self.whole_word_checkbox.toggled.connect(
            self.repl_whole_word_checkbox.setChecked
        )
        self.repl_whole_word_checkbox.toggled.connect(
            self.whole_word_checkbox.setChecked
        )
        self.regex_checkbox.toggled.connect(self.repl_regex_checkbox.setChecked)
        self.repl_regex_checkbox.toggled.connect(self.regex_checkbox.setChecked)

        layout.addWidget(self.group_repl_options)
        layout.addStretch()

    def _on_tab_changed(self, index: int) -> None:
        """Update button enabled states when switching tabs."""
        is_replace = index == 1
        self.btn_replace.setVisible(is_replace)
        self.btn_replace_all.setVisible(is_replace)
        if is_replace:
            self.replace_find_edit.setFocus()
        else:
            self.find_edit.setFocus()

    def get_search_options(self) -> SearchOptions:
        """Construct SearchOptions from current UI field values."""
        text = self.find_edit.text()
        replace_text = self.replace_edit.text()
        match_case = self.case_checkbox.isChecked()
        whole_word = self.whole_word_checkbox.isChecked()
        use_regex = self.regex_checkbox.isChecked()
        direction = "up" if self.radio_up.isChecked() else "down"

        return SearchOptions(
            text=text,
            replace_text=replace_text,
            match_case=match_case,
            whole_word=whole_word,
            use_regex=use_regex,
            direction=direction,
        )

    def _do_find_next(self) -> None:
        opts = self.get_search_options()
        if not opts.text:
            return
        self.controller.find_next(opts)

    def _do_replace(self) -> None:
        opts = self.get_search_options()
        if not opts.text:
            return
        self.controller.replace_one(opts)

    def _do_replace_all(self) -> None:
        opts = self.get_search_options()
        if not opts.text:
            return
        self.controller.replace_all(opts)

    def _on_no_match_found(self) -> None:
        QMessageBox.information(
            self,
            safe_tr("查找完成"),
            safe_tr("ATBOffice 已完成对文档的搜索，未找到匹配项。"),
        )

    def _on_replace_completed(self, count: int) -> None:
        msg = safe_tr("ATBOffice 已完成搜索，共进行了 {0} 处替换。").format(count)
        QMessageBox.information(self, safe_tr("替换完成"), msg)

    def _on_status_message(self, message: str) -> None:
        QMessageBox.warning(self, safe_tr("提示"), message)

    def show_find(self) -> None:
        """Display the dialog with Find tab selected and focused."""
        self.tab_widget.setCurrentIndex(0)
        self.find_edit.setFocus()
        self.find_edit.selectAll()
        self.show()
        self.raise_()
        self.activateWindow()

    def show_replace(self) -> None:
        """Display the dialog with Replace tab selected and focused."""
        self.tab_widget.setCurrentIndex(1)
        self.replace_find_edit.setFocus()
        self.replace_find_edit.selectAll()
        self.show()
        self.raise_()
        self.activateWindow()

    def retranslate_ui(self) -> None:
        """Retranslate all UI labels, tabs, and buttons."""
        self.setWindowTitle(safe_tr("查找和替换"))
        self.tab_widget.setTabText(0, safe_tr("查找(&F)"))
        self.tab_widget.setTabText(1, safe_tr("替换(&R)"))

        # Find tab labels
        self.lbl_find_what.setText(safe_tr("查找内容(&N):"))
        self.group_options.setTitle(safe_tr("查找选项"))
        self.case_checkbox.setText(safe_tr("区分大小写(&C)"))
        self.whole_word_checkbox.setText(safe_tr("全字匹配(&W)"))
        self.regex_checkbox.setText(safe_tr("正则表达式(&X)"))

        self.group_direction.setTitle(safe_tr("搜索方向"))
        self.radio_down.setText(safe_tr("向下(&D)"))
        self.radio_up.setText(safe_tr("向上(&U)"))

        # Replace tab labels
        self.lbl_repl_find_what.setText(safe_tr("查找内容(&N):"))
        self.lbl_replace_with.setText(safe_tr("替换为(&P):"))
        self.group_repl_options.setTitle(safe_tr("替换选项"))
        self.repl_case_checkbox.setText(safe_tr("区分大小写(&C)"))
        self.repl_whole_word_checkbox.setText(safe_tr("全字匹配(&W)"))
        self.repl_regex_checkbox.setText(safe_tr("正则表达式(&X)"))

        # Buttons
        self.btn_find_next.setText(safe_tr("查找下一个(&F)"))
        self.btn_replace.setText(safe_tr("替换(&R)"))
        self.btn_replace_all.setText(safe_tr("全部替换(&A)"))
        self.btn_close.setText(safe_tr("关闭(&C)"))

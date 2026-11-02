"""Reference & Annotation Dialogs for Quire Writer.

Includes:
- FootnoteDialog: Footnote and Endnote settings (脚注和尾注)
- CaptionDialog: Insert Caption (题注设置)
- CrossRefDialog: Cross-reference Linking (交叉引用)
- IndexTablesDialog: Index and Table of Contents (索引和目录，4标签)
- BookmarkDialog: Add/Delete/Go To Bookmark (书签管理)
- HyperlinkDialog: Insert Hyperlink (插入超链接，3标签)
- DateTimeDialog: Insert Date and Time (日期与时间)
- FieldDialog: Insert Field Options (插入域)
- SymbolDialog: Insert Special Characters & Symbols (特殊字符与符号，2标签)
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication, QDate, QDateTime, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("ReferenceDialogs", text)


class FootnoteDialog(QDialog):
    """Footnote and Endnote Settings dialog (脚注和尾注)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("脚注和尾注"))
        self.resize(340, 320)

        layout = QVBoxLayout(self)

        # Location group
        self.grp_loc = QGroupBox(safe_tr("位置"), self)
        l_loc = QFormLayout(self.grp_loc)

        self.radio_fn = QRadioButton(safe_tr("脚注(&F):"), self.grp_loc)
        self.combo_fn_loc = QComboBox(self.grp_loc)
        self.combo_fn_loc.addItems([safe_tr("页面底端"), safe_tr("文字下方")])

        self.radio_en = QRadioButton(safe_tr("尾注(&E):"), self.grp_loc)
        self.combo_en_loc = QComboBox(self.grp_loc)
        self.combo_en_loc.addItems([safe_tr("文档结尾"), safe_tr("节的结尾")])

        self.radio_fn.setChecked(True)
        self.loc_btn_group = QButtonGroup(self)
        self.loc_btn_group.addButton(self.radio_fn, 0)
        self.loc_btn_group.addButton(self.radio_en, 1)

        l_loc.addRow(self.radio_fn, self.combo_fn_loc)
        l_loc.addRow(self.radio_en, self.combo_en_loc)
        layout.addWidget(self.grp_loc)

        # Format group
        self.grp_fmt = QGroupBox(safe_tr("格式"), self)
        l_fmt = QFormLayout(self.grp_fmt)

        self.combo_num_fmt = QComboBox(self.grp_fmt)
        self.combo_num_fmt.addItems([
            "1, 2, 3, ...",
            "a, b, c, ...",
            "A, B, C, ...",
            "i, ii, iii, ...",
            "I, II, III, ...",
            "*, †, ‡, §, ...",
        ])

        h_custom = QHBoxLayout()
        self.edit_custom_mark = QLineEdit(self.grp_fmt)
        self.btn_symbol = QPushButton(safe_tr("符号(&S)..."), self.grp_fmt)
        self.btn_symbol.clicked.connect(self._open_symbol_picker)
        h_custom.addWidget(self.edit_custom_mark)
        h_custom.addWidget(self.btn_symbol)

        self.spin_start = QSpinBox(self.grp_fmt)
        self.spin_start.setRange(1, 9999)
        self.spin_start.setValue(1)

        self.combo_numbering = QComboBox(self.grp_fmt)
        self.combo_numbering.addItems([
            safe_tr("连续编号"),
            safe_tr("每节重新编号"),
            safe_tr("每页重新编号"),
        ])

        self.lbl_num_fmt = QLabel(safe_tr("编号格式(&N):"), self.grp_fmt)
        self.lbl_custom = QLabel(safe_tr("自定义标记(&M):"), self.grp_fmt)
        self.lbl_start = QLabel(safe_tr("起始编号(&S):"), self.grp_fmt)
        self.lbl_numbering = QLabel(safe_tr("编号方式(&U):"), self.grp_fmt)

        l_fmt.addRow(self.lbl_num_fmt, self.combo_num_fmt)
        l_fmt.addRow(self.lbl_custom, h_custom)
        l_fmt.addRow(self.lbl_start, self.spin_start)
        l_fmt.addRow(self.lbl_numbering, self.combo_numbering)
        layout.addWidget(self.grp_fmt)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _open_symbol_picker(self) -> None:
        dlg = SymbolDialog(self)
        if dlg.exec():
            self.edit_custom_mark.setText(dlg.get_selected_character())

    def get_footnote_settings(self) -> dict[str, Any]:
        return {
            "type": "footnote" if self.radio_fn.isChecked() else "endnote",
            "location": (
                self.combo_fn_loc.currentText()
                if self.radio_fn.isChecked()
                else self.combo_en_loc.currentText()
            ),
            "number_format": self.combo_num_fmt.currentText(),
            "custom_mark": self.edit_custom_mark.text(),
            "start_at": self.spin_start.value(),
            "numbering": self.combo_numbering.currentText(),
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("脚注和尾注"))
        self.grp_loc.setTitle(safe_tr("位置"))
        self.radio_fn.setText(safe_tr("脚注(&F):"))
        self.radio_en.setText(safe_tr("尾注(&E):"))
        self.grp_fmt.setTitle(safe_tr("格式"))
        self.lbl_num_fmt.setText(safe_tr("编号格式(&N):"))
        self.lbl_custom.setText(safe_tr("自定义标记(&M):"))
        self.btn_symbol.setText(safe_tr("符号(&S)..."))
        self.lbl_start.setText(safe_tr("起始编号(&S):"))
        self.lbl_numbering.setText(safe_tr("编号方式(&U):"))


class CaptionDialog(QDialog):
    """Insert Caption dialog (题注设置)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("题注"))
        self.resize(320, 240)

        layout = QVBoxLayout(self)
        f_layout = QFormLayout()

        self.edit_caption = QLineEdit(self)
        self.edit_caption.setPlaceholderText(safe_tr("在此键入题注内容"))

        h_label = QHBoxLayout()
        self.combo_label = QComboBox(self)
        self.combo_label.addItems([safe_tr("图表"), safe_tr("表格"), safe_tr("公式")])
        self.btn_new_label = QPushButton(safe_tr("新建标签(&N)..."), self)
        self.btn_new_label.clicked.connect(self._add_new_label)
        h_label.addWidget(self.combo_label)
        h_label.addWidget(self.btn_new_label)

        self.combo_position = QComboBox(self)
        self.combo_position.addItems([safe_tr("所选项目下方"), safe_tr("所选项目上方")])

        self.check_exclude_label = QCheckBox(safe_tr("从题注中排除标签(&E)"), self)

        self.lbl_caption = QLabel(safe_tr("题注(&C):"), self)
        self.lbl_label = QLabel(safe_tr("标签(&L):"), self)
        self.lbl_pos = QLabel(safe_tr("位置(&P):"), self)

        f_layout.addRow(self.lbl_caption, self.edit_caption)
        f_layout.addRow(self.lbl_label, h_label)
        f_layout.addRow(self.lbl_pos, self.combo_position)
        f_layout.addRow("", self.check_exclude_label)
        layout.addLayout(f_layout)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _add_new_label(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle(safe_tr("新建标签"))
        d_layout = QVBoxLayout(dlg)
        inp = QLineEdit(dlg)
        d_layout.addWidget(QLabel(safe_tr("标签:"), dlg))
        d_layout.addWidget(inp)
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dlg)
        bbox.accepted.connect(dlg.accept)
        bbox.rejected.connect(dlg.reject)
        d_layout.addWidget(bbox)
        if dlg.exec() and inp.text().strip():
            new_text = inp.text().strip()
            self.combo_label.addItem(new_text)
            self.combo_label.setCurrentText(new_text)

    def get_caption_data(self) -> dict[str, Any]:
        return {
            "caption": self.edit_caption.text(),
            "label": self.combo_label.currentText(),
            "position": "below" if self.combo_position.currentIndex() == 0 else "above",
            "exclude_label": self.check_exclude_label.isChecked(),
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("题注"))
        self.lbl_caption.setText(safe_tr("题注(&C):"))
        self.lbl_label.setText(safe_tr("标签(&L):"))
        self.btn_new_label.setText(safe_tr("新建标签(&N)..."))
        self.lbl_pos.setText(safe_tr("位置(&P):"))
        self.check_exclude_label.setText(safe_tr("从题注中排除标签(&E)"))


class CrossRefDialog(QDialog):
    """Cross-reference Linking dialog (交叉引用)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("交叉引用"))
        self.resize(360, 360)

        layout = QVBoxLayout(self)
        f_layout = QFormLayout()

        self.combo_ref_type = QComboBox(self)
        self.combo_ref_type.addItems([
            safe_tr("编号项"),
            safe_tr("标题"),
            safe_tr("书签"),
            safe_tr("脚注"),
            safe_tr("尾注"),
            safe_tr("公式"),
            safe_tr("图表"),
            safe_tr("表格"),
        ])
        self.combo_ref_type.currentIndexChanged.connect(self._sync_items)

        self.combo_insert_as = QComboBox(self)
        self.combo_insert_as.addItems([
            safe_tr("页码"),
            safe_tr("段落文字"),
            safe_tr("段落编号"),
            safe_tr("见上方/见下方"),
        ])

        self.check_as_hyperlink = QCheckBox(safe_tr("插入为超链接(&H)"), self)
        self.check_as_hyperlink.setChecked(True)

        self.lbl_type = QLabel(safe_tr("引用类型(&T):"), self)
        self.lbl_as = QLabel(safe_tr("引用内容(&R):"), self)

        f_layout.addRow(self.lbl_type, self.combo_ref_type)
        f_layout.addRow(self.lbl_as, self.combo_insert_as)
        f_layout.addRow("", self.check_as_hyperlink)
        layout.addLayout(f_layout)

        self.lbl_for_which = QLabel(safe_tr("引用哪一个(&W):"), self)
        layout.addWidget(self.lbl_for_which)

        self.list_items = QListWidget(self)
        layout.addWidget(self.list_items)
        self._sync_items()

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _sync_items(self) -> None:
        self.list_items.clear()
        ref_t = self.combo_ref_type.currentText()
        for i in range(1, 6):
            self.list_items.addItem(f"{ref_t} {i}")
        if self.list_items.count() > 0:
            self.list_items.setCurrentRow(0)

    def get_cross_ref_data(self) -> dict[str, Any]:
        item = self.list_items.currentItem()
        return {
            "ref_type": self.combo_ref_type.currentText(),
            "insert_as": self.combo_insert_as.currentText(),
            "as_hyperlink": self.check_as_hyperlink.isChecked(),
            "target": item.text() if item else "",
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("交叉引用"))
        self.lbl_type.setText(safe_tr("引用类型(&T):"))
        self.lbl_as.setText(safe_tr("引用内容(&R):"))
        self.check_as_hyperlink.setText(safe_tr("插入为超链接(&H)"))
        self.lbl_for_which.setText(safe_tr("引用哪一个(&W):"))


class IndexTablesDialog(QDialog):
    """Index and Table of Contents dialog with 4 tabs (索引和目录)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("索引和目录"))
        self.resize(440, 380)

        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget(self)

        # Tab 1: Index
        self.tab_index = QWidget(self.tab_widget)
        l_idx = QVBoxLayout(self.tab_index)
        f_idx = QFormLayout()
        self.combo_idx_type = QComboBox(self.tab_index)
        self.combo_idx_type.addItems([safe_tr("缩进式"), safe_tr("连续式")])
        self.spin_idx_cols = QSpinBox(self.tab_index)
        self.spin_idx_cols.setRange(1, 4)
        self.spin_idx_cols.setValue(2)
        self.check_idx_right = QCheckBox(safe_tr("页码右对齐(&R)"), self.tab_index)
        self.check_idx_right.setChecked(True)
        self.combo_idx_leader = QComboBox(self.tab_index)
        self.combo_idx_leader.addItems([".......", "-------", "_______", safe_tr("(无)")])
        f_idx.addRow(safe_tr("类型:"), self.combo_idx_type)
        f_idx.addRow(safe_tr("栏数:"), self.spin_idx_cols)
        f_idx.addRow("", self.check_idx_right)
        f_idx.addRow(safe_tr("制表符前导符:"), self.combo_idx_leader)
        l_idx.addLayout(f_idx)
        self.tab_widget.addTab(self.tab_index, safe_tr("索引"))

        # Tab 2: Table of Contents (TOC)
        self.tab_toc = QWidget(self.tab_widget)
        l_toc = QVBoxLayout(self.tab_toc)
        f_toc = QFormLayout()
        self.check_toc_show_pages = QCheckBox(safe_tr("显示页码(&S)"), self.tab_toc)
        self.check_toc_show_pages.setChecked(True)
        self.check_toc_right = QCheckBox(safe_tr("页码右对齐(&R)"), self.tab_toc)
        self.check_toc_right.setChecked(True)
        self.combo_toc_leader = QComboBox(self.tab_toc)
        self.combo_toc_leader.addItems([".......", "-------", "_______", safe_tr("(无)")])
        self.combo_toc_formats = QComboBox(self.tab_toc)
        self.combo_toc_formats.addItems([
            safe_tr("来自模板"),
            safe_tr("古典"),
            safe_tr("优雅"),
            safe_tr("现代"),
            safe_tr("正式"),
            safe_tr("简单"),
        ])
        self.spin_toc_levels = QSpinBox(self.tab_toc)
        self.spin_toc_levels.setRange(1, 9)
        self.spin_toc_levels.setValue(3)
        self.check_toc_hyperlinks = QCheckBox(safe_tr("使用超链接而不使用页码（Web 视图）"), self.tab_toc)
        self.check_toc_hyperlinks.setChecked(True)
        f_toc.addRow("", self.check_toc_show_pages)
        f_toc.addRow("", self.check_toc_right)
        f_toc.addRow(safe_tr("制表符前导符(&L):"), self.combo_toc_leader)
        f_toc.addRow(safe_tr("格式(&F):"), self.combo_toc_formats)
        f_toc.addRow(safe_tr("显示级别(&O):"), self.spin_toc_levels)
        f_toc.addRow("", self.check_toc_hyperlinks)
        l_toc.addLayout(f_toc)
        self.tab_widget.addTab(self.tab_toc, safe_tr("目录"))

        # Tab 3: Table of Figures
        self.tab_tof = QWidget(self.tab_widget)
        l_tof = QVBoxLayout(self.tab_tof)
        f_tof = QFormLayout()
        self.combo_tof_caption = QComboBox(self.tab_tof)
        self.combo_tof_caption.addItems([safe_tr("图表"), safe_tr("表格"), safe_tr("公式")])
        self.check_tof_include = QCheckBox(safe_tr("包含标签和编号(&I)"), self.tab_tof)
        self.check_tof_include.setChecked(True)
        f_tof.addRow(safe_tr("题注标签(&C):"), self.combo_tof_caption)
        f_tof.addRow("", self.check_tof_include)
        l_tof.addLayout(f_tof)
        self.tab_widget.addTab(self.tab_tof, safe_tr("图表目录"))

        # Tab 4: Table of Authorities
        self.tab_toa = QWidget(self.tab_widget)
        l_toa = QVBoxLayout(self.tab_toa)
        f_toa = QFormLayout()
        self.combo_toa_cat = QComboBox(self.tab_toa)
        self.combo_toa_cat.addItems([
            safe_tr("全部"),
            safe_tr("判例"),
            safe_tr("法令"),
            safe_tr("规定"),
            safe_tr("其他权威著作"),
        ])
        f_toa.addRow(safe_tr("类别(&C):"), self.combo_toa_cat)
        l_toa.addLayout(f_toa)
        self.tab_widget.addTab(self.tab_toa, safe_tr("引文目录"))

        main_layout.addWidget(self.tab_widget)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def get_index_tables_data(self) -> dict[str, Any]:
        return {
            "active_tab": self.tab_widget.currentIndex(),
            "toc_show_pages": self.check_toc_show_pages.isChecked(),
            "toc_right_align": self.check_toc_right.isChecked(),
            "toc_leader": self.combo_toc_leader.currentText(),
            "toc_format": self.combo_toc_formats.currentText(),
            "toc_levels": self.spin_toc_levels.value(),
            "tof_caption": self.combo_tof_caption.currentText(),
            "toa_category": self.combo_toa_cat.currentText(),
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("索引和目录"))
        self.tab_widget.setTabText(0, safe_tr("索引"))
        self.tab_widget.setTabText(1, safe_tr("目录"))
        self.tab_widget.setTabText(2, safe_tr("图表目录"))
        self.tab_widget.setTabText(3, safe_tr("引文目录"))


class BookmarkDialog(QDialog):
    """Bookmark management dialog (书签)."""

    def __init__(self, initial_bookmarks: list[str] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("书签"))
        self.resize(320, 300)

        layout = QVBoxLayout(self)

        self.lbl_name = QLabel(safe_tr("书签名称(&B):"), self)
        layout.addWidget(self.lbl_name)

        self.edit_name = QLineEdit(self)
        layout.addWidget(self.edit_name)

        h_content = QHBoxLayout()
        self.list_bookmarks = QListWidget(self)
        if initial_bookmarks:
            self.list_bookmarks.addItems(initial_bookmarks)
        h_content.addWidget(self.list_bookmarks)

        # Right buttons: Add, Delete, Go To
        v_btns = QVBoxLayout()
        self.btn_add = QPushButton(safe_tr("添加(&A)"), self)
        self.btn_delete = QPushButton(safe_tr("删除(&D)"), self)
        self.btn_goto = QPushButton(safe_tr("定位(&G)"), self)

        self.btn_add.clicked.connect(self._add_bookmark)
        self.btn_delete.clicked.connect(self._delete_bookmark)
        self.btn_goto.clicked.connect(self.accept)

        v_btns.addWidget(self.btn_add)
        v_btns.addWidget(self.btn_delete)
        v_btns.addWidget(self.btn_goto)
        v_btns.addStretch()
        h_content.addLayout(v_btns)
        layout.addLayout(h_content)

        # Sort radios & Hidden check
        self.grp_sort = QGroupBox(safe_tr("排序方式"), self)
        h_sort = QHBoxLayout(self.grp_sort)
        self.radio_name = QRadioButton(safe_tr("名称(&N)"), self.grp_sort)
        self.radio_loc = QRadioButton(safe_tr("位置(&L)"), self.grp_sort)
        self.radio_name.setChecked(True)
        h_sort.addWidget(self.radio_name)
        h_sort.addWidget(self.radio_loc)
        layout.addWidget(self.grp_sort)

        self.check_hidden = QCheckBox(safe_tr("隐藏书签(&H)"), self)
        layout.addWidget(self.check_hidden)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _add_bookmark(self) -> None:
        txt = self.edit_name.text().strip()
        if txt and not self.list_bookmarks.findItems(txt, Qt.MatchFlag.MatchExactly):
            self.list_bookmarks.addItem(txt)
            self.edit_name.clear()

    def _delete_bookmark(self) -> None:
        row = self.list_bookmarks.currentRow()
        if row >= 0:
            self.list_bookmarks.takeItem(row)

    def get_bookmarks(self) -> list[str]:
        return [self.list_bookmarks.item(i).text() for i in range(self.list_bookmarks.count())]

    def get_selected_bookmark(self) -> str:
        item = self.list_bookmarks.currentItem()
        return item.text() if item else ""

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("书签"))
        self.lbl_name.setText(safe_tr("书签名称(&B):"))
        self.btn_add.setText(safe_tr("添加(&A)"))
        self.btn_delete.setText(safe_tr("删除(&D)"))
        self.btn_goto.setText(safe_tr("定位(&G)"))
        self.grp_sort.setTitle(safe_tr("排序方式"))
        self.radio_name.setText(safe_tr("名称(&N)"))
        self.radio_loc.setText(safe_tr("位置(&L)"))
        self.check_hidden.setText(safe_tr("隐藏书签(&H)"))


class HyperlinkDialog(QDialog):
    """Insert Hyperlink dialog with 3 tabs (插入超链接)."""

    def __init__(self, initial_text: str = "", initial_address: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("插入超链接"))
        self.resize(480, 360)

        main_layout = QVBoxLayout(self)

        # Header fields: Text to display & ScreenTip
        h_top = QHBoxLayout()
        self.lbl_text = QLabel(safe_tr("要显示的文字(&T):"), self)
        self.edit_text = QLineEdit(initial_text, self)
        self.btn_tip = QPushButton(safe_tr("屏幕提示(&P)..."), self)
        h_top.addWidget(self.lbl_text)
        h_top.addWidget(self.edit_text)
        h_top.addWidget(self.btn_tip)
        main_layout.addLayout(h_top)

        self.tab_widget = QTabWidget(self)

        # Tab 1: Existing File or Web Page
        self.tab_file = QWidget(self.tab_widget)
        l_file = QVBoxLayout(self.tab_file)
        f_file = QFormLayout()
        self.edit_address = QLineEdit(initial_address, self.tab_file)
        self.btn_browse_file = QPushButton(safe_tr("浏览文件(&F)..."), self.tab_file)
        self.btn_browse_file.clicked.connect(self._browse_file)
        h_addr = QHBoxLayout()
        h_addr.addWidget(self.edit_address)
        h_addr.addWidget(self.btn_browse_file)
        f_file.addRow(safe_tr("地址(&E):"), h_addr)
        l_file.addLayout(f_file)
        self.tab_widget.addTab(self.tab_file, safe_tr("原有文件或网页"))

        # Tab 2: Place in This Document
        self.tab_doc = QWidget(self.tab_widget)
        l_doc = QVBoxLayout(self.tab_doc)
        self.tree_places = QTreeWidget(self.tab_doc)
        self.tree_places.setHeaderHidden(True)
        top_item = QTreeWidgetItem(self.tree_places, [safe_tr("文档顶端")])
        headings_item = QTreeWidgetItem(self.tree_places, [safe_tr("标题")])
        for h in ["Heading 1", "Heading 2", "Heading 3"]:
            QTreeWidgetItem(headings_item, [h])
        bookmarks_item = QTreeWidgetItem(self.tree_places, [safe_tr("书签")])
        for b in ["Bookmark1", "Bookmark2"]:
            QTreeWidgetItem(bookmarks_item, [b])
        self.tree_places.expandAll()
        l_doc.addWidget(self.tree_places)
        self.tab_widget.addTab(self.tab_doc, safe_tr("本文档中的位置"))

        # Tab 3: E-mail Address
        self.tab_mail = QWidget(self.tab_widget)
        l_mail = QVBoxLayout(self.tab_mail)
        f_mail = QFormLayout()
        self.edit_email = QLineEdit(self.tab_mail)
        self.edit_subject = QLineEdit(self.tab_mail)
        f_mail.addRow(safe_tr("电子邮件地址(&M):"), self.edit_email)
        f_mail.addRow(safe_tr("主题(&S):"), self.edit_subject)
        l_mail.addLayout(f_mail)
        self.tab_widget.addTab(self.tab_mail, safe_tr("电子邮件地址"))

        main_layout.addWidget(self.tab_widget)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, safe_tr("选择目标文件"))
        if path:
            self.edit_address.setText(path)

    def get_hyperlink_data(self) -> dict[str, Any]:
        cur_tab = self.tab_widget.currentIndex()
        if cur_tab == 0:
            target = self.edit_address.text()
            kind = "external"
        elif cur_tab == 1:
            sel = self.tree_places.currentItem()
            target = sel.text(0) if sel else ""
            kind = "internal"
        else:
            target = f"mailto:{self.edit_email.text()}?subject={self.edit_subject.text()}"
            kind = "email"

        return {
            "text": self.edit_text.text(),
            "target": target,
            "kind": kind,
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("插入超链接"))
        self.lbl_text.setText(safe_tr("要显示的文字(&T):"))
        self.btn_tip.setText(safe_tr("屏幕提示(&P)..."))
        self.tab_widget.setTabText(0, safe_tr("原有文件或网页"))
        self.tab_widget.setTabText(1, safe_tr("本文档中的位置"))
        self.tab_widget.setTabText(2, safe_tr("电子邮件地址"))


class DateTimeDialog(QDialog):
    """Insert Date and Time dialog (日期与时间)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("日期和时间"))
        self.resize(320, 260)

        layout = QVBoxLayout(self)
        self.lbl_avail = QLabel(safe_tr("可用格式(&A):"), self)
        layout.addWidget(self.lbl_avail)

        now = QDateTime.currentDateTime()
        self.formats = [
            now.toString("yyyy/M/d"),
            now.toString("yyyy年M月d日"),
            now.toString("yyyy年M月d日 dddd"),
            now.toString("yyyy-MM-dd"),
            now.toString("yyyy-MM-dd hh:mm"),
            now.toString("yyyy-MM-dd hh:mm:ss"),
            now.toString("hh:mm"),
            now.toString("hh:mm:ss"),
            now.toString("MM/dd/yyyy"),
            now.toString("dddd, MMMM d, yyyy"),
        ]

        self.list_formats = QListWidget(self)
        self.list_formats.addItems(self.formats)
        if self.list_formats.count() > 0:
            self.list_formats.setCurrentRow(0)
        layout.addWidget(self.list_formats)

        self.check_update = QCheckBox(safe_tr("自动更新(&U)"), self)
        layout.addWidget(self.check_update)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_selected_format(self) -> tuple[str, bool]:
        item = self.list_formats.currentItem()
        text = item.text() if item else ""
        return (text, self.check_update.isChecked())

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("日期和时间"))
        self.lbl_avail.setText(safe_tr("可用格式(&A):"))
        self.check_update.setText(safe_tr("自动更新(&U)"))


class FieldDialog(QDialog):
    """Insert Field Options dialog (插入域)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("域"))
        self.resize(440, 360)

        layout = QVBoxLayout(self)

        f_cat = QFormLayout()
        self.combo_categories = QComboBox(self)
        self.combo_categories.addItems([
            safe_tr("(全部)"),
            safe_tr("日期和时间"),
            safe_tr("文档信息"),
            safe_tr("邮件合并"),
            safe_tr("编号"),
            safe_tr("等式和公式"),
        ])
        self.combo_categories.currentIndexChanged.connect(self._sync_fields)
        self.lbl_cat = QLabel(safe_tr("类别(&C):"), self)
        f_cat.addRow(self.lbl_cat, self.combo_categories)
        layout.addLayout(f_cat)

        h_mid = QHBoxLayout()
        v_list = QVBoxLayout()
        self.lbl_field_names = QLabel(safe_tr("域名(&F):"), self)
        self.list_fields = QListWidget(self)
        self.list_fields.currentTextChanged.connect(self._on_field_changed)
        v_list.addWidget(self.lbl_field_names)
        v_list.addWidget(self.list_fields)
        h_mid.addLayout(v_list)

        v_props = QVBoxLayout()
        self.lbl_props = QLabel(safe_tr("域属性:"), self)
        self.edit_format = QLineEdit(self)
        self.edit_format.setPlaceholderText(safe_tr("格式或参数"))
        self.lbl_desc = QLabel(safe_tr("说明文字"), self)
        self.lbl_desc.setWordWrap(True)
        v_props.addWidget(self.lbl_props)
        v_props.addWidget(self.edit_format)
        v_props.addWidget(self.lbl_desc)
        v_props.addStretch()
        h_mid.addLayout(v_props)
        layout.addLayout(h_mid)

        self.edit_codes = QLineEdit(self)
        self.edit_codes.setReadOnly(True)
        layout.addWidget(QLabel(safe_tr("高级域代码:"), self))
        layout.addWidget(self.edit_codes)

        self._sync_fields()

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _sync_fields(self) -> None:
        self.list_fields.clear()
        fields = [
            "Author",
            "CreateDate",
            "Date",
            "DocProperty",
            "FileName",
            "FileSize",
            "MergeField",
            "NumPages",
            "NumWords",
            "Page",
            "Time",
            "Title",
            "TOC",
        ]
        self.list_fields.addItems(fields)
        if self.list_fields.count() > 0:
            self.list_fields.setCurrentRow(0)

    def _on_field_changed(self, field_name: str) -> None:
        self.edit_codes.setText(f"{{{field_name}}}")
        self.lbl_desc.setText(safe_tr(f"插入当前文档的 {field_name} 信息。"))

    def get_field_data(self) -> dict[str, str]:
        item = self.list_fields.currentItem()
        return {
            "name": item.text() if item else "",
            "args": self.edit_format.text(),
            "code": self.edit_codes.text(),
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("域"))
        self.lbl_cat.setText(safe_tr("类别(&C):"))
        self.lbl_field_names.setText(safe_tr("域名(&F):"))
        self.lbl_props.setText(safe_tr("域属性:"))


class SymbolDialog(QDialog):
    """Insert Special Character and Symbol dialog with 2 tabs (符号与特殊字符)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("符号"))
        self.resize(440, 360)

        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget(self)

        # Tab 1: Symbols Grid
        self.tab_symbols = QWidget(self.tab_widget)
        l_sym = QVBoxLayout(self.tab_symbols)

        h_top = QHBoxLayout()
        self.combo_font = QComboBox(self.tab_symbols)
        self.combo_font.addItems(["(普通文本)", "Symbol", "Wingdings", "Arial", "Times New Roman"])
        h_top.addWidget(QLabel(safe_tr("字体(&F):"), self.tab_symbols))
        h_top.addWidget(self.combo_font)
        l_sym.addLayout(h_top)

        self.table_symbols = QTableWidget(6, 12, self.tab_symbols)
        self.table_symbols.horizontalHeader().setVisible(False)
        self.table_symbols.verticalHeader().setVisible(False)
        self.table_symbols.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_symbols.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # Populate a sample of useful Unicode symbols
        chars = [
            "±", "×", "÷", "≠", "≤", "≥", "≈", "∞", "√", "∑", "∏", "∫",
            "α", "β", "γ", "δ", "ε", "θ", "λ", "μ", "π", "σ", "φ", "ω",
            "←", "↑", "→", "↓", "↔", "↕", "⇒", "⇔", "★", "☆", "▲", "▼",
            "♠", "♣", "♥", "♦", "✓", "✗", "℃", "℉", "¥", "$", "€", "£",
            "©", "®", "™", "§", "¶", "•", "‰", "§", "№", "※", "…", "—",
            "【", "】", "《", "》", "“", "”", "‘", "’", "、", "。", "！", "？",
        ]
        k = 0
        for r in range(6):
            for c in range(12):
                ch = chars[k] if k < len(chars) else " "
                it = QTableWidgetItem(ch)
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_symbols.setItem(r, c, it)
                k += 1

        self.table_symbols.setCurrentCell(0, 0)
        l_sym.addWidget(self.table_symbols)
        self.tab_widget.addTab(self.tab_symbols, safe_tr("符号"))

        # Tab 2: Special Characters
        self.tab_spec = QWidget(self.tab_widget)
        l_spec = QVBoxLayout(self.tab_spec)
        self.table_spec = QTableWidget(self.tab_spec)
        self.table_spec.setColumnCount(2)
        self.table_spec.setHorizontalHeaderLabels([safe_tr("字符"), safe_tr("快捷键")])
        self.table_spec.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        spec_chars = [
            ("— 长划线 (Em Dash)", "Alt+Ctrl+Num -"),
            ("– 短划线 (En Dash)", "Ctrl+Num -"),
            ("  不间断空格 (Nonbreaking Space)", "Ctrl+Shift+Space"),
            ("© 版权所有 (Copyright)", "Alt+Ctrl+C"),
            ("® 注册商标 (Registered)", "Alt+Ctrl+R"),
            ("™ 商标 (Trademark)", "Alt+Ctrl+T"),
            ("§ 分节符 (Section)", ""),
            ("¶ 段落符 (Paragraph)", ""),
            ("… 省略号 (Ellipsis)", "Alt+Ctrl+."),
        ]
        self.table_spec.setRowCount(len(spec_chars))
        for r, (ch_name, sc) in enumerate(spec_chars):
            self.table_spec.setItem(r, 0, QTableWidgetItem(ch_name))
            self.table_spec.setItem(r, 1, QTableWidgetItem(sc))
        self.table_spec.setCurrentCell(0, 0)
        l_spec.addWidget(self.table_spec)
        self.tab_widget.addTab(self.tab_spec, safe_tr("特殊字符"))

        main_layout.addWidget(self.tab_widget)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def get_selected_character(self) -> str:
        if self.tab_widget.currentIndex() == 0:
            it = self.table_symbols.currentItem()
            return it.text() if it else "±"
        else:
            r = self.table_spec.currentRow()
            chars = ["—", "–", " ", "©", "®", "™", "§", "¶", "…"]
            return chars[r] if 0 <= r < len(chars) else "—"

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("符号"))
        self.tab_widget.setTabText(0, safe_tr("符号"))
        self.tab_widget.setTabText(1, safe_tr("特殊字符"))

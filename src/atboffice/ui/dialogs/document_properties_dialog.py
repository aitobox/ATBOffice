"""Classic Office 2003 Document Properties dialog with 5 tabs."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from atboffice.ui.icons import get_office_icon


def safe_tr(text: str) -> str:
    """Translate UI text safely for DocumentPropertiesDialog."""
    return QCoreApplication.translate("DocumentPropertiesDialog", text)


@dataclass
class DocumentMetadata:
    """Document metadata model containing standard and custom properties."""

    file_path: Path | None = None
    file_type: str = "Microsoft Office Document"
    title: str = ""
    subject: str = ""
    author: str = ""
    manager: str = ""
    company: str = ""
    category: str = ""
    keywords: str = ""
    comments: str = ""
    hyperlink_base: str = ""
    template: str = "Normal"
    created: datetime.datetime | None = None
    modified: datetime.datetime | None = None
    accessed: datetime.datetime | None = None
    last_saved_by: str = ""
    revision: int = 1
    total_editing_time: int = 0  # in minutes
    pages: int = 1
    paragraphs: int = 0
    lines: int = 0
    words: int = 0
    characters_no_spaces: int = 0
    characters_with_spaces: int = 0
    headings: list[str] = field(default_factory=list)
    custom_properties: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary representation."""
        return {
            "title": self.title,
            "subject": self.subject,
            "author": self.author,
            "manager": self.manager,
            "company": self.company,
            "category": self.category,
            "keywords": self.keywords,
            "comments": self.comments,
            "hyperlink_base": self.hyperlink_base,
            "template": self.template,
            "created": self.created.isoformat() if self.created else None,
            "modified": self.modified.isoformat() if self.modified else None,
            "accessed": self.accessed.isoformat() if self.accessed else None,
            "last_saved_by": self.last_saved_by,
            "revision": self.revision,
            "total_editing_time": self.total_editing_time,
            "custom_properties": dict(self.custom_properties),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], file_path: Path | None = None) -> DocumentMetadata:
        """Create metadata instance from dictionary."""
        def parse_dt(val: Any) -> datetime.datetime | None:
            if isinstance(val, datetime.datetime):
                return val
            if isinstance(val, str) and val.strip():
                try:
                    return datetime.datetime.fromisoformat(val)
                except Exception:
                    return None
            return None

        return cls(
            file_path=file_path,
            title=data.get("title", ""),
            subject=data.get("subject", ""),
            author=data.get("author", data.get("creator", "")),
            manager=data.get("manager", ""),
            company=data.get("company", ""),
            category=data.get("category", ""),
            keywords=data.get("keywords", ""),
            comments=data.get("comments", data.get("description", "")),
            hyperlink_base=data.get("hyperlink_base", data.get("hyperlinkBase", "")),
            template=data.get("template", "Normal"),
            created=parse_dt(data.get("created")),
            modified=parse_dt(data.get("modified")),
            accessed=parse_dt(data.get("accessed")),
            last_saved_by=data.get("last_saved_by", data.get("lastModifiedBy", "")),
            revision=int(data.get("revision", 1)),
            total_editing_time=int(data.get("total_editing_time", data.get("totalTime", 0))),
            pages=int(data.get("pages", 1)),
            paragraphs=int(data.get("paragraphs", 0)),
            lines=int(data.get("lines", 0)),
            words=int(data.get("words", 0)),
            characters_no_spaces=int(data.get("characters_no_spaces", 0)),
            characters_with_spaces=int(data.get("characters_with_spaces", 0)),
            headings=list(data.get("headings", [])),
            custom_properties=dict(data.get("custom_properties", data.get("custom", {}))),
        )


STANDARD_CUSTOM_PROPERTY_NAMES: list[str] = [
    "Checked by", "Client", "Date completed", "Department", "Destination",
    "Disposition", "Division", "Document number", "Editor", "Forward to",
    "Group", "Language", "Mailstop", "Matter", "Office", "Owner", "Project",
    "Publisher", "Purpose", "Received from", "Recorded by", "Recorded date",
    "Reference", "Source", "Status", "Telephone number", "Typist",
]


class DocumentPropertiesDialog(QDialog):
    """Office 2003 classic 5-tab Document Properties Dialog."""

    def __init__(
        self,
        metadata: DocumentMetadata | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.metadata = metadata or DocumentMetadata()
        self.setWindowTitle(safe_tr("文档属性"))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.resize(460, 480)

        self._init_ui()
        self._populate_data()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.tab_widget = QTabWidget(self)

        # 1. General Tab
        self.tab_general = QWidget()
        self._setup_general_tab(self.tab_general)
        self.tab_widget.addTab(self.tab_general, safe_tr("常规(&G)"))

        # 2. Summary Tab
        self.tab_summary = QWidget()
        self._setup_summary_tab(self.tab_summary)
        self.tab_widget.addTab(self.tab_summary, safe_tr("摘要(&S)"))

        # 3. Statistics Tab
        self.tab_statistics = QWidget()
        self._setup_statistics_tab(self.tab_statistics)
        self.tab_widget.addTab(self.tab_statistics, safe_tr("统计(&A)"))

        # 4. Contents Tab
        self.tab_contents = QWidget()
        self._setup_contents_tab(self.tab_contents)
        self.tab_widget.addTab(self.tab_contents, safe_tr("内容(&C)"))

        # 5. Custom Tab
        self.tab_custom = QWidget()
        self._setup_custom_tab(self.tab_custom)
        self.tab_widget.addTab(self.tab_custom, safe_tr("自定义(&U)"))

        layout.addWidget(self.tab_widget)

        # Button box
        self.btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.btn_box.button(QDialogButtonBox.StandardButton.Ok).setText(safe_tr("确定"))
        self.btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText(safe_tr("取消"))
        self.btn_box.accepted.connect(self._on_accept)
        self.btn_box.rejected.connect(self.reject)
        layout.addWidget(self.btn_box)

    def _setup_general_tab(self, parent: QWidget) -> None:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header with document icon and file name
        head_layout = QHBoxLayout()
        self.lbl_icon = QLabel(parent)
        self.lbl_icon.setPixmap(get_office_icon("fileNew").pixmap(32, 32))
        head_layout.addWidget(self.lbl_icon)

        self.lbl_filename = QLabel(safe_tr("未命名文档"), parent)
        self.lbl_filename.setStyleSheet("font-weight: bold; font-size: 13px;")
        head_layout.addWidget(self.lbl_filename, stretch=1)
        layout.addLayout(head_layout)

        sep = QFrame(parent)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setSpacing(8)

        self.val_type = QLabel(safe_tr("ATBOffice 文档"), parent)
        form.addRow(safe_tr("类型:"), self.val_type)

        self.val_location = QLabel(safe_tr("未保存"), parent)
        self.val_location.setWordWrap(True)
        form.addRow(safe_tr("位置:"), self.val_location)

        self.val_size = QLabel(safe_tr("0 字节"), parent)
        form.addRow(safe_tr("大小:"), self.val_size)

        sep2 = QFrame(parent)
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        form.addRow(sep2)

        self.val_created = QLabel(safe_tr("未知"), parent)
        form.addRow(safe_tr("创建时间:"), self.val_created)

        self.val_modified = QLabel(safe_tr("未知"), parent)
        form.addRow(safe_tr("修改时间:"), self.val_modified)

        self.val_accessed = QLabel(safe_tr("未知"), parent)
        form.addRow(safe_tr("访问时间:"), self.val_accessed)

        layout.addLayout(form)
        layout.addStretch(1)

    def _setup_summary_tab(self, parent: QWidget) -> None:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(6)

        self.edit_title = QLineEdit(parent)
        form.addRow(safe_tr("标题(&T):"), self.edit_title)

        self.edit_subject = QLineEdit(parent)
        form.addRow(safe_tr("主题(&S):"), self.edit_subject)

        self.edit_author = QLineEdit(parent)
        form.addRow(safe_tr("作者(&A):"), self.edit_author)

        self.edit_manager = QLineEdit(parent)
        form.addRow(safe_tr("经理(&M):"), self.edit_manager)

        self.edit_company = QLineEdit(parent)
        form.addRow(safe_tr("单位(&O):"), self.edit_company)

        self.edit_category = QLineEdit(parent)
        form.addRow(safe_tr("类别(&C):"), self.edit_category)

        self.edit_keywords = QLineEdit(parent)
        form.addRow(safe_tr("关键字(&K):"), self.edit_keywords)

        self.edit_comments = QTextEdit(parent)
        self.edit_comments.setFixedHeight(60)
        form.addRow(safe_tr("备注(&M):"), self.edit_comments)

        self.edit_hyperlink_base = QLineEdit(parent)
        form.addRow(safe_tr("超链接基址(&H):"), self.edit_hyperlink_base)

        self.val_template = QLabel(safe_tr("Normal"), parent)
        form.addRow(safe_tr("模板:"), self.val_template)

        layout.addLayout(form)

    def _setup_statistics_tab(self, parent: QWidget) -> None:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(4)

        self.stat_created = QLabel(parent)
        form.addRow(safe_tr("创建时间:"), self.stat_created)

        self.stat_modified = QLabel(parent)
        form.addRow(safe_tr("修改时间:"), self.stat_modified)

        self.stat_saved_by = QLabel(parent)
        form.addRow(safe_tr("最后保存者:"), self.stat_saved_by)

        self.stat_revision = QLabel(parent)
        form.addRow(safe_tr("修订号:"), self.stat_revision)

        self.stat_total_time = QLabel(parent)
        form.addRow(safe_tr("编辑总时间:"), self.stat_total_time)

        layout.addLayout(form)

        lbl_stat_title = QLabel(safe_tr("统计信息:"), parent)
        lbl_stat_title.setStyleSheet("font-weight: bold; margin-top: 6px;")
        layout.addWidget(lbl_stat_title)

        self.table_stats = QTableWidget(6, 2, parent)
        self.table_stats.setHorizontalHeaderLabels([safe_tr("项目"), safe_tr("值")])
        self.table_stats.horizontalHeader().setStretchLastSection(True)
        self.table_stats.verticalHeader().setVisible(False)
        self.table_stats.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_stats.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        stat_labels = [
            safe_tr("页数:"),
            safe_tr("段落数:"),
            safe_tr("行数:"),
            safe_tr("字数:"),
            safe_tr("字符数(不计空格):"),
            safe_tr("字符数(计空格):"),
        ]
        for row, text in enumerate(stat_labels):
            item = QTableWidgetItem(text)
            self.table_stats.setItem(row, 0, item)
            self.table_stats.setItem(row, 1, QTableWidgetItem("0"))

        layout.addWidget(self.table_stats)

    def _setup_contents_tab(self, parent: QWidget) -> None:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        lbl = QLabel(safe_tr("文档内容(&C):"), parent)
        layout.addWidget(lbl)

        self.list_contents = QListWidget(parent)
        layout.addWidget(self.list_contents)

    def _setup_custom_tab(self, parent: QWidget) -> None:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(6)

        # Name ComboBox (editable)
        self.combo_prop_name = QComboBox(parent)
        self.combo_prop_name.setEditable(True)
        self.combo_prop_name.addItems(STANDARD_CUSTOM_PROPERTY_NAMES)
        form.addRow(safe_tr("名称(&N):"), self.combo_prop_name)

        # Type ComboBox
        self.combo_prop_type = QComboBox(parent)
        self.combo_prop_type.addItems([
            safe_tr("文本"),
            safe_tr("日期"),
            safe_tr("数字"),
            safe_tr("是或否"),
        ])
        form.addRow(safe_tr("类型(&T):"), self.combo_prop_type)

        # Value LineEdit
        self.edit_prop_val = QLineEdit(parent)
        form.addRow(safe_tr("值(&V):"), self.edit_prop_val)

        layout.addLayout(form)

        # Buttons row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        self.btn_add_prop = QPushButton(safe_tr("添加(&A)"), parent)
        self.btn_add_prop.clicked.connect(self._on_add_custom_prop)
        btn_layout.addWidget(self.btn_add_prop)

        self.btn_del_prop = QPushButton(safe_tr("删除(&D)"), parent)
        self.btn_del_prop.clicked.connect(self._on_del_custom_prop)
        btn_layout.addWidget(self.btn_del_prop)
        layout.addLayout(btn_layout)

        lbl_props = QLabel(safe_tr("属性列表(&P):"), parent)
        layout.addWidget(lbl_props)

        # Custom properties table
        self.table_custom = QTableWidget(0, 3, parent)
        self.table_custom.setHorizontalHeaderLabels([
            safe_tr("名称"),
            safe_tr("类型"),
            safe_tr("值"),
        ])
        self.table_custom.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_custom.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_custom.horizontalHeader().setStretchLastSection(True)
        self.table_custom.verticalHeader().setVisible(False)
        self.table_custom.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_custom.itemSelectionChanged.connect(self._on_custom_table_selection_changed)
        layout.addWidget(self.table_custom)

    def _populate_data(self) -> None:
        m = self.metadata

        # General
        if m.file_path is not None and m.file_path.exists():
            self.lbl_filename.setText(m.file_path.name)
            self.val_location.setText(str(m.file_path.parent))
            size = m.file_path.stat().st_size
            if size < 1024:
                self.val_size.setText(f"{size} {safe_tr('字节')}")
            else:
                kb = size / 1024.0
                self.val_size.setText(f"{kb:.1f} KB ({size:,} {safe_tr('字节')})")
        else:
            doc_name = m.file_path.name if m.file_path else safe_tr("未命名文档")
            self.lbl_filename.setText(doc_name)
            self.val_location.setText(safe_tr("未保存"))
            self.val_size.setText(f"0 {safe_tr('字节')}")

        self.val_type.setText(m.file_type)

        def fmt_dt(dt: datetime.datetime | None) -> str:
            return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else safe_tr("未知")

        self.val_created.setText(fmt_dt(m.created))
        self.val_modified.setText(fmt_dt(m.modified))
        self.val_accessed.setText(fmt_dt(m.accessed))

        # Summary
        self.edit_title.setText(m.title)
        self.edit_subject.setText(m.subject)
        self.edit_author.setText(m.author)
        self.edit_manager.setText(m.manager)
        self.edit_company.setText(m.company)
        self.edit_category.setText(m.category)
        self.edit_keywords.setText(m.keywords)
        self.edit_comments.setPlainText(m.comments)
        self.edit_hyperlink_base.setText(m.hyperlink_base)
        self.val_template.setText(m.template)

        # Statistics
        self.stat_created.setText(fmt_dt(m.created))
        self.stat_modified.setText(fmt_dt(m.modified))
        self.stat_saved_by.setText(m.last_saved_by or safe_tr("无"))
        self.stat_revision.setText(str(m.revision))
        self.stat_total_time.setText(f"{m.total_editing_time} {safe_tr('分钟')}")

        stat_vals = [
            m.pages,
            m.paragraphs,
            m.lines,
            m.words,
            m.characters_no_spaces,
            m.characters_with_spaces,
        ]
        for row, val in enumerate(stat_vals):
            self.table_stats.setItem(row, 1, QTableWidgetItem(f"{val:,}"))

        # Contents
        self.list_contents.clear()
        if m.headings:
            for h in m.headings:
                self.list_contents.addItem(h)
        else:
            self.list_contents.addItem(safe_tr("(无标题大纲)"))

        # Custom
        self._refresh_custom_table()

    def _refresh_custom_table(self) -> None:
        self.table_custom.setRowCount(0)
        for name, prop in self.metadata.custom_properties.items():
            row = self.table_custom.rowCount()
            self.table_custom.insertRow(row)
            p_type = prop.get("type", "text") if isinstance(prop, dict) else "text"
            p_val = prop.get("value", prop) if isinstance(prop, dict) else str(prop)
            self.table_custom.setItem(row, 0, QTableWidgetItem(name))
            self.table_custom.setItem(row, 1, QTableWidgetItem(str(p_type)))
            self.table_custom.setItem(row, 2, QTableWidgetItem(str(p_val)))

    def _on_custom_table_selection_changed(self) -> None:
        selected_rows = self.table_custom.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            name_item = self.table_custom.item(row, 0)
            type_item = self.table_custom.item(row, 1)
            val_item = self.table_custom.item(row, 2)
            if name_item and type_item and val_item:
                self.combo_prop_name.setEditText(name_item.text())
                type_str = type_item.text().lower()
                if "date" in type_str or "日期" in type_str:
                    self.combo_prop_type.setCurrentIndex(1)
                elif "num" in type_str or "数字" in type_str:
                    self.combo_prop_type.setCurrentIndex(2)
                elif "bool" in type_str or "yes" in type_str or "是" in type_str:
                    self.combo_prop_type.setCurrentIndex(3)
                else:
                    self.combo_prop_type.setCurrentIndex(0)
                self.edit_prop_val.setText(val_item.text())

    def _on_add_custom_prop(self) -> None:
        name = self.combo_prop_name.currentText().strip()
        val = self.edit_prop_val.text().strip()
        type_idx = self.combo_prop_type.currentIndex()
        type_map = {0: "text", 1: "date", 2: "number", 3: "bool"}
        p_type = type_map.get(type_idx, "text")

        if not name:
            QMessageBox.warning(self, safe_tr("提示"), safe_tr("请输入属性名称。"))
            return

        self.metadata.custom_properties[name] = {"type": p_type, "value": val}
        self._refresh_custom_table()

    def _on_del_custom_prop(self) -> None:
        name = self.combo_prop_name.currentText().strip()
        if name in self.metadata.custom_properties:
            del self.metadata.custom_properties[name]
            self._refresh_custom_table()
            self.edit_prop_val.clear()

    def _on_accept(self) -> None:
        # Save edits back to metadata
        self.metadata.title = self.edit_title.text().strip()
        self.metadata.subject = self.edit_subject.text().strip()
        self.metadata.author = self.edit_author.text().strip()
        self.metadata.manager = self.edit_manager.text().strip()
        self.metadata.company = self.edit_company.text().strip()
        self.metadata.category = self.edit_category.text().strip()
        self.metadata.keywords = self.edit_keywords.text().strip()
        self.metadata.comments = self.edit_comments.toPlainText().strip()
        self.metadata.hyperlink_base = self.edit_hyperlink_base.text().strip()
        self.accept()

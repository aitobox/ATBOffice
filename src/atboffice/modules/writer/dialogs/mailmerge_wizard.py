"""Word 2003 classic Mail Merge Wizard and recipient management dialogs for Quire."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.writer.models.document import Document, Paragraph
from atboffice.modules.writer.models.mailmerge import (
    ADDRESS_FIELDS,
    MailMergeDataSource,
    MailMergeEngine,
    load_data_source_from_csv,
)

if TYPE_CHECKING:
    from atboffice.modules.writer.view import WriterView


def safe_tr(text: str) -> str:
    """Translate UI text safely for Mail Merge dialogs."""
    return QCoreApplication.translate("MailMergeWizard", text)


# ---------------------------------------------------------------------------
# 1. Insert Merge Field Dialog
# ---------------------------------------------------------------------------


class InsertMergeFieldDialog(QDialog):
    """Dialog for picking and inserting a merge field into the active document."""

    field_selected = Signal(str)

    def __init__(
        self,
        engine: MailMergeEngine,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle(safe_tr("插入合并域"))
        self.resize(320, 360)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.lbl_title = QLabel(safe_tr("选择要在文档中插入的字段:"))
        layout.addWidget(self.lbl_title)

        self.field_list = QListWidget(self)
        layout.addWidget(self.field_list)

        btn_box = QHBoxLayout()
        self.btn_insert = QPushButton(safe_tr("插入(&I)"), self)
        self.btn_insert.setDefault(True)
        self.btn_close = QPushButton(safe_tr("关闭(&C)"), self)
        btn_box.addStretch()
        btn_box.addWidget(self.btn_insert)
        btn_box.addWidget(self.btn_close)
        layout.addLayout(btn_box)

        # Wire actions
        self.btn_insert.clicked.connect(self._on_insert)
        self.btn_close.clicked.connect(self.reject)
        self.field_list.itemDoubleClicked.connect(lambda _: self._on_insert())

        self._populate_fields()
        self.retranslate_ui()

    def _populate_fields(self) -> None:
        self.field_list.clear()
        if self.engine.data_source:
            for f in self.engine.data_source.fields:
                self.field_list.addItem(QListWidgetItem(f))
        if self.field_list.count() > 0:
            self.field_list.setCurrentRow(0)

    def _on_insert(self) -> None:
        item = self.field_list.currentItem()
        if item:
            field_name = item.text()
            self.field_selected.emit(field_name)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("插入合并域"))
        self.lbl_title.setText(safe_tr("选择要在文档中插入的字段:"))
        self.btn_insert.setText(safe_tr("插入(&I)"))
        self.btn_close.setText(safe_tr("关闭(&C)"))


# ---------------------------------------------------------------------------
# 2. Mail Merge Recipients Dialog
# ---------------------------------------------------------------------------


class MailMergeRecipientsDialog(QDialog):
    """Word 2003 classic Mail Merge Recipients list view with filtering and sorting."""

    def __init__(
        self,
        engine: MailMergeEngine,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.ds = engine.data_source
        self.sort_col = -1
        self.sort_desc = False

        self.setWindowTitle(safe_tr("邮件合并收件人"))
        self.resize(680, 420)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        info_box = QHBoxLayout()
        self.lbl_desc = QLabel(self)
        info_box.addWidget(self.lbl_desc)
        info_box.addStretch()

        self.btn_select_all = QPushButton(safe_tr("全选"), self)
        self.btn_clear_all = QPushButton(safe_tr("全不选"), self)
        info_box.addWidget(self.btn_select_all)
        info_box.addWidget(self.btn_clear_all)
        layout.addLayout(info_box)

        self.table = QTableWidget(self)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        layout.addWidget(self.table)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self.btn_select_all.clicked.connect(self._select_all)
        self.btn_clear_all.clicked.connect(self._clear_all)

        self._populate_table()
        self.retranslate_ui()

    def _populate_table(self) -> None:
        if not self.ds:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return

        cols = [safe_tr("包含")] + self.ds.fields
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setRowCount(len(self.ds.rows))

        self.table.blockSignals(True)
        for r_idx, row_data in enumerate(self.ds.rows):
            # Checkbox item in column 0
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk_item.setCheckState(
                Qt.CheckState.Checked if r_idx in self.ds.included else Qt.CheckState.Unchecked
            )
            self.table.setItem(r_idx, 0, chk_item)

            for c_idx, val in enumerate(row_data):
                item = QTableWidgetItem(str(val))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.table.setItem(r_idx, c_idx + 1, item)
        self.table.blockSignals(False)

        self._update_info_label()

    def _update_info_label(self) -> None:
        if not self.ds:
            self.lbl_desc.setText(safe_tr("未加载数据源。"))
            return
        total = len(self.ds.rows)
        active = len(self.ds.active_records())
        self.lbl_desc.setText(
            safe_tr("数据源: {0} (选中 {1} / 共 {2} 条记录)").format(
                self.ds.name, active, total
            )
        )

    def _select_all(self) -> None:
        if not self.ds:
            return
        self.ds.included = set(range(len(self.ds.rows)))
        self._populate_table()

    def _clear_all(self) -> None:
        if not self.ds:
            return
        self.ds.included.clear()
        self._populate_table()

    def _on_header_clicked(self, logical_index: int) -> None:
        if logical_index == 0 or not self.ds:
            return
        col = logical_index - 1
        if self.sort_col == col:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_col = col
            self.sort_desc = False

        self.ds.sort_by(column_index=col, descending=self.sort_desc)
        self._populate_table()

    def accept(self) -> None:
        # Save check states back to data source
        if self.ds:
            new_included: set[int] = set()
            for r_idx in range(self.table.rowCount()):
                item = self.table.item(r_idx, 0)
                if item and item.checkState() == Qt.CheckState.Checked:
                    new_included.add(r_idx)
            self.ds.included = new_included
        super().accept()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("邮件合并收件人"))
        self.btn_select_all.setText(safe_tr("全选"))
        self.btn_clear_all.setText(safe_tr("全不选"))
        self._update_info_label()


# ---------------------------------------------------------------------------
# 3. Type a New Address List Dialog
# ---------------------------------------------------------------------------


class AddressListDialog(QDialog):
    """Word 2003 classic 'Type a New Address List' data entry modal."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("新建地址列表"))
        self.resize(520, 520)

        self.fields = list(ADDRESS_FIELDS)
        self.rows: list[list[str]] = [[ "" for _ in self.fields ]]
        self.current_index = 0

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Form fields
        form_group = QGroupBox(safe_tr("联系人信息"), self)
        form_layout = QFormLayout(form_group)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.inputs: list[QLineEdit] = []
        for f_name in self.fields:
            inp = QLineEdit(self)
            inp.textEdited.connect(self._on_text_edited)
            self.inputs.append(inp)
            form_layout.addRow(QLabel(f_name + ":"), inp)

        layout.addWidget(form_group)

        # Navigation & Controls
        nav_box = QHBoxLayout()
        self.btn_new = QPushButton(safe_tr("新建条目(&N)"), self)
        self.btn_delete = QPushButton(safe_tr("删除条目(&D)"), self)
        self.btn_prev = QPushButton("<", self)
        self.btn_next = QPushButton(">", self)
        self.lbl_record = QLabel(self)

        nav_box.addWidget(self.btn_new)
        nav_box.addWidget(self.btn_delete)
        nav_box.addStretch()
        nav_box.addWidget(self.btn_prev)
        nav_box.addWidget(self.btn_next)
        nav_box.addWidget(self.lbl_record)
        layout.addLayout(nav_box)

        # Dialog Buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self.btn_new.clicked.connect(self._add_entry)
        self.btn_delete.clicked.connect(self._delete_entry)
        self.btn_prev.clicked.connect(self._prev_entry)
        self.btn_next.clicked.connect(self._next_entry)

        self._load_current()
        self.retranslate_ui()

    def _load_current(self) -> None:
        row = self.rows[self.current_index]
        for i, val in enumerate(row):
            self.inputs[i].setText(val)
        self.lbl_record.setText(
            safe_tr("条目 {0} / 共 {1} 条").format(self.current_index + 1, len(self.rows))
        )
        self.btn_prev.setEnabled(self.current_index > 0)
        self.btn_next.setEnabled(self.current_index < len(self.rows) - 1)

    def _on_text_edited(self) -> None:
        for i, inp in enumerate(self.inputs):
            self.rows[self.current_index][i] = inp.text()

    def _add_entry(self) -> None:
        self.rows.append(["" for _ in self.fields])
        self.current_index = len(self.rows) - 1
        self._load_current()
        self.inputs[0].setFocus()

    def _delete_entry(self) -> None:
        if len(self.rows) > 1:
            self.rows.pop(self.current_index)
            self.current_index = min(self.current_index, len(self.rows) - 1)
            self._load_current()

    def _prev_entry(self) -> None:
        if self.current_index > 0:
            self.current_index -= 1
            self._load_current()

    def _next_entry(self) -> None:
        if self.current_index < len(self.rows) - 1:
            self.current_index += 1
            self._load_current()

    def get_data_source(self) -> MailMergeDataSource:
        # Filter out empty rows
        valid_rows = [r for r in self.rows if any(cell.strip() for cell in r)]
        if not valid_rows:
            valid_rows = [["" for _ in self.fields]]
        return MailMergeDataSource(
            name=safe_tr("新地址列表"),
            fields=self.fields,
            rows=valid_rows,
            included=set(range(len(valid_rows))),
            is_typed=True,
        )

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("新建地址列表"))
        self.btn_new.setText(safe_tr("新建条目(&N)"))
        self.btn_delete.setText(safe_tr("删除条目(&D)"))
        self._load_current()


# ---------------------------------------------------------------------------
# 4. Word 2003 Classic Mail Merge Wizard Dialog
# ---------------------------------------------------------------------------


class MailMergeWizardDialog(QDialog):
    """Word 2003 classic 6-step Mail Merge Wizard Dialog."""

    wizard_completed = Signal(Document)

    def __init__(
        self,
        doc: Document,
        engine: MailMergeEngine | None = None,
        writer_view: WriterView | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.doc = doc
        self.engine = engine or MailMergeEngine()
        self.writer_view = writer_view
        self.current_step = 1

        self.setWindowTitle(safe_tr("邮件合并向导"))
        self.resize(540, 480)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        # Step title header
        self.lbl_step_header = QLabel(self)
        self.lbl_step_header.setStyleSheet("font-weight: bold; font-size: 13px; color: #003399;")
        main_layout.addWidget(self.lbl_step_header)

        # Wizard pages
        self.pages_stack = QStackedWidget(self)
        self._init_step1_page()
        self._init_step2_page()
        self._init_step3_page()
        self._init_step4_page()
        self._init_step5_page()
        self._init_step6_page()
        main_layout.addWidget(self.pages_stack)

        # Navigation buttons
        nav_layout = QHBoxLayout()
        self.lbl_step_info = QLabel(self)
        nav_layout.addWidget(self.lbl_step_info)
        nav_layout.addStretch()

        self.btn_prev = QPushButton(safe_tr("上一步(&P)"), self)
        self.btn_next = QPushButton(safe_tr("下一步(&N)"), self)
        self.btn_close = QPushButton(safe_tr("关闭(&C)"), self)

        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_next)
        nav_layout.addWidget(self.btn_close)
        main_layout.addLayout(nav_layout)

        self.btn_prev.clicked.connect(self.prev_step)
        self.btn_next.clicked.connect(self.next_step)
        self.btn_close.clicked.connect(self.reject)

        self._update_step_ui()
        self.retranslate_ui()

    # --- Step 1: Select Document Type ---
    def _init_step1_page(self) -> None:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        lbl = QLabel(safe_tr("您正在处理哪种类型的文档?"), page)
        layout.addWidget(lbl)

        self.rb_type_letters = QRadioButton(safe_tr("信函 (Letters)"), page)
        self.rb_type_envelopes = QRadioButton(safe_tr("信封 (Envelopes)"), page)
        self.rb_type_labels = QRadioButton(safe_tr("标签 (Labels)"), page)
        self.rb_type_directory = QRadioButton(safe_tr("目录 (Directory)"), page)
        self.rb_type_letters.setChecked(True)

        self.type_group = QButtonGroup(page)
        self.type_group.addButton(self.rb_type_letters, 0)
        self.type_group.addButton(self.rb_type_envelopes, 1)
        self.type_group.addButton(self.rb_type_labels, 2)
        self.type_group.addButton(self.rb_type_directory, 3)

        layout.addWidget(self.rb_type_letters)
        layout.addWidget(self.rb_type_envelopes)
        layout.addWidget(self.rb_type_labels)
        layout.addWidget(self.rb_type_directory)

        self.lbl_type_desc = QLabel(
            safe_tr("信函: 向一组人员发送个性化信函，每人收到的信件包含定制化个人信息。"),
            page,
        )
        self.lbl_type_desc.setWordWrap(True)
        self.lbl_type_desc.setStyleSheet("color: #555555; margin-top: 10px;")
        layout.addWidget(self.lbl_type_desc)
        layout.addStretch()

        self.pages_stack.addWidget(page)

    # --- Step 2: Select Starting Document ---
    def _init_step2_page(self) -> None:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        lbl = QLabel(safe_tr("如何设置您的信函?"), page)
        layout.addWidget(lbl)

        self.rb_start_current = QRadioButton(safe_tr("使用当前文档"), page)
        self.rb_start_template = QRadioButton(safe_tr("从模板开始"), page)
        self.rb_start_existing = QRadioButton(safe_tr("从现有文档开始"), page)
        self.rb_start_current.setChecked(True)

        layout.addWidget(self.rb_start_current)
        layout.addWidget(self.rb_start_template)
        layout.addWidget(self.rb_start_existing)
        layout.addStretch()

        self.pages_stack.addWidget(page)

    # --- Step 3: Select Recipients ---
    def _init_step3_page(self) -> None:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        lbl = QLabel(safe_tr("选取收件人数据来源:"), page)
        layout.addWidget(lbl)

        self.btn_browse_csv = QPushButton(safe_tr("浏览并选择 CSV/表格数据源..."), page)
        self.btn_edit_recipients = QPushButton(safe_tr("编辑收件人列表..."), page)
        self.btn_type_list = QPushButton(safe_tr("键入新地址列表..."), page)

        layout.addWidget(self.btn_browse_csv)
        layout.addWidget(self.btn_edit_recipients)
        layout.addWidget(self.btn_type_list)

        self.lbl_recipients_info = QLabel(safe_tr("尚未选择数据源。"), page)
        self.lbl_recipients_info.setWordWrap(True)
        self.lbl_recipients_info.setStyleSheet(
            "color: #006600; font-weight: bold; margin-top: 8px;"
        )
        layout.addWidget(self.lbl_recipients_info)
        layout.addStretch()

        self.btn_browse_csv.clicked.connect(self._browse_csv)
        self.btn_edit_recipients.clicked.connect(self._edit_recipients)
        self.btn_type_list.clicked.connect(self._type_new_list)

        self.pages_stack.addWidget(page)

    # --- Step 4: Write Your Letter ---
    def _init_step4_page(self) -> None:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        lbl = QLabel(safe_tr("在正文中插入合并域项目:"), page)
        layout.addWidget(lbl)

        self.btn_insert_addr_block = QPushButton(safe_tr("地址块 (Address Block)..."), page)
        self.btn_insert_greeting = QPushButton(safe_tr("问候行 (Greeting Line)..."), page)
        self.btn_insert_field = QPushButton(safe_tr("更多合并域 (More Items)..."), page)

        layout.addWidget(self.btn_insert_addr_block)
        layout.addWidget(self.btn_insert_greeting)
        layout.addWidget(self.btn_insert_field)

        self.lbl_write_hint = QLabel(
            safe_tr("提示: 单击上方按钮可在文档当前光标处插入动态占位域。"),
            page,
        )
        self.lbl_write_hint.setStyleSheet("color: #555555; margin-top: 10px;")
        layout.addWidget(self.lbl_write_hint)
        layout.addStretch()

        self.btn_insert_addr_block.clicked.connect(self._insert_address_block)
        self.btn_insert_greeting.clicked.connect(self._insert_greeting_line)
        self.btn_insert_field.clicked.connect(self._open_insert_field_dialog)

        self.pages_stack.addWidget(page)

    # --- Step 5: Preview Your Letters ---
    def _init_step5_page(self) -> None:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        lbl = QLabel(safe_tr("预览合并结果:"), page)
        layout.addWidget(lbl)

        preview_nav = QHBoxLayout()
        self.btn_preview_prev = QPushButton("<< " + safe_tr("上一个"), page)
        self.lbl_preview_rec = QLabel(safe_tr("收件人: 0 / 0"), page)
        self.btn_preview_next = QPushButton(safe_tr("下一个") + " >>", page)

        preview_nav.addWidget(self.btn_preview_prev)
        preview_nav.addStretch()
        preview_nav.addWidget(self.lbl_preview_rec)
        preview_nav.addStretch()
        preview_nav.addWidget(self.btn_preview_next)
        layout.addLayout(preview_nav)

        self.btn_exclude_rec = QPushButton(safe_tr("排除此收件人"), page)
        layout.addWidget(self.btn_exclude_rec)
        layout.addStretch()

        self.btn_preview_prev.clicked.connect(lambda: self._preview_step(-1))
        self.btn_preview_next.clicked.connect(lambda: self._preview_step(1))
        self.btn_exclude_rec.clicked.connect(self._exclude_current_recipient)

        self.pages_stack.addWidget(page)

    # --- Step 6: Complete the Merge ---
    def _init_step6_page(self) -> None:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        lbl = QLabel(safe_tr("Quire 已准备好生成您的合并文档:"), page)
        layout.addWidget(lbl)

        self.btn_merge_new_doc = QPushButton(safe_tr("合并到新文档 (编辑各个信函)..."), page)
        self.btn_merge_pdf = QPushButton(safe_tr("打印 / 批量导出 PDF..."), page)

        layout.addWidget(self.btn_merge_new_doc)
        layout.addWidget(self.btn_merge_pdf)
        layout.addStretch()

        self.btn_merge_new_doc.clicked.connect(self._merge_to_new_doc)
        self.btn_merge_pdf.clicked.connect(self._merge_to_pdf)

        self.pages_stack.addWidget(page)

    # --- Navigation Logic ---
    def next_step(self) -> None:
        if self.current_step == 3 and not self.engine.data_source:
            QMessageBox.information(
                self, safe_tr("提示"), safe_tr("请先选择或创建一个收件人数据源。")
            )
            return

        if self.current_step < 6:
            self.current_step += 1
            if self.current_step == 5:
                # Enter preview mode
                self.engine.preview = True
                self.engine.go(self.doc, self.engine.current_record)
            self._update_step_ui()

    def prev_step(self) -> None:
        if self.current_step > 1:
            self.current_step -= 1
            self._update_step_ui()

    def _update_step_ui(self) -> None:
        self.pages_stack.setCurrentIndex(self.current_step - 1)
        self.btn_prev.setEnabled(self.current_step > 1)
        self.btn_next.setVisible(self.current_step < 6)

        step_titles = [
            safe_tr("步骤 1 / 6: 选择文档类型"),
            safe_tr("步骤 2 / 6: 选择起始文档"),
            safe_tr("步骤 3 / 6: 选取收件人"),
            safe_tr("步骤 4 / 6: 撰写信件与插入合并域"),
            safe_tr("步骤 5 / 6: 预览信件"),
            safe_tr("步骤 6 / 6: 完成合并"),
        ]
        self.lbl_step_header.setText(step_titles[self.current_step - 1])
        self.lbl_step_info.setText(safe_tr("第 {0} 步 (共 6 步)").format(self.current_step))

        self._refresh_recipients_info()
        self._refresh_preview_info()

    def _refresh_recipients_info(self) -> None:
        if self.engine.data_source:
            recs = self.engine.data_source.active_records()
            total = len(self.engine.data_source.rows)
            self.lbl_recipients_info.setText(
                safe_tr("当前数据源: {0} (选中 {1} / 共 {2} 位收件人)").format(
                    self.engine.data_source.name, len(recs), total
                )
            )
        else:
            self.lbl_recipients_info.setText(safe_tr("尚未选择数据源。"))

    def _refresh_preview_info(self) -> None:
        n = self.engine.active_record_count()
        cur = self.engine.current_record + 1 if n > 0 else 0
        self.lbl_preview_rec.setText(safe_tr("收件人: {0} / {1}").format(cur, n))
        self.btn_preview_prev.setEnabled(self.engine.current_record > 0)
        self.btn_preview_next.setEnabled(self.engine.current_record < n - 1)

    # --- Actions ---
    def _browse_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            safe_tr("选择数据源文件"),
            "",
            safe_tr("数据表格 (*.csv *.txt *.tsv);;所有文件 (*.*)"),
        )
        if path:
            try:
                ds = load_data_source_from_csv(path)
                self.engine.set_data_source(ds)
                self._refresh_recipients_info()
                # Open recipients editor dialog
                self._edit_recipients()
            except Exception as e:
                QMessageBox.warning(
                    self, safe_tr("错误"), safe_tr("打开数据源失败: {0}").format(str(e))
                )

    def _edit_recipients(self) -> None:
        if not self.engine.data_source:
            QMessageBox.information(self, safe_tr("提示"), safe_tr("请先选择数据源。"))
            return
        dlg = MailMergeRecipientsDialog(engine=self.engine, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._refresh_recipients_info()

    def _type_new_list(self) -> None:
        dlg = AddressListDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            ds = dlg.get_data_source()
            self.engine.set_data_source(ds)
            self._refresh_recipients_info()

    def _get_active_paragraph_and_offset(self) -> tuple[Paragraph, int]:
        """Obtain paragraph and character offset from active canvas caret or doc tail."""
        if self.writer_view and hasattr(self.writer_view, "canvas_view"):
            cv = self.writer_view.canvas_view
            controller = cv.controller
            para = controller.caret_para
            offset = controller.caret_offset
            if para is not None:
                return para, offset

        if self.doc.main.paras:
            last_p = self.doc.main.paras[-1]
            from atboffice.modules.writer.models.document import plen

            return last_p, plen(last_p)

        new_p = Paragraph()
        self.doc.main.paras.append(new_p)
        return new_p, 0

    def _insert_address_block(self) -> None:
        para, _ = self._get_active_paragraph_and_offset()
        self.engine.insert_address_block(self.doc, insert_after_p=para)
        if self.writer_view:
            self.writer_view.canvas_view.update()
        QMessageBox.information(self, safe_tr("成功"), safe_tr("已在文档中插入地址块。"))

    def _insert_greeting_line(self) -> None:
        para, offset = self._get_active_paragraph_and_offset()
        self.engine.insert_greeting_line(para, offset=offset)
        if self.writer_view:
            self.writer_view.canvas_view.update()
        QMessageBox.information(self, safe_tr("成功"), safe_tr("已在光标处插入问候行。"))

    def _open_insert_field_dialog(self) -> None:
        if not self.engine.data_source:
            QMessageBox.information(self, safe_tr("提示"), safe_tr("请先选择数据源。"))
            return
        dlg = InsertMergeFieldDialog(engine=self.engine, parent=self)
        dlg.field_selected.connect(self._do_insert_field)
        dlg.exec()

    def _do_insert_field(self, field_name: str) -> None:
        para, offset = self._get_active_paragraph_and_offset()
        self.engine.insert_field(para, offset=offset, field_name=field_name)
        if self.writer_view:
            self.writer_view.canvas_view.update()

    def _preview_step(self, delta: int) -> None:
        self.engine.step(self.doc, delta)
        self._refresh_preview_info()
        if self.writer_view:
            self.writer_view.canvas_view.update()

    def _exclude_current_recipient(self) -> None:
        if not self.engine.data_source:
            return
        recs = self.engine.data_source.active_records()
        if recs and self.engine.current_record < len(recs):
            rec_to_exclude = recs[self.engine.current_record]
            self.engine.data_source.included.discard(rec_to_exclude)
            self._preview_step(0)

    def _merge_to_new_doc(self) -> None:
        merged = self.engine.build_merged_document(self.doc)
        if not merged:
            QMessageBox.warning(self, safe_tr("错误"), safe_tr("没有可供合并的收件人记录。"))
            return
        self.wizard_completed.emit(merged)
        n = self.engine.active_record_count()
        QMessageBox.information(
            self,
            safe_tr("合并完成"),
            safe_tr("已将 {0} 条收件人记录合并为新文档。").format(n),
        )

    def _merge_to_pdf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            safe_tr("保存合并 PDF"),
            "merged_letters.pdf",
            safe_tr("PDF 文档 (*.pdf)"),
        )
        if path:
            try:
                self.engine.export_merged_pdf(self.doc, path)
                QMessageBox.information(
                    self, safe_tr("成功"), safe_tr("已成功导出 PDF: {0}").format(path)
                )
            except Exception as e:
                QMessageBox.warning(
                    self, safe_tr("错误"), safe_tr("导出 PDF 失败: {0}").format(str(e))
                )

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("邮件合并向导"))
        self.btn_prev.setText(safe_tr("上一步(&P)"))
        self.btn_next.setText(safe_tr("下一步(&N)"))
        self.btn_close.setText(safe_tr("关闭(&C)"))
        self._update_step_ui()

"""Excel 2003 classic 3-step Text Import Wizard Dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.spreadsheet.calc.references import col_name
from atboffice.modules.spreadsheet.io.csv_io import (
    convert_cell_value,
    decode_bytes,
    guess_fixed_breaks,
    parse_delimited,
    parse_fixed_width,
    populate_sheet,
    sniff_delimiter,
)

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("TextImportWizard", text)


class TextImportWizard(QDialog):
    """Classic 3-step Text Import Wizard dialog for CSV and text files."""

    def __init__(
        self,
        data: bytes | str,
        file_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.raw_data: bytes = (
            data.encode("utf-8") if isinstance(data, str) else data
        )
        self.file_name = file_name
        self.text: str = ""
        self.detected_encoding: str = "utf-8"
        self.current_encoding: str = "auto"

        # Parsing state
        self.is_delimited: bool = True
        self.start_row: int = 1
        self.column_formats: dict[int, str] = {}
        self.selected_col: int = 0
        self.fixed_breaks: list[int] = []

        # Initial decoding and sniffing
        self._decode_content()
        sniffed = sniff_delimiter(self.text)
        self.fixed_breaks = guess_fixed_breaks(self.text)

        self.setWindowTitle(
            safe_tr("Text Import Wizard - Step 1 of 3")
        )
        self.resize(650, 520)

        main_layout = QVBoxLayout(self)

        # Header description
        self.step_desc_label = QLabel(self)
        self.step_desc_label.setWordWrap(True)
        main_layout.addWidget(self.step_desc_label)

        # Stacked pages
        self.stack = QStackedWidget(self)
        main_layout.addWidget(self.stack, 1)

        # Page 1: Type & Origin
        self.page1 = self._build_page1(sniffed)
        self.stack.addWidget(self.page1)

        # Page 2: Delimiters / Fixed width
        self.page2 = self._build_page2(sniffed)
        self.stack.addWidget(self.page2)

        # Page 3: Column formats
        self.page3 = self._build_page3()
        self.stack.addWidget(self.page3)

        # Bottom navigation buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.back_btn = QPushButton(safe_tr("< Back"), self)
        self.back_btn.clicked.connect(self._on_back)
        btn_layout.addWidget(self.back_btn)

        self.next_btn = QPushButton(safe_tr("Next >"), self)
        self.next_btn.clicked.connect(self._on_next)
        btn_layout.addWidget(self.next_btn)

        self.finish_btn = QPushButton(safe_tr("Finish"), self)
        self.finish_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.finish_btn)

        self.cancel_btn = QPushButton(safe_tr("Cancel"), self)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        main_layout.addLayout(btn_layout)

        self._update_navigation_state()
        self._update_step1_preview()
        self.retranslate_ui()

    def _decode_content(self) -> None:
        self.text, self.detected_encoding = decode_bytes(
            self.raw_data,
            encoding=None
            if self.current_encoding == "auto"
            else self.current_encoding,
        )

    def _build_page1(self, sniffed_delim: str) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)

        # Type GroupBox
        self.type_group = QGroupBox(
            safe_tr("Original data type"), page
        )
        type_layout = QVBoxLayout(self.type_group)

        self.delimited_radio = QRadioButton(
            safe_tr(
                "Delimited - Characters such as commas or tabs separate each field."
            ),
            self.type_group,
        )
        self.delimited_radio.setChecked(True)
        self.delimited_radio.toggled.connect(self._on_type_changed)
        type_layout.addWidget(self.delimited_radio)

        self.fixed_radio = QRadioButton(
            safe_tr(
                "Fixed width - Fields are aligned in columns with spaces between each field."
            ),
            self.type_group,
        )
        type_layout.addWidget(self.fixed_radio)

        layout.addWidget(self.type_group)

        # Options layout (Start row & Encoding)
        opts_layout = QHBoxLayout()

        self.start_row_label = QLabel(safe_tr("Start import at row:"), page)
        opts_layout.addWidget(self.start_row_label)
        self.start_row_spin = QSpinBox(page)
        self.start_row_spin.setRange(1, 9999)
        self.start_row_spin.setValue(1)
        self.start_row_spin.valueChanged.connect(self._on_start_row_changed)
        opts_layout.addWidget(self.start_row_spin)

        opts_layout.addSpacing(20)

        self.encoding_label = QLabel(safe_tr("File origin:"), page)
        opts_layout.addWidget(self.encoding_label)
        self.encoding_combo = QComboBox(page)
        self.encoding_combo.addItem(
            f"Auto ({self.detected_encoding})", "auto"
        )
        self.encoding_combo.addItem("Unicode (UTF-8)", "utf-8")
        self.encoding_combo.addItem(
            "Chinese Simplified (GB18030)", "gb18030"
        )
        self.encoding_combo.addItem("Windows (ANSI / CP1252)", "windows-1252")
        self.encoding_combo.addItem("Unicode (UTF-16 LE)", "utf-16le")
        self.encoding_combo.addItem("Unicode (UTF-16 BE)", "utf-16be")
        self.encoding_combo.currentIndexChanged.connect(self._on_encoding_changed)
        opts_layout.addWidget(self.encoding_combo)

        opts_layout.addStretch()
        layout.addLayout(opts_layout)

        # Preview of raw text
        self.raw_preview_group = QGroupBox(
            safe_tr("Preview of file:"), page
        )
        raw_layout = QVBoxLayout(self.raw_preview_group)
        self.raw_preview_edit = QPlainTextEdit(self.raw_preview_group)
        self.raw_preview_edit.setReadOnly(True)
        self.raw_preview_edit.setFont(QFont("Courier New", 10))
        raw_layout.addWidget(self.raw_preview_edit)
        layout.addWidget(self.raw_preview_group, 1)

        return page

    def _build_page2(self, sniffed_delim: str) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)

        # Delimiters GroupBox
        self.delim_group = QGroupBox(safe_tr("Delimiters"), page)
        delim_layout = QVBoxLayout(self.delim_group)

        check_row = QHBoxLayout()
        self.tab_check = QCheckBox(safe_tr("Tab"), self.delim_group)
        self.tab_check.setChecked(sniffed_delim == "\t")
        self.tab_check.toggled.connect(self._on_delim_changed)
        check_row.addWidget(self.tab_check)

        self.semicolon_check = QCheckBox(
            safe_tr("Semicolon"), self.delim_group
        )
        self.semicolon_check.setChecked(sniffed_delim == ";")
        self.semicolon_check.toggled.connect(self._on_delim_changed)
        check_row.addWidget(self.semicolon_check)

        self.comma_check = QCheckBox(safe_tr("Comma"), self.delim_group)
        self.comma_check.setChecked(sniffed_delim == ",")
        self.comma_check.toggled.connect(self._on_delim_changed)
        check_row.addWidget(self.comma_check)

        self.space_check = QCheckBox(safe_tr("Space"), self.delim_group)
        self.space_check.setChecked(sniffed_delim == " ")
        self.space_check.toggled.connect(self._on_delim_changed)
        check_row.addWidget(self.space_check)

        self.other_check = QCheckBox(safe_tr("Other:"), self.delim_group)
        self.other_check.setChecked(sniffed_delim not in ("\t", ";", ",", " "))
        self.other_check.toggled.connect(self._on_delim_changed)
        check_row.addWidget(self.other_check)

        self.other_edit = QLineEdit(self.delim_group)
        self.other_edit.setMaxLength(1)
        if sniffed_delim not in ("\t", ";", ",", " "):
            self.other_edit.setText(sniffed_delim)
        self.other_edit.setFixedWidth(30)
        self.other_edit.textChanged.connect(self._on_delim_changed)
        check_row.addWidget(self.other_edit)

        check_row.addStretch()
        delim_layout.addLayout(check_row)

        opts_row = QHBoxLayout()
        self.merge_check = QCheckBox(
            safe_tr("Treat consecutive delimiters as one"),
            self.delim_group,
        )
        self.merge_check.toggled.connect(self._on_delim_changed)
        opts_row.addWidget(self.merge_check)

        opts_row.addSpacing(20)
        self.qualifier_label = QLabel(safe_tr("Text qualifier:"), page)
        opts_row.addWidget(self.qualifier_label)
        self.qualifier_combo = QComboBox(page)
        self.qualifier_combo.addItem('"', '"')
        self.qualifier_combo.addItem("'", "'")
        self.qualifier_combo.addItem(safe_tr("{none}"), "")
        self.qualifier_combo.currentIndexChanged.connect(self._on_delim_changed)
        opts_row.addWidget(self.qualifier_combo)

        opts_row.addStretch()
        delim_layout.addLayout(opts_row)
        layout.addWidget(self.delim_group)

        # Fixed width options
        self.fixed_group = QGroupBox(
            safe_tr("Fixed Width Column Breaks"), page
        )
        fixed_layout = QVBoxLayout(self.fixed_group)
        self.fixed_desc_label = QLabel(
            safe_tr(
                "Column break positions (comma-separated character indices):"
            ),
            page,
        )
        fixed_layout.addWidget(self.fixed_desc_label)
        self.breaks_edit = QLineEdit(page)
        self.breaks_edit.setText(", ".join(str(b) for b in self.fixed_breaks))
        self.breaks_edit.textChanged.connect(self._on_breaks_changed)
        fixed_layout.addWidget(self.breaks_edit)
        layout.addWidget(self.fixed_group)
        self.fixed_group.setVisible(False)

        # Data preview table
        self.step2_preview_group = QGroupBox(
            safe_tr("Data preview:"), page
        )
        prev_layout = QVBoxLayout(self.step2_preview_group)
        self.step2_table = QTableWidget(self.step2_preview_group)
        self.step2_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        prev_layout.addWidget(self.step2_table)
        layout.addWidget(self.step2_preview_group, 1)

        return page

    def _build_page3(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)

        # Column format GroupBox
        self.format_group = QGroupBox(
            safe_tr("Column data format"), page
        )
        fmt_layout = QHBoxLayout(self.format_group)

        self.fmt_btn_group = QButtonGroup(page)

        self.fmt_general_radio = QRadioButton(
            safe_tr("General"), self.format_group
        )
        self.fmt_general_radio.setChecked(True)
        self.fmt_btn_group.addButton(self.fmt_general_radio)
        fmt_layout.addWidget(self.fmt_general_radio)

        self.fmt_text_radio = QRadioButton(
            safe_tr("Text"), self.format_group
        )
        self.fmt_btn_group.addButton(self.fmt_text_radio)
        fmt_layout.addWidget(self.fmt_text_radio)

        self.fmt_date_radio = QRadioButton(
            safe_tr("Date:"), self.format_group
        )
        self.fmt_btn_group.addButton(self.fmt_date_radio)
        fmt_layout.addWidget(self.fmt_date_radio)

        self.date_order_combo = QComboBox(self.format_group)
        self.date_order_combo.addItem("YMD")
        self.date_order_combo.addItem("MDY")
        self.date_order_combo.addItem("DMY")
        fmt_layout.addWidget(self.date_order_combo)

        self.fmt_skip_radio = QRadioButton(
            safe_tr("Do not import column (skip)"), self.format_group
        )
        self.fmt_btn_group.addButton(self.fmt_skip_radio)
        fmt_layout.addWidget(self.fmt_skip_radio)

        self.fmt_general_radio.toggled.connect(self._on_column_format_changed)
        self.fmt_text_radio.toggled.connect(self._on_column_format_changed)
        self.fmt_date_radio.toggled.connect(self._on_column_format_changed)
        self.fmt_skip_radio.toggled.connect(self._on_column_format_changed)
        self.date_order_combo.currentIndexChanged.connect(
            self._on_column_format_changed
        )

        fmt_layout.addStretch()
        layout.addWidget(self.format_group)

        # Data preview table
        self.step3_preview_group = QGroupBox(
            safe_tr("Data preview:"), page
        )
        prev_layout = QVBoxLayout(self.step3_preview_group)
        self.step3_table = QTableWidget(self.step3_preview_group)
        self.step3_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.step3_table.horizontalHeader().sectionClicked.connect(
            self._on_step3_col_clicked
        )
        self.step3_table.cellClicked.connect(
            lambda r, c: self._on_step3_col_clicked(c)
        )
        prev_layout.addWidget(self.step3_table)
        layout.addWidget(self.step3_preview_group, 1)

        return page

    def _get_active_delimiters(self) -> str:
        delims = ""
        if self.tab_check.isChecked():
            delims += "\t"
        if self.semicolon_check.isChecked():
            delims += ";"
        if self.comma_check.isChecked():
            delims += ","
        if self.space_check.isChecked():
            delims += " "
        if self.other_check.isChecked() and self.other_edit.text():
            delims += self.other_edit.text()
        return delims if delims else ","

    def _get_active_quote(self) -> str:
        return self.qualifier_combo.currentData() or ""

    def _parse_current_data(self, max_rows: int | None = None) -> list[list[str]]:
        skip = max(0, self.start_row - 1)
        lines = self.text.splitlines()
        content = "\n".join(lines[skip:]) if skip < len(lines) else ""

        if self.delimited_radio.isChecked():
            return parse_delimited(
                content,
                delims=self._get_active_delimiters(),
                quote=self._get_active_quote(),
                merge=self.merge_check.isChecked(),
                max_rows=max_rows,
            )
        else:
            return parse_fixed_width(
                content,
                breaks=self.fixed_breaks,
                max_rows=max_rows,
            )

    def _update_step1_preview(self) -> None:
        lines = self.text.splitlines()[:50]
        self.raw_preview_edit.setPlainText("\n".join(lines))

    def _populate_preview_table(
        self, table: QTableWidget, with_formats: bool = False
    ) -> None:
        rows = self._parse_current_data(max_rows=25)
        if not rows:
            table.setRowCount(0)
            table.setColumnCount(0)
            return

        cols = max(len(r) for r in rows)
        table.setRowCount(len(rows))
        table.setColumnCount(cols)

        headers: list[str] = []
        for c in range(cols):
            fmt = self.column_formats.get(c, "General")
            if with_formats:
                headers.append(f"[{fmt}]\n{col_name(c)}")
            else:
                headers.append(col_name(c))
        table.setHorizontalHeaderLabels(headers)

        for r_idx, row in enumerate(rows):
            for c_idx in range(cols):
                val = row[c_idx] if c_idx < len(row) else ""
                item = QTableWidgetItem(val)
                if with_formats and c_idx == self.selected_col:
                    item.setBackground(Qt.GlobalColor.lightGray)
                table.setItem(r_idx, c_idx, item)

        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

    def _on_type_changed(self) -> None:
        is_delim = self.delimited_radio.isChecked()
        self.delim_group.setVisible(is_delim)
        self.fixed_group.setVisible(not is_delim)
        self._populate_preview_table(self.step2_table)

    def _on_start_row_changed(self, val: int) -> None:
        self.start_row = val
        self._populate_preview_table(self.step2_table)
        self._populate_preview_table(self.step3_table, with_formats=True)

    def _on_encoding_changed(self) -> None:
        enc = self.encoding_combo.currentData()
        self.current_encoding = enc
        self._decode_content()
        self._update_step1_preview()
        self._populate_preview_table(self.step2_table)
        self._populate_preview_table(self.step3_table, with_formats=True)

    def _on_delim_changed(self) -> None:
        self._populate_preview_table(self.step2_table)
        self._populate_preview_table(self.step3_table, with_formats=True)

    def _on_breaks_changed(self, text: str) -> None:
        try:
            self.fixed_breaks = [
                int(x.strip()) for x in text.split(",") if x.strip().isdigit()
            ]
        except Exception:
            pass
        self._populate_preview_table(self.step2_table)
        self._populate_preview_table(self.step3_table, with_formats=True)

    def _on_step3_col_clicked(self, col: int) -> None:
        self.selected_col = col
        fmt = self.column_formats.get(col, "General")
        self.fmt_general_radio.blockSignals(True)
        self.fmt_text_radio.blockSignals(True)
        self.fmt_date_radio.blockSignals(True)
        self.fmt_skip_radio.blockSignals(True)

        if fmt == "General":
            self.fmt_general_radio.setChecked(True)
        elif fmt == "Text":
            self.fmt_text_radio.setChecked(True)
        elif fmt.startswith("Date"):
            self.fmt_date_radio.setChecked(True)
        elif fmt == "Skip":
            self.fmt_skip_radio.setChecked(True)

        self.fmt_general_radio.blockSignals(False)
        self.fmt_text_radio.blockSignals(False)
        self.fmt_date_radio.blockSignals(False)
        self.fmt_skip_radio.blockSignals(False)

        self._populate_preview_table(self.step3_table, with_formats=True)

    def _on_column_format_changed(self) -> None:
        fmt = "General"
        if self.fmt_text_radio.isChecked():
            fmt = "Text"
        elif self.fmt_date_radio.isChecked():
            fmt = f"Date:{self.date_order_combo.currentText()}"
        elif self.fmt_skip_radio.isChecked():
            fmt = "Skip"

        self.column_formats[self.selected_col] = fmt
        self._populate_preview_table(self.step3_table, with_formats=True)

    def _update_navigation_state(self) -> None:
        idx = self.stack.currentIndex()
        self.back_btn.setEnabled(idx > 0)
        self.next_btn.setEnabled(idx < 2)
        titles = [
            safe_tr("Text Import Wizard - Step 1 of 3"),
            safe_tr("Text Import Wizard - Step 2 of 3"),
            safe_tr("Text Import Wizard - Step 3 of 3"),
        ]
        descs = [
            safe_tr(
                "The Text Wizard has determined that your data is Delimited. If this is correct, choose Next, or choose the data type that best describes your data."
            ),
            safe_tr(
                "This screen lets you set the delimiters your data contains. You can see how your text is affected in the preview below."
            ),
            safe_tr(
                "This screen lets you select each column and set the Data Format."
            ),
        ]
        self.setWindowTitle(titles[idx])
        self.step_desc_label.setText(descs[idx])

    def _on_next(self) -> None:
        idx = self.stack.currentIndex()
        if idx < 2:
            self.stack.setCurrentIndex(idx + 1)
            self._update_navigation_state()
            if idx + 1 == 1:
                self._populate_preview_table(self.step2_table)
            elif idx + 1 == 2:
                self._populate_preview_table(self.step3_table, with_formats=True)

    def _on_back(self) -> None:
        idx = self.stack.currentIndex()
        if idx > 0:
            self.stack.setCurrentIndex(idx - 1)
            self._update_navigation_state()

    def get_result_rows(self) -> list[list[Any]]:
        """Return parsed and converted cell data matrix according to selected settings."""
        raw_rows = self._parse_current_data()
        out: list[list[Any]] = []
        for row in raw_rows:
            out_row: list[Any] = []
            for c_idx, val in enumerate(row):
                fmt = self.column_formats.get(c_idx, "General")
                if fmt == "Skip":
                    continue
                converted = convert_cell_value(val, fmt)
                out_row.append(converted)
            out.append(out_row)
        return out

    def populate_model(
        self, model: SheetDataModel, start_row: int = 0, start_col: int = 0
    ) -> None:
        """Populate SheetDataModel using the configured import settings."""
        raw_rows = self._parse_current_data()
        populate_sheet(
            model,
            raw_rows,
            start_row=start_row,
            start_col=start_col,
            col_formats=self.column_formats,
        )

    def retranslate_ui(self) -> None:
        """Retranslate all UI labels and captions."""
        self._update_navigation_state()
        self.type_group.setTitle(safe_tr("Original data type"))
        self.delimited_radio.setText(
            safe_tr(
                "Delimited - Characters such as commas or tabs separate each field."
            )
        )
        self.fixed_radio.setText(
            safe_tr(
                "Fixed width - Fields are aligned in columns with spaces between each field."
            )
        )
        self.start_row_label.setText(safe_tr("Start import at row:"))
        self.encoding_label.setText(safe_tr("File origin:"))
        self.raw_preview_group.setTitle(safe_tr("Preview of file:"))
        self.delim_group.setTitle(safe_tr("Delimiters"))
        self.tab_check.setText(safe_tr("Tab"))
        self.semicolon_check.setText(safe_tr("Semicolon"))
        self.comma_check.setText(safe_tr("Comma"))
        self.space_check.setText(safe_tr("Space"))
        self.other_check.setText(safe_tr("Other:"))
        self.merge_check.setText(
            safe_tr("Treat consecutive delimiters as one")
        )
        self.qualifier_label.setText(safe_tr("Text qualifier:"))
        self.fixed_group.setTitle(safe_tr("Fixed Width Column Breaks"))
        self.fixed_desc_label.setText(
            safe_tr(
                "Column break positions (comma-separated character indices):"
            )
        )
        self.step2_preview_group.setTitle(safe_tr("Data preview:"))
        self.format_group.setTitle(safe_tr("Column data format"))
        self.fmt_general_radio.setText(safe_tr("General"))
        self.fmt_text_radio.setText(safe_tr("Text"))
        self.fmt_date_radio.setText(safe_tr("Date:"))
        self.fmt_skip_radio.setText(
            safe_tr("Do not import column (skip)")
        )
        self.step3_preview_group.setTitle(safe_tr("Data preview:"))
        self.back_btn.setText(safe_tr("< Back"))
        self.next_btn.setText(safe_tr("Next >"))
        self.finish_btn.setText(safe_tr("Finish"))
        self.cancel_btn.setText(safe_tr("Cancel"))

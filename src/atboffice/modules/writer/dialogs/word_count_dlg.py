"""Word 2003 classic Word Count Dialog and statistics engine for Quire Writer."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    plain_text,
    reindex,
)

if TYPE_CHECKING:
    from atboffice.modules.writer.layout.pagination import PaginationResult


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("WordCountDialog", text)


# Regex pattern for CJK Ideographs and syllabaries
_CJK_PATTERN = re.compile(
    r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]"
)

# Regex pattern for Western alphanumeric words
_WORD_PATTERN = re.compile(r"[A-Za-z0-9]+(?:[-_'][A-Za-z0-9]+)*")


@dataclass
class WordCountStats:
    """Detailed layout and content metrics for Word Count."""

    pages: int = 1
    words: int = 0
    chars_no_spaces: int = 0
    chars_with_spaces: int = 0
    paragraphs: int = 0
    lines: int = 0


def count_text_statistics(text: str) -> WordCountStats:
    """Compute word and character statistics for a given text snippet."""
    if not text:
        return WordCountStats(
            pages=1,
            words=0,
            chars_no_spaces=0,
            chars_with_spaces=0,
            paragraphs=1,
            lines=1,
        )

    # 1. CJK and Western word counting
    cjk_count = len(_CJK_PATTERN.findall(text))
    non_cjk_text = _CJK_PATTERN.sub(" ", text)
    western_count = len(_WORD_PATTERN.findall(non_cjk_text))
    words = cjk_count + western_count

    # 2. Characters without spaces (excluding all whitespace and unicode spaces)
    chars_no_spaces = len(re.sub(r"[\s    ]", "", text))

    # 3. Characters with spaces (excluding newline/carriage return/tabs)
    chars_with_spaces = len(re.sub(r"[\r\n\t]", "", text))

    # 4. Paragraph count
    stripped_lines = [p for p in text.split("\n") if p.strip()]
    paragraphs = max(1, len(stripped_lines)) if text.strip() else 1

    # 5. Line count
    lines = max(paragraphs, len(text.splitlines()) if text else 1)

    return WordCountStats(
        pages=1,
        words=words,
        chars_no_spaces=chars_no_spaces,
        chars_with_spaces=chars_with_spaces,
        paragraphs=paragraphs,
        lines=lines,
    )


def calculate_document_statistics(
    doc: Document | None,
    include_notes: bool = False,
    pagination: PaginationResult | None = None,
) -> WordCountStats:
    """Calculate comprehensive statistics for a Document."""
    if doc is None:
        return WordCountStats()

    reindex(doc)
    paras: list[Paragraph] = list(doc.main.paras) if hasattr(doc.main, "paras") else []

    if include_notes:
        for fn_story in doc.fn.values():
            if hasattr(fn_story, "paras"):
                paras.extend(fn_story.paras)
        for en_story in doc.en.values():
            if hasattr(en_story, "paras"):
                paras.extend(en_story.paras)

    total_words = 0
    total_chars_no_spaces = 0
    total_chars_with_spaces = 0
    non_empty_paras = 0

    for p in paras:
        pt = plain_text(p)
        if pt.strip():
            non_empty_paras += 1
        st = count_text_statistics(pt)
        total_words += st.words
        total_chars_no_spaces += st.chars_no_spaces
        total_chars_with_spaces += st.chars_with_spaces

    # Paragraph count defaults to at least 1 in Word
    paragraphs = max(1, non_empty_paras)

    # Calculate page count from pagination layout if available
    pages = 1
    lines = 0
    if pagination is not None and getattr(pagination, "pages", None):
        pages = max(1, len(pagination.pages))
        for pg in pagination.pages:
            for region in getattr(pg, "regions", []):
                for col in getattr(region, "columns", []):
                    for frag in getattr(col, "fragments", []):
                        lines += len(getattr(frag, "lines", []))

    if lines == 0:
        lines = max(paragraphs, 1)

    return WordCountStats(
        pages=pages,
        words=total_words,
        chars_no_spaces=total_chars_no_spaces,
        chars_with_spaces=total_chars_with_spaces,
        paragraphs=paragraphs,
        lines=lines,
    )


class WordCountDialog(QDialog):
    """Word 2003 classic Word Count modal dialog with selection comparison."""

    def __init__(
        self,
        doc: Document | None = None,
        selection_text: str | None = None,
        pagination: PaginationResult | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.doc = doc
        self.selection_text = selection_text.strip() if selection_text else ""
        self.has_selection = bool(self.selection_text)
        self.pagination = pagination

        self.doc_stats = WordCountStats()
        self.selection_stats: WordCountStats | None = None

        self.setWindowTitle(safe_tr("字数统计"))
        self.setModal(True)
        self.resize(360, 320)
        self.setMinimumWidth(320)

        self._setup_ui()
        self.recalculate()
        self.retranslate_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # 1. Statistics header label
        self.label_caption = QLabel(self)
        self.label_caption.setStyleSheet("font-weight: bold; color: #222;")
        main_layout.addWidget(self.label_caption)

        # 2. Statistics table
        self.table = QTableWidget(self)
        self.table.setRowCount(6)
        cols = 3 if self.has_selection else 2
        self.table.setColumnCount(cols)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for c in range(1, cols):
            self.table.horizontalHeader().setSectionResizeMode(
                c, QHeaderView.ResizeMode.ResizeToContents
            )
        main_layout.addWidget(self.table)

        # 3. Checkbox: Include footnotes and endnotes
        self.check_include_notes = QCheckBox(self)
        self.check_include_notes.setChecked(False)
        self.check_include_notes.toggled.connect(self.recalculate)
        main_layout.addWidget(self.check_include_notes)

        # 4. Button Box with Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_close = QPushButton(self)
        self.btn_close.setDefault(True)
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)
        main_layout.addLayout(btn_layout)

    def recalculate(self) -> None:
        """Compute document and selection metrics, then refresh table."""
        include_notes = self.check_include_notes.isChecked()
        self.doc_stats = calculate_document_statistics(
            self.doc, include_notes=include_notes, pagination=self.pagination
        )

        if self.has_selection:
            self.selection_stats = count_text_statistics(self.selection_text)
        else:
            self.selection_stats = None

        self._refresh_table()

    def _refresh_table(self) -> None:
        """Populate table cells with latest statistics."""
        row_keys = [
            safe_tr("页数"),
            safe_tr("字数"),
            safe_tr("字符数(不计空格)"),
            safe_tr("字符数(计空格)"),
            safe_tr("段落数"),
            safe_tr("行数"),
        ]

        doc_values = [
            str(self.doc_stats.pages),
            f"{self.doc_stats.words:,}",
            f"{self.doc_stats.chars_no_spaces:,}",
            f"{self.doc_stats.chars_with_spaces:,}",
            f"{self.doc_stats.paragraphs:,}",
            f"{self.doc_stats.lines:,}",
        ]

        if self.has_selection and self.selection_stats is not None:
            sel_values = [
                str(self.selection_stats.pages),
                f"{self.selection_stats.words:,}",
                f"{self.selection_stats.chars_no_spaces:,}",
                f"{self.selection_stats.chars_with_spaces:,}",
                f"{self.selection_stats.paragraphs:,}",
                f"{self.selection_stats.lines:,}",
            ]
            for row in range(6):
                # Col 0: Item name
                it_name = QTableWidgetItem(row_keys[row])
                self.table.setItem(row, 0, it_name)

                # Col 1: Selection value
                it_sel = QTableWidgetItem(sel_values[row])
                it_sel.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self.table.setItem(row, 1, it_sel)

                # Col 2: Entire Document value
                it_doc = QTableWidgetItem(doc_values[row])
                it_doc.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self.table.setItem(row, 2, it_doc)
        else:
            for row in range(6):
                # Col 0: Item name
                it_name = QTableWidgetItem(row_keys[row])
                self.table.setItem(row, 0, it_name)

                # Col 1: Document value
                it_doc = QTableWidgetItem(doc_values[row])
                it_doc.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self.table.setItem(row, 1, it_doc)

    def retranslate_ui(self) -> None:
        """Update all text for localization."""
        self.setWindowTitle(safe_tr("字数统计"))
        if self.has_selection:
            self.label_caption.setText(safe_tr("统计信息 (包含选定内容与整篇文档对比):"))
            self.table.setHorizontalHeaderLabels(
                [safe_tr("统计项目"), safe_tr("选定内容"), safe_tr("整篇文档")]
            )
        else:
            self.label_caption.setText(safe_tr("统计信息:"))
            self.table.setHorizontalHeaderLabels([safe_tr("统计项目"), safe_tr("统计值")])

        self.check_include_notes.setText(safe_tr("包括文本框、脚注和尾注(&I)"))
        self.btn_close.setText(safe_tr("关闭(&C)"))
        self._refresh_table()

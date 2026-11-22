"""Excel 2003 style Spelling dialog for worksheet text cells."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.spreadsheet.calc.references import cell_name
from atboffice.modules.spreadsheet.tools.sheet_spelling import SheetSpellChecker, SpellIssue


def safe_tr(text: str) -> str:
    return QCoreApplication.translate("SheetSpellingDialog", text)


class SheetSpellingDialog(QDialog):
    """Walk misspellings: Ignore Once / Ignore All / Add / Change / Change All."""

    def __init__(self, checker: SheetSpellChecker, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.checker = checker
        self.issue: SpellIssue | None = None
        self.finished_clean = False

        self.resize(460, 320)
        layout = QGridLayout(self)
        self.lbl_word = QLabel(self)
        self.edit_word = QLineEdit(self)
        self.lbl_cell = QLabel(self)
        self.lbl_suggest = QLabel(self)
        self.list_suggest = QListWidget(self)
        self.list_suggest.currentTextChanged.connect(self._on_suggestion)
        self.list_suggest.itemDoubleClicked.connect(lambda _item: self._on_change())

        layout.addWidget(self.lbl_word, 0, 0)
        layout.addWidget(self.lbl_cell, 0, 1)
        layout.addWidget(self.edit_word, 1, 0, 1, 2)
        layout.addWidget(self.lbl_suggest, 2, 0, 1, 2)
        layout.addWidget(self.list_suggest, 3, 0, 1, 2)

        buttons = QVBoxLayout()
        self.btn_ignore = QPushButton(self)
        self.btn_ignore_all = QPushButton(self)
        self.btn_add = QPushButton(self)
        self.btn_change = QPushButton(self)
        self.btn_change_all = QPushButton(self)
        self.btn_close = QPushButton(self)
        self.btn_ignore.clicked.connect(self._on_ignore)
        self.btn_ignore_all.clicked.connect(self._on_ignore_all)
        self.btn_add.clicked.connect(self._on_add)
        self.btn_change.clicked.connect(self._on_change)
        self.btn_change_all.clicked.connect(self._on_change_all)
        self.btn_close.clicked.connect(self.accept)
        for btn in (
            self.btn_ignore,
            self.btn_ignore_all,
            self.btn_add,
            self.btn_change,
            self.btn_change_all,
        ):
            buttons.addWidget(btn)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_close)
        layout.addLayout(buttons, 0, 2, 4, 1)

        self.retranslate_ui()

    # ---------------------------------------------------------------- flow
    def start(self) -> bool:
        """Load the first issue. Returns False when the sheet has no misspellings."""
        return self._advance()

    def _advance(self) -> bool:
        self.issue = self.checker.next_issue()
        if self.issue is None:
            self.finished_clean = True
            return False
        issue = self.issue
        self.lbl_cell.setText(safe_tr("单元格 {0}").format(cell_name(issue.r, issue.c)))
        self.edit_word.setText(issue.word)
        self.list_suggest.clear()
        engine: Any = self.checker.engine
        suggestions = engine.suggest(issue.word) if hasattr(engine, "suggest") else []
        if suggestions:
            self.list_suggest.addItems(suggestions)
            self.list_suggest.setCurrentRow(0)
        else:
            self.list_suggest.addItem(safe_tr("(无建议)"))
            self.list_suggest.setEnabled(False)
            return True
        self.list_suggest.setEnabled(True)
        return True

    def _finish_or_next(self) -> None:
        if not self._advance():
            QMessageBox.information(
                self, safe_tr("拼写检查"), safe_tr("已完成对整个工作表的拼写检查。")
            )
            self.accept()

    def _on_suggestion(self, text: str) -> None:
        if text and self.list_suggest.isEnabled():
            self.edit_word.setText(text)

    def _replacement(self) -> str:
        return self.edit_word.text()

    def _on_ignore(self) -> None:
        if self.issue is not None:
            self.checker.ignore(self.issue)
        self._finish_or_next()

    def _on_ignore_all(self) -> None:
        if self.issue is not None:
            self.checker.ignore_everywhere(self.issue)
        self._finish_or_next()

    def _on_add(self) -> None:
        if self.issue is not None:
            self.checker.add_to_dictionary(self.issue)
        self._finish_or_next()

    def _on_change(self) -> None:
        if self.issue is not None:
            self.checker.change(self.issue, self._replacement())
        self._finish_or_next()

    def _on_change_all(self) -> None:
        if self.issue is not None:
            self.checker.change_everywhere(self.issue, self._replacement())
        self._finish_or_next()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("拼写检查"))
        self.lbl_word.setText(safe_tr("不在词典中(&N):"))
        self.lbl_suggest.setText(safe_tr("建议(&N):"))
        self.btn_ignore.setText(safe_tr("忽略一次(&I)"))
        self.btn_ignore_all.setText(safe_tr("全部忽略(&G)"))
        self.btn_add.setText(safe_tr("添加到词典(&A)"))
        self.btn_change.setText(safe_tr("更改(&C)"))
        self.btn_change_all.setText(safe_tr("全部更改(&L)"))
        self.btn_close.setText(safe_tr("关闭"))

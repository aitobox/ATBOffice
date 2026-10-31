"""Excel 2003 classic cell comment dialog."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("CommentDialog", text)


class CommentDialog(QDialog):
    """Dialog for creating and editing cell comments."""

    def __init__(
        self,
        existing_text: str = "",
        author: str = "Ledger User",
        cell_ref: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.cell_ref = cell_ref
        title = (
            safe_tr("编辑批注 - {cell}").format(cell=cell_ref)
            if cell_ref
            else safe_tr("编辑批注")
        )
        self.setWindowTitle(title)
        self.resize(360, 240)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        form = QFormLayout()
        self.lbl_author_title = QLabel(safe_tr("作者(&A):"), self)
        self.edit_author = QLineEdit(author, self)
        form.addRow(self.lbl_author_title, self.edit_author)

        layout.addLayout(form)

        self.lbl_comment_title = QLabel(safe_tr("批注正文(&T):"), self)
        layout.addWidget(self.lbl_comment_title)

        self.edit_text = QTextEdit(self)
        self.edit_text.setPlainText(existing_text)
        layout.addWidget(self.edit_text)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.edit_text.setFocus()
        if existing_text:
            cursor = self.edit_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.edit_text.setTextCursor(cursor)

    def get_text(self) -> str:
        """Return comment text content."""
        return self.edit_text.toPlainText().strip()

    def get_author(self) -> str:
        """Return comment author name."""
        return self.edit_author.text().strip()

    def retranslate_ui(self) -> None:
        """Retranslate dialog text dynamically."""
        title = (
            safe_tr("编辑批注 - {cell}").format(cell=self.cell_ref)
            if self.cell_ref
            else safe_tr("编辑批注")
        )
        self.setWindowTitle(title)
        self.lbl_author_title.setText(safe_tr("作者(&A):"))
        self.lbl_comment_title.setText(safe_tr("批注正文(&T):"))
        ok_btn = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(safe_tr("确定"))
        cancel_btn = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(safe_tr("取消"))

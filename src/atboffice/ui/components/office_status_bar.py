"""The status bar shared by Quire, Ledger and Lectern.

It keeps the Office 2003 layout: a message area that stretches on the left and
sunken fields on the right. Colors come from the active theme's style sheet
(``QStatusBar`` in :mod:`atboffice.ui.styles.luna_2003`), so the bar follows
theme changes like the rest of the window.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QStatusBar, QWidget

#: Raised field look of Office 2003: light edge on the left, shadow on the right.
_FIELD_STYLE = (
    "QLabel[statusField=\"true\"] { padding: 1px 6px; "
    "border-left: 1px solid rgba(255, 255, 255, 160); "
    "border-right: 1px solid rgba(0, 0, 0, 60); }"
)


class OfficeStatusBar(QStatusBar):
    """A message area plus named fields, in the order they are added."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizeGripEnabled(False)
        self.setStyleSheet(_FIELD_STYLE)
        self._fields: dict[str, QLabel] = {}
        self.lbl_message = QLabel(self)
        self.addWidget(self.lbl_message, 1)

    def add_field(
        self,
        key: str,
        text: str = "",
        *,
        min_width: int = 0,
        permanent: bool = False,
        align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft,
    ) -> QLabel:
        """Add a field; permanent fields sit at the right and survive messages."""
        label = QLabel(text, self)
        label.setProperty("statusField", True)
        label.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
        if min_width:
            label.setMinimumWidth(min_width)
        if permanent:
            self.addPermanentWidget(label, 0)
        else:
            self.addWidget(label, 0)
        self._fields[key] = label
        return label

    def field(self, key: str) -> QLabel | None:
        return self._fields.get(key)

    def set_field(self, key: str, text: str) -> None:
        label = self._fields.get(key)
        if label is not None and label.text() != text:
            label.setText(text)

    def set_message(self, message: str) -> None:
        """Set the lasting text of the message area (temporary messages use showMessage)."""
        self.lbl_message.setText(message)

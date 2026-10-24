"""Initial view for the spreadsheet module."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SpreadsheetView(QWidget):
    """Placeholder view for future spreadsheet editing features."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        label = QLabel("电子表格模块")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

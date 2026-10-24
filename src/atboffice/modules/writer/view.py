"""Initial view for the word-processing module."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class WriterView(QWidget):
    """Placeholder view for future document editing features."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        label = QLabel("文字处理模块")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

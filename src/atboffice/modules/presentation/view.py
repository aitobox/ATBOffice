"""Initial view for the presentation module."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PresentationView(QWidget):
    """Placeholder view for future presentation editing features."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        label = QLabel("演示文稿模块")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

"""Main application window and office module navigation."""

from PySide6.QtWidgets import QMainWindow, QTabWidget

from atboffice.modules.presentation.view import PresentationView
from atboffice.modules.spreadsheet.view import SpreadsheetView
from atboffice.modules.writer.view import WriterView


class MainWindow(QMainWindow):
    """Top-level window for the ATBOffice suite."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ATBOffice")
        self.resize(1100, 720)

        tabs = QTabWidget()
        tabs.addTab(WriterView(), "文字处理")
        tabs.addTab(SpreadsheetView(), "电子表格")
        tabs.addTab(PresentationView(), "演示文稿")
        self.setCentralWidget(tabs)

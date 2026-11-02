"""Reading Layout Toolbar for Quire word-processing (Word 2003 port)."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, Signal
from PySide6.QtWidgets import (
    QToolBar,
    QToolButton,
    QWidget,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely for ReadingLayoutToolbar."""
    return QCoreApplication.translate("ReadingLayoutToolbar", text)


class ReadingLayoutToolbar(QToolBar):
    """Specialized toolbar displayed in Reading Layout View mode."""

    toggle_doc_map_requested = Signal()
    toggle_thumbnails_requested = Signal()
    find_requested = Signal()
    research_requested = Signal()
    grow_font_requested = Signal()
    shrink_font_requested = Signal()
    single_page_requested = Signal()
    multi_page_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("tb_reading_layout")
        self.setWindowTitle(safe_tr("阅读版式工具栏"))
        self.setMovable(False)

        # Document Map toggle
        self._btn_doc_map = QToolButton(self)
        self._btn_doc_map.setText(safe_tr("文档结构图"))
        self._btn_doc_map.setCheckable(True)
        self._btn_doc_map.clicked.connect(self.toggle_doc_map_requested.emit)
        self.addWidget(self._btn_doc_map)

        # Thumbnails toggle
        self._btn_thumbnails = QToolButton(self)
        self._btn_thumbnails.setText(safe_tr("缩略图"))
        self._btn_thumbnails.setCheckable(True)
        self._btn_thumbnails.clicked.connect(self.toggle_thumbnails_requested.emit)
        self.addWidget(self._btn_thumbnails)

        # Find
        self._btn_find = QToolButton(self)
        self._btn_find.setText(safe_tr("查找"))
        self._btn_find.clicked.connect(self.find_requested.emit)
        self.addWidget(self._btn_find)

        # Research
        self._btn_research = QToolButton(self)
        self._btn_research.setText(safe_tr("信息检索"))
        self._btn_research.clicked.connect(self.research_requested.emit)
        self.addWidget(self._btn_research)

        self.addSeparator()

        # Text size controls
        self._btn_grow = QToolButton(self)
        self._btn_grow.setText(safe_tr("放大文字 (A+)"))
        self._btn_grow.setToolTip(safe_tr("增加文字大小"))
        self._btn_grow.clicked.connect(self.grow_font_requested.emit)
        self.addWidget(self._btn_grow)

        self._btn_shrink = QToolButton(self)
        self._btn_shrink.setText(safe_tr("缩小文字 (A-)"))
        self._btn_shrink.setToolTip(safe_tr("减小文字大小"))
        self._btn_shrink.clicked.connect(self.shrink_font_requested.emit)
        self.addWidget(self._btn_shrink)

        # Single / Multi page
        self._btn_one_page = QToolButton(self)
        self._btn_one_page.setText(safe_tr("单页"))
        self._btn_one_page.setToolTip(safe_tr("单页舒适阅读"))
        self._btn_one_page.clicked.connect(self.single_page_requested.emit)
        self.addWidget(self._btn_one_page)

        self._btn_multi_page = QToolButton(self)
        self._btn_multi_page.setText(safe_tr("双页并排"))
        self._btn_multi_page.setToolTip(safe_tr("允许并排显示多页"))
        self._btn_multi_page.clicked.connect(self.multi_page_requested.emit)
        self.addWidget(self._btn_multi_page)

        self.addSeparator()

        # Close Reading Layout
        self._btn_close = QToolButton(self)
        self._btn_close.setText(safe_tr("关闭"))
        self._btn_close.setToolTip(safe_tr("关闭阅读版式，返回先前的视图"))
        self._btn_close.clicked.connect(self.close_requested.emit)
        self.addWidget(self._btn_close)

        self.retranslate_ui()

    def set_doc_map_active(self, active: bool) -> None:
        self._btn_doc_map.setChecked(active)

    def set_thumbnails_active(self, active: bool) -> None:
        self._btn_thumbnails.setChecked(active)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("阅读版式工具栏"))
        self._btn_doc_map.setText(safe_tr("文档结构图"))
        self._btn_doc_map.setToolTip(safe_tr("切换文档结构图导航"))
        self._btn_thumbnails.setText(safe_tr("缩略图"))
        self._btn_thumbnails.setToolTip(safe_tr("切换页面缩略图导航"))
        self._btn_find.setText(safe_tr("查找"))
        self._btn_find.setToolTip(safe_tr("查找文本"))
        self._btn_research.setText(safe_tr("信息检索"))
        self._btn_research.setToolTip(safe_tr("打开信息检索任务窗格"))
        self._btn_grow.setText(safe_tr("放大文字 (A+)"))
        self._btn_grow.setToolTip(safe_tr("增加文字大小"))
        self._btn_shrink.setText(safe_tr("缩小文字 (A-)"))
        self._btn_shrink.setToolTip(safe_tr("减小文字大小"))
        self._btn_one_page.setText(safe_tr("单页"))
        self._btn_one_page.setToolTip(safe_tr("单页舒适阅读"))
        self._btn_multi_page.setText(safe_tr("双页并排"))
        self._btn_multi_page.setToolTip(safe_tr("允许并排显示多页"))
        self._btn_close.setText(safe_tr("关闭"))
        self._btn_close.setToolTip(safe_tr("关闭阅读版式，返回先前的视图"))

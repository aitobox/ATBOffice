"""Office 2003 style in-window Print Preview (replaces the modal QPrintPreviewDialog)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewWidget
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.core.i18n import safe_tr

ZOOM_CHOICES: list[tuple[str, float | str]] = [
    ("整页", "fit"),
    ("页宽", "width"),
    ("500%", 5.0),
    ("200%", 2.0),
    ("150%", 1.5),
    ("100%", 1.0),
    ("75%", 0.75),
    ("50%", 0.5),
    ("25%", 0.25),
    ("10%", 0.1),
]


class PrintPreviewPanel(QWidget):
    """Preview overlay covering a window's central area.

    ``render`` paints every page onto the given printer (the same callable used for Print
    and PDF export), so preview, print and PDF never diverge.
    """

    closed = Signal()
    print_requested = Signal()
    page_setup_requested = Signal()

    def __init__(
        self,
        printer: QPrinter,
        render: Callable[[QPrinter], None],
        parent: QWidget,
        host: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PrintPreviewPanel")
        self.setAutoFillBackground(True)
        self.printer = printer
        self._render = render
        self._host = host
        self._magnified = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar = QWidget(self)
        bar.setObjectName("PrintPreviewToolbar")
        self.bar_layout = QHBoxLayout(bar)
        self.bar_layout.setContentsMargins(4, 2, 4, 2)
        self.bar_layout.setSpacing(4)

        self.btn_print = self._button(self._on_print)
        self.btn_magnifier = self._button(self.toggle_magnifier, checkable=True)
        self.btn_one_page = self._button(lambda: self.set_view("single"))
        self.btn_multi_page = self._button(lambda: self.set_view("facing"))
        self.btn_all_pages = self._button(lambda: self.set_view("all"))
        self.combo_zoom = QComboBox(bar)
        self.combo_zoom.setEditable(False)
        for _label, value in ZOOM_CHOICES:
            self.combo_zoom.addItem("", value)
        self.combo_zoom.activated.connect(self._on_zoom_chosen)
        self.btn_setup = self._button(self.page_setup_requested.emit)
        self.lbl_page = QLabel(bar)
        self.extra_layout = QHBoxLayout()
        self.extra_layout.setSpacing(4)
        self.btn_close = self._button(self.close_preview)

        for w in (self.btn_print, self.btn_magnifier, self.btn_one_page, self.btn_multi_page,
                  self.btn_all_pages, self.combo_zoom, self.btn_setup):
            self.bar_layout.addWidget(w)
        self.bar_layout.addLayout(self.extra_layout)
        self.bar_layout.addStretch(1)
        self.bar_layout.addWidget(self.lbl_page)
        self.bar_layout.addWidget(self.btn_close)
        layout.addWidget(bar)

        self.preview = QPrintPreviewWidget(printer, self)
        self.preview.paintRequested.connect(self._paint)
        self.preview.previewChanged.connect(self._update_page_label)
        layout.addWidget(self.preview, 1)

        self.retranslate_ui()
        if host is not None:
            host.installEventFilter(self)
            self._follow_host()

    # ------------------------------------------------------------------ ui helpers
    def _button(self, slot: Callable[[], object], checkable: bool = False) -> QToolButton:
        btn = QToolButton(self)
        btn.setCheckable(checkable)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        btn.clicked.connect(lambda _checked=False: slot())
        return btn

    def add_extra_widget(self, widget: QWidget) -> None:
        """Module-specific controls (Lectern Print What / Color, Ledger Margins, …)."""
        widget.setParent(self)
        self.extra_layout.addWidget(widget)

    # ------------------------------------------------------------------ behaviour
    def _paint(self, printer: QPrinter) -> None:
        self._render(printer)

    def refresh(self) -> None:
        """Re-render pages (after options or page setup changed)."""
        self.preview.updatePreview()

    def page_count(self) -> int:
        return self.preview.pageCount()

    def _update_page_label(self) -> None:
        count = self.preview.pageCount()
        current = self.preview.currentPage() if count else 0
        self.lbl_page.setText(safe_tr("第 {0} 页，共 {1} 页").format(current, count))

    def set_view(self, mode: str) -> None:
        if mode == "single":
            self.preview.setViewMode(QPrintPreviewWidget.ViewMode.SinglePageView)
        elif mode == "facing":
            self.preview.setViewMode(QPrintPreviewWidget.ViewMode.FacingPagesView)
        else:
            self.preview.setViewMode(QPrintPreviewWidget.ViewMode.AllPagesView)
        self.preview.fitInView()
        self._magnified = False
        self.btn_magnifier.setChecked(False)

    def toggle_magnifier(self) -> None:
        """Magnifier: switch between the whole page and 100 % (Office 2003 behaviour)."""
        self._magnified = not self._magnified
        if self._magnified:
            self.preview.setZoomMode(QPrintPreviewWidget.ZoomMode.CustomZoom)
            self.preview.setZoomFactor(1.0)
        else:
            self.preview.fitInView()
        self.btn_magnifier.setChecked(self._magnified)

    def _on_zoom_chosen(self, index: int) -> None:
        value = self.combo_zoom.itemData(index)
        if value == "fit":
            self.preview.fitInView()
        elif value == "width":
            self.preview.fitToWidth()
        else:
            self.preview.setZoomMode(QPrintPreviewWidget.ZoomMode.CustomZoom)
            self.preview.setZoomFactor(float(value))

    def _on_print(self) -> None:
        self.print_requested.emit()

    def close_preview(self) -> None:
        if self._host is not None:
            self._host.removeEventFilter(self)
        self.hide()
        self.closed.emit()
        self.deleteLater()

    # ------------------------------------------------------------------ geometry / keys
    def _follow_host(self) -> None:
        if self._host is not None:
            self.setGeometry(self._host.geometry())
            self.raise_()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if obj is self._host and event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            self._follow_host()
        return False

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close_preview()
            return
        if key in (Qt.Key.Key_PageDown, Qt.Key.Key_Down):
            self.preview.setCurrentPage(min(self.page_count(), self.preview.currentPage() + 1))
            return
        if key in (Qt.Key.Key_PageUp, Qt.Key.Key_Up):
            self.preview.setCurrentPage(max(1, self.preview.currentPage() - 1))
            return
        super().keyPressEvent(event)

    def retranslate_ui(self) -> None:
        self.btn_print.setText(safe_tr("打印(&P)..."))
        self.btn_print.setToolTip(safe_tr("打印文档"))
        self.btn_magnifier.setText(safe_tr("放大镜"))
        self.btn_magnifier.setToolTip(safe_tr("在整页和 100% 之间切换"))
        self.btn_one_page.setText(safe_tr("单页"))
        self.btn_one_page.setToolTip(safe_tr("一次显示一页"))
        self.btn_multi_page.setText(safe_tr("双页"))
        self.btn_multi_page.setToolTip(safe_tr("并排显示两页"))
        self.btn_all_pages.setText(safe_tr("多页"))
        self.btn_all_pages.setToolTip(safe_tr("显示所有页面"))
        for row, (label, _value) in enumerate(ZOOM_CHOICES):
            self.combo_zoom.setItemText(row, safe_tr(label))
        self.combo_zoom.setToolTip(safe_tr("显示比例"))
        self.btn_setup.setText(safe_tr("页面设置(&U)..."))
        self.btn_setup.setToolTip(safe_tr("更改页面大小、方向、边距和页眉页脚"))
        self.btn_close.setText(safe_tr("关闭(&C)"))
        self.btn_close.setToolTip(safe_tr("关闭打印预览"))
        self._update_page_label()

"""Notes Page View (备注页视图) for Lectern presentations.

Provides:
- Authentic PowerPoint 2003 A4 portrait layout with paper drop-shadow.
- Upper region: High-definition slide preview thumbnail with border.
- Lower region: Editable speaker notes editor for speech scripts.
- Navigation bar: Previous / Next slide buttons, slide indicator, and zoom controls.
- Real-time synchronization with Slide model and SpeakerNotesPane in Normal view.
- 100% i18n support with safe_tr and retranslate_ui.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.views.workspace import render_slide_thumbnail


def safe_tr(text: str) -> str:
    """Safe translation for Notes Page UI."""
    app = QApplication.instance()
    if app:
        translated = app.translate("NotesPage", text)
        if translated and translated != text:
            return translated
    return text


class NotesPagePaper(QFrame):
    """A4 portrait paper representation inside the Notes Page View."""

    notes_edited = Signal(int, str)

    def __init__(
        self,
        presentation: Presentation | None = None,
        slide_index: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.presentation = presentation or Presentation()
        self.slide_index = slide_index
        self._scale: float = 1.0

        # Base A4 paper dimensions at 100% scale (approx 595 x 842 pt)
        self.base_width = 560
        self.base_height = 792

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setObjectName("NotesPagePaper")
        self.setStyleSheet(
            """
            #NotesPagePaper {
                background-color: #FFFFFF;
                border: 1px solid #ACACAC;
            }
            """
        )

        self._init_ui()

    def _init_ui(self) -> None:
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(36, 36, 36, 36)
        self.main_layout.setSpacing(16)

        # 1. Header Row (Header label & Date)
        self.header_row = QWidget(self)
        h_layout = QHBoxLayout(self.header_row)
        h_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_header = QLabel(safe_tr("页眉"), self.header_row)
        self.lbl_header.setFont(QFont("Arial", 8))
        self.lbl_header.setStyleSheet("color: #888888;")
        h_layout.addWidget(self.lbl_header)
        h_layout.addStretch()
        self.lbl_date = QLabel("", self.header_row)
        self.lbl_date.setFont(QFont("Arial", 8))
        self.lbl_date.setStyleSheet("color: #888888;")
        h_layout.addWidget(self.lbl_date)
        self.main_layout.addWidget(self.header_row)

        # 2. Upper Region: Slide Thumbnail Preview with Frame
        self.slide_box = QFrame(self)
        self.slide_box.setFrameShape(QFrame.Shape.Box)
        self.slide_box.setStyleSheet("border: 1px solid #707070; background-color: #000000;")
        box_layout = QVBoxLayout(self.slide_box)
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setSpacing(0)

        self.thumb_label = QLabel(self.slide_box)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        box_layout.addWidget(self.thumb_label)
        self.main_layout.addWidget(self.slide_box, alignment=Qt.AlignmentFlag.AlignCenter)

        # 3. Lower Region: Speaker Notes Box
        self.notes_container = QWidget(self)
        n_layout = QVBoxLayout(self.notes_container)
        n_layout.setContentsMargins(0, 8, 0, 0)
        n_layout.setSpacing(4)

        self.lbl_notes_title = QLabel(safe_tr("单击此处添加备注"), self.notes_container)
        self.lbl_notes_title.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.lbl_notes_title.setStyleSheet("color: #555555;")
        n_layout.addWidget(self.lbl_notes_title)

        self.notes_edit = QTextEdit(self.notes_container)
        self.notes_edit.setPlaceholderText(safe_tr("在此处输入演讲者的详细演讲备注与旁白..."))
        self.notes_edit.setFont(QFont("Arial", 10))
        self.notes_edit.setStyleSheet(
            """
            QTextEdit {
                border: 1px dashed #A0A0A0;
                background-color: #FAFAFA;
                padding: 8px;
                color: #222222;
            }
            QTextEdit:focus {
                border: 1px solid #2B579A;
                background-color: #FFFFFF;
            }
            """
        )
        self.notes_edit.textChanged.connect(self._on_notes_changed)
        n_layout.addWidget(self.notes_edit)
        self.main_layout.addWidget(self.notes_container, stretch=1)

        # 4. Footer Row (Footer label & Slide Number)
        self.footer_row = QWidget(self)
        f_layout = QHBoxLayout(self.footer_row)
        f_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_footer = QLabel(safe_tr("页脚"), self.footer_row)
        self.lbl_footer.setFont(QFont("Arial", 8))
        self.lbl_footer.setStyleSheet("color: #888888;")
        f_layout.addWidget(self.lbl_footer)
        f_layout.addStretch()
        self.lbl_slide_num = QLabel("1", self.footer_row)
        self.lbl_slide_num.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        self.lbl_slide_num.setStyleSheet("color: #444444;")
        f_layout.addWidget(self.lbl_slide_num)
        self.main_layout.addWidget(self.footer_row)

        self.apply_scale(1.0)

    def apply_scale(self, scale: float) -> None:
        """Scale paper widget size and thumbnail."""
        self._scale = max(0.4, min(2.0, scale))
        w = int(self.base_width * self._scale)
        h = int(self.base_height * self._scale)
        self.setFixedSize(w, h)
        self.refresh()

    def load_slide(self, slide: Slide | None, index: int, presentation: Presentation) -> None:
        """Bind slide data into paper view."""
        self.presentation = presentation
        self.slide_index = index

        first_num = getattr(self.presentation, "first_num", 1)
        self.lbl_slide_num.setText(str(index + first_num))

        if slide is None:
            self.thumb_label.clear()
            self.thumb_label.setText(safe_tr("无幻灯片"))
            self.notes_edit.blockSignals(True)
            self.notes_edit.setPlainText("")
            self.notes_edit.setEnabled(False)
            self.notes_edit.blockSignals(False)
            return

        self.notes_edit.setEnabled(True)
        # Load notes text without triggering change signal
        current_notes = getattr(slide, "notes", "") or ""
        self.notes_edit.blockSignals(True)
        self.notes_edit.setPlainText(current_notes)
        self.notes_edit.blockSignals(False)

        # Render slide thumbnail scaled to paper upper region
        thumb_w = max(180, int((self.base_width - 80) * self._scale))
        pixmap = render_slide_thumbnail(slide, presentation, width=thumb_w)
        self.thumb_label.setPixmap(pixmap)
        self.thumb_label.setFixedSize(pixmap.size())

    def refresh(self) -> None:
        """Re-render current slide."""
        slides = getattr(self.presentation, "slides", [])
        if 0 <= self.slide_index < len(slides):
            self.load_slide(slides[self.slide_index], self.slide_index, self.presentation)
        else:
            self.load_slide(None, 0, self.presentation)

    def get_notes_text(self) -> str:
        return self.notes_edit.toPlainText()

    def set_notes_text(self, text: str) -> None:
        self.notes_edit.blockSignals(True)
        self.notes_edit.setPlainText(text)
        self.notes_edit.blockSignals(False)

    def _on_notes_changed(self) -> None:
        text = self.notes_edit.toPlainText()
        slides = getattr(self.presentation, "slides", [])
        if 0 <= self.slide_index < len(slides):
            slides[self.slide_index].notes = text
        self.notes_edited.emit(self.slide_index, text)

    def retranslate_ui(self) -> None:
        self.lbl_header.setText(safe_tr("页眉"))
        self.lbl_notes_title.setText(safe_tr("单击此处添加备注"))
        self.notes_edit.setPlaceholderText(safe_tr("在此处输入演讲者的详细演讲备注与旁白..."))
        self.lbl_footer.setText(safe_tr("页脚"))


class NotesPageView(QScrollArea):
    """Interactive Notes Page View embedding scrollable A4 canvas."""

    notes_changed = Signal(int, str)
    slide_navigated = Signal(int)

    def __init__(
        self,
        presentation: Presentation | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.presentation = presentation or Presentation()
        self._current_slide_index: int = 0
        self._zoom: float = 1.0

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("QScrollArea { background-color: #6A6A6A; }")

        # Container widget holding nav bar and centered paper
        self.container = QWidget(self)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(16, 12, 16, 16)
        self.container_layout.setSpacing(12)

        # 1. Navigation & Zoom Tool Bar
        self.nav_bar = QWidget(self.container)
        self.nav_bar.setStyleSheet(
            """
            QWidget {
                background-color: #EFEFEF;
                border: 1px solid #B0B0B0;
                border-radius: 4px;
            }
            QPushButton, QToolButton {
                padding: 4px 10px;
                background-color: #FFFFFF;
                border: 1px solid #ABABAB;
                border-radius: 2px;
                color: #222222;
            }
            QPushButton:hover, QToolButton:hover {
                background-color: #E2ECF6;
                border: 1px solid #2B579A;
            }
            QPushButton:disabled {
                color: #999999;
                background-color: #F5F5F5;
            }
            """
        )
        nav_layout = QHBoxLayout(self.nav_bar)
        nav_layout.setContentsMargins(8, 4, 8, 4)
        nav_layout.setSpacing(8)

        self.btn_prev = QPushButton("◄ " + safe_tr("上一页"), self.nav_bar)
        self.btn_prev.clicked.connect(self.prev_slide)
        nav_layout.addWidget(self.btn_prev)

        self.lbl_indicator = QLabel(self.nav_bar)
        self.lbl_indicator.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.lbl_indicator.setStyleSheet("color: #333333; padding: 0 6px;")
        nav_layout.addWidget(self.lbl_indicator)

        self.btn_next = QPushButton(safe_tr("下一页") + " ►", self.nav_bar)
        self.btn_next.clicked.connect(self.next_slide)
        nav_layout.addWidget(self.btn_next)

        nav_layout.addStretch()

        # Zoom buttons
        self.btn_zoom_out = QToolButton(self.nav_bar)
        self.btn_zoom_out.setText("-")
        self.btn_zoom_out.setToolTip(safe_tr("缩小"))
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        nav_layout.addWidget(self.btn_zoom_out)

        self.lbl_zoom = QLabel("100%", self.nav_bar)
        self.lbl_zoom.setFont(QFont("Arial", 9))
        self.lbl_zoom.setStyleSheet("color: #444444;")
        nav_layout.addWidget(self.lbl_zoom)

        self.btn_zoom_in = QToolButton(self.nav_bar)
        self.btn_zoom_in.setText("+")
        self.btn_zoom_in.setToolTip(safe_tr("放大"))
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        nav_layout.addWidget(self.btn_zoom_in)

        self.container_layout.addWidget(self.nav_bar)

        # 2. Centered Paper Widget
        self.paper_center_wrapper = QWidget(self.container)
        paper_layout = QHBoxLayout(self.paper_center_wrapper)
        paper_layout.setContentsMargins(0, 0, 0, 0)
        paper_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.paper = NotesPagePaper(
            presentation=self.presentation,
            slide_index=self._current_slide_index,
            parent=self.paper_center_wrapper,
        )
        self.paper.notes_edited.connect(self._on_paper_notes_edited)
        paper_layout.addWidget(self.paper)

        self.container_layout.addWidget(self.paper_center_wrapper, stretch=1)
        self.setWidget(self.container)

        self.load_presentation(self.presentation)

    @property
    def current_slide_index(self) -> int:
        return self._current_slide_index

    def load_presentation(self, presentation: Presentation) -> None:
        """Bind presentation and load initial slide."""
        self.presentation = presentation
        slides = getattr(presentation, "slides", [])
        if self._current_slide_index >= len(slides):
            self._current_slide_index = max(0, len(slides) - 1)
        self.set_current_slide_index(self._current_slide_index)

    def set_current_slide_index(self, index: int) -> None:
        """Display notes page for specified slide index."""
        slides = getattr(self.presentation, "slides", [])
        total = len(slides)
        if total == 0:
            self._current_slide_index = 0
            self.lbl_indicator.setText(safe_tr("无幻灯片"))
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
            self.paper.load_slide(None, 0, self.presentation)
            return

        self._current_slide_index = max(0, min(total - 1, index))
        curr = self._current_slide_index
        first_num = getattr(self.presentation, "first_num", 1)
        self.lbl_indicator.setText(
            f"{safe_tr('幻灯片')} {curr + first_num} / {total}"
        )
        self.btn_prev.setEnabled(curr > 0)
        self.btn_next.setEnabled(curr < total - 1)

        self.paper.load_slide(slides[curr], curr, self.presentation)
        self.slide_navigated.emit(curr)

    def next_slide(self) -> None:
        slides = getattr(self.presentation, "slides", [])
        if self._current_slide_index < len(slides) - 1:
            self.set_current_slide_index(self._current_slide_index + 1)

    def prev_slide(self) -> None:
        if self._current_slide_index > 0:
            self.set_current_slide_index(self._current_slide_index - 1)

    def set_zoom(self, zoom: float) -> None:
        """Set zoom scale factor (0.5 - 1.5)."""
        clamped = max(0.5, min(1.5, zoom))
        self._zoom = clamped
        self.lbl_zoom.setText(f"{int(round(self._zoom * 100))}%")
        self.paper.apply_scale(self._zoom)

    def zoom_in(self) -> None:
        self.set_zoom(self._zoom + 0.1)

    def zoom_out(self) -> None:
        self.set_zoom(self._zoom - 0.1)

    def _on_paper_notes_edited(self, index: int, text: str) -> None:
        self.notes_changed.emit(index, text)

    def retranslate_ui(self) -> None:
        """Retranslate all Notes Page UI controls."""
        self.btn_prev.setText("◄ " + safe_tr("上一页"))
        self.btn_next.setText(safe_tr("下一页") + " ►")
        self.btn_zoom_out.setToolTip(safe_tr("缩小"))
        self.btn_zoom_in.setToolTip(safe_tr("放大"))
        slides = getattr(self.presentation, "slides", [])
        total = len(slides)
        if total == 0:
            self.lbl_indicator.setText(safe_tr("无幻灯片"))
        else:
            first_num = getattr(self.presentation, "first_num", 1)
            self.lbl_indicator.setText(
                f"{safe_tr('幻灯片')} {self._current_slide_index + first_num} / {total}"
            )
        self.paper.retranslate_ui()

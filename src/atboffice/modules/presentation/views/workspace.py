"""Classic PowerPoint 2003 Three-Pane Workspace for Lectern.

Provides:
- Left Pane (QTabWidget): Slides thumbnail bar with drag reorder + Outline hierarchy editor
- Center Area (Vertical QSplitter): Main slide design canvas + Speaker Notes pane
- Right Task Pane (LecternTaskPane): Slide Layout gallery (21 layouts) + Slide Design gallery
- Complete double-way binding, live synchronization, and i18n support.
"""

from __future__ import annotations

import copy
from typing import Any

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.presentation.models.designs import (
    DESIGNS,
    DesignTemplate,
    build_design,
)
from atboffice.modules.presentation.models.layouts import (
    LAYOUTS,
    LayoutInfo,
    layout_frames,
    make_placeholder,
)
from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.models.text import Paragraph, TextBody, TextRun
from atboffice.modules.presentation.views.slide_canvas import (
    SlideCanvasView,
    SlideScene,
)


def safe_tr(text: str) -> str:
    """Translate UI text with fallbacks."""
    app = QApplication.instance()
    if app:
        translated = app.translate("LecternWorkspace", text)
        if translated and translated != text:
            return translated
    # Default to Chinese native text for ATBOffice
    return text


def render_slide_thumbnail(
    slide: Slide,
    presentation: Presentation,
    width: int = 160,
) -> QPixmap:
    """Render a high-fidelity thumbnail preview of a slide onto a QPixmap."""
    w = max(100.0, presentation.w)
    h = max(100.0, presentation.h)
    height = max(60, int(width * h / w))

    pixmap = QPixmap(width, height)
    pixmap.fill(QColor("#FFFFFF"))

    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        sx = float(width) / w
        sy = float(height) / h

        # 1. Background fill from design
        design = presentation.get_design_for_slide(slide)
        bg_color = QColor(design.colors.lt1 if design else "#FFFFFF")
        painter.fillRect(0, 0, width, height, bg_color)

        # 2. Draw slide shapes
        for sh in slide.shapes:
            if sh.w <= 0 or sh.h <= 0:
                continue
            rect = QRectF(sh.x * sx, sh.y * sy, sh.w * sx, sh.h * sy)

            # Fill
            if sh.fill and sh.fill.type == "solid":
                painter.fillRect(rect, QColor(sh.fill.color))
            elif sh.placeholder and sh.placeholder.type in ("title", "ctrTitle"):
                # Subtle hint for empty placeholders
                painter.setPen(QPen(QColor("#CCCCCC"), 0.5, Qt.DashLine))
                painter.drawRect(rect)
            elif sh.placeholder:
                painter.setPen(QPen(QColor("#E0E0E0"), 0.5, Qt.DashLine))
                painter.drawRect(rect)

            # Border
            if sh.line and sh.line.width > 0:
                painter.setPen(QPen(QColor(sh.line.color), max(1.0, sh.line.width * sx)))
                painter.drawRect(rect)

            # Text snippet
            if sh.text and not sh.text.is_empty():
                txt = sh.text.plain_text
                painter.setPen(QColor(design.colors.dk1 if design else "#000000"))
                font = QFont("Arial", max(6, int(10 * sy)))
                if sh.placeholder and sh.placeholder.type in ("title", "ctrTitle"):
                    font.setBold(True)
                painter.setFont(font)
                painter.drawText(
                    rect.adjusted(2, 2, -2, -2),
                    Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
                    txt,
                )

        # 3. Outer boundary outline
        painter.setPen(QPen(QColor("#C0C0C0"), 1.0))
        painter.drawRect(0, 0, width - 1, height - 1)
    finally:
        painter.end()

    return pixmap


def build_master_slide(
    presentation: Presentation,
    design: DesignTemplate,
    master_kind: str = "slide",
) -> Slide:
    """Build a synthetic master slide for editing in master view."""
    title_kind = master_kind == "title"
    deco = (
        list(design.title_decorations)
        if (title_kind and design.title_decorations is not None)
        else list(design.decorations)
    )
    ph = design.placeholder_frames

    def mk_ph(
        ptype: str,
        r: tuple[float, float, float, float] | list[float],
        text_paras: list[str],
    ) -> Shape:
        fr = {"type": ptype, "x": r[0], "y": r[1], "w": r[2], "h": r[3]}
        s = make_placeholder(fr, design)
        s.id = f"mph-{ptype}"
        paras = [
            Paragraph(level=i if ptype == "body" else 0, runs=[TextRun(text=t)])
            for i, t in enumerate(text_paras)
        ]
        s.text = TextBody(
            anchor="ctr" if ptype in ("title", "ctrTitle") else "t",
            paragraphs=paras,
            wrap=True,
            autofit="none",
        )
        return s

    shapes: list[Shape] = [copy.deepcopy(sh) for sh in deco]

    if title_kind:
        ctr_r = ph.get("ctrTitle", (120.0, 150.0, 720.0, 100.0))
        sub_r = ph.get("subTitle", (120.0, 270.0, 720.0, 120.0))
        shapes.append(mk_ph("ctrTitle", ctr_r, [safe_tr("单击此处编辑母版标题样式")]))
        shapes.append(mk_ph("subTitle", sub_r, [safe_tr("单击此处编辑母版副标题样式")]))
    else:
        title_r = ph.get("title", (48.0, 36.0, 864.0, 72.0))
        body_r = ph.get("body", (48.0, 120.0, 864.0, 360.0))
        shapes.append(mk_ph("title", title_r, [safe_tr("单击此处编辑母版标题样式")]))
        body_levels = [
            safe_tr("单击此处编辑母版文本样式"),
            safe_tr("第二级"),
            safe_tr("第三级"),
            safe_tr("第四级"),
            safe_tr("第五级"),
        ]
        shapes.append(mk_ph("body", body_r, body_levels))

    # Footers
    if "dt" in ph:
        shapes.append(mk_ph("dt", ph["dt"], ["<日期/时间>"]))
    if "ftr" in ph:
        shapes.append(mk_ph("ftr", ph["ftr"], ["<页脚>"]))
    if "sldNum" in ph:
        shapes.append(mk_ph("sldNum", ph["sldNum"], ["<#>"]))

    ms = Slide(
        id=f"master_{master_kind}",
        layout="title" if title_kind else "text",
        design_id=design.id,
        shapes=shapes,
    )
    setattr(ms, "is_master", True)
    setattr(ms, "master_kind", master_kind)
    setattr(ms, "master_bg", design.title_bg if (title_kind and design.title_bg) else design.bg)
    return ms


def sync_master_slide(presentation: Presentation, master_slide: Slide) -> None:
    """Fold master view edits back into the design template."""
    design_id = master_slide.design_id
    design = presentation.designs.get(design_id) or presentation.get_design_for_slide(None)
    if not design:
        return

    master_kind = getattr(master_slide, "master_kind", "slide")
    title_kind = master_kind == "title"

    # Separate decorations from placeholder shapes
    decos = [copy.deepcopy(s) for s in master_slide.shapes if not str(s.id).startswith("mph-")]
    if title_kind:
        design.title_decorations = decos
    else:
        design.decorations = decos

    # Update placeholder positions
    for s in master_slide.shapes:
        if not str(s.id).startswith("mph-"):
            continue
        ptype = s.placeholder.type if s.placeholder else str(s.id).replace("mph-", "")
        design.placeholder_frames[ptype] = (
            round(s.x, 2),
            round(s.y, 2),
            round(s.w, 2),
            round(s.h, 2),
        )

    # Update background
    if hasattr(master_slide, "master_bg") and master_slide.master_bg:
        if title_kind:
            design.title_bg = master_slide.master_bg
        else:
            design.bg = master_slide.master_bg


class MasterViewCloseBar(QFrame):
    """Notification and toolbar banner for closing Slide Master View."""

    close_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            """
            MasterViewCloseBar {
                background-color: #FFF2CC;
                border-bottom: 2px solid #D6B656;
                padding: 4px 8px;
            }
            """
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(12)

        self.title_label = QLabel(safe_tr("幻灯片母版视图 — 在此定制全局母版排版与样式"), self)
        self.title_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #7F6000;")
        layout.addWidget(self.title_label)

        layout.addStretch()

        self.btn_close = QToolButton(self)
        self.btn_close.setText(safe_tr("关闭母版视图"))
        self.btn_close.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.btn_close.setStyleSheet(
            """
            QToolButton {
                background-color: #2B579A;
                color: #FFFFFF;
                border: 1px solid #1E3D6B;
                border-radius: 3px;
                padding: 4px 14px;
            }
            QToolButton:hover {
                background-color: #3B72C4;
            }
            """
        )
        self.btn_close.clicked.connect(self.close_clicked)
        layout.addWidget(self.btn_close)

    def retranslate_ui(self) -> None:
        self.title_label.setText(safe_tr("幻灯片母版视图 — 在此定制全局母版排版与样式"))
        self.btn_close.setText(safe_tr("关闭母版视图"))


class SlideThumbnailList(QListWidget):
    """Left-pane thumbnail list with drag-and-drop slide reordering."""

    slide_reordered = Signal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setViewMode(QListWidget.ViewMode.ListMode)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setIconSize(QSize(160, 90))
        self.setSpacing(6)
        self.setStyleSheet(
            """
            QListWidget {
                background-color: #F0F0F0;
                border: none;
                padding: 4px;
            }
            QListWidget::item {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 3px;
                padding: 4px;
                margin-bottom: 4px;
                color: #333333;
                font-weight: bold;
            }
            QListWidget::item:selected {
                background-color: #DCE6F1;
                border: 2px solid #2B579A;
                color: #000000;
            }
            QListWidget::item:hover {
                border: 1px solid #707070;
            }
            """
        )

    def dropEvent(self, event: Any) -> None:
        from_idx = self.currentRow()
        super().dropEvent(event)
        to_idx = self.currentRow()
        if from_idx != -1 and to_idx != -1 and from_idx != to_idx:
            self.slide_reordered.emit(from_idx, to_idx)


class OutlineEditorWidget(QWidget):
    """Left-pane slide text outline editor with bidirectional canvas sync."""

    slide_selected = Signal(int)
    content_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.presentation: Presentation | None = None
        self._is_syncing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.editor = QTextEdit(self)
        self.editor.setFont(QFont("Arial", 11))
        self.editor.setPlaceholderText(safe_tr("在此处输入演示文稿大纲..."))
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.cursorPositionChanged.connect(self._on_cursor_changed)
        layout.addWidget(self.editor)

    def reload(self, presentation: Presentation) -> None:
        """Reload presentation slides into the outline view."""
        self.presentation = presentation
        self._is_syncing = True
        try:
            lines: list[str] = []
            for idx, s in enumerate(presentation.slides):
                title_sh = next(
                    (
                        sh
                        for sh in s.shapes
                        if sh.placeholder and sh.placeholder.type in ("title", "ctrTitle")
                    ),
                    s.shapes[0] if s.shapes else None,
                )
                title = title_sh.text.to_plain_text() if title_sh and title_sh.text else ""
                lines.append(f"[{idx + 1}] {title}")

                body_sh = next(
                    (
                        sh
                        for sh in s.shapes
                        if sh.placeholder and sh.placeholder.type in ("body", "subTitle", "obj")
                    ),
                    None,
                )
                if body_sh and body_sh.text:
                    for para in body_sh.text.paragraphs:
                        t = para.to_plain_text().strip()
                        if t:
                            lines.append(f"    • {t}")
            self.editor.setPlainText("\n".join(lines))
        finally:
            self._is_syncing = False

    def to_plain_text(self) -> str:
        return self.editor.toPlainText()

    def update_slide_title(self, slide_idx: int, new_title: str) -> None:
        """Update slide title shape and outline editor directly."""
        if not self.presentation or not (0 <= slide_idx < len(self.presentation.slides)):
            return
        s = self.presentation.slides[slide_idx]
        title_sh = next(
            (
                sh
                for sh in s.shapes
                if sh.placeholder and sh.placeholder.type in ("title", "ctrTitle")
            ),
            None,
        )
        if not title_sh:
            if s.shapes:
                title_sh = s.shapes[0]
            else:
                title_sh = Shape(id=f"sh_title_{slide_idx}")
                s.shapes.append(title_sh)

        title_sh.text = TextBody.from_plain_text(new_title)
        self.reload(self.presentation)
        self.content_changed.emit()

    def _on_text_changed(self) -> None:
        if self._is_syncing or not self.presentation:
            return
        # Parse outline lines back into slide titles
        text = self.editor.toPlainText()
        lines = text.split("\n")
        cur_slide_idx = -1
        for line in lines:
            trimmed = line.strip()
            if trimmed.startswith("[") and "]" in trimmed:
                try:
                    num_str = trimmed[1 : trimmed.index("]")]
                    cur_slide_idx = int(num_str) - 1
                    after = trimmed[trimmed.index("]") + 1 :].strip()
                    if 0 <= cur_slide_idx < len(self.presentation.slides):
                        s = self.presentation.slides[cur_slide_idx]
                        title_sh = next(
                            (
                                sh
                                for sh in s.shapes
                                if sh.placeholder and sh.placeholder.type in ("title", "ctrTitle")
                            ),
                            s.shapes[0] if s.shapes else None,
                        )
                        if title_sh:
                            title_sh.text = TextBody.from_plain_text(after)
                except ValueError:
                    continue
        self.content_changed.emit()

    def _on_cursor_changed(self) -> None:
        if self._is_syncing or not self.presentation:
            return
        cursor = self.editor.textCursor()
        block_text = cursor.block().text()
        if block_text.startswith("[") and "]" in block_text:
            try:
                num = int(block_text[1 : block_text.index("]")]) - 1
                if 0 <= num < len(self.presentation.slides):
                    self.slide_selected.emit(num)
            except ValueError:
                pass


class SpeakerNotesPane(QWidget):
    """Bottom-split speaker notes pane with double-way binding."""

    notes_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_syncing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        header_layout = QHBoxLayout()
        self.title_label = QLabel(safe_tr("演讲者备注:"), self)
        self.title_label.setFont(QFont("Arial", 9, QFont.Bold))
        self.title_label.setStyleSheet("color: #555555;")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        self.editor = QTextEdit(self)
        self.editor.setFont(QFont("Arial", 10))
        self.editor.setPlaceholderText(safe_tr("单击此处添加备注..."))
        self.editor.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.editor)

    def set_plain_text(self, text: str, emit_signal: bool = True) -> None:
        if not emit_signal:
            self._is_syncing = True
            try:
                self.editor.setPlainText(text)
            finally:
                self._is_syncing = False
        else:
            self.editor.setPlainText(text)

    def to_plain_text(self) -> str:
        return self.editor.toPlainText()

    def _on_text_changed(self) -> None:
        if not self._is_syncing:
            self.notes_changed.emit(self.editor.toPlainText())

    def retranslate_ui(self) -> None:
        self.title_label.setText(safe_tr("演讲者备注:"))
        self.editor.setPlaceholderText(safe_tr("单击此处添加备注..."))


class SlideLayoutPane(QWidget):
    """Right task pane: Slide Layout (21 PowerPoint 2003 layouts)."""

    layout_applied = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.layout_cards: dict[str, QToolButton] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Group layouts
        groups: dict[str, list[LayoutInfo]] = {}
        for layout_info in LAYOUTS:
            groups.setdefault(layout_info.group, []).append(layout_info)

        group_names = {
            "Text Layouts": safe_tr("文本版式:"),
            "Content Layouts": safe_tr("内容版式:"),
            "Text and Content Layouts": safe_tr("文本与内容版式:"),
            "Other Layouts": safe_tr("其他版式:"),
        }

        for grp_key, grp_layouts in groups.items():
            lbl = QLabel(group_names.get(grp_key, grp_key), self)
            lbl.setFont(QFont("Arial", 9, QFont.Bold))
            lbl.setStyleSheet("color: #333333; margin-top: 4px;")
            layout.addWidget(lbl)

            grid_widget = QWidget()
            grid_layout = QHBoxLayout(grid_widget)
            grid_layout.setContentsMargins(0, 0, 0, 0)
            grid_layout.setSpacing(6)

            card_col = QVBoxLayout()
            card_col.setSpacing(6)

            for layout_item in grp_layouts:
                btn = QToolButton(self)
                btn.setText(safe_tr(layout_item.name))
                btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
                btn.setIconSize(QSize(64, 48))
                btn.setIcon(self._create_layout_icon(layout_item.key))
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                btn.setStyleSheet(
                    """
                    QToolButton {
                        background-color: #FFFFFF;
                        border: 1px solid #C0C0C0;
                        border-radius: 2px;
                        padding: 4px;
                        font-size: 10px;
                    }
                    QToolButton:hover {
                        background-color: #E5EEF8;
                        border: 1px solid #2B579A;
                    }
                    """
                )
                key = layout_item.key
                btn.clicked.connect(lambda checked=False, k=key: self.apply_layout(k))
                self.layout_cards[key] = btn
                layout.addWidget(btn)

        layout.addStretch()
        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _create_layout_icon(self, key: str) -> QIcon:
        pix = QPixmap(64, 48)
        pix.fill(QColor("#FFFFFF"))
        painter = QPainter(pix)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(QPen(QColor("#B0B0B0"), 1.0))
            painter.drawRect(0, 0, 63, 47)

            if not hasattr(self, "_cached_design"):
                self._cached_design = build_design("default", 64.0, 48.0)
            frames = layout_frames(key, self._cached_design)
            for f in frames:
                fx = float(f.get("x", 0))
                fy = float(f.get("y", 0))
                fw = float(f.get("w", 20))
                fh = float(f.get("h", 10))
                ftype = f.get("type", "")
                if ftype in ("title", "ctrTitle"):
                    painter.fillRect(QRectF(fx, fy, fw, fh), QColor("#7A7A7A"))
                elif ftype == "body":
                    painter.fillRect(QRectF(fx, fy, fw, fh), QColor("#A8A8A8"))
                else:
                    painter.setPen(QPen(QColor("#2B579A"), 1.0, Qt.DashLine))
                    painter.drawRect(QRectF(fx, fy, fw, fh))
        finally:
            painter.end()
        return QIcon(pix)

    def apply_layout(self, key: str) -> None:
        self.layout_applied.emit(key)


class SlideDesignPane(QWidget):
    """Right task pane: Slide Design (15 PowerPoint 2003 design templates)."""

    design_applied = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.design_cards: dict[str, QToolButton] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        lbl = QLabel(safe_tr("可供使用的设计模板:"), self)
        lbl.setFont(QFont("Arial", 9, QFont.Bold))
        lbl.setStyleSheet("color: #333333;")
        layout.addWidget(lbl)

        for d in DESIGNS:
            btn = QToolButton(self)
            btn.setText(safe_tr(d.name))
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn.setIconSize(QSize(40, 28))
            btn.setIcon(self._create_design_icon(d.key))
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setStyleSheet(
                """
                QToolButton {
                    background-color: #FFFFFF;
                    border: 1px solid #D0D0D0;
                    border-radius: 2px;
                    padding: 4px;
                    font-size: 11px;
                    text-align: left;
                }
                QToolButton:hover {
                    background-color: #E5EEF8;
                    border: 1px solid #2B579A;
                }
                """
            )
            key = d.key
            btn.clicked.connect(lambda checked=False, k=key: self.apply_design(k))
            self.design_cards[key] = btn
            layout.addWidget(btn)

        layout.addStretch()
        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _create_design_icon(self, key: str) -> QIcon:
        pix = QPixmap(40, 28)
        d = build_design(key, 40.0, 28.0)
        pix.fill(QColor(d.colors.lt1))
        painter = QPainter(pix)
        try:
            painter.fillRect(QRectF(0, 0, 40, 10), QColor(d.colors.accent1))
            painter.fillRect(QRectF(4, 14, 20, 4), QColor(d.colors.dk1))
            painter.fillRect(QRectF(4, 20, 32, 3), QColor(d.colors.accent2))
            painter.setPen(QColor("#A0A0A0"))
            painter.drawRect(0, 0, 39, 27)
        finally:
            painter.end()
        return QIcon(pix)

    def apply_design(self, key: str) -> None:
        self.design_applied.emit(key)


class LecternTaskPane(QWidget):
    """Right-side multi-function collapsible task pane with history navigation."""

    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.panes: dict[str, QWidget] = {}
        self.current_pane_id: str = ""
        self._history: list[str] = []
        self._history_index: int = -1

        self.setMinimumWidth(220)
        self.setMaximumWidth(360)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        header = QFrame(self)
        header.setStyleSheet("background-color: #EBEBEB; border-bottom: 1px solid #CCCCCC;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(4, 4, 4, 4)
        header_layout.setSpacing(2)

        self.btn_back = QToolButton(header)
        self.btn_back.setText("<")
        self.btn_back.setToolTip(safe_tr("后退"))
        self.btn_back.clicked.connect(self.go_back)
        header_layout.addWidget(self.btn_back)

        self.btn_fwd = QToolButton(header)
        self.btn_fwd.setText(">")
        self.btn_fwd.setToolTip(safe_tr("前进"))
        self.btn_fwd.clicked.connect(self.go_forward)
        header_layout.addWidget(self.btn_fwd)

        self.title_button = QToolButton(header)
        self.title_button.setText(safe_tr("幻灯片版式"))
        self.title_button.setPopupMode(QToolButton.InstantPopup)
        self.title_button.setStyleSheet("font-weight: bold; border: none; padding: 2px 6px;")
        header_layout.addWidget(self.title_button, 1)

        self.menu = QMenu(self.title_button)
        self.title_button.setMenu(self.menu)

        self.btn_close = QToolButton(header)
        self.btn_close.setText("×")
        self.btn_close.setToolTip(safe_tr("关闭任务窗格"))
        self.btn_close.clicked.connect(self.close_pane)
        header_layout.addWidget(self.btn_close)

        main_layout.addWidget(header)

        # Stacked body
        self.stack = QStackedWidget(self)
        main_layout.addWidget(self.stack)

        self._update_nav_buttons()

    def register_pane(self, pane_id: str, title: str, widget: QWidget) -> None:
        self.panes[pane_id] = widget
        self.stack.addWidget(widget)

        action = self.menu.addAction(title)
        action.triggered.connect(lambda checked=False, pid=pane_id: self.show_pane(pid))

    def get_pane(self, pane_id: str) -> QWidget | None:
        return self.panes.get(pane_id)

    def show_pane(self, pane_id: str) -> None:
        if pane_id not in self.panes:
            return
        if self._history_index == -1 or self._history[self._history_index] != pane_id:
            self._history = self._history[: self._history_index + 1]
            self._history.append(pane_id)
            self._history_index = len(self._history) - 1

        self.current_pane_id = pane_id
        widget = self.panes[pane_id]
        self.stack.setCurrentWidget(widget)

        titles = {
            "layout": safe_tr("幻灯片版式"),
            "design": safe_tr("幻灯片设计"),
        }
        self.title_button.setText(titles.get(pane_id, safe_tr("任务窗格")))
        self.show()
        self._update_nav_buttons()

    def go_back(self) -> None:
        if self._history_index > 0:
            self._history_index -= 1
            pane_id = self._history[self._history_index]
            self.current_pane_id = pane_id
            self.stack.setCurrentWidget(self.panes[pane_id])
            titles = {
                "layout": safe_tr("幻灯片版式"),
                "design": safe_tr("幻灯片设计"),
            }
            self.title_button.setText(titles.get(pane_id, safe_tr("任务窗格")))
            self._update_nav_buttons()

    def go_forward(self) -> None:
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            pane_id = self._history[self._history_index]
            self.current_pane_id = pane_id
            self.stack.setCurrentWidget(self.panes[pane_id])
            titles = {
                "layout": safe_tr("幻灯片版式"),
                "design": safe_tr("幻灯片设计"),
            }
            self.title_button.setText(titles.get(pane_id, safe_tr("任务窗格")))
            self._update_nav_buttons()

    def close_pane(self) -> None:
        self.hide()
        self.closed.emit()

    def _update_nav_buttons(self) -> None:
        self.btn_back.setEnabled(self._history_index > 0)
        self.btn_fwd.setEnabled(self._history_index < len(self._history) - 1)


class LecternWorkspace(QWidget):
    """Complete three-pane workspace implementation for Lectern."""

    slide_changed = Signal(int)

    def __init__(
        self,
        presentation: Presentation | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.presentation = presentation or Presentation()
        self.current_slide_index: int = 0
        self._view_mode: str = "normal"
        self.master_kind: str = "slide"
        self.master_slide: Slide | None = None

        self._init_ui()
        self.load_presentation(self.presentation)
        self.retranslate_ui()

    @property
    def current_slide(self) -> Slide:
        if self.presentation.slides and 0 <= self.current_slide_index < len(
            self.presentation.slides
        ):
            return self.presentation.slides[self.current_slide_index]
        return Slide(id="empty_slide")

    def _init_ui(self) -> None:
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Main horizontal splitter (Left, Center, Right)
        self.main_splitter = QSplitter(Qt.Horizontal, self)
        root_layout.addWidget(self.main_splitter)

        # 1. Left Navigation Pane (Tabs: Slides, Outline)
        self.left_pane = QTabWidget(self.main_splitter)
        self.left_pane.setMinimumWidth(180)
        self.left_pane.setMaximumWidth(320)

        self.thumbnail_list = SlideThumbnailList(self.left_pane)
        self.thumbnail_list.currentRowChanged.connect(self._on_thumbnail_clicked)
        self.thumbnail_list.slide_reordered.connect(self.move_slide)
        self.left_pane.addTab(self.thumbnail_list, safe_tr("幻灯片"))

        self.outline_editor = OutlineEditorWidget(self.left_pane)
        self.outline_editor.slide_selected.connect(self.set_current_slide_index)
        self.outline_editor.content_changed.connect(self._on_outline_content_changed)
        self.left_pane.addTab(self.outline_editor, safe_tr("大纲"))

        self.main_splitter.addWidget(self.left_pane)

        # 2. Center Area (Vertical Splitter inside Center Stack: Canvas + Speaker Notes vs Sorter View)
        self.center_stack = QStackedWidget(self.main_splitter)

        self.center_normal_widget = QWidget(self.center_stack)
        center_normal_layout = QVBoxLayout(self.center_normal_widget)
        center_normal_layout.setContentsMargins(0, 0, 0, 0)
        center_normal_layout.setSpacing(0)

        self.master_close_bar = MasterViewCloseBar(self.center_normal_widget)
        self.master_close_bar.close_clicked.connect(self.exit_master_view)
        self.master_close_bar.hide()
        center_normal_layout.addWidget(self.master_close_bar)

        self.center_splitter = QSplitter(Qt.Vertical, self.center_normal_widget)

        current_slide = self.presentation.slides[0] if self.presentation.slides else None
        self.scene = SlideScene(
            slide=current_slide,
            slide_width=self.presentation.w,
            slide_height=self.presentation.h,
            parent=self,
        )
        self.canvas_view = SlideCanvasView(scene=self.scene, parent=self.center_splitter)
        self.center_splitter.addWidget(self.canvas_view)

        self.notes_pane = SpeakerNotesPane(self.center_splitter)
        self.notes_pane.notes_changed.connect(self._on_notes_changed)
        self.notes_pane.setMinimumHeight(60)
        self.center_splitter.addWidget(self.notes_pane)

        self.center_splitter.setStretchFactor(0, 4)
        self.center_splitter.setStretchFactor(1, 1)

        center_normal_layout.addWidget(self.center_splitter)
        self.center_stack.addWidget(self.center_normal_widget)

        from atboffice.modules.presentation.views.sorter_view import SlideSorterView

        self.sorter_view = SlideSorterView(presentation=self.presentation, parent=self.center_stack)
        self.sorter_view.slide_double_clicked.connect(self._on_sorter_slide_double_clicked)
        self.sorter_view.slides_reordered.connect(self._on_sorter_slides_reordered)
        self.center_stack.addWidget(self.sorter_view)

        self.main_splitter.addWidget(self.center_stack)

        # 3. Right Task Pane
        self.task_pane = LecternTaskPane(self.main_splitter)
        self.layout_pane = SlideLayoutPane(self.task_pane)
        self.layout_pane.layout_applied.connect(self.apply_layout)
        self.task_pane.register_pane("layout", safe_tr("幻灯片版式"), self.layout_pane)

        self.design_pane = SlideDesignPane(self.task_pane)
        self.design_pane.design_applied.connect(self.apply_design)
        self.task_pane.register_pane("design", safe_tr("幻灯片设计"), self.design_pane)

        from atboffice.modules.presentation.smartart.text_pane import SmartArtTextPane

        self.smartart_pane = SmartArtTextPane(self.task_pane)
        self.smartart_pane.diagram_changed.connect(self._on_smartart_diagram_changed)
        self.smartart_pane.converted_to_shapes.connect(self._on_smartart_converted_to_shapes)
        self.task_pane.register_pane("smartart", safe_tr("智能图示设计"), self.smartart_pane)

        self.scene.selectionChangedCustom.connect(self._on_canvas_selection_changed)

        self.task_pane.show_pane("layout")
        self.main_splitter.addWidget(self.task_pane)

        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 5)
        self.main_splitter.setStretchFactor(2, 2)

        self._active_slideshow: Any | None = None

        # Presentation shortcuts (F5: from start, Shift+F5: from current)
        self._shortcut_f5 = QShortcut(QKeySequence(Qt.Key.Key_F5), self)
        self._shortcut_f5.activated.connect(lambda: self.start_slideshow(from_current=False))
        self._shortcut_shift_f5 = QShortcut(QKeySequence("Shift+F5"), self)
        self._shortcut_shift_f5.activated.connect(lambda: self.start_slideshow(from_current=True))

    def load_presentation(self, presentation: Presentation) -> None:
        """Load presentation document and update all panes."""
        self.presentation = presentation
        self.current_slide_index = 0

        self.scene.slide_width = presentation.w
        self.scene.slide_height = presentation.h

        self._refresh_thumbnails()
        self.outline_editor.reload(presentation)
        self._refresh_active_slide()

    def set_current_slide_index(self, index: int) -> None:
        """Switch active slide shown in canvas and notes."""
        if not self.presentation.slides:
            return
        clamped = max(0, min(index, len(self.presentation.slides) - 1))
        if self.current_slide_index != clamped or self.scene.slide != self.current_slide:
            self.current_slide_index = clamped
            self._refresh_active_slide()
            # Sync thumbnail list selection
            if self.thumbnail_list.currentRow() != clamped:
                self.thumbnail_list.setCurrentRow(clamped)
            self.slide_changed.emit(clamped)

    def set_current_slide(self, index: int) -> None:
        """Alias for set_current_slide_index."""
        self.set_current_slide_index(index)

    def start_slideshow(
        self,
        from_current: bool = False,
        fullscreen: bool = False,
    ) -> Any | None:
        """Launch the presentation in fullscreen or windowed SlideShowView."""
        if not self.presentation.slides:
            return None
        from atboffice.modules.presentation.slideshow.slideshow_view import SlideShowView

        start_idx = self.current_slide_index if from_current else 0
        show_view = SlideShowView(
            presentation=self.presentation,
            start_slide_index=start_idx,
            fullscreen=fullscreen,
        )
        show_view.slideChanged.connect(self.set_current_slide_index)
        self._active_slideshow = show_view
        show_view.show()
        return show_view

    def load_slide(self, slide: Slide) -> None:
        """Switch active slide by reference."""
        for i, s in enumerate(self.presentation.slides):
            if s.id == slide.id:
                self.set_current_slide_index(i)
                return

    def move_slide(self, from_idx: int, to_idx: int) -> None:
        """Reorder slides within the presentation."""
        self.presentation.move_slide(from_idx, to_idx)
        self._refresh_thumbnails()
        self.outline_editor.reload(self.presentation)
        self.set_current_slide_index(to_idx)

    def apply_layout(self, layout_key: str) -> None:
        """Apply layout to the currently active slide."""
        if not self.presentation.slides:
            return
        cur = self.current_slide
        self.presentation.apply_layout(cur, layout_key)
        self.scene.load_slide(cur)
        self._refresh_current_thumbnail()
        self.outline_editor.reload(self.presentation)

    def apply_design(self, design_key: str) -> None:
        """Apply design to presentation and refresh canvas."""
        self.presentation.apply_design(design_key, [self.current_slide])
        self.scene.load_slide(self.current_slide)
        self._refresh_thumbnails()

    def toggle_task_pane(self, visible: bool) -> None:
        self.task_pane.setVisible(visible)

    def _refresh_thumbnails(self) -> None:
        self.thumbnail_list.clear()
        for idx, s in enumerate(self.presentation.slides):
            pixmap = render_slide_thumbnail(s, self.presentation, width=160)
            item = QListWidgetItem(QIcon(pixmap), f"{idx + 1}")
            item.setSizeHint(QSize(160, pixmap.height() + 24))
            self.thumbnail_list.addItem(item)
        if self.presentation.slides:
            self.thumbnail_list.setCurrentRow(self.current_slide_index)

    def _refresh_current_thumbnail(self) -> None:
        idx = self.current_slide_index
        if 0 <= idx < self.thumbnail_list.count():
            s = self.current_slide
            pixmap = render_slide_thumbnail(s, self.presentation, width=160)
            item = self.thumbnail_list.item(idx)
            item.setIcon(QIcon(pixmap))

    def _refresh_active_slide(self) -> None:
        if self.presentation.slides:
            cur = self.current_slide
            self.scene.load_slide(cur)
            self.notes_pane.set_plain_text(cur.notes, emit_signal=False)
            self.canvas_view.zoom_fit()
        else:
            self.notes_pane.set_plain_text("", emit_signal=False)

    def _on_thumbnail_clicked(self, row: int) -> None:
        if self._view_mode == "master":
            kind = "title" if row == 1 else "slide"
            if kind != self.master_kind:
                if self.master_slide:
                    sync_master_slide(self.presentation, self.master_slide)
                self.enter_master_view(kind)
            return
        if row >= 0 and row != self.current_slide_index:
            self.set_current_slide_index(row)

    @property
    def view_mode(self) -> str:
        return self._view_mode

    def set_view_mode(self, mode: str) -> None:
        """Switch workspace view mode ('normal', 'sorter', 'master')."""
        if mode not in ("normal", "sorter", "master"):
            mode = "normal"
        self._view_mode = mode

        if mode == "sorter":
            self.left_pane.hide()
            self.task_pane.hide()
            self.master_close_bar.hide()
            self.sorter_view.load_presentation(self.presentation)
            if self.presentation.slides:
                self.sorter_view.select_slide(self.current_slide_index)
            self.center_stack.setCurrentWidget(self.sorter_view)
        elif mode == "master":
            self.left_pane.show()
            self.task_pane.hide()
            self.master_close_bar.show()
            self.notes_pane.hide()
            self.enter_master_view(self.master_kind)
            self.center_stack.setCurrentWidget(self.center_normal_widget)
        else:  # "normal"
            self.left_pane.show()
            self.task_pane.show()
            self.master_close_bar.hide()
            self.notes_pane.show()
            self._restore_normal_thumbnails()
            self._refresh_active_slide()
            self.center_stack.setCurrentWidget(self.center_normal_widget)

    def _on_sorter_slide_double_clicked(self, index: int) -> None:
        self.set_view_mode("normal")
        self.set_current_slide_index(index)

    def _on_sorter_slides_reordered(self, indices: list[int], target_index: int) -> None:
        self._refresh_thumbnails()
        self.outline_editor.reload(self.presentation)
        self._refresh_active_slide()

    def enter_master_view(self, master_kind: str = "slide") -> None:
        """Enter master editing view."""
        self._view_mode = "master"
        self.master_kind = master_kind
        design = self.presentation.get_design_for_slide(
            self.current_slide if self.presentation.slides else None
        )
        self.master_slide = build_master_slide(
            self.presentation, design, master_kind=master_kind
        )
        self.scene.load_slide(self.master_slide)
        self.canvas_view.zoom_fit()
        self._refresh_master_thumbnails()

    def exit_master_view(self) -> None:
        """Sync master edits back to design and return to normal view."""
        if self.master_slide:
            sync_master_slide(self.presentation, self.master_slide)
        self.set_view_mode("normal")

    def _refresh_master_thumbnails(self) -> None:
        self.thumbnail_list.clear()
        design = self.presentation.get_design_for_slide(
            self.current_slide if self.presentation.slides else None
        )

        # 1. Slide master
        sm = build_master_slide(self.presentation, design, master_kind="slide")
        sm_pix = render_slide_thumbnail(sm, self.presentation, width=160)
        item1 = QListWidgetItem(QIcon(sm_pix), safe_tr("1 幻灯片母版"))
        item1.setSizeHint(QSize(160, sm_pix.height() + 24))
        self.thumbnail_list.addItem(item1)

        # 2. Title master
        tm = build_master_slide(self.presentation, design, master_kind="title")
        tm_pix = render_slide_thumbnail(tm, self.presentation, width=160)
        item2 = QListWidgetItem(QIcon(tm_pix), safe_tr("2 标题母版"))
        item2.setSizeHint(QSize(160, tm_pix.height() + 24))
        self.thumbnail_list.addItem(item2)

        cur_row = 1 if self.master_kind == "title" else 0
        self.thumbnail_list.setCurrentRow(cur_row)

    def _restore_normal_thumbnails(self) -> None:
        self._refresh_thumbnails()
        self.outline_editor.reload(self.presentation)

    def _on_outline_content_changed(self) -> None:
        # Refresh current slide scene and thumbnail
        if self.presentation.slides:
            self.scene.load_slide(self.current_slide)
            self._refresh_current_thumbnail()

    def _on_notes_changed(self, text: str) -> None:
        if self.presentation.slides:
            self.current_slide.notes = text

    def _on_canvas_selection_changed(self) -> None:
        items = self.scene.selectedItems()
        for it in items:
            sh = getattr(it, "shape", None)
            if sh and sh.is_diagram:
                self.task_pane.show_pane("smartart")
                self.smartart_pane.set_diagram(sh)
                return

    def insert_smartart(
        self,
        layout_id: str = "process",
        colors: str = "ocean",
        style: str = "moderate",
    ) -> Shape:
        """Insert a new IntelliArt diagram on the current slide and open editor pane."""
        from atboffice.modules.presentation.smartart.engine import (
            SmartArtEngine,
            relayout,
        )

        eng = SmartArtEngine()
        blank_items = eng.blank(layout_id)
        s_obj = Shape(
            id=f"diagram_{eng.new_id()}",
            type="group",
            name=f"IntelliArt ({layout_id})",
            x=80.0,
            y=80.0,
            w=520.0,
            h=340.0,
            sa={
                "layout": layout_id,
                "colors": colors,
                "style": style,
                "items": [it.to_dict() for it in blank_items],
            },
        )
        relayout(s_obj)
        cur = self.current_slide
        cur.shapes.append(s_obj)
        self.scene.load_slide(cur)
        self.task_pane.show_pane("smartart")
        self.smartart_pane.set_diagram(s_obj)
        self._refresh_current_thumbnail()
        return s_obj

    def _on_smartart_diagram_changed(self, shape: Shape) -> None:
        cur = self.current_slide
        self.scene.load_slide(cur)
        self._refresh_current_thumbnail()

    def _on_smartart_converted_to_shapes(self, shape: Shape) -> None:
        cur = self.current_slide
        self.scene.load_slide(cur)
        self._refresh_current_thumbnail()
        self.task_pane.show_pane("layout")

    def retranslate_ui(self) -> None:
        """Retranslate all workspace controls."""
        self.left_pane.setTabText(0, safe_tr("幻灯片"))
        self.left_pane.setTabText(1, safe_tr("大纲"))
        self.notes_pane.retranslate_ui()
        self.canvas_view.retranslate_ui()
        if hasattr(self, "master_close_bar"):
            self.master_close_bar.retranslate_ui()
        if hasattr(self, "sorter_view"):
            self.sorter_view.retranslate_ui()
        if hasattr(self, "smartart_pane"):
            self.smartart_pane.retranslate_ui()

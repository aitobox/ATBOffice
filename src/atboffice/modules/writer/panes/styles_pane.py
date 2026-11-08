"""Word 2003 Styles and Formatting task pane for Quire."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.writer.models.styles import builtin_styles

if TYPE_CHECKING:
    from atboffice.modules.writer.models.document import Document


def safe_tr(text: str) -> str:
    """Translate UI text safely for StylesAndFormattingPane."""
    return QCoreApplication.translate("StylesAndFormattingPane", text)


class StyleItemWidget(QPushButton):
    """Clickable style card displaying preview text and style-type indicator."""

    style_clicked = Signal(str)

    def __init__(
        self,
        style_id: str,
        display_name: str,
        style_type: str = "paragraph",
        is_clear: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.style_id = style_id
        self.display_name = display_name
        self.style_type = style_type
        self.is_clear = is_clear

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(30)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)

        # Style name label
        self.lbl_name = QLabel(display_name, self)
        font = QFont()
        if style_id == "Heading1":
            font.setPointSize(12)
            font.setBold(True)
        elif style_id == "Heading2":
            font.setPointSize(11)
            font.setBold(True)
            font.setItalic(True)
        elif style_id == "Heading3":
            font.setPointSize(10)
            font.setBold(True)
        elif is_clear:
            font.setPointSize(10)
            font.setItalic(True)
        else:
            font.setPointSize(10)
        self.lbl_name.setFont(font)
        self.lbl_name.setStyleSheet("background: transparent; color: #000000;")
        layout.addWidget(self.lbl_name, stretch=1)

        # Badge indicator: ¶ for paragraph, a for character
        if not is_clear:
            badge_text = "¶" if style_type == "paragraph" else "a"
            self.lbl_badge = QLabel(badge_text, self)
            self.lbl_badge.setStyleSheet(
                "color: #000080; font-weight: bold; font-size: 11px; background: transparent;"
            )
            layout.addWidget(self.lbl_badge)
        else:
            self.lbl_badge = None

        self._set_selected(False)
        self.clicked.connect(lambda: self.style_clicked.emit(self.style_id))

    def _set_selected(self, selected: bool) -> None:
        if selected:
            self.setStyleSheet(
                """
                QPushButton {
                    background-color: #B6BDD2;
                    border: 1px solid #0A246A;
                    border-radius: 2px;
                    text-align: left;
                }
                """
            )
        else:
            self.setStyleSheet(
                """
                QPushButton {
                    background-color: #FFFFFF;
                    border: 1px solid transparent;
                    border-radius: 2px;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: #E5EEF8;
                    border: 1px solid #7B9EBD;
                }
                """
            )


class StylesAndFormattingPane(QWidget):
    """Word 2003 Styles and Formatting task pane."""

    apply_style_requested = Signal(str)
    clear_formatting_requested = Signal()
    select_all_requested = Signal()
    new_style_requested = Signal()

    def __init__(
        self,
        doc: Document | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.doc = doc
        self.current_style_id: str = "Normal"
        self._style_widgets: dict[str, StyleItemWidget] = {}

        self._init_ui()
        self.populate_styles()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # 1. Section: Formatting of selected text
        self.lbl_sel_heading = QLabel(safe_tr("所选文字的格式:"), self)
        self.lbl_sel_heading.setStyleSheet("font-weight: bold; color: #000080;")
        main_layout.addWidget(self.lbl_sel_heading)

        self.box_cur_style = QFrame(self)
        self.box_cur_style.setFrameShape(QFrame.Shape.StyledPanel)
        self.box_cur_style.setStyleSheet(
            "background-color: #FFFFFF; border: 1px solid #7B9EBD; padding: 4px;"
        )
        box_layout = QVBoxLayout(self.box_cur_style)
        box_layout.setContentsMargins(6, 4, 6, 4)
        self.lbl_cur_style = QLabel("Normal", self.box_cur_style)
        self.lbl_cur_style.setStyleSheet("font-size: 11px; font-weight: bold; color: #000000;")
        box_layout.addWidget(self.lbl_cur_style)
        main_layout.addWidget(self.box_cur_style)

        # Buttons under current format box
        h_btns = QHBoxLayout()
        h_btns.setSpacing(4)
        self.btn_select_all = QPushButton(safe_tr("全选类似格式"), self)
        self.btn_select_all.setStyleSheet("font-size: 10px; padding: 2px 6px;")
        self.btn_select_all.clicked.connect(self.select_all_requested)
        h_btns.addWidget(self.btn_select_all)

        self.btn_new_style = QPushButton(safe_tr("新建样式..."), self)
        self.btn_new_style.setStyleSheet("font-size: 10px; padding: 2px 6px;")
        self.btn_new_style.clicked.connect(self.new_style_requested)
        h_btns.addWidget(self.btn_new_style)
        h_btns.addStretch()
        main_layout.addLayout(h_btns)

        # 2. Section: Pick formatting to apply
        self.lbl_pick_heading = QLabel(safe_tr("请选择要应用的格式:"), self)
        self.lbl_pick_heading.setStyleSheet("font-weight: bold; color: #000080; margin-top: 6px;")
        main_layout.addWidget(self.lbl_pick_heading)

        # Scrollable style list
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.StyledPanel)
        self.scroll_area.setStyleSheet("background-color: #FFFFFF; border: 1px solid #7B9EBD;")

        self.styles_container = QWidget()
        self.styles_container.setStyleSheet("background-color: #FFFFFF;")
        self.styles_layout = QVBoxLayout(self.styles_container)
        self.styles_layout.setContentsMargins(4, 4, 4, 4)
        self.styles_layout.setSpacing(2)
        self.styles_layout.addStretch()
        self.scroll_area.setWidget(self.styles_container)
        main_layout.addWidget(self.scroll_area, stretch=1)

        # 3. Section: Show filter combo
        h_show = QHBoxLayout()
        h_show.setSpacing(4)
        self.lbl_show = QLabel(safe_tr("显示(&S):"), self)
        h_show.addWidget(self.lbl_show)

        self.combo_show = QComboBox(self)
        self.combo_show.addItem(safe_tr("有效格式"), "avail")
        self.combo_show.addItem(safe_tr("正在使用的格式"), "inuse")
        self.combo_show.addItem(safe_tr("有效样式"), "styles")
        self.combo_show.addItem(safe_tr("所有样式"), "all")
        self.combo_show.currentIndexChanged.connect(self._on_show_changed)
        h_show.addWidget(self.combo_show, stretch=1)
        main_layout.addLayout(h_show)

    def set_document(self, doc: Document) -> None:
        """Update active document reference and refresh styles list."""
        self.doc = doc
        self.populate_styles()

    def populate_styles(self) -> None:
        """Populate the styles list based on builtins and active document styles."""
        # Clear existing items
        self._style_widgets.clear()
        while self.styles_layout.count() > 0:
            item = self.styles_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 1. Clear Formatting item
        clear_item = StyleItemWidget("clear", safe_tr("清除格式"), is_clear=True, parent=self)
        clear_item.style_clicked.connect(self._on_clear_clicked)
        self.styles_layout.addWidget(clear_item)
        self._style_widgets["clear"] = clear_item

        # Core standard styles with localization
        core_styles = [
            ("Normal", safe_tr("正文"), "paragraph"),
            ("Heading1", safe_tr("标题 1"), "paragraph"),
            ("Heading2", safe_tr("标题 2"), "paragraph"),
            ("Heading3", safe_tr("标题 3"), "paragraph"),
            ("Title", safe_tr("标题"), "paragraph"),
            ("Subtitle", safe_tr("副标题"), "paragraph"),
            ("DefaultParagraphFont", safe_tr("默认段落字体"), "character"),
        ]

        b_styles = builtin_styles()
        doc_styles = self.doc.styles if self.doc else {}

        # Merge doc styles if any custom ones exist
        style_entries = list(core_styles)
        seen_ids = {s[0] for s in core_styles}

        mode = self.combo_show.currentData() if hasattr(self, "combo_show") else "avail"
        if mode == "all":
            for sid, s in b_styles.items():
                if sid not in seen_ids:
                    style_entries.append((sid, s.name, s.style_type))
                    seen_ids.add(sid)

        for sid, s in doc_styles.items():
            if sid not in seen_ids:
                style_entries.append(
                    (sid, getattr(s, "name", sid), getattr(s, "style_type", "paragraph"))
                )
                seen_ids.add(sid)

        for sid, display_name, stype in style_entries:
            w = StyleItemWidget(sid, display_name, style_type=stype, parent=self)
            w.style_clicked.connect(self._on_style_item_clicked)
            self.styles_layout.addWidget(w)
            self._style_widgets[sid] = w

        self.styles_layout.addStretch()
        self.update_current_style(self.current_style_id)

    def update_current_style(self, style_id: str, desc: str = "") -> None:
        """Update the current style label and highlight the active style card."""
        self.current_style_id = style_id
        text = style_id
        if desc:
            text = f"{style_id} + {desc}"
        self.lbl_cur_style.setText(text)

        for sid, w in self._style_widgets.items():
            w._set_selected(sid == style_id)

    def _on_style_item_clicked(self, style_id: str) -> None:
        self.update_current_style(style_id)
        self.apply_style_requested.emit(style_id)

    def _on_clear_clicked(self, _: str) -> None:
        self.update_current_style("Normal")
        self.clear_formatting_requested.emit()

    def _on_show_changed(self) -> None:
        self.populate_styles()

    def retranslate_ui(self) -> None:
        """Update localized UI text."""
        self.lbl_sel_heading.setText(safe_tr("所选文字的格式:"))
        self.btn_select_all.setText(safe_tr("全选类似格式"))
        self.btn_new_style.setText(safe_tr("新建样式..."))
        self.lbl_pick_heading.setText(safe_tr("请选择要应用的格式:"))
        self.lbl_show.setText(safe_tr("显示(&S):"))
        self.combo_show.setItemText(0, safe_tr("有效格式"))
        self.combo_show.setItemText(1, safe_tr("正在使用的格式"))
        self.combo_show.setItemText(2, safe_tr("有效样式"))
        self.combo_show.setItemText(3, safe_tr("所有样式"))
        self.populate_styles()

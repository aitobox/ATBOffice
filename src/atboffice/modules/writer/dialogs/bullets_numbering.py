"""Word 2003 classic Bullets and Numbering Dialog for Quire writer."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.writer.models.properties import NumberingRef


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("BulletsNumberingDialog", text)


BULLET_PRESETS: list[tuple[str, str]] = [
    ("none", "无"),
    ("•", "实心圆点"),
    ("○", "空心圆点"),
    ("■", "实心方块"),
    ("◆", "实心菱形"),
    ("➢", "箭头形"),
    ("✓", "对勾形"),
    ("❖", "装饰星形"),
]

NUMBER_PRESETS: list[tuple[str, list[str]]] = [
    ("none", ["无"]),
    ("1. 2. 3.", ["1.", "2.", "3."]),
    ("1) 2) 3)", ["1)", "2)", "3)"]),
    ("I. II. III.", ["I.", "II.", "III."]),
    ("A. B. C.", ["A.", "B.", "C."]),
    ("a) b) c)", ["a)", "b)", "c)"]),
    ("a. b. c.", ["a.", "b.", "c."]),
    ("i. ii. iii.", ["i.", "ii.", "iii."]),
]

OUTLINE_PRESETS: list[tuple[str, list[tuple[int, str]]]] = [
    ("none", [(0, "无")]),
    ("1. / 1.1 / 1.1.1", [(0, "1."), (1, "1.1"), (2, "1.1.1")]),
    ("1) / a) / i)", [(0, "1)"), (1, "a)"), (2, "i)")]),
    ("第一章 / 第1条 / 1.1", [(0, "第一章"), (1, "第1条"), (2, "1.1")]),
    ("Article I / Section 1.01", [(0, "Article I."), (1, "Section 1.01"), (2, "(a)")]),
    ("I. / A. / 1.", [(0, "I."), (1, "A."), (2, "1.")]),
    ("一、 / (一) / 1.", [(0, "一、"), (1, "(一)"), (2, "1.")]),
    ("1. / a. / i.", [(0, "1."), (1, "a."), (2, "i.")]),
]


class GalleryItemWidget(QFrame):
    """Visual preview button representing a bullet/numbering preset."""

    selected = Signal(int)
    double_clicked = Signal(int)

    def __init__(
        self,
        kind: str,
        index: int,
        data: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.kind = kind
        self.index = index
        self.data = data
        self.is_selected = False

        self.setFixedSize(110, 80)
        self.setFrameShape(QFrame.Shape.Box)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_selected(self, sel: bool) -> None:
        if self.is_selected != sel:
            self.is_selected = sel
            self.update()

    def mousePressEvent(self, event: Any) -> None:
        self.selected.emit(self.index)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: Any) -> None:
        self.double_clicked.emit(self.index)
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()

        # Background & border
        if self.is_selected:
            painter.fillRect(rect, QColor("#D6E6F8"))
            painter.setPen(QPen(QColor("#0A246A"), 2))
            painter.drawRect(rect.adjusted(1, 1, -1, -1))
        else:
            painter.fillRect(rect, Qt.GlobalColor.white)
            painter.setPen(QPen(QColor("#A0A0A0"), 1))
            painter.drawRect(rect.adjusted(0, 0, -1, -1))

        if self.index == 0 or self.data[0] == "none":
            painter.setPen(QPen(Qt.GlobalColor.black))
            f = painter.font()
            f.setPointSize(10)
            painter.setFont(f)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, safe_tr("无"))
            return

        # Render 3 sample lines
        align_left_vcenter = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        if self.kind == "bullet":
            sym = self.data[0]
            for i in range(3):
                y = 20 + i * 20
                painter.setPen(QPen(Qt.GlobalColor.black))
                painter.drawText(QRect(12, y - 10, 16, 20), align_left_vcenter, sym)
                painter.setPen(QPen(QColor("#808080"), 2))
                painter.drawLine(32, y, 95, y)

        elif self.kind == "number":
            labels = self.data[1]
            for i in range(min(3, len(labels))):
                y = 20 + i * 20
                painter.setPen(QPen(Qt.GlobalColor.black))
                f = painter.font()
                f.setPointSize(8)
                painter.setFont(f)
                painter.drawText(QRect(10, y - 10, 30, 20), align_left_vcenter, labels[i])
                painter.setPen(QPen(QColor("#808080"), 2))
                painter.drawLine(44, y, 95, y)

        elif self.kind == "outline":
            items = self.data[1]
            for i in range(min(3, len(items))):
                lvl, label = items[i]
                y = 20 + i * 20
                indent_x = 10 + lvl * 12
                painter.setPen(QPen(Qt.GlobalColor.black))
                f = painter.font()
                f.setPointSize(7)
                painter.setFont(f)
                painter.drawText(QRect(indent_x, y - 10, 40, 20), align_left_vcenter, label)
                painter.setPen(QPen(QColor("#808080"), 1))
                painter.drawLine(indent_x + 36, y, 98, y)


class BulletsNumberingDialog(QDialog):
    """Word 2003 classic Bullets and Numbering Dialog."""

    def __init__(
        self,
        num_ref: NumberingRef | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.num_ref = num_ref
        self.setMinimumWidth(520)
        self.setWindowTitle(safe_tr("项目符号和编号"))

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)

        self.tab_widget = QTabWidget(self)

        self._active_kind = "bullet"
        self._selected_indices = {"bullet": 1, "number": 1, "outline": 1}
        self._customized_result: dict[str, Any] | None = None

        # --- Tab 1: 项目符号 (Bulleted) ---
        self.tab_bullets = QWidget()
        b_layout = QVBoxLayout(self.tab_bullets)
        self.grid_bullets = QGridLayout()
        self.grid_bullets.setSpacing(10)
        self._bullet_widgets: list[GalleryItemWidget] = []
        for idx, item in enumerate(BULLET_PRESETS):
            w = GalleryItemWidget("bullet", idx, item, self.tab_bullets)
            w.selected.connect(lambda i: self.select_item("bullet", i))
            w.double_clicked.connect(self._on_item_double_clicked)
            self._bullet_widgets.append(w)
            self.grid_bullets.addWidget(w, idx // 4, idx % 4)
        b_layout.addLayout(self.grid_bullets)
        self.tab_widget.addTab(self.tab_bullets, safe_tr("项目符号"))

        # --- Tab 2: 编号 (Numbered) ---
        self.tab_numbered = QWidget()
        n_layout = QVBoxLayout(self.tab_numbered)
        self.grid_numbered = QGridLayout()
        self.grid_numbered.setSpacing(10)
        self._numbered_widgets: list[GalleryItemWidget] = []
        for idx, item in enumerate(NUMBER_PRESETS):
            w = GalleryItemWidget("number", idx, item, self.tab_numbered)
            w.selected.connect(lambda i: self.select_item("number", i))
            w.double_clicked.connect(self._on_item_double_clicked)
            self._numbered_widgets.append(w)
            self.grid_numbered.addWidget(w, idx // 4, idx % 4)
        n_layout.addLayout(self.grid_numbered)

        # List numbering radios
        self.group_list_num = QGroupBox(self.tab_numbered)
        ln_layout = QHBoxLayout(self.group_list_num)
        self.radio_restart = QRadioButton(self.group_list_num)
        self.radio_continue = QRadioButton(self.group_list_num)
        self.radio_continue.setChecked(True)
        ln_group = QButtonGroup(self.group_list_num)
        ln_group.addButton(self.radio_restart)
        ln_group.addButton(self.radio_continue)
        ln_layout.addWidget(self.radio_restart)
        ln_layout.addWidget(self.radio_continue)
        ln_layout.addStretch()
        n_layout.addWidget(self.group_list_num)
        self.tab_widget.addTab(self.tab_numbered, safe_tr("编号"))

        # --- Tab 3: 多级符号 (Outline Numbered) ---
        self.tab_outline = QWidget()
        o_layout = QVBoxLayout(self.tab_outline)
        self.grid_outline = QGridLayout()
        self.grid_outline.setSpacing(10)
        self._outline_widgets: list[GalleryItemWidget] = []
        for idx, item in enumerate(OUTLINE_PRESETS):
            w = GalleryItemWidget("outline", idx, item, self.tab_outline)
            w.selected.connect(lambda i: self.select_item("outline", i))
            w.double_clicked.connect(self._on_item_double_clicked)
            self._outline_widgets.append(w)
            self.grid_outline.addWidget(w, idx // 4, idx % 4)
        o_layout.addLayout(self.grid_outline)
        self.tab_widget.addTab(self.tab_outline, safe_tr("多级符号"))

        main_layout.addWidget(self.tab_widget)

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        self.btn_reset = QPushButton(safe_tr("重新设置(&R)"), self)
        self.btn_reset.clicked.connect(self._on_reset_clicked)
        self.btn_customize = QPushButton(safe_tr("自定义(&Z)..."), self)
        self.btn_customize.clicked.connect(self._on_customize_clicked)
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addWidget(self.btn_customize)
        btn_layout.addStretch()

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        btn_layout.addWidget(self.button_box)
        main_layout.addLayout(btn_layout)

        # Tab change tracker
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # Initial selection
        self.select_item("bullet", 1)
        self.select_item("number", 1)
        self.select_item("outline", 1)
        self.retranslate_ui()

    def _on_tab_changed(self, idx: int) -> None:
        kinds = ["bullet", "number", "outline"]
        if 0 <= idx < len(kinds):
            self._active_kind = kinds[idx]

    def _on_item_double_clicked(self, idx: int) -> None:
        self.select_item(self._active_kind, idx)
        self.accept()

    def _on_reset_clicked(self) -> None:
        self.select_item(self._active_kind, 0)

    def _on_customize_clicked(self) -> None:
        """Launch classic list customization wizard/dialog."""
        from atboffice.modules.writer.dialogs.customize_list_dialog import CustomizeListDialog

        dlg = CustomizeListDialog(kind=self._active_kind, initial_level=0, parent=self)
        if dlg.exec():
            self._customized_result = dlg.get_customized_level()
            self.accept()

    def select_item(self, tab_kind: str, idx: int) -> None:
        """Select a preset item in the designated tab."""
        self._selected_indices[tab_kind] = idx
        widgets_map = {
            "bullet": self._bullet_widgets,
            "number": self._numbered_widgets,
            "outline": self._outline_widgets,
        }
        widgets = widgets_map.get(tab_kind, [])
        for i, w in enumerate(widgets):
            w.set_selected(i == idx)

    def get_result(self) -> dict[str, Any]:
        """Construct result dict from current active tab and selection."""
        if self._customized_result is not None:
            res = dict(self._customized_result)
            res["kind"] = self._active_kind
            res["customized"] = True
            return res

        cur_tab = self.tab_widget.currentIndex()
        kind_name = ["bullet", "number", "outline"][cur_tab] if cur_tab in (0, 1, 2) else "bullet"
        idx = self._selected_indices.get(kind_name, 0)

        if idx == 0:
            return {"kind": "none", "choice_idx": 0, "restart": False}

        if kind_name == "bullet":
            item = BULLET_PRESETS[idx]
            return {
                "kind": "bullet",
                "choice_idx": idx,
                "char": item[0],
                "name": item[1],
                "restart": False,
            }
        elif kind_name == "number":
            item = NUMBER_PRESETS[idx]
            return {
                "kind": "number",
                "choice_idx": idx,
                "format": item[0],
                "samples": item[1],
                "restart": self.radio_restart.isChecked(),
            }
        else:
            item = OUTLINE_PRESETS[idx]
            return {
                "kind": "outline",
                "choice_idx": idx,
                "format": item[0],
                "levels": item[1],
                "restart": False,
            }

    def retranslate_ui(self) -> None:
        """Localize UI strings."""
        self.setWindowTitle(safe_tr("项目符号和编号"))
        self.tab_widget.setTabText(0, safe_tr("项目符号"))
        self.tab_widget.setTabText(1, safe_tr("编号"))
        self.tab_widget.setTabText(2, safe_tr("多级符号"))

        self.group_list_num.setTitle(safe_tr("列表编号"))
        self.radio_restart.setText(safe_tr("重新开始编号(&R)"))
        self.radio_continue.setText(safe_tr("继续前一列表(&C)"))

        self.btn_reset.setText(safe_tr("重新设置(&R)"))
        self.btn_customize.setText(safe_tr("自定义(&Z)..."))

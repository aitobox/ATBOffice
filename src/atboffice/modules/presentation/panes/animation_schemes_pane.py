"""PowerPoint 2003 Slide Design - Animation Schemes Task Pane for Lectern."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from atboffice.modules.presentation.models.presentation import Presentation


def safe_tr(text: str) -> str:
    """Translate UI text safely for AnimationSchemesPane."""
    return QCoreApplication.translate("AnimationSchemesPane", text)


class PaneLinkButton(QPushButton):
    """Hyperlink button for top task pane navigation."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setStyleSheet(
            """
            QPushButton {
                color: #000080;
                text-decoration: underline;
                text-align: left;
                background: transparent;
                border: none;
                font-size: 11px;
                padding: 2px 4px;
            }
            QPushButton:hover {
                color: #FF0000;
            }
            """
        )


ANIMATION_SCHEMES_DATA = [
    (
        safe_tr("无动画"),
        [
            ("none", safe_tr("无")),
        ],
    ),
    (
        safe_tr("细微型"),
        [
            ("appear", safe_tr("出现")),
            ("appear_dim", safe_tr("出现变暗")),
            ("fade_all", safe_tr("整体淡入")),
            ("fade_one", safe_tr("按项淡入")),
            ("faded_wipe", safe_tr("渐变擦除")),
            ("faded_zoom", safe_tr("淡入缩放")),
            ("dissolve", safe_tr("溶解")),
            ("random_bars", safe_tr("随机线条")),
            ("wipe", safe_tr("擦除")),
            ("blinds", safe_tr("百叶窗")),
        ],
    ),
    (
        safe_tr("中度型"),
        [
            ("ascend", safe_tr("上升")),
            ("descend", safe_tr("下降")),
            ("zoom", safe_tr("缩放")),
            ("expand", safe_tr("展开")),
            ("spinner", safe_tr("回旋")),
            ("peek_in", safe_tr("切入")),
        ],
    ),
    (
        safe_tr("华丽型"),
        [
            ("fly_in", safe_tr("飞入")),
            ("checkerboard", safe_tr("棋盘")),
            ("wheel", safe_tr("轮子")),
            ("plus", safe_tr("十字形")),
            ("diamond", safe_tr("菱形")),
            ("box_out", safe_tr("正方形")),
        ],
    ),
]


class AnimationSchemesPane(QWidget):
    """Slide Design - Animation Schemes task pane."""

    apply_animation_scheme_requested = Signal(str, bool)  # (scheme_key, apply_to_all)
    play_requested = Signal()
    slide_show_requested = Signal()
    navigate_pane = Signal(str)

    def __init__(
        self,
        presentation: Presentation | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.presentation = presentation
        self.selected_scheme_key: str = "none"
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # 1. Top navigation switcher links
        self.nav_box = QWidget(self)
        nav_layout = QVBoxLayout(self.nav_box)
        nav_layout.setContentsMargins(0, 0, 0, 4)
        nav_layout.setSpacing(2)

        self.btn_nav_design = PaneLinkButton(safe_tr("设计模板"), self)
        self.btn_nav_colors = PaneLinkButton(safe_tr("配色方案"), self)
        self.btn_nav_anims = PaneLinkButton(safe_tr("动画方案"), self)

        self.btn_nav_design.clicked.connect(lambda: self.navigate_pane.emit("design"))
        self.btn_nav_colors.clicked.connect(lambda: self.navigate_pane.emit("colors"))
        self.btn_nav_anims.clicked.connect(lambda: self.navigate_pane.emit("animations"))

        nav_layout.addWidget(self.btn_nav_design)
        nav_layout.addWidget(self.btn_nav_colors)
        nav_layout.addWidget(self.btn_nav_anims)
        main_layout.addWidget(self.nav_box)

        # Divider
        div = QFrame(self)
        div.setFrameShape(QFrame.Shape.HLine)
        div.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(div)

        # 2. Section label
        self.lbl_apply = QLabel(safe_tr("应用到所选幻灯片:"), self)
        self.lbl_apply.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        main_layout.addWidget(self.lbl_apply)

        # 3. Categorized Schemes Tree
        self.tree = QTreeWidget(self)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setStyleSheet(
            """
            QTreeWidget {
                border: 1px solid #7B9EBD;
                background-color: #FFFFFF;
                font-size: 11px;
            }
            QTreeWidget::item:selected {
                background-color: #0A246A;
                color: #FFFFFF;
            }
            """
        )
        self.tree.itemClicked.connect(self._on_item_clicked)
        self._populate_tree()
        main_layout.addWidget(self.tree, 1)

        # 4. Action buttons
        self.btn_apply_all = QPushButton(safe_tr("应用到所有幻灯片(&A)"), self)
        self.btn_apply_all.setStyleSheet("padding: 4px;")
        self.btn_apply_all.clicked.connect(
            lambda: self.apply_animation_scheme_requested.emit(self.selected_scheme_key, True)
        )
        main_layout.addWidget(self.btn_apply_all)

        btns_row = QHBoxLayout()
        btns_row.setSpacing(6)
        self.btn_play = QPushButton(safe_tr("▶ 播放(&P)"), self)
        self.btn_play.clicked.connect(self.play_requested.emit)
        self.btn_slide_show = QPushButton(safe_tr("幻灯片放映(&S)"), self)
        self.btn_slide_show.clicked.connect(self.slide_show_requested.emit)
        btns_row.addWidget(self.btn_play)
        btns_row.addWidget(self.btn_slide_show)
        main_layout.addLayout(btns_row)

        # 5. AutoPreview checkbox
        self.chk_autopreview = QCheckBox(safe_tr("自动预览(&U)"), self)
        self.chk_autopreview.setChecked(True)
        main_layout.addWidget(self.chk_autopreview)

    def _populate_tree(self) -> None:
        self.tree.clear()
        for group_name, items in ANIMATION_SCHEMES_DATA:
            group_item = QTreeWidgetItem(self.tree, [group_name])
            group_item.setFlags(group_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            font = group_item.font(0)
            font.setBold(True)
            group_item.setFont(0, font)

            for key, name in items:
                child = QTreeWidgetItem(group_item, [name])
                child.setData(0, Qt.ItemDataRole.UserRole, key)
                if key == self.selected_scheme_key:
                    child.setSelected(True)

            group_item.setExpanded(True)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        key = item.data(0, Qt.ItemDataRole.UserRole)
        if not key:
            return
        self.selected_scheme_key = key
        self.apply_animation_scheme_requested.emit(key, False)
        if self.chk_autopreview.isChecked():
            self.play_requested.emit()

    def retranslate_ui(self) -> None:
        """Retranslate UI texts upon language change."""
        self.btn_nav_design.setText(safe_tr("设计模板"))
        self.btn_nav_colors.setText(safe_tr("配色方案"))
        self.btn_nav_anims.setText(safe_tr("动画方案"))
        self.lbl_apply.setText(safe_tr("应用到所选幻灯片:"))
        self.btn_apply_all.setText(safe_tr("应用到所有幻灯片(&A)"))
        self.btn_play.setText(safe_tr("▶ 播放(&P)"))
        self.btn_slide_show.setText(safe_tr("幻灯片放映(&S)"))
        self.chk_autopreview.setText(safe_tr("自动预览(&U)"))
        self._populate_tree()

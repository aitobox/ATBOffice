"""Slide Show HUD (全屏放映浮动交互控制条) for Lectern presentations.

Provides:
- Authentic PowerPoint 2003 translucent floating control bar at bottom-left screen.
- Auto fade-in on mouse hover near bottom-left corner and auto fade-out after inactivity.
- Controls:
  * Previous slide (◄)
  * Pointer / Pen Tools menu (✎): Arrow, Ballpoint Pen, Highlighter, Ink Color, Eraser, Clear Ink.
  * Quick navigation menu (☰): Go to Slide submenu, Black Screen, White Screen.
  * Next slide (►)
  * End Show button (✕)
- 100% i18n support with safe_tr and retranslate_ui.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QEvent,
    QPropertyAnimation,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QMenu,
    QToolButton,
    QWidget,
)

if TYPE_CHECKING:
    from atboffice.modules.presentation.models.presentation import Presentation


def safe_tr(text: str) -> str:
    """Safe translation for SlideShow HUD."""
    app = QApplication.instance()
    if app:
        translated = app.translate("SlideShowHud", text)
        if translated and translated != text:
            return translated
    return text


class SlideShowHud(QFrame):
    """Floating translucent HUD bar placed at the bottom-left of the slide show."""

    prev_clicked = Signal()
    next_clicked = Signal()
    pen_mode_changed = Signal(str, str)  # (tool_name, color_hex)
    goto_slide_requested = Signal(int)
    blank_screen_requested = Signal(str)  # "#000000" or "#FFFFFF"
    end_clicked = Signal()

    def __init__(
        self,
        presentation: Presentation | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.presentation = presentation
        self.current_slide_index: int = 0
        self.total_slides: int = 1
        self.current_pen_tool: str = "arrow"  # "arrow", "pen", "highlighter", "eraser"
        self.current_pen_color: str = "#FF0000"

        # Auto-hide timer
        self._fade_timer = QTimer(self)
        self._fade_timer.setSingleShot(True)
        self._fade_timer.setInterval(3000)
        self._fade_timer.timeout.connect(self.fade_out)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._opacity_anim.setDuration(250)

        self.setObjectName("SlideShowHud")
        self.setStyleSheet(
            """
            #SlideShowHud {
                background-color: rgba(36, 36, 36, 210);
                border: 1px solid rgba(160, 160, 160, 160);
                border-radius: 6px;
            }
            QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                color: #FFFFFF;
                font-family: Arial, sans-serif;
                font-size: 13px;
                font-weight: bold;
                padding: 4px 6px;
                min-width: 26px;
                min-height: 24px;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 60);
                color: #FFFFFF;
            }
            QToolButton:pressed {
                background-color: rgba(255, 255, 255, 90);
            }
            QToolButton::menu-indicator {
                image: none;
                width: 0px;
            }
            """
        )

        self._init_ui()
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        # 1. Previous Slide Button
        self.btn_prev = QToolButton(self)
        self.btn_prev.setText("◄")
        self.btn_prev.setToolTip(safe_tr("上一张 (P)"))
        self.btn_prev.clicked.connect(self.prev_clicked.emit)
        layout.addWidget(self.btn_prev)

        # 2. Pen Tools Menu Button
        self.btn_pen = QToolButton(self)
        self.btn_pen.setText("✎")
        self.btn_pen.setToolTip(safe_tr("指针与画笔选项"))
        self.btn_pen.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._build_pen_menu()
        layout.addWidget(self.btn_pen)

        # 3. Quick Menu Button (Go to slide, Screen)
        self.btn_menu = QToolButton(self)
        self.btn_menu.setText("≡")
        self.btn_menu.setToolTip(safe_tr("幻灯片放映快捷菜单"))
        self.btn_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._build_quick_menu()
        layout.addWidget(self.btn_menu)

        # 4. Next Slide Button
        self.btn_next = QToolButton(self)
        self.btn_next.setText("►")
        self.btn_next.setToolTip(safe_tr("下一张 (N)"))
        self.btn_next.clicked.connect(self.next_clicked.emit)
        layout.addWidget(self.btn_next)

        # 5. End Show Button
        self.btn_end = QToolButton(self)
        self.btn_end.setText("✕")
        self.btn_end.setToolTip(safe_tr("结束放映 (Esc)"))
        self.btn_end.setStyleSheet(
            """
            QToolButton:hover {
                background-color: rgba(232, 17, 35, 180);
                color: #FFFFFF;
            }
            """
        )
        self.btn_end.clicked.connect(self.end_clicked.emit)
        layout.addWidget(self.btn_end)

        self.adjustSize()
        self.setFixedSize(self.sizeHint())

    def _build_pen_menu(self) -> None:
        """Construct the Pointer / Pen options menu."""
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #2D2D2D; color: #FFFFFF; border: 1px solid #555555; }"
        )

        act_arrow = menu.addAction(safe_tr("箭头指针 (&A)"))
        act_arrow.triggered.connect(lambda: self._select_pen_tool("arrow"))

        act_pen = menu.addAction(safe_tr("圆珠笔 (&P)"))
        act_pen.triggered.connect(lambda: self._select_pen_tool("pen"))

        act_highlighter = menu.addAction(safe_tr("荧光笔 (&H)"))
        act_highlighter.triggered.connect(lambda: self._select_pen_tool("highlighter"))

        act_laser = menu.addAction(safe_tr("激光笔 (&L)"))
        act_laser.triggered.connect(lambda: self._select_pen_tool("laser"))

        menu.addSeparator()

        # Ink Color submenu
        menu_color = menu.addMenu(safe_tr("墨迹颜色 (&C)"))
        colors = [
            (safe_tr("黑色"), "#000000"),
            (safe_tr("红色"), "#FF0000"),
            (safe_tr("蓝色"), "#0066FF"),
            (safe_tr("绿色"), "#009933"),
            (safe_tr("黄色"), "#FFCC00"),
            (safe_tr("白色"), "#FFFFFF"),
        ]
        for name, hex_code in colors:
            act_col = menu_color.addAction(name)
            act_col.triggered.connect(lambda checked=False, c=hex_code: self._select_pen_color(c))

        menu.addSeparator()

        act_eraser = menu.addAction(safe_tr("橡皮擦 (&E)"))
        act_eraser.triggered.connect(lambda: self._select_pen_tool("eraser"))

        act_clear = menu.addAction(safe_tr("清除幻灯片上的所有墨迹 (&K)"))
        act_clear.triggered.connect(lambda: self._select_pen_tool("clear"))

        self.btn_pen.setMenu(menu)

    def _build_quick_menu(self) -> None:
        """Construct the Quick Slide Jump & Screen control menu."""
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #2D2D2D; color: #FFFFFF; border: 1px solid #555555; }"
        )

        # Go to slide submenu
        self.menu_goto = menu.addMenu(safe_tr("定位到幻灯片 (&G)"))
        self._populate_goto_menu()

        menu.addSeparator()

        # Screen submenu
        menu_screen = menu.addMenu(safe_tr("屏幕 (&S)"))
        act_black = menu_screen.addAction(safe_tr("黑屏 (&B)"))
        act_black.triggered.connect(lambda: self.blank_screen_requested.emit("#000000"))

        act_white = menu_screen.addAction(safe_tr("白屏 (&W)"))
        act_white.triggered.connect(lambda: self.blank_screen_requested.emit("#FFFFFF"))

        menu.addSeparator()

        act_end = menu.addAction(safe_tr("结束放映 (&E)"))
        act_end.triggered.connect(self.end_clicked.emit)

        self.btn_menu.setMenu(menu)

    def _populate_goto_menu(self) -> None:
        self.menu_goto.clear()
        if not self.presentation or not getattr(self.presentation, "slides", []):
            act_empty = self.menu_goto.addAction(safe_tr("无幻灯片"))
            act_empty.setEnabled(False)
            return

        first_num = getattr(self.presentation, "first_num", 1)
        for idx, slide in enumerate(self.presentation.slides):
            title = f"{idx + first_num}. {safe_tr('幻灯片')} {idx + first_num}"
            if slide.shapes and slide.shapes[0].text and not slide.shapes[0].text.is_empty():
                first_line = slide.shapes[0].text.plain_text.splitlines()[0][:26]
                title = f"{idx + first_num}. {first_line}"
            act = self.menu_goto.addAction(title)
            if idx == self.current_slide_index:
                act.setText("✔ " + title)
            act.triggered.connect(
                lambda checked=False, target=idx: self.goto_slide_requested.emit(target)
            )

    def update_slide_context(
        self,
        current_index: int,
        total_slides: int,
        presentation: Presentation | None = None,
    ) -> None:
        """Refresh current slide index and jump targets."""
        self.current_slide_index = current_index
        self.total_slides = max(1, total_slides)
        if presentation is not None:
            self.presentation = presentation
        self._populate_goto_menu()

    def _select_pen_tool(self, tool_name: str) -> None:
        self.current_pen_tool = tool_name
        self.pen_mode_changed.emit(tool_name, self.current_pen_color)

    def _select_pen_color(self, hex_code: str) -> None:
        self.current_pen_color = hex_code
        if self.current_pen_tool not in ("pen", "highlighter"):
            self.current_pen_tool = "pen"
        self.pen_mode_changed.emit(self.current_pen_tool, self.current_pen_color)

    def fade_in(self) -> None:
        """Animate opacity to visible and restart idle timer."""
        self._opacity_anim.stop()
        self._opacity_anim.setStartValue(self._opacity_effect.opacity())
        self._opacity_anim.setEndValue(1.0)
        self._opacity_anim.start()
        self.show()
        self._fade_timer.start()

    def fade_out(self) -> None:
        """Animate opacity to invisible."""
        self._opacity_anim.stop()
        self._opacity_anim.setStartValue(self._opacity_effect.opacity())
        self._opacity_anim.setEndValue(0.0)
        self._opacity_anim.start()

    def enterEvent(self, event: QEvent) -> None:
        """Keep HUD fully visible when mouse is hovered over it."""
        self._fade_timer.stop()
        self._opacity_effect.setOpacity(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Restart fade timer when mouse leaves HUD."""
        self._fade_timer.start()
        super().leaveEvent(event)

    def retranslate_ui(self) -> None:
        """Retranslate all tooltips and submenus."""
        self.btn_prev.setToolTip(safe_tr("上一张 (P)"))
        self.btn_pen.setToolTip(safe_tr("指针与画笔选项"))
        self.btn_menu.setToolTip(safe_tr("幻灯片放映快捷菜单"))
        self.btn_next.setToolTip(safe_tr("下一张 (N)"))
        self.btn_end.setToolTip(safe_tr("结束放映 (Esc)"))
        self._build_pen_menu()
        self._build_quick_menu()

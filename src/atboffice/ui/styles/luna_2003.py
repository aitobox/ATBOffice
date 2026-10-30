"""Office 2003 Luna Blue & Luna Silver design system and QSS stylesheets."""

from __future__ import annotations

import re
import sys
from typing import Final

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QWidget

# --- Luna Blue Color Tokens ---
LUNA_BLUE_DOCK_TOP: Final = "#9EBEF5"
LUNA_BLUE_DOCK_BOTTOM: Final = "#C4DAFA"
LUNA_BLUE_TB_A: Final = "#E3EFFF"
LUNA_BLUE_TB_B: Final = "#CBE1FC"
LUNA_BLUE_TB_C: Final = "#7BA4E0"
LUNA_BLUE_TB_BORDER: Final = "#3B619C"
LUNA_BLUE_TB_EDGE: Final = "#5E85C6"
LUNA_BLUE_GRIP: Final = "#274176"
LUNA_BLUE_GRIP_HI: Final = "#FFFFFF"

LUNA_BLUE_HOT_A: Final = "#FFF4CC"
LUNA_BLUE_HOT_B: Final = "#FFD091"
LUNA_BLUE_HOT_BORDER: Final = "#000080"
LUNA_BLUE_PRESS_A: Final = "#FE803E"
LUNA_BLUE_PRESS_B: Final = "#FFDF9A"
LUNA_BLUE_PRESS_BORDER: Final = "#800000"
LUNA_BLUE_CHK_A: Final = "#FFDF9A"
LUNA_BLUE_CHK_B: Final = "#FFA64C"

LUNA_BLUE_MENU_BORDER: Final = "#002D96"
LUNA_BLUE_MENU_HOT: Final = "#FFEEC2"
LUNA_BLUE_MENU_FACE: Final = "#FCFCF9"
LUNA_BLUE_STATUS_BG: Final = "#D8E2F3"
LUNA_BLUE_STATUS_SEP: Final = "#8EAADB"
LUNA_BLUE_STATUS_SEP_HI: Final = "#E7F0FD"

# --- Luna Silver Color Tokens ---
LUNA_SILVER_DOCK_TOP: Final = "#E8E8F0"
LUNA_SILVER_DOCK_BOTTOM: Final = "#DCDCE6"
LUNA_SILVER_TB_A: Final = "#F6F6F9"
LUNA_SILVER_TB_B: Final = "#EAEAF1"
LUNA_SILVER_TB_C: Final = "#D8D8E5"
LUNA_SILVER_TB_BORDER: Final = "#7C7C8E"
LUNA_SILVER_TB_EDGE: Final = "#A8A8B7"
LUNA_SILVER_GRIP: Final = "#5A5A6E"
LUNA_SILVER_GRIP_HI: Final = "#FFFFFF"

LUNA_SILVER_HOT_A: Final = "#FFF6DC"
LUNA_SILVER_HOT_B: Final = "#FFEEC2"
LUNA_SILVER_HOT_BORDER: Final = "#7A8A9E"
LUNA_SILVER_PRESS_A: Final = "#F9A465"
LUNA_SILVER_PRESS_B: Final = "#FED59B"
LUNA_SILVER_PRESS_BORDER: Final = "#7A4A2E"
LUNA_SILVER_CHK_A: Final = "#FEE2AD"
LUNA_SILVER_CHK_B: Final = "#F9B87A"

LUNA_SILVER_MENU_BORDER: Final = "#666677"
LUNA_SILVER_MENU_HOT: Final = "#FFEEC2"
LUNA_SILVER_MENU_FACE: Final = "#F9F9FA"
LUNA_SILVER_STATUS_BG: Final = "#E2E2EC"
LUNA_SILVER_STATUS_SEP: Final = "#A0A0B0"
LUNA_SILVER_STATUS_SEP_HI: Final = "#FFFFFF"

# --- Luna Olive Green Color Tokens ---
LUNA_OLIVE_DOCK_TOP: Final = "#D1DAC6"
LUNA_OLIVE_DOCK_BOTTOM: Final = "#BDC8B1"
LUNA_OLIVE_TB_A: Final = "#F0F4E8"
LUNA_OLIVE_TB_B: Final = "#E0E8D0"
LUNA_OLIVE_TB_C: Final = "#B8C8A0"
LUNA_OLIVE_TB_BORDER: Final = "#4E6838"
LUNA_OLIVE_TB_EDGE: Final = "#7A9660"
LUNA_OLIVE_GRIP: Final = "#3E562B"
LUNA_OLIVE_GRIP_HI: Final = "#FFFFFF"
LUNA_OLIVE_HOT_A: Final = "#FFF4CC"
LUNA_OLIVE_HOT_B: Final = "#FFD091"
LUNA_OLIVE_HOT_BORDER: Final = "#335A22"
LUNA_OLIVE_PRESS_A: Final = "#FE803E"
LUNA_OLIVE_PRESS_B: Final = "#FFDF9A"
LUNA_OLIVE_PRESS_BORDER: Final = "#6B4210"
LUNA_OLIVE_CHK_A: Final = "#E6F0D8"
LUNA_OLIVE_CHK_B: Final = "#C8DCB0"
LUNA_OLIVE_MENU_BORDER: Final = "#335A22"
LUNA_OLIVE_MENU_HOT: Final = "#FFEEC2"
LUNA_OLIVE_MENU_FACE: Final = "#FCFCF9"
LUNA_OLIVE_STATUS_BG: Final = "#CED7C2"
LUNA_OLIVE_STATUS_SEP: Final = "#8A9E74"
LUNA_OLIVE_STATUS_SEP_HI: Final = "#E7EFE0"

# --- Windows Classic Color Tokens ---
CLASSIC_DOCK_TOP: Final = "#ECE9D8"
CLASSIC_DOCK_BOTTOM: Final = "#ECE9D8"
CLASSIC_TB_A: Final = "#ECE9D8"
CLASSIC_TB_B: Final = "#ECE9D8"
CLASSIC_TB_C: Final = "#D4D0C8"
CLASSIC_TB_BORDER: Final = "#808080"
CLASSIC_TB_EDGE: Final = "#FFFFFF"
CLASSIC_GRIP: Final = "#808080"
CLASSIC_GRIP_HI: Final = "#FFFFFF"
CLASSIC_HOT_A: Final = "#F5F4EE"
CLASSIC_HOT_B: Final = "#E0DFD8"
CLASSIC_HOT_BORDER: Final = "#0A246A"
CLASSIC_PRESS_A: Final = "#D4D0C8"
CLASSIC_PRESS_B: Final = "#D4D0C8"
CLASSIC_PRESS_BORDER: Final = "#808080"
CLASSIC_CHK_A: Final = "#FFFFFF"
CLASSIC_CHK_B: Final = "#DFDED8"
CLASSIC_MENU_BORDER: Final = "#808080"
CLASSIC_MENU_HOT: Final = "#316AC5"
CLASSIC_MENU_FACE: Final = "#FFFFFF"
CLASSIC_STATUS_BG: Final = "#ECE9D8"
CLASSIC_STATUS_SEP: Final = "#9A9A9A"
CLASSIC_STATUS_SEP_HI: Final = "#FFFFFF"


def format_mnemonic(text: str, is_macos: bool | None = None) -> str:
    """Format mnemonic accelerators across platforms.

    On macOS, strips (&X) and & to conform with native Apple HIG.
    On Windows/Linux, preserves mnemonic accelerators for keyboard navigation.
    """
    if is_macos is None:
        is_macos = sys.platform == "darwin"

    if is_macos:
        # Strip CJK style (&F) or (&1)
        cleaned = re.sub(r"\(&[A-Za-z0-9]\)", "", text)
        # Strip inline & accelerator
        cleaned = re.sub(r"&([A-Za-z0-9])", r"\1", cleaned)
        return cleaned.strip()

    return text


def get_luna_stylesheet(theme: str = "blue") -> str:
    """Generate complete Qt Style Sheet (QSS) for Office 2003 Luna and Classic themes."""
    t = theme.lower().strip()
    if t == "silver":
        tb_a = LUNA_SILVER_TB_A
        tb_b = LUNA_SILVER_TB_B
        tb_c = LUNA_SILVER_TB_C
        tb_border = LUNA_SILVER_TB_BORDER
        tb_edge = LUNA_SILVER_TB_EDGE
        dock_top = LUNA_SILVER_DOCK_TOP
        dock_bottom = LUNA_SILVER_DOCK_BOTTOM
        hot_a = LUNA_SILVER_HOT_A
        hot_b = LUNA_SILVER_HOT_B
        hot_border = LUNA_SILVER_HOT_BORDER
        press_a = LUNA_SILVER_PRESS_A
        press_b = LUNA_SILVER_PRESS_B
        press_border = LUNA_SILVER_PRESS_BORDER
        chk_a = LUNA_SILVER_CHK_A
        chk_b = LUNA_SILVER_CHK_B
        menu_border = LUNA_SILVER_MENU_BORDER
        menu_hot = LUNA_SILVER_MENU_HOT
        menu_face = LUNA_SILVER_MENU_FACE
        status_bg = LUNA_SILVER_STATUS_BG
        status_sep = LUNA_SILVER_STATUS_SEP
    elif t == "olive":
        tb_a = LUNA_OLIVE_TB_A
        tb_b = LUNA_OLIVE_TB_B
        tb_c = LUNA_OLIVE_TB_C
        tb_border = LUNA_OLIVE_TB_BORDER
        tb_edge = LUNA_OLIVE_TB_EDGE
        dock_top = LUNA_OLIVE_DOCK_TOP
        dock_bottom = LUNA_OLIVE_DOCK_BOTTOM
        hot_a = LUNA_OLIVE_HOT_A
        hot_b = LUNA_OLIVE_HOT_B
        hot_border = LUNA_OLIVE_HOT_BORDER
        press_a = LUNA_OLIVE_PRESS_A
        press_b = LUNA_OLIVE_PRESS_B
        press_border = LUNA_OLIVE_PRESS_BORDER
        chk_a = LUNA_OLIVE_CHK_A
        chk_b = LUNA_OLIVE_CHK_B
        menu_border = LUNA_OLIVE_MENU_BORDER
        menu_hot = LUNA_OLIVE_MENU_HOT
        menu_face = LUNA_OLIVE_MENU_FACE
        status_bg = LUNA_OLIVE_STATUS_BG
        status_sep = LUNA_OLIVE_STATUS_SEP
    elif t == "classic":
        tb_a = CLASSIC_TB_A
        tb_b = CLASSIC_TB_B
        tb_c = CLASSIC_TB_C
        tb_border = CLASSIC_TB_BORDER
        tb_edge = CLASSIC_TB_EDGE
        dock_top = CLASSIC_DOCK_TOP
        dock_bottom = CLASSIC_DOCK_BOTTOM
        hot_a = CLASSIC_HOT_A
        hot_b = CLASSIC_HOT_B
        hot_border = CLASSIC_HOT_BORDER
        press_a = CLASSIC_PRESS_A
        press_b = CLASSIC_PRESS_B
        press_border = CLASSIC_PRESS_BORDER
        chk_a = CLASSIC_CHK_A
        chk_b = CLASSIC_CHK_B
        menu_border = CLASSIC_MENU_BORDER
        menu_hot = CLASSIC_MENU_HOT
        menu_face = CLASSIC_MENU_FACE
        status_bg = CLASSIC_STATUS_BG
        status_sep = CLASSIC_STATUS_SEP
    else:  # default "blue"
        tb_a = LUNA_BLUE_TB_A
        tb_b = LUNA_BLUE_TB_B
        tb_c = LUNA_BLUE_TB_C
        tb_border = LUNA_BLUE_TB_BORDER
        tb_edge = LUNA_BLUE_TB_EDGE
        dock_top = LUNA_BLUE_DOCK_TOP
        dock_bottom = LUNA_BLUE_DOCK_BOTTOM
        hot_a = LUNA_BLUE_HOT_A
        hot_b = LUNA_BLUE_HOT_B
        hot_border = LUNA_BLUE_HOT_BORDER
        press_a = LUNA_BLUE_PRESS_A
        press_b = LUNA_BLUE_PRESS_B
        press_border = LUNA_BLUE_PRESS_BORDER
        chk_a = LUNA_BLUE_CHK_A
        chk_b = LUNA_BLUE_CHK_B
        menu_border = LUNA_BLUE_MENU_BORDER
        menu_hot = LUNA_BLUE_MENU_HOT
        menu_face = LUNA_BLUE_MENU_FACE
        status_bg = LUNA_BLUE_STATUS_BG
        status_sep = LUNA_BLUE_STATUS_SEP

    return f"""
    /* Main Window and Docking area */
    QMainWindow {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1, stop:0 {dock_top}, stop:1 {dock_bottom}
        );
    }}

    /* Classic Office 2003 Command Bars */
    QToolBar {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1, stop:0 {tb_a}, stop:0.5 {tb_b}, stop:1 {tb_c}
        );
        border-top: 1px solid {tb_a};
        border-left: 1px solid {tb_a};
        border-right: 1px solid {tb_edge};
        border-bottom: 1px solid {tb_border};
        border-radius: 3px;
        padding: 1px 2px;
        spacing: 2px;
    }}

    /* Tool Buttons */
    QToolBar QToolButton {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 2px;
        padding: 2px 4px;
        font-family: Tahoma, "Segoe UI", "PingFang SC", sans-serif;
        font-size: 11px;
        color: #000000;
        min-height: 20px;
    }}

    QToolBar QToolButton:hover {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {hot_a}, stop:1 {hot_b});
        border: 1px solid {hot_border};
    }}

    QToolBar QToolButton:pressed {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {press_a}, stop:1 {press_b});
        border: 1px solid {press_border};
    }}

    QToolBar QToolButton:checked {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {chk_a}, stop:1 {chk_b});
        border: 1px solid {hot_border};
    }}

    QToolBar QToolButton:disabled {{
        color: #8D8D8D;
        background: transparent;
        border: 1px solid transparent;
    }}

    /* Classic Menus */
    QMenu {{
        background-color: {menu_face};
        border: 1px solid {menu_border};
        padding: 2px;
        font-family: Tahoma, "Segoe UI", "PingFang SC", sans-serif;
        font-size: 11px;
    }}

    QMenu::item {{
        padding: 3px 24px 3px 20px;
        border: 1px solid transparent;
        border-radius: 2px;
    }}

    QMenu::item:selected {{
        background-color: {menu_hot};
        border: 1px solid {hot_border};
        color: #000000;
    }}

    QMenu::separator {{
        height: 1px;
        background: {tb_edge};
        margin: 2px 4px;
    }}

    /* Status Bar */
    QStatusBar {{
        background-color: {status_bg};
        border-top: 1px solid {status_sep};
        color: #000000;
        font-family: Tahoma, "Segoe UI", "PingFang SC", sans-serif;
        font-size: 11px;
    }}

    /* Floating Panel Frame (Color Picker & Dropdowns) */
    QFrame[accessibleName="OfficeColorPicker"] {{
        background-color: {menu_face};
        border: 1px solid {menu_border};
        border-radius: 2px;
    }}
    """


def apply_luna_theme(widget: QWidget, theme: str = "blue") -> None:
    """Apply the Luna Blue, Silver, Olive Green, or Windows Classic theme to widget."""
    t = theme.lower().strip()
    qss = get_luna_stylesheet(t)
    widget.setStyleSheet(qss)

    palette = widget.palette()
    if t == "silver":
        bg_hex = LUNA_SILVER_DOCK_TOP
    elif t == "olive":
        bg_hex = LUNA_OLIVE_DOCK_TOP
    elif t == "classic":
        bg_hex = CLASSIC_DOCK_TOP
    else:
        bg_hex = LUNA_BLUE_DOCK_TOP

    bg_color = QColor(bg_hex)
    palette.setColor(QPalette.ColorRole.Window, bg_color)
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#000000"))
    widget.setPalette(palette)


THEMES: list[tuple[str, str, str]] = [
    ("blue", "Luna 2003 蓝色", "经典 Windows XP 湛蓝风格，搭配淡蓝渐变工具栏与深蓝命令菜单"),
    ("silver", "Luna 2003 银色", "沉稳金属拉丝质感，精致灰白高光与银灰立体底衬"),
    ("olive", "Luna 2003 橄榄绿", "经典温润自然橄榄绿，雅致柔和的护眼复古质感"),
    ("classic", "Windows 经典", "经典 Windows 2000 / 98 工业灰与 3D 浮雕按键风格"),
]


def apply_theme_globally(theme: str) -> None:
    """Apply theme globally across QApplication, active windows, and save setting."""
    from PySide6.QtWidgets import QApplication
    from atboffice.core.settings import get_app_settings

    theme_key = theme.lower().strip()
    if theme_key not in ("blue", "silver", "olive", "classic"):
        theme_key = "blue"

    import os
    app = QApplication.instance()
    qss = get_luna_stylesheet(theme_key)
    if app is not None and app.styleSheet() != qss:
        if not os.environ.get("PYTEST_CURRENT_TEST"):
            app.setStyleSheet(qss)

    try:
        get_app_settings().set_value("theme/active_theme", theme_key)
    except Exception:
        pass

    try:
        from atboffice.core.window_manager import WindowManager
        wm = WindowManager.get_instance()
        all_wins = set(wm.active_windows)
        if wm.start_center is not None:
            all_wins.add(wm.start_center)
        if app is not None:
            for w in app.topLevelWidgets():
                if hasattr(w, "set_theme") and callable(w.set_theme):
                    all_wins.add(w)

        for win in all_wins:
            try:
                if hasattr(win, "set_theme"):
                    win.set_theme(theme_key)
                else:
                    apply_luna_theme(win, theme_key)
            except Exception:
                pass
    except Exception:
        pass


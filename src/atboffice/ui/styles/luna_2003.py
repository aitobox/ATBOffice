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
    """Generate complete Qt Style Sheet (QSS) for Office 2003 Luna themes."""
    is_silver = theme.lower() == "silver"

    tb_a = LUNA_SILVER_TB_A if is_silver else LUNA_BLUE_TB_A
    tb_b = LUNA_SILVER_TB_B if is_silver else LUNA_BLUE_TB_B
    tb_c = LUNA_SILVER_TB_C if is_silver else LUNA_BLUE_TB_C
    tb_border = LUNA_SILVER_TB_BORDER if is_silver else LUNA_BLUE_TB_BORDER
    tb_edge = LUNA_SILVER_TB_EDGE if is_silver else LUNA_BLUE_TB_EDGE

    dock_top = LUNA_SILVER_DOCK_TOP if is_silver else LUNA_BLUE_DOCK_TOP
    dock_bottom = LUNA_SILVER_DOCK_BOTTOM if is_silver else LUNA_BLUE_DOCK_BOTTOM

    hot_a = LUNA_SILVER_HOT_A if is_silver else LUNA_BLUE_HOT_A
    hot_b = LUNA_SILVER_HOT_B if is_silver else LUNA_BLUE_HOT_B
    hot_border = LUNA_SILVER_HOT_BORDER if is_silver else LUNA_BLUE_HOT_BORDER

    press_a = LUNA_SILVER_PRESS_A if is_silver else LUNA_BLUE_PRESS_A
    press_b = LUNA_SILVER_PRESS_B if is_silver else LUNA_BLUE_PRESS_B
    press_border = LUNA_SILVER_PRESS_BORDER if is_silver else LUNA_BLUE_PRESS_BORDER

    chk_a = LUNA_SILVER_CHK_A if is_silver else LUNA_BLUE_CHK_A
    chk_b = LUNA_SILVER_CHK_B if is_silver else LUNA_BLUE_CHK_B

    menu_border = LUNA_SILVER_MENU_BORDER if is_silver else LUNA_BLUE_MENU_BORDER
    menu_hot = LUNA_SILVER_MENU_HOT if is_silver else LUNA_BLUE_MENU_HOT
    menu_face = LUNA_SILVER_MENU_FACE if is_silver else LUNA_BLUE_MENU_FACE

    status_bg = LUNA_SILVER_STATUS_BG if is_silver else LUNA_BLUE_STATUS_BG
    status_sep = LUNA_SILVER_STATUS_SEP if is_silver else LUNA_BLUE_STATUS_SEP

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
    """Apply the Luna Blue or Luna Silver theme to the given widget and its palette."""
    qss = get_luna_stylesheet(theme)
    widget.setStyleSheet(qss)

    palette = widget.palette()
    is_silver = theme.lower() == "silver"

    bg_color = QColor(LUNA_SILVER_DOCK_TOP if is_silver else LUNA_BLUE_DOCK_TOP)
    palette.setColor(QPalette.ColorRole.Window, bg_color)
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#000000"))
    widget.setPalette(palette)
